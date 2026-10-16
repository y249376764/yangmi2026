# -*- coding: utf-8 -*-
"""🇨🇳 听中国/275听书 (i275.py) —— 默影视听书蜘蛛
m.i275.com：分类/搜索/章节/播放页 lrts 直链
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

UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
I2 = "https://m.i275.com"
LR = "https://m.lrts.me"
HL = {"User-Agent": UA, "Referer": "https://m.lrts.me/", "Accept": "application/json, text/plain, */*"}
HDR = {"User-Agent": UA, "Referer": I2 + "/", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "zh-CN,zh;q=0.9"}

def get(url, h=None):
    try:
        r = requests.get(url, headers=h or HDR, timeout=16)
        return r.text if r.status_code == 200 else ""
    except Exception:
        return ""

def absurl(u, base):
    from urllib.parse import urljoin
    return urljoin(base, str(u or ""))

def txt(s):
    return re.sub(r"\s{2,}", " ", re.sub(r"<[^>]+>", "", s or "")).strip()

def hdec(s):
    import html as _h
    return _h.unescape(str(s or ""))

def parse(h):
    out, seen = [], {}
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>', h or ""):
        href = absurl(m.group(1), I2)
        if href.startswith("//"): href = "https:" + href
        if not re.search(r"/book/\d+\.html$", href) or href in seen: continue
        img = re.search(r'<img[^>]+alt="([^"]+)"[^>]+src="([^"]+)"', m.group(2)) or re.search(r'<img[^>]+src="([^"]+)"[^>]+alt="([^"]+)"', m.group(2))
        nm, pic = "", ""
        if img:
            if img.lastindex == 2:
                nm, pic = img.group(1), img.group(2)
            else:
                nm, pic = img.group(2), img.group(1)
        if not nm:
            h3 = re.search(r"<h3[^>]*>([\s\S]*?)</h3>", m.group(2))
            if h3: nm = txt(h3.group(1))
        if not nm: nm = txt(m.group(2))
        if not nm: continue
        seen[href] = 1
        out.append({"vod_id": "ss:i275:" + str(href), "vod_name": hdec(nm).replace("有声小说", ""),
                    "vod_pic": absurl(pic, I2), "vod_remarks": "听中国", "vod_content": "听中国",
                    "style": {"type": "rect", "ratio": 1.0}})
    return out

def nextlink(h):
    m = re.search(r'<a[^>]+rel="next"[^>]+href="([^"]+)"', h or "") or re.search(r'<a[^>]+class="next"[^>]+href="([^"]+)"', h or "")
    return absurl(m.group(1), I2) if m else ""

class Spider(BaseSpider):
    def getName(self): return "🇨🇳听中国"
    def init(self, extend=""): pass

    def homeContent(self, filter=False):
        cls = [{"type_id": "/", "type_name": "🇨🇳 听中国", "land": 1, "ratio": 1.0}]
        lst = parse(get(I2 + "/"))
        return {"class": cls, "list": lst, "filters": {}}

    def homeVideoContent(self): return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        p = max(int(pg or 1), 1)
        url = I2 + ("/" if tid == "/" else tid)
        if p == 1:
            lst = parse(get(url))
        else:
            nx = nextlink(get(url))
            lst = parse(get(nx)) if nx else []
        return {"list": lst, "page": p, "pagecount": p + 1 if lst else p, "limit": 30, "total": len(lst)}

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        u = vid.split(":")[-1] if vid.startswith("ss:i275:") else vid
        if u.startswith("//"): u = "https:" + u
        h = get(u)
        if not h:
            return {"list": [{"vod_id": vid, "vod_name": "", "vod_pic": "", "vod_remarks": "打不开页面", "vod_play_url": ""}]}
        eps, seen = [], {}
        for m in re.finditer(r'<a[^>]+id="chapter-pos-[^"]*"[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>', h):
            href = absurl(m.group(1), I2)
            if href in seen: continue
            seen[href] = 1
            eps.append("%s$%s" % (txt(m.group(2)).replace("$", " ").replace("#", " "), href))
        if not eps:
            for m in re.finditer(r'<a[^>]+href="(/play/\d+/\d+\.html)"[^>]*>([\s\S]*?)</a>', h, re.I):
                href = absurl(m.group(1), I2)
                if href in seen: continue
                seen[href] = 1
                eps.append("%s$%s" % (txt(m.group(2)).replace("$", " ").replace("#", " "), href))
        h1 = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", h)
        t = txt(h1.group(1)) if h1 else ""
        au = ""
        pm = re.search(r"作者[：:]\s*(?:<[^>]*>)*([^<\n]{1,20})", h)
        if pm: au = pm.group(1).strip()
        im = re.search(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']*)["\']', h, re.I)
        vod = {"vod_id": vid, "vod_name": t.replace("275听书", ""), "vod_pic": "", "type_name": "听书",
               "vod_actor": au, "vod_content": hdec(im.group(1)) if im else "",
               "vod_play_from": "听中国", "vod_play_url": "#".join(eps),
               "vod_remarks": "%d 集" % len(eps) if eps else "暂无章节"}
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        p = max(int(pg or 1), 1)
        if p > 1: return {"list": [], "page": p, "pagecount": p, "limit": 20, "total": 0}
        lst = parse(get(I2 + "/search.php?q=" + requests.utils.quote(str(key or ""))))
        return {"list": lst, "page": p, "pagecount": p, "limit": 20, "total": len(lst)}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, id, vipFlags=None):
        cid = str(id or "")
        if cid.startswith("http") and re.search(r"\.(mp3|m4a|aac|m4b)(\?|$)", cid, re.I):
            return {"parse": 0, "url": cid, "header": '{"User-Agent": "%s", "Range": "bytes=0-"}' % UA}
        h = get(cid)
        if not h: return {"parse": 0, "url": ""}
        m = re.search(r'url\s*:\s*["\']([^"\']+)["\']', h) or re.search(r'<source[^>]+src=["\']([^"\']+)["\']', h)
        if not m: return {"parse": 0, "url": ""}
        raw = m.group(1)
        if raw.startswith("lrts$"):
            ps = raw.split("#")
            eid = ps[0].replace("lrts$", "")
            sec = int(ps[2]) if len(ps) > 2 and ps[2].isdigit() else 1
            try:
                r = requests.get(LR + "/ajax/getPlayPath?entityId=%s&entityType=3&opType=1&sections=[%d]&type=0" % (eid, sec), headers=HL, timeout=16)
                j = r.json() if r.status_code == 200 else None
                u = ((j or {}).get("list") or [{}])[0].get("path")
                if u:
                    return {"parse": 0, "url": u, "header": '{"User-Agent": "%s", "Referer": "https://m.lrts.me/", "Range": "bytes=0-"}' % UA}
            except Exception:
                pass
            return {"parse": 0, "url": "", "msg": "未取到播放地址（懒人接口无返回）"}
        if raw.startswith("http"):
            return {"parse": 0, "url": raw, "header": '{"User-Agent": "%s", "Range": "bytes=0-"}' % UA}
        return {"parse": 0, "url": ""}

    def isVideoFormat(self, url): return False
    def manualVideoCheck(self): return False
    def localProxy(self, param=""): return {}
    def destroy(self): pass
