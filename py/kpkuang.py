# -*- coding: utf-8 -*-
"""
看片狂人 (kpkuang) TVBox / 默影视 py 蜘蛛 v1
由海阔视界 home_rule_v2 规则《看片狂人》改写 (作者: 星火AI)
站点: MacCMS 模板  vodtype(分类) / voddetail(详情) / vodplay(播放)
多域名自动切换 + 播放页 data-play 解密直链
"""
import re
import json
import base64
import urllib.parse

try:
    from base.spider import Spider as BaseSpider
except Exception:  # 本地调试用
    class BaseSpider(object):
        pass

DOMAINS = [
    'https://www.kpkuang.us',
    'https://www.kpkuang.cfd',
    'https://kpkuang.fyi',
    'https://kpkuang.org',
]
SEARCH_API = 'https://kpdata.flixfiend.top/esearch/index?kw={kw}&callback=cb'

PC_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
         '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

# 分类: 一级 -> 二级(名称, code)
CATS = [
    ('电影', [('全部', '1'), ('动作片', '6'), ('喜剧片', '7'), ('爱情片', '8'),
              ('科幻片', '9'), ('恐怖片', '10'), ('剧情片', '11'), ('战争片', '12'),
              ('纪录片', '29')]),
    ('连续剧', [('全部', '2'), ('国产剧', '13'), ('港剧', '14'), ('日剧', '15'),
                ('欧美剧', '16'), ('韩剧', '23'), ('越南剧', '22'), ('泰剧', '21'),
                ('台剧', '20')]),
    ('综艺', [('全部', '3')]),
    ('动漫', [('全部', '4')]),
    ('短剧', [('全部', '37'), ('爽文短剧', '36'), ('现代都市', '39'), ('脑洞悬疑', '40'),
              ('年代穿越', '41'), ('古装仙侠', '42'), ('反转爽剧', '43'),
              ('女频恋爱', '44'), ('成长逆袭', '45')]),
]


class Spider(BaseSpider):

    def __init__(self):
        self.host = DOMAINS[0]
        self.fast = ''
        self.session = None

    # ---------------- 基础 ----------------
    def getName(self):
        return {'name': '看片狂人[py]'}

    def init(self, extend=''):
        try:
            self.session = self._session()
        except Exception:
            self.session = None
        return self

    def isVideoFormat(self, url):
        return True

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def _session(self):
        try:
            import requests
            s = requests.Session()
            s.headers.update({'User-Agent': PC_UA})
            return s
        except Exception:
            return None

    def _fetch(self, url, referer=None, timeout=10):
        """多域名依次尝试, 返回 (html, 实际url)"""
        urls = []
        base = None
        for d in DOMAINS:
            if url.find(d) == 0:
                base = d
                break
        if base is None:
            # 外部链接(搜索API等)直接请求
            urls = [url]
        else:
            if self.fast and self.fast != base:
                urls.append(url.replace(base, self.fast))
            urls.append(url)
            for d in DOMAINS:
                u2 = url.replace(base, d)
                if u2 not in urls:
                    urls.append(u2)
        headers = {'User-Agent': PC_UA}
        if referer:
            headers['Referer'] = referer
        for u in urls:
            txt = ''
            try:
                if self.session is not None:
                    r = self.session.get(u, headers=headers, timeout=timeout)
                    txt = r.text or ''
                else:
                    import urllib.request
                    req = urllib.request.Request(u, headers=headers)
                    txt = urllib.request.urlopen(req, timeout=timeout).read().decode('utf-8', 'ignore')
            except Exception:
                txt = ''
            if txt and 'Just a moment' not in txt and '<html' in txt:
                if base is not None:
                    m = re.match(r'^(https?://[^/]+)', u)
                    if m:
                        self.fast = m.group(1)
                return txt, u
        return '', url

    @staticmethod
    def _img(u, host):
        if not u:
            return ''
        if u == '/':
            return ''
        if u.startswith('//'):
            return 'https:' + u
        if u.startswith('http://'):
            u = 'https://' + u[7:]
        if not u.startswith('http'):
            u = host + (u if u.startswith('/') else '/' + u)
        return u

    @staticmethod
    def _url(u, host):
        if not u:
            return ''
        if u.startswith('//'):
            return 'https:' + u
        if not u.startswith('http'):
            u = host + (u if u.startswith('/') else '/' + u)
        return u

    @staticmethod
    def _clean(s):
        if not s:
            return ''
        s = re.sub(r'<[^>]+>', '', s)
        return re.sub(r'\s+', ' ', s).strip()

    @staticmethod
    def _blocks(html, cls):
        """取 class 含 cls 的 li 块(非贪婪到 </li>)"""
        out = []
        pat = re.compile(r'<li[^>]*class="[^"]*' + re.escape(cls) + r'[^"]*"[^>]*>([\s\S]*?)</li>', re.I)
        for m in pat.finditer(html or ''):
            out.append(m.group(1))
        return out

    @staticmethod
    def _blocks_marker(html, cls):
        """按起始标记切块(避免 li 嵌套被 </li> 截断):
        块 = 本标记位置 -> 下一个同类标记 / fed-drop-btns / 文档尾"""
        html = html or ''
        pat = re.compile(r'<li[^>]*class="[^"]*' + re.escape(cls) + r'[^"]*"[^>]*>', re.I)
        starts = [m.start() for m in pat.finditer(html)]
        if not starts:
            return []
        marks = []
        for m in re.finditer(r'class="[^"]*fed-drop-btns[^"]*"', html, re.I):
            marks.append(m.start())
        out = []
        for i, s in enumerate(starts):
            e = len(html)
            if i + 1 < len(starts):
                e = starts[i + 1]
            for mk in marks:
                if s < mk < e:
                    e = mk
            out.append(html[s:e])
        return out

    @staticmethod
    def _attr(block, tag, attr):
        """取块内第一个 tag 的 attr 值"""
        m = re.search(r'<' + tag + r'\b[^>]*\b' + attr + r'="([^"]*)"', block, re.I)
        return m.group(1) if m else ''

    # ---------------- 首页 / 分类 ----------------
    def homeContent(self, filter=None):
        result = {}
        classes = []
        for name, subs in CATS:
            classes.append({'type_name': name, 'type_id': name})
        result['class'] = classes
        if filter:
            result['filters'] = {}
            for name, subs in CATS:
                vals = [{'n': '全部', 'v': ''}]
                for sn, sc in subs[1:]:
                    vals.append({'n': sn, 'v': sc})
                if len(vals) > 1:
                    result['filters'][name] = [{'key': 'sub', 'name': '分类', 'value': vals}]
        return result

    def homeVideoContent(self):
        return self.categoryContent(CATS[0][0], '1', False, {})

    def _code_of(self, tid, extend):
        default = None
        for name, subs in CATS:
            if name == tid:
                default = subs[0][1]
                break
        if default is None:
            return tid
        code = ''
        try:
            if isinstance(extend, dict):
                code = str(extend.get('sub') or '')
        except Exception:
            code = ''
        return code or default

    def categoryContent(self, tid, pg='1', filter=None, extend=None):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        extend = extend if isinstance(extend, dict) else {}
        code = self._code_of(tid, extend)
        url = self.host + '/vodtype/' + str(code) + '/page/' + str(pg) + '.html'
        html, real = self._fetch(url)
        videos = self._parse_list(html, real)
        # 分页: 取页面里的最大页码
        pagecount = pg
        try:
            nums = [int(x) for x in re.findall(r'/vodtype/' + str(code) + r'/page/(\d+)\.html', html)]
            mx = max(nums) if nums else pg
            pagecount = max(mx, pg)
        except Exception:
            pass
        return {
            'list': videos,
            'page': pg,
            'pagecount': pagecount if pagecount > 1 else 9999,
            'limit': len(videos),
            'total': 999999,
        }

    def _parse_list(self, html, host):
        host = self._base(host) or self.host
        out = []
        for b in self._blocks(html, 'fed-list-item'):
            title = self._attr(b, 'a', 'title')
            link = self._attr(b, 'a', 'href')
            pic = self._attr(b, 'a', 'data-original')
            if not title:
                m = re.search(r'<span[^>]*class="[^"]*cinema_title[^"]*"[^>]*>([\s\S]*?)</span>', b, re.I)
                if m:
                    title = self._clean(m.group(1))
            if not title:
                m = re.search(r'<a[^>]*class="[^"]*fed-list-title[^"]*"[^>]*>([\s\S]*?)</a>', b, re.I)
                if m:
                    title = self._clean(m.group(1))
            if not link:
                m = re.search(r'<a[^>]*class="[^"]*fed-list-pics[^"]*"[^>]*href="([^"]*)"', b, re.I)
                if m:
                    link = m.group(1)
            if not pic:
                pic = self._attr(b, 'img', 'data-original')
            remarks = ''
            m = re.search(r'<span[^>]*class="[^"]*fed-list-name[^"]*"[^>]*>([\s\S]*?)</span>', b, re.I)
            if m:
                remarks = self._clean(m.group(1))
            if not remarks:
                m = re.search(r'<span[^>]*class="[^"]*fed-list-remarks[^"]*"[^>]*>([\s\S]*?)</span>', b, re.I)
                if m:
                    remarks = self._clean(m.group(1))
            title = self._clean(title)
            if not title or not link:
                continue
            out.append({
                'vod_id': self._url(link, host),
                'vod_name': title,
                'vod_pic': self._img(pic, host),
                'vod_remarks': remarks or '',
            })
        return out

    @staticmethod
    def _base(u):
        m = re.match(r'^(https?://[^/]+)', u or '')
        return m.group(1) if m else ''

    # ---------------- 详情 ----------------
    def detailContent(self, array):
        aid = array[0] if array else ''
        url = aid if str(aid).startswith('http') else self.host + str(aid)
        html, real = self._fetch(url)
        host = self._base(real) or self.host
        vod = {
            'vod_id': aid,
            'vod_name': '',
            'vod_pic': '',
            'type_name': '',
            'vod_year': '',
            'vod_area': '',
            'vod_remarks': '',
            'vod_actor': '',
            'vod_director': '',
            'vod_content': '',
            'vod_play_from': '',
            'vod_play_url': '',
        }
        if not html:
            vod['vod_name'] = '加载失败'
            return {'list': [vod]}
        m = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', html)
        if m:
            vod['vod_name'] = self._clean(m.group(1))
        pic = self._attr(html, 'img', 'data-original')
        vod['vod_pic'] = self._img(pic, host)
        # 简介
        raw = self._clean(re.sub(r'<script[\s\S]*?</script>', '', html))
        desc = ''
        di = raw.find('以下是剧情简介')
        if di >= 0:
            desc = raw[di:di + 300]
        else:
            di = raw.find('简介')
            if di >= 0:
                desc = raw[di:di + 300]
        vod['vod_content'] = desc[:200]

        # 线路
        line_names = []
        for b in self._blocks(html, 'fed-drop-btns'):
            m = re.search(r'<a\b[^>]*>([\s\S]*?)</a>', b, re.I)
            nm = self._clean(m.group(1)) if m else ''
            nm = re.sub(r'\s+', '', nm or '')
            if nm:
                line_names.append(nm)
        # 选集(按线路顺序)
        blocks = self._blocks_marker(html, 'fed-play-item')
        ep_blocks = []
        if blocks:
            # 每个线路块内取所有 li:has(a.fed-btns-info)
            for pb in blocks:
                eps = []
                # 直接抓所有 a.fed-btns-info (href 与 class 顺序不定)
                for m in re.finditer(r'<a\b([^>]*)>([\s\S]*?)</a>', pb, re.I):
                    attrs, inner = m.group(1), m.group(2)
                    if 'fed-btns-info' not in attrs:
                        continue
                    hm = re.search(r'href="([^"]*)"', attrs, re.I)
                    if not hm:
                        continue
                    href = hm.group(1)
                    if '/vodplay/' not in href:
                        continue
                    nm = self._clean(inner)
                    num = ''
                    mm = re.search(r'EP(\d+)', nm, re.I)
                    if mm:
                        num = mm.group(1)
                    if not num:
                        mm = re.search(r'第?(\d+)集', nm)
                        if mm:
                            num = mm.group(1)
                    if not num:
                        mm = re.search(r'-(\d+)\.html$', href)
                        if mm:
                            num = mm.group(1)
                    if not num:
                        num = nm
                    eps.append((num, self._url(href, host)))
                # 同集去重
                seen = set()
                cl = []
                for num, u in eps:
                    if num in seen:
                        continue
                    seen.add(num)
                    cl.append((num, u))
                ep_blocks.append(cl)
        if not line_names:
            line_names = ['默认']
            if ep_blocks:
                ep_blocks = [ep_blocks[0]]
        if not ep_blocks:
            ep_blocks = [[]]
        # 线路数与集数块对齐(只保留有集数的块)
        valid = [cl for cl in ep_blocks if cl]
        if not valid:
            valid = [[]]
        froms, urls = [], []
        for i, cl in enumerate(valid):
            if not cl:
                continue
            try:
                cl = sorted(cl, key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0)
            except Exception:
                pass
            nm = line_names[i] if i < len(line_names) else ('线路%d' % (i + 1))
            froms.append(nm)
            urls.append('#'.join(['第%s集$%s' % (num, u) for num, u in cl]))
        vod['vod_play_from'] = '$$$'.join(froms)
        vod['vod_play_url'] = '$$$'.join(urls)
        if not froms:
            vod['vod_remarks'] = '暂无线路'
        return {'list': [vod]}

    # ---------------- 搜索 ----------------
    def searchContent(self, key, quick=False, pg='1'):
        kw = urllib.parse.quote(str(key))
        url = SEARCH_API.replace('{kw}', kw)
        ts = ''
        try:
            import time
            ts = str(int(time.time() * 1000))
            url = url + '&ts=' + ts
        except Exception:
            pass
        html = ''
        try:
            html, _ = self._fetch(url, referer=self.host + '/')
        except Exception:
            html = ''
        data = []
        m = re.search(r'"js"\s*:\s*"([^"]+)"', html or '')
        if m and m.group(1):
            try:
                pad = m.group(1) + '=' * (-len(m.group(1)) % 4)
                data = json.loads(base64.b64decode(pad).decode('utf-8', 'ignore'))
            except Exception:
                data = []
        out = []
        for it in (data or []):
            if not isinstance(it, dict):
                continue
            d1 = it.get('data') or {}
            hi = it.get('high') or {}
            title = hi.get('vod_name') or d1.get('vod_name') or ''
            if isinstance(title, list):
                title = ' '.join(title)
            title = self._clean(str(title))
            if not title:
                continue
            pic = d1.get('vod_imdb_poster') or d1.get('vod_douban_cover') or d1.get('vod_pic') or ''
            vid = it.get('id')
            out.append({
                'vod_id': self.host + '/voddetail/' + str(vid) + '/',
                'vod_name': title,
                'vod_pic': self._img(pic, self.host) if pic else '',
                'vod_remarks': '',
            })
        return {'list': out, 'page': 1, 'pagecount': 1, 'limit': len(out), 'total': len(out)}

    # ---------------- 播放 ----------------
    def playerContent(self, flag='', id='', vipFlags=None):
        url = str(id)
        result = {
            'parse': 0,
            'playUrl': '',
            'url': url,
            'header': {'User-Agent': PC_UA},
            'message': '',
        }
        html = ''
        try:
            html, _ = self._fetch(url, referer=self.host + '/')
        except Exception:
            html = ''
        real = ''
        m = re.search(r'data-play="([^"]+)"', html or '')
        if m and m.group(1):
            for cut in (3, 0):
                try:
                    raw = m.group(1)[cut:]
                    pad = raw + '=' * (-len(raw) % 4)
                    cand = base64.b64decode(pad).decode('utf-8', 'ignore')
                    if cand.startswith('http'):
                        real = cand
                        break
                except Exception:
                    continue
        if real and ('.m3u8' in real or '.mp4' in real or '.flv' in real):
            result['url'] = real
            result['parse'] = 0
            result['jx'] = 0
            return result
        if real:
            # 非直链: 交给解析接口
            result['url'] = real
            result['parse'] = 1
            result['jx'] = 1
            return result
        # 兜底: 嗅探播放页
        result['url'] = url
        result['parse'] = 1
        result['jx'] = 1
        return result
