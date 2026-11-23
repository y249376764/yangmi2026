# -*- coding: utf-8 -*-
"""
青牛影院（m.artxyzy.com）TVBox / 蜘蛛🕷️ 单文件 Python 源
================================================================
站点类型：苹果CMS V10 魔改（模板 xm12），但采集接口全关（api.php 一律「非法请求」），
          数据只能从 HTML 里 re 解析。

路由：
  分类    /vodtype/{dianying|dianshiju|dongman|zongyi|duanjudaquan|tiyu|...}.html
  详情    /voddetail/<拼音slug>.html
  播放    /vodplay/<slug>-<线路号>-<集号>.html
  搜索    /vodsearch/-------------.html?wd=<关键词>

播放：播放页里有 `var player_aaaa={...}`：
  encrypt=0 → url 直接就是 m3u8
  encrypt=1 → unescape(url)
  encrypt=2 → unescape(base64decode(url))     ← player.js 原文逻辑，照抄

多域名：m / www / 裸域 三条都通、内容一致，可互为备份。
        （证书 SAN 里另有 14 个域名，但那些是站群里的**别的站**，模板/内容都不同，不能当镜像用。）

踩过的坑：
  FIX1  无采集接口，别去试 api.php/index.php/ajax，全是 HTML。
  FIX2  分类**没有翻页**：整页 130 条，?page=2、/page/2.html、-2.html 全是同一份内容。
        所以整页抓一次本地切片 40 条/页，配合 TTL 缓存，翻页零请求。
  FIX3  页面里塞满 <dfn><fss><areass> 之类的垃圾标签做干扰，正则锚点必须选 class（pic/name/playlist-item）。
  FIX4  封面在 data-original（src 是 load.gif 占位），且图片走外链 CDN（mtzy2.com、p.bfp*.com），
        要原样保留绝对地址，不能拼站点域。
  FIX5  详情页「立即播放」与「第01集」同 href，先按集名过滤再按 href 去重，否则第 1 集丢失。
  FIX6  播放 CDN 域名各族不互通（v.baofeng10.com / vodcnd02.trjho.com / v.fengbao14.com），
        一律以 player_aaaa.url 为准。探测分三态：ok=能取到 #EXTM3U；dead=域名不解析/404/
        返回图片流（如 vodcnd02.trjho.com 已 NXDOMAIN）；slow=连接超时（海外 IP 常被墙，
        地址本身没问题）→ slow 也按 parse:0 交给客户端，别把整部剧判死。
  FIX7  单页 600KB+，必须带 gzip 且 15s 超时，否则大页面能拖到几十秒。
"""
import base64
import gzip
import json
import re
import time
import urllib.parse
import urllib.request
import zlib
import html as html_mod

HOSTS = ['https://m.artxyzy.com', 'https://www.artxyzy.com', 'https://artxyzy.com']
UA = ('Mozilla/5.0 (Linux; Android 13; PGT-AN10) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36')
TTL_LIST = 1800
TTL_DETAIL = 3600
TTL_SEARCH = 600
TTL_PLAY = 900
CACHE_MAX = 120
PAGE_SIZE = 40          # 本地切片，站点整页 130 条

CATS = [
    ('dianying', '电影'),
    ('dianshiju', '电视剧'),
    ('dongman', '动漫'),
    ('zongyi', '综艺'),
    ('duanjudaquan', '短剧大全'),
    ('tiyu', '体育'),
    ('dianyingjieshuo', '电影解说'),
    ('guochanju', '国产剧'),
    ('oumeiju', '欧美剧'),
    ('dongzuopian', '动作片'),
]


class Spider(object):
    def __init__(self):
        self.host = HOSTS[0]
        self._cache = {}

    # ------------------------------------------------------------------ 基础
    def init(self, extend=''):
        try:
            cfg = extend if isinstance(extend, dict) else (json.loads(extend) if extend else {})
        except Exception:
            cfg = {}
        h = str(cfg.get('host') or '').strip().rstrip('/')
        if h:
            if not h.startswith('http'):
                h = 'https://' + h
            self.host = h
        return None

    def getName(self):
        return '青牛影院'

    @staticmethod
    def _headers():
        return {
            'User-Agent': UA,
            'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'close',
        }

    def _cache_get(self, key):
        it = self._cache.get(key)
        if not it:
            return None
        if it[0] < time.time():
            self._cache.pop(key, None)
            return None
        return it[1]

    def _cache_put(self, key, val, ttl):
        if len(self._cache) > CACHE_MAX:
            for k in list(self._cache.keys())[:CACHE_MAX // 4]:
                self._cache.pop(k, None)
        self._cache[key] = (time.time() + ttl, val)

    def _raw(self, url, timeout=15, retry=1):
        last = (0, b'')
        for _ in range(retry + 1):
            try:
                req = urllib.request.Request(url, headers=self._headers())
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    code = getattr(r, 'status', 200) or 200
                    body = r.read()
                    enc = ''
                    try:
                        enc = (r.headers.get('Content-Encoding') or '').lower()
                    except Exception:
                        enc = ''
                    if 'gzip' in enc:
                        try:
                            body = gzip.decompress(body)
                        except Exception:
                            pass
                    elif 'deflate' in enc:
                        try:
                            body = zlib.decompress(body)
                        except Exception:
                            pass
                    return code, body
            except Exception as e:
                last = (0, str(e).encode('utf-8', 'ignore'))
            time.sleep(0.3)
        return last

    def _get(self, path, ttl=TTL_LIST, timeout=15, retry=1):
        key = path
        hit = self._cache_get(key)
        if hit is not None:
            return hit
        url = path if path.startswith('http') else self.host + path
        code, body = self._raw(url, timeout=timeout, retry=retry)
        # 主域失败就换另外两条域名（FIX：三域内容一致）
        if not body and not path.startswith('http'):
            for alt in HOSTS:
                if alt == self.host:
                    continue
                _, body = self._raw(alt + path, timeout=timeout, retry=retry)
                if body:
                    break
        if not body:
            return ''
        txt = body.decode('utf-8', 'ignore')
        self._cache_put(key, txt, ttl)
        return txt

    # ------------------------------------------------------------------ 解析
    @staticmethod
    def _clean(t):
        t = re.sub(r'<[^>]+>', '', str(t or ''))
        return html_mod.unescape(t).replace('\u3000', ' ').strip()

    def _cards(self, txt):
        """列表卡片：<li class="col-xs-4..."><div class="pic"><a href title><div data-original=PIC>..."""
        out = []
        seen = set()
        # 锚点用 <li class="col-xs-4...">：卡片结构一层层嵌套，按 li 切最稳
        for blk in re.findall(r'<li class="col-xs-4[^"]*">(.*?)</li>', txt, re.S):
            m = re.search(r'href="(/voddetail/[^"]+\.html)"', blk)
            if not m:
                continue
            path = m.group(1)
            if path in seen:
                continue
            seen.add(path)
            pic = re.search(r'data-original="([^"]+)"', blk)
            nm = re.search(r'<h3>\s*<a[^>]*title="([^"]*)"', blk) or re.search(r'<h3>\s*<a[^>]*>(.*?)</a>', blk, re.S)
            st = re.search(r'class="item-status[^"]*">(.*?)</p>', blk, re.S)
            out.append({
                'vod_id': path,
                'vod_name': self._clean(nm.group(1)) if nm else '',
                'vod_pic': pic.group(1) if pic else '',          # FIX4：外链 CDN 原样保留
                'vod_remarks': self._clean(st.group(1)) if st else '',
                'vod_year': '',
                'vod_area': '',
                'vod_actor': '',
                'vod_director': '',
                'vod_content': '',
                'type_name': '',
                'vod_play_from': '',
                'vod_play_url': '',
            })
        return out

    # ------------------------------------------------------------------ 首页
    def homeContent(self, filter):
        cls = [{'type_id': t, 'type_name': n} for t, n in CATS]
        return {'class': cls, 'filters': {}, 'list': self.homeVideoContent().get('list', [])}

    def homeVideoContent(self):
        txt = self._get('/vodtype/dianying.html', ttl=TTL_LIST)
        return {'list': self._cards(txt)[:PAGE_SIZE]}

    # ------------------------------------------------------------------ 分类
    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        tid = str(tid or 'dianying')
        slug = tid if tid in dict(CATS) else 'dianying'
        # FIX2：站点无翻页，整页抓 + 本地切片
        txt = self._get('/vodtype/%s.html' % slug, ttl=TTL_LIST)
        allc = self._cards(txt)
        total = len(allc)
        pagecount = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        if pg > pagecount:
            pg = pagecount
        st = (pg - 1) * PAGE_SIZE
        return {'page': pg, 'pagecount': pagecount, 'limit': PAGE_SIZE,
                'total': total, 'list': allc[st:st + PAGE_SIZE]}

    # ------------------------------------------------------------------ 详情
    def detailContent(self, ids):
        if isinstance(ids, (list, tuple)):
            ids = ids[0] if ids else ''
        vid = str(ids or '').strip()
        if vid.startswith('http'):
            vid = urllib.parse.urlparse(vid).path
        if not vid.startswith('/voddetail/'):
            vid = '/voddetail/%s.html' % vid.strip('/')
        txt = self._get(vid, ttl=TTL_DETAIL, timeout=18)
        if not txt:
            return {'list': []}

        # 信息块：<div class="info"><h3><a>标题</a></h3>...
        name = ''
        m = re.search(r'class="vod-info[^"]*".*?<div class="info">\s*<h3>\s*<a[^>]*>(.*?)</a>', txt, re.S)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = re.search(r'<div class="info">\s*<h3>\s*<a[^>]*>(.*?)</a>', txt, re.S)
            name = self._clean(m.group(1)) if m else ''

        pic = ''
        m = re.search(r'class="vod-info[^"]*".*?data-original="([^"]+)"', txt, re.S)
        if m:
            pic = m.group(1)

        def field(label):
            mm = re.search(label + r'：\s*(.*?)</span>', txt, re.S)
            return self._clean(mm.group(1)) if mm else ''

        area = field('地区')
        year = field('年份')
        # 分类：第一个 /vodtype/ 链接
        m = re.search(r'分类：\s*<a href="/vodtype/[^"]+">(.*?)</a>', txt, re.S)
        type_name = self._clean(m.group(1)) if m else ''
        m = re.search(r'主演：(.*?)</span>', txt, re.S)
        actor = self._clean(m.group(1)) if m else ''
        m = re.search(r'导演：(.*?)</span>', txt, re.S)
        director = self._clean(m.group(1)) if m else ''
        m = re.search(r'<div class="text text-row[^"]*">简介：(.*?)</div>', txt, re.S)
        content = self._clean(m.group(1)) if m else ''

        # 线路名 + 选集（FIX5）
        tabs = re.findall(r'data-target="#ewave-playlist-(\d+)"[^>]*>(.*?)<em', txt, re.S)
        play_from = []
        play_url = []
        for idx, tabname in tabs:
            nm = self._clean(tabname)
            nm = re.sub(r'^《[^》]*》\s*[-—]\s*', '', nm)
            nm = nm.replace('在线', '').strip() or ('线路' + str(idx))
            blk_m = re.search(r'id="ewave-playlist-%s"[^>]*>(.*?)</ul>' % str(idx), txt, re.S)
            if not blk_m:
                continue
            eps = []
            seen = set()
            for href, label in re.findall(r'href="(/vodplay/[^"]+\.html)"[^>]*>(.*?)</a>', blk_m.group(1), re.S):
                cname = self._clean(label)
                if not cname or cname.startswith('立即'):
                    continue
                if href in seen:
                    continue
                seen.add(href)
                eps.append('%s$%s' % (cname, href))
            if eps:
                play_from.append(nm)
                play_url.append('#'.join(eps))

        vod = {
            'vod_id': vid,
            'vod_name': name,
            'vod_pic': pic,
            'vod_remarks': year,
            'vod_year': year,
            'vod_area': area,
            'vod_actor': actor,
            'vod_director': director,
            'vod_content': content,
            'type_name': type_name,
            'vod_play_from': '$$$'.join(play_from),
            'vod_play_url': '$$$'.join(play_url),
        }
        return {'list': [vod]}

    # ------------------------------------------------------------------ 搜索
    def searchContent(self, key, quick, pg=1):
        if int(pg or 1) > 1:
            return {'list': []}       # 站点搜索单页
        kw = urllib.parse.quote(str(key or ''), safe='')
        txt = self._get('/vodsearch/-------------.html?wd=%s' % kw, ttl=TTL_SEARCH, timeout=18)
        return {'list': self._cards(txt)}

    # ------------------------------------------------------------------ 播放
    @staticmethod
    def _b64d(s):
        s = str(s or '').strip().replace('-', '+').replace('_', '/')
        if not s:
            return ''
        s += '=' * ((4 - len(s) % 4) % 4)
        try:
            return base64.b64decode(s).decode('utf-8', 'ignore')
        except Exception:
            return ''

    def _player_url(self, page):
        m = re.search(r'var player_aaaa=(\{.*?\})\s*</script>', page, re.S)
        if not m:
            return ''
        try:
            cfg = json.loads(m.group(1))
        except Exception:
            return ''
        url = str(cfg.get('url') or '')
        enc = str(cfg.get('encrypt') or '0')
        if not url:
            return ''
        if enc == '1':
            url = urllib.parse.unquote(url)
        elif enc == '2':
            url = urllib.parse.unquote(self._b64d(url))
        return url.replace('\\/', '/')

    def _probe(self, url):
        """返回 'ok' / 'dead' / 'slow'。
        dead = 域名不解析、404/403、返回图片 —— 这集换了也没用，只能回落网页；
        slow = 连接超时（这台 CDN 常见海外 IP 不通），地址本身是对的，交给客户端去试，
               不能因为本机不通就把整部剧判死。"""
        last_err = None
        for _ in range(2):
            try:
                req = urllib.request.Request(url, headers={'User-Agent': UA, 'Range': 'bytes=0-2047'})
                with urllib.request.urlopen(req, timeout=8) as r:
                    body = r.read()
                head = body[:512]
                if b'#EXTM3U' in head or head[4:8] == b'ftyp' or head[:4] == b'\x00\x00\x00\x18':
                    return 'ok'
                if head[:3] == b'\xff\xd8\xff' or head[:4] == b'\x89PNG' or head[:4] == b'GIF8':
                    return 'dead'          # 伪装成视频的图片流
                return 'ok' if head[:1] == b'\x47' else 'dead'
            except urllib.error.HTTPError as e:
                return 'dead' if e.code in (403, 404, 410, 500, 502) else 'slow'
            except Exception as e:
                msg = str(e)
                if 'Name or service not known' in msg or 'nodename nor servname' in msg or 'gaierror' in msg:
                    return 'dead'          # 域名都没了
                last_err = e
                time.sleep(0.4)
        return 'slow'

    def playerContent(self, flag, id, vipFlags=None):
        pid = str(id or '').strip()
        if not pid.startswith('http') and not pid.startswith('/vodplay/'):
            pid = '/vodplay/%s' % pid
        url = pid if pid.startswith('http') else self.host + pid
        page = self._get(url, ttl=TTL_PLAY, timeout=15)
        play = self._player_url(page) if page else ''
        state = self._probe(play) if play else 'dead'
        if play and state in ('ok', 'slow'):
            return {'parse': 0, 'url': play, 'header': json.dumps({'User-Agent': UA}),
                    'playUrl': '', 'format': 'm3u8'}
        # FIX6：CDN 域名已死 / 返回图片流 → 回落网页嗅探，绝不给空地址
        return {'parse': 1, 'url': url, 'header': json.dumps({'User-Agent': UA}),
                'playUrl': '', 'format': ''}

    def isVideoFormat(self, url):
        u = str(url or '').lower()
        return any(k in u for k in ('.m3u8', '.mp4', '.ts'))

    def manualVideoCheck(self):
        return False
