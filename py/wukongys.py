# -*- coding: utf-8 -*-
"""悟空影视 (www.yikucun.com) —— 默影视 / TVBox py 蜘蛛

站点是 MacCMS10 手机端模板，WAF 只放行移动 UA：
  PC/桌面 UA  → 连接被直接重置（curl 报 000/空响应）
  移动端 UA    → 200 + 完整 HTML
所以本蜘蛛所有请求强制走移动 UA，且每个请求都做「整页完整性」校验 + 重试，
解析失败时也返回分类骨架，保证首页不空白。

接口：
  列表 /ucutp/{分类ID}.html          第2页起 /ucutp/{分类ID}-{页码}.html
  详情 /ucudt/{影片ID}.html
  播放 /ucupy/{影片ID}-{线路}-{集数}.html  → player_aaaa JSON 内 m3u8 直链（encrypt=0）
  搜索 /index.php/ajax/suggest?mid=1&wd={关键词}&limit=100
"""
import re
import json
import time

import requests

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        def getName(self):
            return ''

        def init(self, extend=''):
            pass

        def homeContent(self, filter=False):
            return {'class': [], 'list': [], 'filters': {}}

        def homeVideoContent(self):
            return {'list': []}

        def categoryContent(self, tid, pg, filter=False, extend=''):
            return {'list': []}

        def detailContent(self, ids):
            return {'list': []}

        def searchContent(self, key, quick, pg='1'):
            return {'list': []}

        def playerContent(self, flag, id, vipFlags=None):
            return {'parse': 0, 'url': ''}

        def localProxy(self, param=''):
            return {}

        def isVideoFormat(self, url):
            return False

        def manualVideoCheck(self):
            return False

        def destroy(self):
            pass


class Spider(BaseSpider):
    # ========== 站点配置 ==========
    BASE = 'https://www.yikucun.com'
    # 必须是移动端 UA，这个站的 WAF 会掐掉桌面 UA 的连接
    UA = ('Mozilla/5.0 (Linux; Android 13; PGT-AN10 Build/HONORPGT-AN10; wv) '
          'AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/120.0 Mobile Safari/537.36')
    timeout = 12
    retry = 3

    # 分类硬编码：数字 = 站点 /ucutp/ 下的分类 ID（一级分类同理可用）
    CLASSES = [
        {'type_id': '1', 'type_name': '电影'},
        {'type_id': '6', 'type_name': '动作片'},
        {'type_id': '7', 'type_name': '喜剧片'},
        {'type_id': '8', 'type_name': '惊悚片'},
        {'type_id': '9', 'type_name': '科幻片'},
        {'type_id': '10', 'type_name': '悬疑片'},
        {'type_id': '11', 'type_name': '剧情片'},
        {'type_id': '12', 'type_name': '战争片'},
        {'type_id': '14', 'type_name': '恐怖片'},
        {'type_id': '15', 'type_name': '犯罪片'},
        {'type_id': '16', 'type_name': '奇幻片'},
        {'type_id': '31', 'type_name': '动画片'},
        {'type_id': '2', 'type_name': '电视剧'},
        {'type_id': '17', 'type_name': '国产剧'},
        {'type_id': '18', 'type_name': '港台剧'},
        {'type_id': '20', 'type_name': '日韩剧'},
        {'type_id': '21', 'type_name': '欧美剧'},
        {'type_id': '22', 'type_name': '海外剧'},
        {'type_id': '3', 'type_name': '综艺'},
        {'type_id': '23', 'type_name': '大陆综艺'},
        {'type_id': '4', 'type_name': '动漫'},
        {'type_id': '5', 'type_name': '短剧'},
    ]

    # ========== 基础 ==========
    def init(self, extend=''):
        # vid -> {'lines': [(线路名, [(集名, URL)])], 'eids': {集序号: [各线路播放页URL]}}
        self._cache = {}

    def getName(self):
        return '悟空影视'

    def _headers(self, referer=None):
        return {
            'User-Agent': self.UA,
            'Referer': referer or (self.BASE + '/'),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Connection': 'close',
        }

    def _get(self, url, must=None, referer=None):
        """带整页校验的 GET（不用 Session，避免连接被复用后失效）"""
        for _ in range(self.retry):
            try:
                r = requests.get(url, headers=self._headers(referer), timeout=self.timeout)
                if r.status_code == 200 and r.text and len(r.text) > 800:
                    txt = r.text
                    body = txt.rstrip()
                    # 站点偶尔返回半截页/限流页，检查结尾与关键特征
                    if body[-8:].find('</html>') >= 0 and (must is None or must in txt):
                        return txt
                    if must is not None and must in txt and len(txt) > 3000:
                        return txt
            except Exception:
                pass
            time.sleep(0.4)
        return ''

    @staticmethod
    def _clean(s):
        s = re.sub(r'<[^>]+>', ' ', s or '')
        s = (s.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&quot;', '"')
              .replace('&#39;', "'").replace('&lt;', '<').replace('&gt;', '>'))
        return re.sub(r'\s+', ' ', s).strip()

    @staticmethod
    def _abs(u):
        u = (u or '').strip()
        if u.startswith('//'):
            return 'https:' + u
        if u.startswith('/'):
            return 'https://www.yikucun.com' + u
        return u

    # ========== 解析：列表 ==========
    def _parse_list(self, html):
        out, seen = [], set()
        for seg in html.split('class="li_all"')[1:]:
            m = re.search(r'href="[^"]*?/ucudt/(\d+)\.html"', seg)
            if not m:
                continue
            vid = m.group(1)
            if vid in seen:
                continue
            nm = re.search(r'<p class="name">\s*<a[^>]*>(.*?)</a>', seg, re.S)
            if not nm:
                continue
            seen.add(vid)
            pm = re.search(r'<img[^>]+src="([^"]+)"', seg)
            rm = re.search(r'<span class="rgba1">(.*?)</span>', seg, re.S)
            out.append({
                'vod_id': vid,
                'vod_name': self._clean(nm.group(1)),
                'vod_pic': self._abs(pm.group(1)) if pm else '',
                'vod_remarks': self._clean(rm.group(1)) if rm else '',
            })
        return out

    # ========== 首页 ==========
    def homeContent(self, filter=False):
        lst = []
        try:
            html = self._get(self.BASE + '/ucutp/1.html', must='li_all')
            lst = self._parse_list(html)
        except Exception:
            lst = []
        # 首页推荐拉不到也照常返回分类，界面不会是白板
        return {'class': list(self.CLASSES), 'list': lst, 'filters': {}}

    def homeVideoContent(self):
        try:
            return {'list': self._parse_list(self._get(self.BASE + '/ucutp/1.html', must='li_all'))}
        except Exception:
            return {'list': []}

    # ========== 分类 ==========
    def categoryContent(self, tid, pg, filter=False, extend=''):
        tid = str(tid or '1').strip()
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        url = self.BASE + '/ucutp/' + tid + ('.html' if pg == 1 else '-%d.html' % pg)
        try:
            html = self._get(url, must='li_all')
            lst = self._parse_list(html)
            pagecount = pg
            mm = re.search(r'href="/ucutp/' + re.escape(tid) + r'-(\d+)\.html"[^>]*>\s*尾页', html)
            if mm:
                pagecount = max(pg, int(mm.group(1)))
            else:
                for n in re.findall(r'/ucutp/' + re.escape(tid) + r'-(\d+)\.html', html):
                    pagecount = max(pagecount, int(n))
            return {'list': lst, 'page': pg, 'pagecount': pagecount,
                    'limit': len(lst) or 30, 'total': pagecount * 30}
        except Exception:
            return {'list': [], 'page': pg, 'pagecount': pg, 'limit': 30, 'total': 0}

    # ========== 详情 ==========
    def _field(self, html, label):
        m = re.search(r'<dt>' + label + r'：</dt>\s*<dd>(.*?)</dd>', html, re.S)
        return self._clean(m.group(1)) if m else ''

    def _lines(self, html):
        """返回 [(线路名, [(集名, 播放页URL), ...]), ...]"""
        lines = []
        dt = re.search(r'<dt class="tabt3 title">(.*?)</dt>', html, re.S)
        spans = re.findall(r'<span id="([^"]+)"[^>]*>([^<]*)</span>', dt.group(1)) if dt else []
        dd_map = {}
        for cm in re.finditer(r'<dd class="([^"]*)"[^>]*>(.*?)</dd>', html, re.S):
            tokens = cm.group(1).split()
            if 'mod' not in tokens:
                continue
            sid = [t for t in tokens if t != 'mod']
            if not sid:
                continue
            eps = []
            for a in re.finditer(r'<a[^>]+href="(/ucupy/[^"]+)"[^>]*>(.*?)</a>', cm.group(2), re.S):
                name = self._clean(a.group(2))
                name = re.sub(r'\s+', '', name)
                eps.append((name, self._abs(a.group(1))))
            if eps:
                dd_map[sid[0]] = eps
        order = [s[0] for s in spans if s[0] in dd_map]
        for k in dd_map:
            if k not in order:
                order.append(k)
        for i, sid in enumerate(order):
            title = ''
            for k, v in spans:
                if k == sid:
                    title = self._clean(v)
                    break
            lines.append((title or ('%d线' % (i + 1)), dd_map[sid]))
        return lines

    def detailContent(self, ids):
        try:
            vid = ids[0] if isinstance(ids, (list, tuple)) else ids
            vid = str(vid)
            m = re.search(r'(\d{3,})', vid)
            if m:
                vid = m.group(1)
            html = self._get(self.BASE + '/ucudt/' + vid + '.html', must='ucupy')
            if not html:
                return {'list': []}
            nm = re.search(r'<span class="name">(.*?)</span>', html, re.S)
            pm = re.search(r'<div class="detail_img">\s*<img[^>]+src="([^"]+)"', html, re.S)
            if not pm:
                pm = re.search(r'<img class="dpic"[^>]+src="([^"]+)"', html)
            lines = self._lines(html)
            froms, urls = [], []
            for i, (title, eps) in enumerate(lines):
                froms.append(('%d线' % (i + 1)))
                urls.append('#'.join('%s$%s' % (n or str(idx + 1), u)
                                     for idx, (n, u) in enumerate(eps)))
            # 缓存各线路同集播放页，playerContent 里某条线路取流失败可自动换线
            cache = getattr(self, '_cache', None)
            if cache is None:
                cache = self._cache = {}
            eids = {}
            for title, eps in lines:
                for name, u in eps:
                    em = re.search(r'/ucupy/[^-]+-\d+-(\d+)\.html', u)
                    if em:
                        eids.setdefault(em.group(1), []).append(u)
            cache[vid] = {'lines': lines, 'eids': eids}

            plot = ''
            mi = re.search(r'<p class="movieintro"[^>]*>(.*?)</p>', html, re.S)
            if mi:
                plot = self._clean(mi.group(1))
                plot = re.sub(r'^[^：]{2,30}简介：\s*', '', plot)
            if not plot:
                plot = self._field(html, '剧情') or self._field(html, '简介')
            plot = re.sub(r'\s*详细\s*$', '', plot).strip()
            vod = {
                'vod_id': vid,
                'vod_name': self._clean(nm.group(1)) if nm else '',
                'vod_pic': self._abs(pm.group(1)) if pm else '',
                'type_name': self._field(html, '类型'),
                'vod_year': self._field(html, '年代') or self._field(html, '年份'),
                'vod_area': self._field(html, '地区'),
                'vod_remarks': self._field(html, '备注'),
                'vod_actor': self._field(html, '主演'),
                'vod_director': self._field(html, '导演'),
                'vod_lang': self._field(html, '语言'),
                'vod_content': plot,
                'vod_play_from': '$$$'.join(froms),
                'vod_play_url': '$$$'.join(urls),
            }
            return {'list': [vod]}
        except Exception:
            return {'list': []}

    # ========== 搜索 ==========
    def searchContent(self, key, quick=False, pg='1'):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg > 1:
            return {'list': []}
        key = (key or '').strip()
        if not key:
            return {'list': []}
        try:
            r = requests.get(self.BASE + '/index.php/ajax/suggest',
                             params={'mid': 1, 'wd': key, 'limit': 100},
                             headers=self._headers(), timeout=self.timeout)
            jo = r.json()
        except Exception:
            return {'list': []}
        rows, seen = [], set()
        k = key.lower()
        for it in (jo.get('list') or []):
            vid = str(it.get('id') or '')
            name = self._clean(it.get('name') or '')
            if not vid or not name or vid in seen:
                continue
            seen.add(vid)
            low = name.lower()
            if low == k:
                rank = 0
            elif low.startswith(k):
                rank = 1
            elif k in low:
                rank = 2
            else:
                rank = 3
            rows.append((rank, {'vod_id': vid, 'vod_name': name,
                                'vod_pic': self._abs(it.get('pic') or ''), 'vod_remarks': ''}))
        rows.sort(key=lambda x: x[0])
        return {'list': [x[1] for x in rows]}

    # ========== 播放 ==========
    def _play(self, url):
        # 只带 UA，不带 Referer：部分 CDN（如 cdn.yzzy*-play.com）带 Referer 会直接 SSL 断连
        header = json.dumps({'User-Agent': self.UA})
        return {'parse': 0, 'url': url, 'header': header}

    def _resolve(self, play_url):
        """播放页 → m3u8/mp4 直链"""
        html = self._get(play_url, must='player_aaaa')
        if not html:
            return ''
        m = re.search(r'player_aaaa\s*=\s*(\{.*?\})\s*</script>', html, re.S)
        if m:
            try:
                jo = json.loads(m.group(1))
                purl = (jo.get('url') or '').strip()
                if purl.startswith('http'):
                    return purl.replace('\\/', '/')
            except Exception:
                pass
        m2 = re.search(r'(https?:[^"\'\s\\]+?\.(?:m3u8|mp4)[^"\'\s\\]*)', html)
        return m2.group(1).replace('\\/', '/') if m2 else ''

    def _alive(self, url):
        """轻量探活：3 秒内拿到 #EXTM3U / 视频头就算活（CDN 偶发超时不做强判）"""
        try:
            r = requests.get(url, headers={'User-Agent': self.UA}, timeout=6, stream=True)
            if r.status_code != 200:
                return False
            chunk = r.raw.read(64, decode_content=True) or b''
            try:
                r.close()
            except Exception:
                pass
            head = chunk.decode('utf-8', 'ignore')
            return head.startswith('#EXTM3U') or 'ftyp' in head or head.startswith('FLV') or head.startswith('ID3')
        except Exception:
            return False

    def playerContent(self, flag, id, vipFlags=None):
        try:
            u = str(id or '').strip()
            if not u:
                return {'parse': 0, 'url': ''}
            if u.startswith('http') and '.html' not in u:
                return self._play(u)
            if not u.startswith('http'):
                u = self.BASE + '/ucupy/' + u.lstrip('/')

            url = self._resolve(u)
            if url and self._alive(url):
                return self._play(url)

            # 换线：同一集的其他线路
            cache = getattr(self, '_cache', {}) or {}
            em = re.search(r'/ucupy/([^-]+)-\d+-(\d+)\.html', u)
            if em:
                cands = (cache.get(em.group(1)) or {}).get('eids', {}).get(em.group(2), [])
                for cand in cands:
                    if cand == u:
                        continue
                    u2 = self._resolve(cand)
                    if u2 and self._alive(u2):
                        return self._play(u2)
                    if url == '' and u2:
                        url = u2
            if url:
                return self._play(url)
            return {'parse': 0, 'url': ''}
        except Exception:
            return {'parse': 0, 'url': ''}

    # ========== 其他 ==========
    def isVideoFormat(self, url):
        return True

    def manualVideoCheck(self):
        return False

    def localProxy(self, param=''):
        return {}

    def destroy(self):
        pass
