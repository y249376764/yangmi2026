# -*- coding: utf-8 -*-
"""📕 爱听书 (itingshu.py) —— 默影视听书蜘蛛
51.la 反爬自动解锁（base64 reverse → __51guid__）+ audio 直链
更多资源请到网站：https://navpage-2026.surge.sh/
"""
import re, time, base64 as _b64
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
ITS = "https://www.itingshu.net"
HDR = {"User-Agent": UA, "Referer": ITS + "/", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "zh-CN,zh;q=0.9"}

CATS = [
    ["有声小说", [["全部", "all"], ["玄幻修真", "xuanhuan"], ["都市言情", "dushi"], ["灵异惊悚", "lingyi"],
                  ["军事历史", "junshi"], ["官场商战", "guanchangshangzhan"], ["人物传记", "chuanji"],
                  ["儿童故事", "ertong"]]],
    ["评书曲艺", [["长篇评书", "pingshu"], ["相声戏曲", "xiangsheng"], ["百家讲坛", "bjjt"]]],
]

_tok = {"v": "", "e": 0}

def itoken(k):
    return "".join("oOo%02X" % b for b in str(k or "").encode("utf-8"))

def get(url, h=None, t=18):
    try:
        r = requests.get(url, headers=h or HDR, timeout=t)
        return r.text if r.status_code == 200 else ""
    except Exception:
        return ""

def post(url, data, h=None):
    hd = dict(HDR)
    hd.update({"Content-Type": "application/x-www-form-urlencoded", "Origin": ITS})
    if h: hd.update(h)
    try:
        r = requests.post(url, data=data, headers=hd, timeout=20)
        return r.text if r.status_code == 200 else ""
    except Exception:
        return ""

def unlock(url, ref):
    global _tok
    ck = _tok["v"] if _tok["e"] > time.time() + 120 else ""
    h = dict(HDR, Referer=ref)
    if ck: h["Cookie"] = "__51guid__=" + ck
    html = get(url, h)
    if not html or "var reversed" not in html: return html
    m = re.search(r'var\s+reversed\s*=\s*"([^"]*)"', html)
    if not m: return html
    try:
        code = _b64.b64decode(m.group(1)[::-1]).decode("utf-8", "ignore")
    except Exception:
        return html
    t = re.search(r"var\s+token\s*=\s*'([^']*)'", code)
    if not t: return html
    tok = t.group(1)
    exp = 0
    try:
        dec = _b64.b64decode(tok.replace("-", "+").replace("_", "/")).decode("utf-8", "ignore")
        seg = dec.split("|")
        if len(seg) > 2 and seg[2].isdigit(): exp = int(seg[2])
    except Exception:
        pass
    if not exp: exp = int(time.time()) + 7000
    _tok["v"], _tok["e"] = tok, exp
    time.sleep(0.16)
    h2 = dict(HDR, Referer=ref)
    h2["Cookie"] = "__51guid__=" + tok
    h2r = get(url, h2)
    return h2r if h2r and "var reversed" not in h2r else (h2r or html)

def absurl(u, base):
    from urllib.parse import urljoin
    return urljoin(base, str(u or ""))

def txt(s):
    return re.sub(r"\s{2,}", " ", re.sub(r"<[^>]+>", "", s or "")).strip()

def parse(h):
    out, seen = [], {}
    for m in re.finditer(r'<a[^>]+class="thumb"[^>]+href="([^"]+)"[^>]*>[\s\S]*?<img[^>]+(?:data-original|src)="([^"]+)"[^>]*>', h or ""):
        href = absurl(m.group(1), ITS)
        if href in seen: continue
        seen[href] = 1
        nm = ""
        tm = re.search(r'title="([^"]+)"', m.group(0))
        if tm: nm = tm.group(1)
        if not nm:
            am = re.search(r'alt="([^"]+)"', m.group(0))
            if am: nm = am.group(1)
        nm = nm.replace("有声小说", "")
        out.append({"vod_id": "ss:itingshu:" + href, "vod_name": nm, "vod_pic": m.group(2),
                    "vod_remarks": "爱听书", "vod_content": "爱听书", "style": {"type": "rect", "ratio": 1.0}})
    return out

class Spider(BaseSpider):
    def getName(self): return "📕爱听书"
    def init(self, extend=""): pass

    def homeContent(self, filter=False):
        cls = []
        for g in CATS:
            for c in g[1]:
                cls.append({"type_id": c[1], "type_name": "📕 " + c[0], "land": 1, "ratio": 1.0})
        lst = parse(get(ITS + "/yousheng/all/lastupdate/1/1.html", dict(HDR, Referer=ITS + "/")))
        return {"class": cls, "list": lst, "filters": {}}

    def homeVideoContent(self): return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        p = max(int(pg or 1), 1)
        u = ITS + "/yousheng/%s/lastupdate/%d/1.html" % (tid, p)
        h = get(u, dict(HDR, Referer=ITS + "/"))
        lst = parse(h)
        return {"list": lst, "page": p, "pagecount": p + 1 if lst else p, "limit": 30, "total": len(lst)}

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        u = vid.split(":", 2)[-1] if vid.startswith("ss:itingshu:") else vid
        h = get(u, dict(HDR, Referer=u))
        if not h:
            return {"list": [{"vod_id": vid, "vod_name": "", "vod_pic": "", "vod_remarks": "打不开页面", "vod_play_url": ""}]}
        h1 = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", h)
        t = txt(h1.group(1)).replace("有声小说", "") if h1 else ""
        eps, seen = [], {}

        def push(hh):
            for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>', hh or ""):
                href = absurl(m.group(1), ITS)
                if "/play/" not in href or href in seen: continue
                seen[href] = 1
                nm = txt(m.group(2))
                if nm:
                    eps.append("%s$%s" % (nm.replace("$", " ").replace("#", " "), href))
        du = ""
        dm = re.search(r'<a[^>]+class="dirurl"[^>]+href="([^"]+)"', h)
        if dm: du = absurl(dm.group(1), ITS)
        if du:
            dh = unlock(du, u)
            if dh:
                push(dh)
                mp = 1
                for mm in re.finditer(r"[?&]page=(\d+)", dh):
                    if int(mm.group(1)) > mp: mp = int(mm.group(1))
                for p in range(2, min(mp, 20) + 1):
                    pu = du + ("&" if "?" in du else "?") + "page=%d&sort=asc" % p
                    ph = unlock(pu, du)
                    if not ph: break
                    push(ph)
                    time.sleep(0.14)
        if not eps: push(h)
        vod = {"vod_id": vid, "vod_name": t, "vod_pic": "", "type_name": "听书",
               "vod_play_from": "爱听书", "vod_play_url": "#".join(eps),
               "vod_remarks": "%d 集" % len(eps) if eps else "暂无章节"}
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        p = max(int(pg or 1), 1)
        if p > 1:
            h = unlock(ITS + "/search/" + itoken(key) + "/lastupdate/%d.html" % p, ITS + "/")
            return {"list": parse(h), "page": p, "pagecount": p, "limit": 20, "total": len(parse(h))}
        h = post(ITS + "/novelsearch/search/result.html", "searchword=" + requests.utils.quote(str(key or "")))
        if not h or "暂时没有您要的结果" in h:
            return {"list": [], "page": p, "pagecount": p, "limit": 20, "total": 0}
        return {"list": parse(h), "page": p, "pagecount": p, "limit": 20, "total": len(parse(h))}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, id, vipFlags=None):
        cid = str(id or "")
        if cid.startswith("http") and re.search(r"\.(mp3|m4a|aac|m4b)(\?|$)", cid, re.I):
            return {"parse": 0, "url": cid, "header": '{"User-Agent": "%s", "Range": "bytes=0-"}' % UA}
        h = get(cid, dict(HDR, Referer=cid))
        if not h: return {"parse": 0, "url": "", "msg": "打不开该集页面"}
        m = re.search(r'<audio[^>]+src="([^"]+)"', h) or re.search(r'<source[^>]+src="([^"]+)"', h)
        if m:
            return {"parse": 0, "url": m.group(1), "header": '{"User-Agent": "%s", "Range": "bytes=0-"}' % UA}
        m2 = re.search(r'https?://[^\s"\'<>]+\.(?:mp3|m4a|aac|m4b)(?:\?[^\s"\']*)?', h, re.I)
        if m2:
            return {"parse": 0, "url": m2.group(0), "header": '{"User-Agent": "%s", "Range": "bytes=0-"}' % UA}
        return {"parse": 0, "url": "", "msg": "该集音频由 JS 动态加载（需 WebView 嗅探）"}

    def isVideoFormat(self, url): return False
    def manualVideoCheck(self): return False
    def localProxy(self, param=""): return {}
    def destroy(self): pass
