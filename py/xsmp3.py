# -*- coding: utf-8 -*-
"""😂 相声随身听 (xsmp3.py) —— 默影视听书蜘蛛
站内索引搜索 + 艺人/德云社分类 + APlayer 直链
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
XS = "https://www.xsmp3.com/"
HDR = {"User-Agent": UA, "Referer": XS, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "zh-CN,zh;q=0.9"}

CATS = [["郭德纲", "gdg"], ["于谦", "gdg-yq"], ["张文顺", "gdg-zws"], ["李菁", "gdg-lj"],
        ["德云社", "dys"], ["岳云鹏", "dys-yyp"], ["郭麒麟", "dys-gql"], ["张鹤伦", "dys-zhl"],
        ["马三立", "msl"], ["侯宝林", "hbl"], ["刘宝瑞", "lbr"], ["马季", "mj"], ["最新", "page/1"], ["新势力", "xsxsl"]]

_idx = {"t": 0, "l": []}

def get(url):
    try:
        r = requests.get(url, headers=HDR, timeout=13)
        return r.text if r.status_code == 200 else ""
    except Exception:
        return ""

def absurl(u, base):
    from urllib.parse import urljoin
    return urljoin(base, str(u or ""))

def txt(s):
    return re.sub(r"\s{2,}", " ", re.sub(r"<[^>]+>", "", s or "")).strip()

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

def parse_list(h):
    out = []
    for m in re.finditer(r'class="post_list_li"[^>]*>[\s\S]*?<h2[^>]*><a[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>', h or ""):
        u = absurl(m.group(1), XS)
        if re.search(r"xsmp3\.com/[a-z0-9-]+/[^/]+\.html$", u):
            out.append((u, txt(m.group(2))))
    return out

def index():
    if _idx["l"] and time.time() - _idx["t"] < 3600:
        return _idx["l"]
    f = get(XS)
    if not f: return []
    l = parse_list(f)
    last = 1
    for m in re.findall(r"/page/(\d+)\.html", f):
        if int(m) > last: last = int(m)
    for p in range(2, min(last, 8) + 1):
        h = get(XS + "page/%d.html" % p)
        if h: l += parse_list(h)
        time.sleep(0.1)
    seen, out = set(), []
    for u, nm in l:
        if u not in seen:
            seen.add(u)
            out.append((u, nm))
    _idx["t"], _idx["l"] = time.time(), out
    return out

def mkb(u, nm):
    return {"vod_id": "ss:xsmp3:" + str(u), "vod_name": nm, "vod_pic": "",
            "vod_remarks": "相声随身听", "style": {"type": "rect", "ratio": 1.0}}

class Spider(BaseSpider):
    def getName(self): return "😂相声随身听"
    def init(self, extend=""): pass

    def homeContent(self, filter=False):
        cls = [{"type_id": c[1], "type_name": "😂 " + c[0], "land": 1, "ratio": 1.0} for c in CATS]
        lst = [mkb(u, nm) for u, nm in parse_list(get(XS))][:20]
        return {"class": cls, "list": lst, "filters": {}}

    def homeVideoContent(self): return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        p = max(int(pg or 1), 1)
        lst = [mkb(u, nm) for u, nm in parse_list(get(XS + tid + "/%d.html" % p))] if p <= 8 else []
        return {"list": lst, "page": p, "pagecount": p + 1 if lst else p, "limit": 30, "total": len(lst)}

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        u = vid.split(":")[-1] if vid.startswith("ss:xsmp3:") else vid
        h = get(u)
        if not h:
            return {"list": [{"vod_id": vid, "vod_name": "", "vod_pic": "", "vod_remarks": "打不开页面", "vod_play_url": ""}]}
        eps = []
        for nm, url in aplayer(h):
            if url:
                eps.append("%s$%s" % (nm.replace("$", " ").replace("#", " "), url))
        vod = {"vod_id": vid, "vod_name": "", "vod_pic": "", "type_name": "听书",
               "vod_play_from": "相声随身听", "vod_play_url": "#".join(eps),
               "vod_remarks": "%d 集" % len(eps) if eps else "暂无章节"}
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        p = max(int(pg or 1), 1)
        ws = [w.lower() for w in re.split(r"\s+", str(key or "")) if w]
        if not ws: return {"list": [], "page": p, "pagecount": p, "limit": 20, "total": 0}
        hits = [e for e in index() if all(w in e[1].lower() for w in ws)]
        frm = (p - 1) * 30
        if frm >= len(hits): return {"list": [], "page": p, "pagecount": p, "limit": 20, "total": 0}
        return {"list": [mkb(u, nm) for u, nm in hits[frm:frm + 30]], "page": p,
                "pagecount": p + 1 if hits else p, "limit": 30, "total": len(hits)}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, id, vipFlags=None):
        cid = str(id or "")
        if cid.startswith("http") and re.search(r"\.(mp3|m4a|aac|m4b)(\?|$)", cid, re.I):
            return {"parse": 0, "url": cid, "header": '{"User-Agent": "%s", "Referer": "%s", "Range": "bytes=0-"}' % (UA, XS)}
        return {"parse": 0, "url": ""}

    def isVideoFormat(self, url): return False
    def manualVideoCheck(self): return False
    def localProxy(self, param=""): return {}
    def destroy(self): pass
