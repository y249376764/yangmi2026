# -*- coding: utf-8 -*-
"""🎬 哔哩哔哩听书 (bilibili.py) —— 默影视听书蜘蛛
B站音频合集：搜索/分类/详情/播放直链
更多资源请到网站：https://navpage-2026.surge.sh/
"""
import re, json
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
API = "https://api.bilibili.com/x/"
HDR = {"User-Agent": UA, "Referer": "https://www.bilibili.com/"}
WORDS = [["有声小说", "有声小说"], ["广播剧", "广播剧"], ["评书", "评书"], ["相声", "相声"],
         ["有声漫画", "有声漫画"], ["英文有声书", "audiobooks"]]

def getj(url):
    try:
        r = requests.get(url, headers=HDR, timeout=14)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None

def mkb(bvid, name, author, pic, play, dur):
    return {"vod_id": "ss:bili:" + bvid, "vod_name": name, "vod_pic": pic,
            "vod_remarks": "播放 %s%s" % (play, " · " + dur if dur else ""),
            "vod_actor": author, "vod_content": "UP主：%s" % author,
            "style": {"type": "rect", "ratio": 1.0}}

class Spider(BaseSpider):
    def getName(self): return "🎬哔哩哔哩听书"
    def init(self, extend=""): pass

    def homeContent(self, filter=False):
        cls = [{"type_id": "kw:" + w[1], "type_name": w[0], "land": 1, "ratio": 1.0} for w in WORDS]
        lst = []
        try:
            d = getj(API + "web-interface/search/type?search_type=video&keyword=%s&page=1" % requests.utils.quote("评书"))
            for v in ((d or {}).get("data") or {}).get("result") or []:
                if not v.get("bvid"): continue
                lst.append(mkb(v["bvid"], re.sub(r"<[^>]+>", "", v.get("title") or ""), v.get("author") or "",
                               ("https:" + v["pic"]) if v.get("pic", "").startswith("//") else v.get("pic") or "",
                               "播放中", ""))
        except Exception:
            pass
        return {"class": cls, "list": lst, "filters": {}}

    def homeVideoContent(self): return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        p = max(int(pg or 1), 1)
        kw = tid[3:] if tid.startswith("kw:") else "评书"
        out = []
        d = getj(API + "web-interface/search/type?search_type=video&keyword=%s&page=%d" % (requests.utils.quote(kw), p))
        for v in ((d or {}).get("data") or {}).get("result") or []:
            if not v.get("bvid"): continue
            play = v.get("play") or 0
            ps = ("%s万" % round(play / 10000, 1)) if play >= 10000 else str(play)
            out.append(mkb(v["bvid"], re.sub(r"<[^>]+>", "", v.get("title") or ""), v.get("author") or "",
                           ("https:" + v["pic"]) if v.get("pic", "").startswith("//") else v.get("pic") or "",
                           ps, v.get("duration") or ""))
        return {"list": out, "page": p, "pagecount": p + 1 if out else p, "limit": 20, "total": len(out)}

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        bvid = vid.split(":")[-1]
        d = getj(API + "web-interface/view?bvid=" + bvid)
        if not d or d.get("code") != 0:
            return {"list": []}
        dd = d.get("data") or {}
        pages = dd.get("pages") or []
        eps = []
        for i, p in enumerate(pages):
            t = dd.get("title") or "" if len(pages) == 1 else (p.get("part") or "").strip() or ("P" + str(p.get("page")))
            eps.append("%s$bi:%s:%s" % (t.replace("$", " ").replace("#", " "), dd.get("aid"), p.get("cid")))
        pic = dd.get("pic") or ""
        if pic.startswith("//"): pic = "https:" + pic
        vod = {"vod_id": vid, "vod_name": dd.get("title") or "", "vod_pic": pic,
               "vod_actor": (dd.get("owner") or {}).get("name") or "", "type_name": "听书",
               "vod_content": dd.get("desc") or "", "vod_play_from": "哔哩哔哩",
               "vod_play_url": "#".join(eps), "vod_remarks": "%d 集" % len(eps)}
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        p = max(int(pg or 1), 1)
        d = getj(API + "web-interface/search/type?search_type=video&keyword=%s&page=%d" % (requests.utils.quote(str(key or "")), p))
        out = []
        for v in ((d or {}).get("data") or {}).get("result") or []:
            if not v.get("bvid"): continue
            play = v.get("play") or 0
            ps = ("%s万" % round(play / 10000, 1)) if play >= 10000 else str(play)
            out.append(mkb(v["bvid"], re.sub(r"<[^>]+>", "", v.get("title") or ""), v.get("author") or "",
                           ("https:" + v["pic"]) if v.get("pic", "").startswith("//") else v.get("pic") or "",
                           ps, v.get("duration") or ""))
        return {"list": out, "page": p, "pagecount": p + 1 if out else p, "limit": 20, "total": len(out)}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, id, vipFlags=None):
        cid = str(id or "")
        if cid.startswith("bi:"):
            p = cid.split(":")
            d = getj(API + "player/playurl?avid=%s&cid=%s&platform=html5&otype=json&qn=16&type=mp4&html5=1" % (p[1], p[2]))
            u = d.get("data", {}).get("durl", [{}])[0].get("url") if d and d.get("data") else ""
            if u:
                return {"parse": 0, "url": u, "header": json.dumps({"User-Agent": UA, "Referer": "https://www.bilibili.com/"})}
        return {"parse": 0, "url": ""}

    def isVideoFormat(self, url): return False
    def manualVideoCheck(self): return False
    def localProxy(self, param=""): return {}
    def destroy(self): pass
