# -*- coding: utf-8 -*-
"""
幻听网 听书蜘蛛版 (ting39.py)
--------------------------------
站点: https://www.ting39.com (幻听网/听书网)
提取自 Timbre .jdr 接口源 (com.ting39.timbre.source, ting39.js), 2026-10-03 实测:

  * 分类     /book/{拼音}/lastupdate/{页码}.html       (26 个分类, 每页约 15 本)
  * 搜索     /search.html?searchword={kw}             -> <li> list-book-dt 条目
  * 详情     /book/{bookId}.html                      -> 封面/书名/演播/简介 + href="/bookdir/xxx.html"
  * 章节     /bookdir/{dir}/{file}.html[?page=N&sort=asc]  (50 集/页, 总数可几十页)
            目录/<a href='/tingshu/{bookId}/{chapterId}.html'>
  * 播放     /player.html?nid={bookId}&cid={chapterId}&site=16
            返回 JS: url<rand>='<base>'; murl<rand>='<ext>'; 直链=base(+ext)
            实测直链走 car-*.kuwo.cn CDN (mp3), 无需 Referer

反爬守卫 (ptcms):
  章节目录/部分页面首次请求返回混淆 JS: var reversed="...base64反转..."
  解码执行后种下 pt_browser_id + pt_guid 两个 cookie 并刷新页面。
  本实现: 请求遇守卫页 -> 解析 reversed -> base64 反转解码 -> 取 var token='...' ->
           token 再 base64 解码 -> IP|browserId|ts|sign -> 组 cookie, 带 cookie 重试。
"""
import re
import time
import base64
import requests

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        def getName(self): return ''
        def init(self, extend=''): pass
        def homeContent(self, filter=False): return {"class": [], "list": [], "filters": {}}
        def homeVideoContent(self): return {"list": []}
        def categoryContent(self, tid, pg, filter=False, extend=''): return {"list": []}
        def detailContent(self, ids): return {"list": []}
        def searchContent(self, key, quick, pg='1'): return {"list": []}
        def playerContent(self, flag, id, vipFlags=None): return {"parse": 0, "url": ""}
        def localProxy(self, param=''): return {}
        def isVideoFormat(self, url): return False
        def manualVideoCheck(self): return False
        def destroy(self): pass


class Spider(BaseSpider):
    BASE = "https://www.ting39.com"
    UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    timeout = 12

    # 站点真实分类 (拼音 key -> 显示名), 26 个
    CLASSES = [
        {"type_id": "xhqh", "type_name": "玄幻奇幻"},
        {"type_id": "wxxx", "type_name": "武侠仙侠"},
        {"type_id": "pingshu", "type_name": "长篇评书"},
        {"type_id": "xdyq", "type_name": "现代言情"},
        {"type_id": "cyjk", "type_name": "穿越架空"},
        {"type_id": "xytl", "type_name": "悬疑推理"},
        {"type_id": "lsjs", "type_name": "历史军事"},
        {"type_id": "hxyq", "type_name": "幻想言情"},
        {"type_id": "gdyq", "type_name": "古代言情"},
        {"type_id": "ysyz", "type_name": "影视原著"},
        {"type_id": "khjj", "type_name": "科幻竞技"},
        {"type_id": "ertong", "type_name": "儿童频道"},
        {"type_id": "wxmz", "type_name": "文学名著"},
        {"type_id": "gxjd", "type_name": "国学经典"},
        {"type_id": "mxdt", "type_name": "明星电台"},
        {"type_id": "xsqy", "type_name": "相声曲艺"},
        {"type_id": "mjcj", "type_name": "名家传记"},
        {"type_id": "qita", "type_name": "其他"},
    ]

    def __init__(self):
        # session 持久 cookie (守卫种子 + 站点会话)
        self.s = requests.Session()
        self.s.headers["User-Agent"] = self.UA
        self.guard_cookie = None
        self.guard_ts = 0
        self._cat_pages = {}

    # ---------------- 守卫处理 ----------------
    @staticmethod
    def _b64_decode(s):
        pad = '=' * (-len(s) % 4)
        try:
            return base64.b64decode(s + pad).decode('utf-8', errors='replace')
        except Exception:
            return ''

    @staticmethod
    def _is_guard(html):
        return isinstance(html, str) and "var reversed" in html and "Loading..." in html

    def _solve_guard(self, html):
        """解析 ptcms 守卫页, 返回 cookie 串 (用于重试)"""
        import re as _re
        from urllib.parse import quote
        m = _re.search(r'var\s+reversed\s*=\s*"([^"]+)"', html)
        if not m:
            return None
        b64 = m.group(1)[::-1]                       # 反转
        code = self._b64_decode(b64)                  # 解码守卫脚本
        tm = _re.search(r"var\s+token\s*=\s*'([^']+)'", code)
        if not tm:
            return None
        token = tm.group(1)
        decoded = self._b64_decode(token)              # IP|browserId|timestamp|sign
        parts = decoded.split('|')
        if len(parts) < 2:
            return None
        cookie = ("pt_browser_id=%s; pt_guid=%s; ptcms_guard_retry=1"
                  % (parts[1].strip(), quote(token)))
        return cookie

    def _get(self, url, referer=None, retry_guard=True):
        """带守卫处理的 GET"""
        h = {"Referer": referer or self.BASE + "/"}
        try:
            r = self.s.get(url, headers=h, timeout=self.timeout, allow_redirects=True)
        except Exception:
            return ""
        if r.status_code != 200:
            return ""
        html = r.text
        if self._is_guard(html):
            ck = self._solve_guard(html)
            if ck:
                # 加守卫 cookie 后重试
                self.s.headers["Cookie"] = ck
                try:
                    r2 = self.s.get(url, headers={"Referer": referer or self.BASE + "/"},
                                    timeout=self.timeout)
                    if r2.status_code == 200 and not self._is_guard(r2.text):
                        return r2.text
                except Exception:
                    pass
        return html

    # ---------------- 解析 ----------------
    @staticmethod
    def _strip(s):
        import re as _re
        return _re.sub(r'\s+', ' ', _re.sub(r'<[^>]+>', '', s or '')).strip()

    def _parse_books(self, html):
        """分类/搜索/首页 书籍列表卡片解析 (li 内 list-book-dt)"""
        import re as _re
        out = []
        seen = set()
        for m in _re.finditer(r'<li([\s\S]*?)</li>', html):
            it = m.group(1)
            if 'list-book-dt' not in it:
                continue
            am = _re.search(r'href="/book/(\d+)\.html"', it)
            if not am:
                continue
            bid = am.group(1).strip()
            if bid in seen:
                continue
            seen.add(bid)
            # 书名: 优先 title 属性, 或 a 内文本
            nm = _re.search(r'<a[^>]*href="/book/%s\.html"[^>]*title="([^"]+)"' % bid, it)
            if not nm:
                nm2 = _re.search(r'<a[^>]*href="/book/%s\.html"[^>]*>([\s\S]*?)</a>' % bid, it)
                nm2 = nm2.group(1) if nm2 else ''
            name = nm.group(1).strip() if nm else self._strip(nm2).strip() if locals().get('nm2') else ''
            # 清理书名里的 "有声小说" 等后缀
            name = _re.sub(r'(有声小说|小说)$', '', name)
            if not name:
                name = bid
            # 封面
            ic = _re.search(r'data-original="([^"]+)"', it) or _re.search(r'<img[^>]+src="([^"]+)"', it)
            pic = ic.group(1) if ic else ''
            if pic and pic.startswith('/'):
                pic = self.BASE + pic
            # 演播/状态
            au = _re.search(r'book-author[^>]*>([\s\S]*?)</', it) or _re.search(r'book-zt[^>]*>([^<]+)<', it)
            rem = self._strip(au.group(1)) if au else ''
            out.append({"vod_id": bid, "vod_name": name[:40], "vod_pic": pic,
                        "vod_remarks": rem[:20]})
        return out

    def _parse_chapters(self, html):
        import re as _re
        eps = []
        for m in _re.finditer(r"<a[^>]*href='/tingshu/\d+/(\d+)\.html'[^>]*>([\s\S]*?)</a>", html):
            title = self._strip(m.group(2))
            if title:
                eps.append((m.group(1), title))
        return eps

    def _parse_total_pages(self, html):
        import re as _re
        mx = 1
        for m in _re.finditer(r'bookdir/[^"]+\?page=(\d+)&sort=asc', html):
            mx = max(mx, int(m.group(1)))
        return mx

    # ---------------- 标准接口 ----------------
    def init(self, extend=""):
        pass

    def getName(self):
        return "幻听网[py]"

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def homeContent(self, filter):
        vods = self._parse_books(self._get(self.BASE + "/"))
        return {"class": self.CLASSES, "list": vods, "filters": {}}

    def homeVideoContent(self):
        return {"list": self._parse_books(self._get(self.BASE + "/"))}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
        url = f"{self.BASE}/book/{tid}/lastupdate.html"
        if page > 1:
            url = f"{self.BASE}/book/{tid}/lastupdate/{page}.html"
        html = self._get(url)
        vods = self._parse_books(html)
        pgmax = 1
        import re as _re
        for m in _re.finditer(r'/book/' + _re.escape(str(tid)) + r'/lastupdate/(\d+)\.html', html):
            pgmax = max(pgmax, int(m.group(1)))
        return {"list": vods, "page": page, "pagecount": pgmax}

    def searchContent(self, key, quick, pg="1"):
        from urllib.parse import quote
        html = self._get(f"{self.BASE}/search.html?searchword={quote(str(key))}")
        return {"list": self._parse_books(html)}

    def detailContent(self, ids):
        vid = str(ids[0]) if isinstance(ids, (list, tuple)) else str(ids)
        html = self._get(f"{self.BASE}/book/{vid}.html")
        vod = {"vod_id": vid, "vod_name": vid, "vod_pic": "", "vod_actor": "",
               "vod_content": "", "vod_remarks": ""}
        if not html:
            return {"list": [vod]}
        tm = re.search(r'<title>([^<]*)</title>', html)
        if tm:
            t = self._strip(tm.group(1))
            # 书名取 title 中第一个 "-" 前 (去掉 "有声小说 - 真人演播...幻听网" 等后缀)
            vod["vod_name"] = t.split('-')[0].strip().replace("有声小说", "").strip() or t[:40]
        # 封面
        ic = re.search(r'(?:data-original|src)="([^"]+\.(?:jpg|jpeg|png|webp))"', html) \
            or re.search(r'<img[^>]+src="([^"]+)"', html)
        if ic:
            p = ic.group(1)
            if p.startswith('/'):
                p = self.BASE + p
            vod["vod_pic"] = p
        # 演播/作者
        au = re.search(r'book-author[^>]*>([\s\S]*?)</', html)
        if au:
            vod["vod_actor"] = self._strip(au.group(1))
        # 简介
        intro = re.search(r'(?:book-intro|list-book-des|intro)[^>]*>([\s\S]*?)</(?:p|dd|div)', html, re.I)
        if intro:
            vod["vod_content"] = self._strip(intro.group(1))[:300]
        # 章节目录链接
        dm = re.search(r'href="(/bookdir/[^"]+\.html)"', html)
        if not dm:
            return {"list": [vod]}
        dir_url = self.BASE + dm.group(1)
        # 抓第一页(带守卫) -> 章节 + 总页数
        h1 = self._get(dir_url, referer=f"{self.BASE}/book/{vid}.html")
        eps = self._parse_chapters(h1)
        total = self._parse_total_pages(h1) if eps else 1
        # 逐页抓剩余 (每页50集)
        for p in range(2, total + 1):
            if len(eps) >= 2000:  # 安全上限
                break
            hp = self._get(f"{dir_url}?page={p}&sort=asc", referer=dir_url)
            eps.extend(self._parse_chapters(hp))
        if eps:
            # 去重保序
            seen = set()
            uniq = []
            for cid, t in eps:
                if cid in seen:
                    continue
                seen.add(cid)
                uniq.append((cid, t))
            vod["vod_play_from"] = "幻听网"
            vod["vod_play_url"] = "#".join(f"{t}${cid}" for cid, t in uniq)
            vod["vod_remarks"] = f"{len(uniq)}集"
        return {"list": [vod]}

    def playerContent(self, flag, ids, vipFlags=None):
        from urllib.parse import unquote
        # id = "bookId$$chapterId"
        parts = str(ids).split("$$")
        chapter_id = parts[-1] if parts else ""
        book_id = parts[0] if len(parts) > 1 else ""
        if not chapter_id or not book_id:
            return {"parse": 0, "url": ""}
        purl = f"{self.BASE}/player.html?nid={book_id}&cid={chapter_id}&site=16"
        referer = f"{self.BASE}/tingshu/{book_id}/{chapter_id}.html"
        mp3 = ""
        for attempt in range(3):
            html = self._get(purl, referer=referer)
            um = re.search(r"\burl(\d+)\s*=\s*'([^']*)'", html)
            if um:
                u = um.group(2)
                if re.search(r'\.(mp3|m4a|aac|wav|flac)$', u, re.I):
                    mp3 = u
                    break
                if u.startswith('http'):
                    ext = '.mp3'
                    mum = re.search(r"\bmurl(\d+)\s*=\s*'([^']*)'", html)
                    if mum and mum.group(1) == um.group(1):
                        ext = mum.group(2) if mum.group(2) else '.mp3'
                    mp3 = u + ext
                    break
            time.sleep(1.2 * (attempt + 1))
        if not mp3:
            return {"parse": 0, "url": ""}
        return {"parse": 0, "url": mp3, "flag": "幻听网", "format": "audio/mpeg",
                "header": {"User-Agent": self.UA, "Referer": self.BASE + "/"}}

    def localProxy(self, param=""):
        return {}

    def destroy(self):
        pass