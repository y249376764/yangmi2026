# -*- coding: utf-8 -*-
"""🎙️ 评书随身听 (psmp3.py) —— 默影视听书蜘蛛
Z-Blog 主题：艺人分类/搜索/APlayer 直链
更多资源请到网站：https://navpage-2026.surge.sh/
"""
import re, time, json as _json
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

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
PM = "https://www.psmp3.com/"
HDR = {"User-Agent": UA, "Referer": PM, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "zh-CN,zh;q=0.9"}

ARTISTS = [["单田芳", "stf"], ["袁阔成", "ykc"], ["田连元", "tly"], ["刘兰芳", "llf"], ["连丽如", "llr"], ["张少佐", "zsz"], ["田战义", "tzy"]]

def get(url):
    try:
        r = requests.get(url, headers=HDR, timeout=16)
        return r.text if r.status_code == 200 else ""
    except Exception:
        return ""

def absurl(u, base):
    from urllib.parse import urljoin
    return urljoin(base, str(u or ""))

def txt(s):
    return re.sub(r"\s{2,}", " ", re.sub(r"<[^>]+>", "", s or "")).strip()

def artist(code):
    for x in ARTISTS:
        if x[1] == code: return x[0]
    return ""

def artist_of(u):
    m = re.search(r"psmp3\.com/([a-z]+)-", str(u))
    return artist(m.group(1)) if m else ""

def book_url_of(u):
    m = re.search(r"psmp3\.com/([a-z]+-[a-z0-9]+)/[^/]+\.html", str(u))
    return (PM + m.group(1) + ".html") if m else ""

def title(raw):
    m = re.search(r"《(.+?)》(全\d+回)?", str(raw))
    return (m.group(1) + (" " + m.group(2) if m.group(2) else "")) if m else str(raw)

def aplayer(h):
    out = []
    for m in re.finditer(r'name:\s*"((?:[^"\\]|\\.)*)"\s*,\s*artist:\s*"((?:[^"\\]|\\.)*)"\s*,\s*url:\s*"([^"]+)"', str(h or "")):
        u = m.group(3)
        try:
            u = _json.loads('"' + m.group(3).replace('"', '\\"') + '"')
        except Exception:
            pass
        out.append((m.group(1), u))
    return out

def mkb(href, name, au, cat):
    return {"vod_id": "ss:psmp3:" + str(href), "vod_name": name, "vod_pic": "",
            "vod_remarks": "评书随身听", "vod_actor": au, "vod_content": "艺人：" + au + " · " + cat,
            "style": {"type": "rect", "ratio": 1.0}}

class Spider(BaseSpider):
    def getName(self): return "🎙️评书随身听"
    def init(self, extend=""): pass

    def homeContent(self, filter=False):
        cls = [{"type_id": c[1], "type_name": "🎙️ " + c[0], "land": 1, "ratio": 1.0} for c in ARTISTS]
        lst = self._browse("stf")
        return {"class": cls, "list": lst, "filters": {}}

    def homeVideoContent(self): return {"list": []}

    def _browse(self, code):
        h = get(PM + code + ".html")
        if not h: return []
        au = artist(code)
        out, seen = [], {}
        re_book = re.compile(r"psmp3\.com/" + re.escape(code) + r"-[a-z0-9]+\.html$")
        for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>', h):
            href = absurl(m.group(1), PM)
            if not re_book.search(href) or href in seen: continue
            seen[href] = 1
            nm = txt(m.group(2))
            if au and nm.startswith(au): nm = nm[len(au):]
            out.append(mkb(href, nm, au, "艺人"))
        return out

    def categoryContent(self, tid, pg, filter=False, extend=""):
        p = max(int(pg or 1), 1)
        lst = self._browse(tid) if p == 1 else []
        return {"list": lst, "page": p, "pagecount": p, "limit": 30, "total": len(lst)}

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        u = vid.split(":")[-1] if vid.startswith("ss:psmp3:") else vid
        h = get(u)
        if not h:
            return {"list": [{"vod_id": vid, "vod_name": "", "vod_pic": "", "vod_remarks": "打不开页面", "vod_play_url": ""}]}
        parts, seen, pages = [], {}, {u: 1}
        cur = h
        for i in range(20):
            if not cur: break
            for m in re.finditer(r'class="post_list_li"[^>]*>[\s\S]*?<h2[^>]*><a[^>]+href="([^"]+)"', cur):
                href = absurl(m.group(1), PM)
                if href and href not in seen:
                    seen[href] = 1
                    parts.append(href)
            nm = re.search(r'<a[^>]+href="([^"]+)"[^>]*>\s*下一页\s*</a>', cur)
            nxt = absurl(nm.group(1), PM) if nm else ""
            if nxt and nxt not in pages:
                pages[nxt] = 1
                cur = get(nxt)
            else:
                cur = None
        parts.sort(key=lambda a: int((re.search(r"-(\d+)\.html$", a) or [0, 0])[1] or 0))
        eps = []
        for pt in parts:
            for nm, url in aplayer(get(pt)):
                if url:
                    eps.append("%s$%s" % (nm.replace("$", " ").replace("#", " "), url))
            time.sleep(0.12)
        vod = {"vod_id": vid, "vod_name": "", "vod_pic": "", "type_name": "听书",
               "vod_play_from": "评书随身听", "vod_play_url": "#".join(eps),
               "vod_remarks": "%d 集" % len(eps) if eps else "暂无章节"}
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        p = max(int(pg or 1), 1)
        h = get(PM + "search.php?q=%s&page=%d" % (requests.utils.quote(str(key or "")), p))
        out, seen = [], {}
        if h:
            for m in re.finditer(r'class="post_list_li"[^>]*>[\s\S]*?<h2[^>]*><a[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>', h):
                bu = book_url_of(absurl(m.group(1), PM))
                if not bu or bu in seen: continue
                seen[bu] = 1
                out.append(mkb(bu, title(txt(m.group(2))), artist_of(bu), "搜索"))
        return {"list": out, "page": p, "pagecount": p + 1 if out else p, "limit": 20, "total": len(out)}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, id, vipFlags=None):
        cid = str(id or "")
        if cid.startswith("http") and re.search(r"\.(mp3|m4a|aac|m4b)(\?|$)", cid, re.I):
            return {"parse": 0, "url": cid, "header": '{"User-Agent": "%s", "Referer": "%s", "Range": "bytes=0-"}' % (UA, PM)}
        return {"parse": 0, "url": ""}

    def isVideoFormat(self, url): return False
    def manualVideoCheck(self): return False
    def localProxy(self, param=""): return {}
    def destroy(self): pass
