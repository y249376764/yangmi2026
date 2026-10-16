# -*- coding: utf-8 -*-
"""🚌 声音巴士 (vbus.py) —— 默影视听书蜘蛛
节目=一集，audio src 直链
更多资源请到网站：https://navpage-2026.surge.sh/
"""
import re
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
VB = "https://vbus.cc"
HDR = {"User-Agent": UA, "Referer": VB + "/", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "zh-CN,zh;q=0.9"}

TABS = [["推荐", "/recommend"], ["最新", "/new"], ["最热", "/hot"], ["专辑", "/album"]]

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

def parse(h):
    out = []
    for li in re.findall(r'<li[^>]*>[\s\S]*?</li>', h or ""):
        m = re.search(r'<h3[^>]*><a[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>', li) or re.search(r'<a[^>]+data-program-entry[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>', li)
        if not m: continue
        href = absurl(m.group(1), VB)
        if "/v/" not in href: continue
        nm = txt(m.group(2))
        pic = ""
        mi = re.search(r'<img[^>]+src="([^"]+)"', li)
        if mi: pic = absurl(mi.group(1), VB)
        meta = txt(re.search(r'class="program-meta"[^>]*>([\s\S]*?)</', li).group(1)) if re.search(r'class="program-meta"[^>]*>([\s\S]*?)</', li) else ""
        out.append({"vod_id": "ss:vbus:" + str(href), "vod_name": nm, "vod_pic": pic,
                    "vod_remarks": meta[:70], "vod_content": "声音巴士", "style": {"type": "rect", "ratio": 1.0}})
    return out

def nextlink(h):
    m = re.search(r'<a[^>]+rel="next"[^>]+href="([^"]+)"', h or "") or re.search(r'<a[^>]+class="next"[^>]+href="([^"]+)"', h or "")
    return absurl(m.group(1), VB) if m else ""

class Spider(BaseSpider):
    def getName(self): return "🚌声音巴士"
    def init(self, extend=""): pass

    def homeContent(self, filter=False):
        cls = [{"type_id": t[1], "type_name": "🚌 " + t[0], "land": 1, "ratio": 1.0} for t in TABS]
        lst = parse(get(VB + "/recommend"))
        return {"class": cls, "list": lst, "filters": {}}

    def homeVideoContent(self): return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        p = max(int(pg or 1), 1)
        url = tid if tid.startswith("http") else (VB + tid)
        if p == 1:
            lst = parse(get(url))
        else:
            cur = nextlink(get(url))
            for i in range(2, p):
                cur = nextlink(get(cur)) if cur else ""
                if not cur: break
            lst = parse(get(cur)) if cur else []
        return {"list": lst, "page": p, "pagecount": p + 1 if lst else p, "limit": 30, "total": len(lst)}

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        u = vid.split(":")[-1] if vid.startswith("ss:vbus:") else vid
        h = get(u)
        if not h:
            return {"list": [{"vod_id": vid, "vod_name": "", "vod_pic": "", "vod_remarks": "打不开页面", "vod_play_url": ""}]}
        tm = re.search(r"<title>([^<]*)</title>", h)
        t = re.sub(r"声音巴士", "", txt(tm.group(1) if tm else "")) or "节目"
        vod = {"vod_id": vid, "vod_name": t, "vod_pic": "", "type_name": "听书",
               "vod_play_from": "声音巴士", "vod_play_url": "%s$%s" % (t.replace("$", " "), u),
               "vod_remarks": "1 集"}
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        p = max(int(pg or 1), 1)
        lst = parse(get(VB + "/search?q=%s&page=%d" % (requests.utils.quote(str(key or "")), p)))
        return {"list": lst, "page": p, "pagecount": p + 1 if lst else p, "limit": 20, "total": len(lst)}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, id, vipFlags=None):
        cid = str(id or "")
        h = get(cid)
        if h:
            m = re.search(r'<audio[^>]+src="([^"]+)"', h)
            if m:
                return {"parse": 0, "url": absurl(m.group(1), VB),
                        "header": '{"User-Agent": "%s", "Referer": "%s", "Range": "bytes=0-"}' % (UA, VB)}
        return {"parse": 0, "url": ""}

    def isVideoFormat(self, url): return False
    def manualVideoCheck(self): return False
    def localProxy(self, param=""): return {}
    def destroy(self): pass
