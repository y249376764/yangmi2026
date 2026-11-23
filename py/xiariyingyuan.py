# -*- coding: utf-8 -*-
"""
夏日影院（sasa01.cc）TVBox / 蜘蛛🕷️ 单文件 Python 源
================================================================
站点类型：自研 SSR 站（非苹果CMS，api.php/index.php 均 403）
  首页            https://www.sasa01.cc/
  分类            /movie/{dianyingl|dianshic|dongmanc|zongyic|duanjuc|juchangc|yingshic}[?page=N]
  详情            /movie/<24位id>.html
  播放            /play/<id>-<7位token>.html
  搜索            /movie/search=<关键词>     （单页，无翻页）
数据都在 HTML 里，无 XHR 接口，只能 re 解析（wu-poster-card 卡片结构稳定）。

播放机制：播放页里 <button data-player-token="..."> 的值是 base64 编码的 m3u8 地址；
  播放列表在 ppqrrs.com 的 v1~v12 子域上（每部剧固定落一台，**不可互换**，换域名 404）；
  分片在 adfg8.vip 的 vN 子域上。两个域名族都随剧变化，所以一律以 token 解出来的地址为准。

踩过的坑：
  FIX1  站点无备用域名：证书 SAN 只有 sasa01.cc / *.sasa01.cc，sasa02/03 等全不解析。
        仅 www 与裸域可互为备份，故 HOSTS 只放这两条 + ext 覆盖。
  FIX2  历史线路的 CDN（如 v6.ppqrrrs.com，三个 r）已停止解析，token 解出来照样 404；
        因此玩家页面必须做真实探测，失败回落 parse:1 网页嗅探，不能直接给 parse:0。
  FIX3  分类第 2 页参数是 ?page=2（不是 /page/2.html，后者 404）。
  FIX4  搜索无翻页，pg>1 直接返回空，避免重复请求同一页。
  FIX5  站点偶发超时（同一 URL 有时 40s 不返回），必须重试 + TTL 缓存兜底。
  FIX6  封面是相对路径 /cdn-uploads/...，且 img 的真实地址在 data-cover-src（src 是占位图）。
  FIX7  详情页选集是 /play/<id>-<token>.html，token 与集号无对应关系，必须从 HTML 抓。
"""
import sys
import re
import json
import time
import gzip
import zlib
import base64
import html as html_mod
import urllib.parse
import urllib.request

HOSTS = ['https://www.sasa01.cc', 'https://sasa01.cc']
UA = ('Mozilla/5.0 (Linux; Android 13; PGT-AN10) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36')
REFERER = HOSTS[0] + '/'
TTL_LIST = 1800
TTL_DETAIL = 3600
TTL_SEARCH = 600
TTL_PLAY = 900
CACHE_MAX = 200
PAGE_SIZE = 24

CATS = [
    ('dianyingl', '电影'),
    ('dianshic', '电视剧'),
    ('dongmanc', '动漫'),
    ('zongyic', '综艺'),
    ('duanjuc', '短剧'),
    ('juchangc', '剧场'),
    ('yingshic', '影视'),
]


class Spider(object):
    def __init__(self):
        self.host = HOSTS[0]
        self._cache = {}
        self._idx = 0

    # ------------------------------------------------------------------ 基础
    def init(self, extend=''):
        cfg = {}
        try:
            if isinstance(extend, dict):
                cfg = extend
            elif extend:
                cfg = json.loads(extend)
        except Exception:
            cfg = {}
        h = str(cfg.get('host') or '').strip().rstrip('/')
        if h:
            if not h.startswith('http'):
                h = 'https://' + h
            self.host = h
        return None

    def getName(self):
        return '夏日影院'

    def _headers(self, referer=None):
        return {
            'User-Agent': UA,
            'Referer': referer or REFERER,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
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
            # 粗暴淘汰最早插入的 1/4，比按时间排序省 CPU，够用
            for k in list(self._cache.keys())[:CACHE_MAX // 4]:
                self._cache.pop(k, None)
        self._cache[key] = (time.time() + ttl, val)

    def _raw(self, url, timeout=12, referer=None, retry=2):
        """返回 (状态码, 字节)。异常全部吞掉，返回 (0, b'')。"""
        last = (0, b'')
        for i in range(retry + 1):
            try:
                req = urllib.request.Request(url, headers=self._headers(referer))
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
            time.sleep(0.4)
        return last

    def _get(self, path, ttl=TTL_LIST, timeout=12, retry=2):
        """带 TTL 缓存 + 双域名失败的 GET。path 可传完整 URL。"""
        if path.startswith('http'):
            url = path
            key = path
        else:
            url = self.host + path
            key = path
        hit = self._cache_get(key)
        if hit is not None:
            return hit
        code, body = self._raw(url, timeout=timeout, retry=retry)
        # FIX5：主域超时就换另一个域（只有 www / 裸域两条）
        if not body and not path.startswith('http'):
            alt = (HOSTS[1] if self.host == HOSTS[0] else HOSTS[0])
            code2, body2 = self._raw(alt + path, timeout=timeout, retry=retry)
            if body2:
                body = body2
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

    @staticmethod
    def _abspath(p):
        p = str(p or '').strip()
        if not p:
            return ''
        if p.startswith('//'):
            return 'https:' + p
        if p.startswith('/'):
            return HOSTS[0] + p
        if p.startswith('http'):
            return p
        return HOSTS[0] + '/' + p.lstrip('/')

    def _cards(self, txt):
        """列表页卡片：FIX6 封面取 data-cover-src。"""
        out = []
        seen = set()
        for blk in re.findall(r'<article class="wu-poster-card">(.*?)</article>', txt, re.S):
            m = re.search(r'href="(/movie/[A-Za-z0-9]+\.html)"', blk)
            if not m:
                continue
            path = m.group(1)
            if path in seen:
                continue
            seen.add(path)
            nm = re.search(r'<h3>\s*<a[^>]*>(.*?)</a>', blk, re.S)
            pic = re.search(r'data-cover-src="([^"]+)"', blk) or re.search(r'<img[^>]+src="(/[^"]+)"', blk)
            info = re.search(r'<p>(.*?)</p>', blk, re.S)
            year = re.search(r'<small>(.*?)</small>', blk, re.S)
            remarks = self._clean(year.group(1)) if year else ''
            out.append({
                'vod_id': path,
                'vod_name': self._clean(nm.group(1)) if nm else '',
                'vod_pic': self._abspath(pic.group(1)) if pic else '',
                'vod_remarks': remarks,
                'vod_year': remarks if remarks.isdigit() else '',
                'type_name': self._clean(info.group(1)) if info else '',
                'vod_content': '',
                'vod_actor': '',
                'vod_director': '',
                'vod_area': '',
                'vod_play_from': '',
                'vod_play_url': '',
            })
        return out

    # ------------------------------------------------------------------ 首页
    def homeContent(self, filter):
        cls = [{'type_id': tid, 'type_name': nm} for tid, nm in CATS]
        lst = self.homeVideoContent().get('list', [])
        return {'class': cls, 'filters': {}, 'list': lst}

    def homeVideoContent(self):
        txt = self._get('/movie/dianyingl', ttl=TTL_LIST)
        return {'list': self._cards(txt)}

    # ------------------------------------------------------------------ 分类
    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        tid = str(tid or 'dianyingl')
        slug = tid if tid in dict(CATS) else 'dianyingl'
        # FIX3：?page=N
        path = '/movie/%s' % slug
        if pg > 1:
            path += '?page=%d' % pg
        txt = self._get(path, ttl=TTL_LIST)
        lst = self._cards(txt)
        # 站点没有 total；满页就认为还有下一页，交给客户端继续翻
        pagecount = pg + 1 if len(lst) >= PAGE_SIZE else pg
        return {'page': pg, 'pagecount': pagecount, 'limit': PAGE_SIZE,
                'total': pagecount * PAGE_SIZE, 'list': lst}

    # ------------------------------------------------------------------ 详情
    def detailContent(self, ids):
        if isinstance(ids, (list, tuple)):
            ids = ids[0] if ids else ''
        vid = str(ids or '').strip()
        if vid.startswith('http'):
            vid = urllib.parse.urlparse(vid).path
        if not vid.startswith('/movie/'):
            vid = '/movie/%s.html' % vid
        txt = self._get(vid, ttl=TTL_DETAIL, timeout=15)
        if not txt:
            return {'list': []}

        name = ''
        m = re.search(r'<h1[^>]*>(.*?)</h1>', txt, re.S)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = re.search(r'<meta property="og:title" content="([^"]+)"', txt)
            name = self._clean(m.group(1)) if m else ''

        pic = ''
        m = re.search(r'<meta property="og:image" content="([^"]+)"', txt)
        if m:
            pic = self._abspath(m.group(1))
        if not pic:
            m = re.search(r'data-cover-src="([^"]+)"', txt)
            pic = self._abspath(m.group(1)) if m else ''

        content = ''
        m = re.search(r'itemprop="description">(.*?)</p>', txt, re.S)
        if m:
            content = self._clean(m.group(1))

        info = ''
        m = re.search(r'<h1[^>]*>.*?</h1>(.*?)<', txt, re.S)
        year = ''
        m2 = re.search(r'<small>(19|20)\d{2}</small>', txt)
        if m2:
            year = self._clean(m2.group(0))
        area = ''
        if info:
            seg = self._clean(info)
            if '·' in seg:
                info = seg
                area = seg.split('·')[-1].strip()

        # 选集：/play/<id>-<token>.html，FIX7
        # FIX8：详情页「立即播放」按钮和「第01集」指向同一个 href，
        #        先按名字过滤再按 href 去重，否则第 1 集会被按钮吃掉。
        eps = []
        seen = set()
        for href, label in re.findall(r'href="(/play/[^"]+\.html)"[^>]*>(.*?)</a>', txt, re.S):
            cname = self._clean(label)
            if not cname or cname.startswith('立即'):
                continue
            if href in seen:
                continue
            seen.add(href)
            eps.append((cname, href))

        play_from = ''
        play_url = ''
        if eps:
            play_from = '夏日线路'
            play_url = '#'.join('%s$%s' % (n, u) for n, u in eps)

        vod = {
            'vod_id': vid,
            'vod_name': name,
            'vod_pic': pic,
            'vod_remarks': year,
            'vod_year': year,
            'vod_area': area,
            'vod_actor': '',
            'vod_director': '',
            'vod_content': content,
            'type_name': info,
            'vod_play_from': play_from,
            'vod_play_url': play_url,
        }
        return {'list': [vod]}

    # ------------------------------------------------------------------ 搜索
    def searchContent(self, key, quick, pg=1):
        pg = int(pg or 1)
        if pg > 1:
            return {'list': []}          # FIX4
        kw = urllib.parse.quote(str(key or ''), safe='')
        txt = self._get('/movie/search=%s' % kw, ttl=TTL_SEARCH, timeout=15)
        return {'list': self._cards(txt)}

    # ------------------------------------------------------------------ 播放
    @staticmethod
    def _b64d(s):
        s = str(s or '').strip()
        if not s:
            return ''
        s = s.replace('-', '+').replace('_', '/')
        pad = '=' * ((4 - len(s) % 4) % 4)
        try:
            return base64.b64decode(s + pad).decode('utf-8', 'ignore')
        except Exception:
            return ''

    def _pick_m3u8(self, page):
        cands = []
        for tok in re.findall(r'data-player-token="([^"]+)"', page):
            u = self._b64d(tok)
            if u.startswith('http'):
                cands.append(u)
        for tok in re.findall(r'data-video-token="([^"]+)"', page):
            u = self._b64d(tok)
            if u.startswith('http'):
                cands.append(u)
        for u in re.findall(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', page):
            cands.append(u.replace('&amp;', '&'))
        out = []
        for u in cands:
            if u not in out:
                out.append(u)
        return out

    def _probe(self, url):
        """真下 1KB 判断能不能播：FIX2 光有 m3u8 地址不代表活着。"""
        code, body = self._raw(url, timeout=6, retry=1)
        if code not in (200, 206) or not body:
            return False
        head = body[:512]
        if b'#EXTM3U' in head:
            return True
        # 直接给的是 mp4 时校验魔数，防图片流
        if head[:4] == b'\x00\x00\x00\x18' or head[4:8] == b'ftyp':
            return True
        if head[:3] == b'\xff\xd8\xff' or head[:4] == b'\x89PNG' or head[:4] == b'GIF8':
            return False
        return bool(head[:1] == b'\x47')   # TS 同步字节

    def playerContent(self, flag, id, vipFlags=None):
        pid = str(id or '').strip()
        if not pid.startswith('http') and not pid.startswith('/play/'):
            pid = '/play/%s' % pid
        url = pid if pid.startswith('http') else self.host + pid
        page = self._get(url, ttl=TTL_PLAY, timeout=15)
        cands = self._pick_m3u8(page) if page else []
        for u in cands:
            if self._probe(u):
                return {'parse': 0, 'url': u, 'header': json.dumps({'User-Agent': UA}),
                        'playUrl': '', 'format': 'm3u8'}
        # 全部探测失败 → 回退网页，让客户端自己嗅探（FIX2）
        return {'parse': 1, 'url': url, 'header': json.dumps({'User-Agent': UA}),
                'playUrl': '', 'format': ''}

    def isVideoFormat(self, url):
        u = str(url or '').lower()
        return any(k in u for k in ('.m3u8', '.mp4', '.ts'))

    def manualVideoCheck(self):
        return False
