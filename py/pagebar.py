# -*- coding: utf-8 -*-
"""🎧 乐听吧/米听书/囧贼/一夜幻听 (pagebar.py) —— 默影视听书蜘蛛
4 站同构（PAGEBAR CMS）：分类/章节/var now 直链；搜索有验证码→提示
更多资源请到网站：https://navpage-2026.surge.sh/
"""
import re, json as _json
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

ST = {
    "leting8": {"host": "https://www.leting8.com", "name": "乐听吧", "cat": "/le/1.html",
                "search": "https://www.leting8.com/search.php?searchword=", "catpat": "/le/%s.html"},
    "ting78": {"host": "https://www.ting78.com", "name": "米听书", "cat": "/books/1.html",
               "search": "https://www.ting78.com/search.php?searchword=", "catpat": "/books/%s.html"},
    "jiongzei": {"host": "https://www.jiongzei.com", "name": "囧贼听书网", "cat": "/jiongzei/61.html",
                 "search": "https://www.jiongzei.com/search.php?searchword=", "catpat": "/jiongzei/%s.html"},
    "ting22": {"host": "https://www.22ting.com", "name": "一夜幻听", "cat": "/html/221.html",
               "search": "https://www.22ting.com/search.php?searchword=", "catpat": "/html/22%s.html"},
}
CATS = [["玄幻", 1], ["言情", 2], ["都市", 3], ["恐怖", 4], ["推理", 6], ["武侠", 7], ["历史", 8],
        ["军事", 9], ["穿越", 10], ["科幻", 11], ["评书", 13], ["戏曲", 14], ["儿童", 16],
        ["相声小品", 23], ["百家讲坛", 24]]

def get(url, h=None):
    try:
        r = requests.get(url, headers=h, timeout=16)
        return r.text if r.status_code == 200 else ""
    except Exception:
        return ""

def absurl(u, base):
    from urllib.parse import urljoin
    return urljoin(base, str(u or ""))

def txt(s):
    return re.sub(r"\s{2,}", " ", re.sub(r"<[^>]+>", "", s or "")).strip()

def hdr(host, ref):
    return {"User-Agent": UA, "Referer": ref or host + "/", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "zh-CN,zh;q=0.9"}

def parse(h, host, plat):
    out, seen = [], {}
    # 原书源选择器：ul.row-b > li / ul.row3 > li；书名 h2 a.f-bold；封面 a.img-80 img
    if h:
        # 定位 ul.row3.row-b 或 ul.row-b 列表
        ul = re.search(r'<ul[^>]*class="[^"]*row[3-]?-?b[^"]*"[^>]*>([\s\S]*?)</ul>', h, re.I)
        body = ul.group(1) if ul else h
        for li in re.findall(r'<li[^>]*>([\s\S]*?)</li>', body):
            m = re.search(r'<h2[^>]*>[\s\S]*?<a[^>]*(?:class="[^"]*f-bold[^"]*"[^>]*)?href="([^"]+)"[^>]*>([\s\S]*?)</a>', li) \
                or re.search(r'<h2[^>]*>[\s\S]*?<a[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>', li) \
                or re.search(r'<a[^>]+class="[^"]*img-80[^"]*"[^>]+href="([^"]+)"', li)
            if not m: continue
            href = absurl(m.group(1), host)
            if href in seen: continue
            seen[href] = 1
            nm = txt(m.group(2)) if m.lastindex >= 2 else ""
            if not nm:
                ia = re.search(r'<img[^>]+alt="([^"]+)"', li)
                if ia: nm = txt(ia.group(1))
            if not nm: continue
            pic = ""
            mi = re.search(r'<img[^>]+src="([^"]+)"', li)
            if mi: pic = absurl(mi.group(1), host)
            out.append({"vod_id": "ss:%s:%s" % (plat, href), "vod_name": nm.replace("有声小说", ""),
                        "vod_pic": pic, "vod_remarks": ST[plat]["name"], "vod_content": ST[plat]["name"],
                        "style": {"type": "rect", "ratio": 1.0}})
    return out

def nextlink(h, host):
    m = re.search(r'<a[^>]+href="([^"]+)"[^>]*>\s*(?:下一页|下页|››|»|>>|>)\s*</a>', h or "")
    return absurl(m.group(1), host) if m else ""

class Spider(BaseSpider):
    def getName(self): return "🎧乐听吧4站"
    def init(self, extend=""): pass

    def _plat(self, extend=""):
        # 兼容两种 extend：站点 key（leting8）或 host URL（https://www.leting8.com）
        e = (extend or "").strip().lower()
        if not e:
            return "leting8"
        if e in ST:
            return e
        for k, v in ST.items():
            if v["host"].lower() in e or e in v["host"].lower():
                return k
        return "leting8"

    def homeContent(self, filter=False):
        cls = [{"type_id": str(c[1]), "type_name": "🎧 " + c[0], "land": 1, "ratio": 1.0} for c in CATS]
        g = ST["leting8"]
        lst = parse(get(g["host"] + g["cat"], hdr(g["host"], g["host"] + g["cat"])), g["host"], "leting8")
        return {"class": cls, "list": lst, "filters": {}}

    def homeVideoContent(self): return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        p = max(int(pg or 1), 1)
        plat = extend or "leting8"
        g = ST.get(plat) or ST["leting8"]
        url = (g["catpat"] % tid) if tid.isdigit() else tid
        if not url.startswith("http"): url = g["host"] + ("/" if not url.startswith("/") else "") + url
        if p == 1:
            lst = parse(get(url, hdr(g["host"], url)), g["host"], plat)
        else:
            nx = nextlink(get(url, hdr(g["host"], url)), g["host"])
            lst = parse(get(nx, hdr(g["host"], nx)), g["host"], plat) if nx else []
        return {"list": lst, "page": p, "pagecount": p + 1 if lst else p, "limit": 30, "total": len(lst)}

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        ps = vid.split(":", 2)
        if len(ps) < 3: return {"list": []}
        plat, u = ps[1], ps[2]
        g = ST.get(plat) or ST["leting8"]
        hm = re.match(r"^https?://[^/]+", u)
        host = hm.group(0) if hm else g["host"]
        h = get(u, hdr(host, u))
        if not h:
            return {"list": [{"vod_id": vid, "vod_name": "", "vod_pic": "", "vod_remarks": "打不开页面", "vod_play_url": ""}]}
        eps, seen = [], {}
        for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>', h):
            href = absurl(m.group(1), host)
            if href in seen or "/play/" not in href: continue
            seen[href] = 1
            nm = txt(m.group(2))
            if nm:
                eps.append("%s$%s" % (nm.replace("$", " ").replace("#", " "), href))
        h1 = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", h)
        t = txt(h1.group(1)).replace("有声小说", "") if h1 else ""
        vod = {"vod_id": vid, "vod_name": t, "vod_pic": "", "type_name": "听书",
               "vod_play_from": g["name"], "vod_play_url": "#".join(eps),
               "vod_remarks": "%d 集" % len(eps) if eps else "暂无章节"}
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        p = max(int(pg or 1), 1)
        if p > 1: return {"list": [], "page": p, "pagecount": p, "limit": 20, "total": 0}
        g = ST["leting8"]
        h = get(g["search"] + requests.utils.quote(str(key or "")), hdr(g["host"], g["host"] + "/"))
        if not h or "系统安全验证" in h:
            return {"list": [{"vod_id": "ss:leting8:notice", "vod_name": "⚠️ %s：搜索需人工验证" % g["name"], "vod_pic": "",
                              "vod_remarks": "分类浏览不受限制", "vod_content": "该站搜索接口启用图形验证码。请打开网页输入验证码；或用分类列表浏览全部书目。",
                              "style": {"type": "rect", "ratio": 1.0}}], "page": p, "pagecount": p, "limit": 20, "total": 1}
        return {"list": parse(h, g["host"], "leting8"), "page": p, "pagecount": p, "limit": 20, "total": len(parse(h, g["host"], "leting8"))}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, id, vipFlags=None):
        cid = str(id or "")
        if cid.startswith("http") and re.search(r"\.(mp3|m4a|aac|m4b|wav)(\?|$)", cid, re.I):
            return {"parse": 0, "url": cid, "header": '{"User-Agent": "%s", "Range": "bytes=0-"}' % UA}
        hm = re.match(r"^https?://[^/]+", cid)
        host = hm.group(0) if hm else ""
        h = get(cid, hdr(host, cid))
        if not h: return {"parse": 0, "url": "", "msg": "打不开该集页面"}
        m = re.search(r'var\s+now\s*=\s*["\']([^"\']+)["\']', h)
        if m:
            import html as _h
            return {"parse": 0, "url": _h.unescape(m.group(1)), "header": '{"User-Agent": "%s", "Range": "bytes=0-"}' % UA}
        m2 = re.search(r'(?:src|url)\s*[=:]\s*["\'](https?://[^"\']+\.(?:mp3|m4a|aac|wav))["\']', h, re.I)
        if m2:
            return {"parse": 0, "url": m2.group(1), "header": '{"User-Agent": "%s", "Range": "bytes=0-"}' % UA}
        return {"parse": 0, "url": "", "msg": "未找到音频地址"}

    def isVideoFormat(self, url): return False
    def manualVideoCheck(self): return False
    def localProxy(self, param=""): return {}
    def destroy(self): pass
