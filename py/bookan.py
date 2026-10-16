# -*- coding: utf-8 -*-
"""📚 博看有声 (bookan.py) —— 默影视听书蜘蛛
图书/专辑分类+搜索，JSON API 直链播放
更多资源请到网站：https://navpage-2026.surge.sh/
"""
import re, time
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
BES = "https://es.bookan.com.cn/api/v3/voice/"
BAPI = "https://api.bookan.com.cn/voice/"
BINST = "25304"
HDR = {"User-Agent": UA}

# 图书分类
BOOK_C = [["经典必读", 1314], ["国学经典", 1320], ["文学文艺", 1306], ["少年读物", 1305],
          ["儿童文学", 1304], ["心理哲学", 1310], ["育儿心经", 1309], ["家庭健康", 1311],
          ["青春励志", 1307], ["历史小说", 1312], ["商业财经", 1315], ["科技科普", 1313],
          ["故事会", 1303], ["音乐戏曲", 1317], ["相声评书", 1319]]
# 专辑分类
ALBUM_C = [["健康养生", 4], ["休闲娱乐", 5], ["财经科技", 6], ["广播节目", 7], ["人文社科", 8],
           ["少儿学堂", 9], ["文史军事", 10], ["投资理财", 11], ["亲子教育", 12], ["时尚生活", 13],
           ["汽车知识", 14], ["发展创业", 15], ["婚恋情感", 16], ["自我提升", 17], ["商业资讯", 18],
           ["新闻热点", 19]]

def getj(url):
    try:
        r = requests.get(url, headers=HDR, timeout=14)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None

def mkb(typ, bid, name, pic, au, total, cat):
    return {"vod_id": "ss:bookan:%s:%s" % (typ, bid), "vod_name": name, "vod_pic": pic,
            "vod_remarks": "共 %s 章" % total if total else "", "vod_actor": au,
            "vod_content": cat, "style": {"type": "rect", "ratio": 1.0}}

def fetch_list(url, typ, cat):
    out = []
    j = getj(url)
    for b in ((j or {}).get("data") or {}).get("list") or []:
        if not b.get("id"): continue
        au = (b.get("extra") or {}).get("author") if isinstance(b.get("extra"), dict) else b.get("press") or ""
        cv = b.get("cover") or ""
        if cv.startswith("//"): cv = "https:" + cv
        out.append(mkb(typ, b["id"], b.get("name") or "", cv, au, b.get("total") or "", cat))
    return out

class Spider(BaseSpider):
    def getName(self): return "📚博看有声"
    def init(self, extend=""): pass

    def homeContent(self, filter=False):
        cls = [{"type_id": "book:0", "type_name": "📖 图书", "land": 1, "ratio": 1.0}]
        for c in BOOK_C:
            cls.append({"type_id": "book:%d" % c[1], "type_name": "· " + c[0], "land": 1, "ratio": 1.0})
        cls.append({"type_id": "album:0", "type_name": "💿 专辑", "land": 1, "ratio": 1.0})
        for c in ALBUM_C:
            cls.append({"type_id": "album:%d" % c[1], "type_name": "· " + c[0], "land": 1, "ratio": 1.0})
        lst = []
        for kw in ("三国演义", "水浒传", "西游记"):
            if len(lst) >= 10: break
            j = getj(BES + "book?instanceId=%s&keyword=%s&pageNum=1&limitNum=10" % (BINST, requests.utils.quote(kw)))
            for b in ((j or {}).get("data") or {}).get("list") or []:
                if len(lst) >= 10: break
                if b.get("id"):
                    au = (b.get("extra") or {}).get("author") if isinstance(b.get("extra"), dict) else ""
                    cv = b.get("cover") or ""
                    if cv.startswith("//"): cv = "https:" + cv
                    lst.append(mkb("book", b["id"], b.get("name") or "", cv, au, b.get("total") or "", "推荐"))
        return {"class": cls, "list": lst, "filters": {}}

    def homeVideoContent(self): return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        p = max(int(pg or 1), 1)
        ps = tid.split(":")
        typ = ps[0]; cid = ps[1] if len(ps) > 1 else "0"
        if typ == "book":
            lst = fetch_list(BAPI + "book/list?instance_id=%s&page=%s&category_id=%s&num=24" % (BINST, p, cid), "book", "图书")
        else:
            lst = fetch_list(BAPI + "album/list?instance_id=%s&page=%s&category_id=%s&num=24" % (BINST, p, cid), "album", "专辑")
        return {"list": lst, "page": p, "pagecount": p + 1 if lst else p, "limit": 24, "total": len(lst)}

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        ps = vid.split(":")
        if len(ps) < 4: return {"list": []}
        typ, bid = ps[2], ps[3]
        if typ != "album":
            return {"list": [{"vod_id": vid, "vod_name": "", "vod_pic": "", "vod_remarks": "该书未提供音频章节", "vod_play_url": ""}]}
        eps = []
        f = getj(BAPI + "album/units?album_id=%s&page=1&num=20&order=1" % bid)
        dd = (f or {}).get("data")
        if not dd or not dd.get("list"):
            return {"list": [{"vod_id": vid, "vod_name": "", "vod_pic": "", "vod_remarks": "暂无章节", "vod_play_url": ""}]}
        total = min(int(dd.get("last_page") or 1), 60)

        def push(j):
            for u in (j or {}).get("list") or []:
                url = str(u.get("file") or "").replace("http://", "https://")
                if url:
                    eps.append("%s$%s" % (str(u.get("title") or "").replace("$", " ").replace("#", " "), url))
        push(dd)
        for p in range(2, total + 1):
            j = getj(BAPI + "album/units?album_id=%s&page=%s&num=20&order=1" % (bid, p))
            if not j or not (j.get("data") or {}).get("list"): break
            push((j.get("data") or {}))
            time.sleep(0.12)
        vod = {"vod_id": vid, "vod_name": "", "vod_pic": "", "type_name": "听书",
               "vod_play_from": "博看有声", "vod_play_url": "#".join(eps),
               "vod_remarks": "%d 集" % len(eps) if eps else "暂无章节"}
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        p = max(int(pg or 1), 1)
        out = []
        for typ in ("book", "album"):
            j = getj(BES + typ + "?instanceId=%s&keyword=%s&pageNum=%s&limitNum=20" % (BINST, requests.utils.quote(str(key or "")), p))
            for b in ((j or {}).get("data") or {}).get("list") or []:
                x = None
                if b.get("id"):
                    au = (b.get("extra") or {}).get("author") if isinstance(b.get("extra"), dict) else ""
                    cv = b.get("cover") or ""
                    if cv.startswith("//"): cv = "https:" + cv
                    x = mkb(typ, b["id"], b.get("name") or "", cv, au, b.get("total") or "", "搜索")
                if x: out.append(x)
        return {"list": out, "page": p, "pagecount": p + 1 if out else p, "limit": 20, "total": len(out)}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, id, vipFlags=None):
        cid = str(id or "")
        if cid.startswith("http") and re.search(r"\.(mp3|m4a|aac|m4b)(\?|$)", cid, re.I):
            return {"parse": 0, "url": cid, "header": '{"User-Agent": "%s", "Range": "bytes=0-"}' % UA}
        return {"parse": 0, "url": ""}

    def isVideoFormat(self, url): return False
    def manualVideoCheck(self): return False
    def localProxy(self, param=""): return {}
    def destroy(self): pass
