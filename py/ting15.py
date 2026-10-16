# -*- coding: utf-8 -*-
"""🔊 有听网 (ting15.py) —— 默影视听书蜘蛛
guoguo CMS：分类/搜索/章节/API 取流（_b/_cp meta）
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
HOST = "https://www.ting15.com"
HDR = {"User-Agent": UA, "Referer": HOST + "/", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "zh-CN,zh;q=0.9"}

CATS = [["武侠玄幻", "wuxiaxuanhuan"], ["恐怖灵异", "kongbulingyi"], ["推理悬疑", "tuilixuanyi"],
        ["都市言情", "dushiyanqing"], ["家庭伦理", "jiatinglunli"], ["经典评书", "jingdianpingshu"],
        ["相声小品", "xiangshengxiaopin"]]

def get(url, h=None):
    try:
        r = requests.get(url, headers=h or HDR, timeout=16)
        return r.text if r.status_code == 200 else ""
    except Exception:
        return ""

def post(url, data, h=None):
    hd = dict(HDR)
    hd.update({"Content-Type": "application/x-www-form-urlencoded", "X-Requested-With": "XMLHttpRequest"})
    if h: hd.update(h)
    try:
        r = requests.post(url, data=data, headers=hd, timeout=16)
        return r.text if r.status_code == 200 else ""
    except Exception:
        return ""

def absurl(u, base):
    from urllib.parse import urljoin
    return urljoin(base, str(u or ""))

def txt(s):
    return re.sub(r"\s{2,}", " ", re.sub(r"<[^>]+>", "", s or "")).strip()

def parse(h):
    out, seen = [], {}
    for li in re.findall(r'<li[^>]*>[\s\S]*?</li>', h or ""):
        m = re.search(r'<h4[^>]*><a[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>', li) or re.search(r'<a[^>]+href="([^"]+)"[^>]*><img[^>]+alt="([^"]+)"', li)
        if not m: continue
        href = absurl(m.group(1), HOST)
        if ".html" not in href or href in seen: continue
        seen[href] = 1
        nm = txt(m.group(2)).replace("有声小说", "")
        pic = ""
        mi = re.search(r'<img[^>]+src="([^"]+)"', li)
        if mi: pic = absurl(mi.group(1), HOST)
        out.append({"vod_id": "ss:ting15:" + str(href), "vod_name": nm, "vod_pic": pic,
                    "vod_remarks": "有听网", "vod_content": "有听网", "style": {"type": "rect", "ratio": 1.0}})
    return out

def nextlink(h):
    m = re.search(r'<a[^>]+href="([^"]+)"[^>]*>\s*(?:下一页|下页|››|»|>>|>)\s*</a>', h or "")
    return absurl(m.group(1), HOST) if m else ""

class Spider(BaseSpider):
    def getName(self): return "🔊有听网"
    def init(self, extend=""): pass

    def homeContent(self, filter=False):
        cls = [{"type_id": c[1], "type_name": "🔊 " + c[0], "land": 1, "ratio": 1.0} for c in CATS]
        lst = parse(get(HOST + "/"))
        return {"class": cls, "list": lst, "filters": {}}

    def homeVideoContent(self): return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        p = max(int(pg or 1), 1)
        url = HOST + ("/" if not tid.startswith("/") else "") + tid
        if p == 1:
            lst = parse(get(url, dict(HDR, Referer=url)))
        else:
            nx = nextlink(get(url, dict(HDR, Referer=url)))
            lst = parse(get(nx, dict(HDR, Referer=nx))) if nx else []
        return {"list": lst, "page": p, "pagecount": p + 1 if lst else p, "limit": 30, "total": len(lst)}

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        u = vid.split(":")[-1] if vid.startswith("ss:ting15:") else vid
        h = get(u, dict(HDR, Referer=u))
        if not h:
            return {"list": [{"vod_id": vid, "vod_name": "", "vod_pic": "", "vod_remarks": "打不开页面", "vod_play_url": ""}]}
        eps, seen = [], {}
        for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>', h):
            href = absurl(m.group(1), HOST)
            if href in seen: continue
            seen[href] = 1
            nm = txt(m.group(2))
            if nm:
                eps.append("%s$%s" % (nm.replace("$", " ").replace("#", " "), href))
        h1 = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", h)
        t = txt(h1.group(1)).replace("有声小说", "") if h1 else ""
        vod = {"vod_id": vid, "vod_name": t, "vod_pic": "", "type_name": "听书",
               "vod_play_from": "有听网", "vod_play_url": "#".join(eps),
               "vod_remarks": "%d 集" % len(eps) if eps else "暂无章节"}
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        p = max(int(pg or 1), 1)
        if p > 1: return {"list": [], "page": p, "pagecount": p, "limit": 20, "total": 0}
        h = post(HOST + "/?s=ting-search", "wd=" + requests.utils.quote(str(key or "")))
        if not h or "caterank" not in h or re.search(r"没有找到|暂无|无相关", h):
            return {"list": [], "page": p, "pagecount": p, "limit": 20, "total": 0}
        return {"list": parse(h), "page": p, "pagecount": p, "limit": 20, "total": len(parse(h))}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, id, vipFlags=None):
        cid = str(id or "")
        if cid.startswith("http") and re.search(r"\.(mp3|m4a|aac|m4b)(\?|$)", cid, re.I):
            return {"parse": 0, "url": cid, "header": '{"User-Agent": "%s", "Range": "bytes=0-"}' % UA}
        h = get(cid, dict(HDR, Referer=cid))
        if not h: return {"parse": 0, "url": "", "msg": "打不开该集页面（网络不通或已下架）"}

        def meta(n):
            m = re.search(r'<meta\s+name=["\']%s["\']\s+content=["\']([^"\']*)["\']' % n, h, re.I)
            return m.group(1) if m else ""
        bid, cp, xt, l = meta("_b"), meta("_cp"), meta("_c"), meta("_l")
        hm = re.match(r"^https?://[^/]+", cid)
        host = hm.group(0) if hm else ""
        if not bid:
            m0 = re.search(r'(?:var\s+now|src)\s*[=:]\s*["\']([^"\']+\.(?:mp3|m4a|aac))["\']', h, re.I)
            if m0:
                return {"parse": 0, "url": absurl(m0.group(1), host), "header": '{"User-Agent": "%s", "Range": "bytes=0-"}' % UA}
            return {"parse": 0, "url": "", "msg": "未找到音频（可能需打开网页确认）"}
        hd = dict(HDR, Referer=cid)
        hd["Content-Type"] = "application/x-www-form-urlencoded"
        hd["X-Requested-With"] = "XMLHttpRequest"
        if xt: hd["xt"] = xt
        if l: hd["l"] = l
        for pay in (0, 1):
            r = post(host + "/?s=api-getneoplay", "bookId=%s&isPay=%d&page=%s" % (requests.utils.quote(bid), pay, requests.utils.quote(cp or "1")), hd)
            try:
                j = _json.loads(r or "{}")
                u = j.get("url") or ((j.get("data") or {}).get("url") if isinstance(j.get("data"), dict) else "")
                if u and str(u).startswith("http"):
                    return {"parse": 0, "url": str(u), "header": '{"User-Agent": "%s", "Range": "bytes=0-"}' % UA}
            except Exception:
                pass
            time.sleep(0.12)
        return {"parse": 0, "url": "", "msg": "未取到播放地址（该集可能已下架或为付费集）"}

    def isVideoFormat(self, url): return False
    def manualVideoCheck(self): return False
    def localProxy(self, param=""): return {}
    def destroy(self): pass
