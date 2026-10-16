# -*- coding: utf-8 -*-
"""☁️ 云图有声 (yuntu.py) —— 默影视听书蜘蛛
公开 JSON 接口，免登录，audioUrl 直链播放
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
YU = "https://open-service.yuntuys.com/api/w_ys/book/"
WX = "wechat:07955551-706c-4259-9aa0-db4627dfca57"
HDR = {"User-Agent": UA}

CATS = [
    ["特色", [["四史专栏", 585], ["远读重洋", 571], ["听见真知", 124], ["豆瓣高分", 125], ["广播剧", 126],
              ["影视同期", 127], ["云图学院", 421]]],
    ["经典文学", [["世界名著", 131], ["中国文学", 132], ["国学经典", 134], ["外国文学", 133], ["诗词散文", 135],
                  ["人物传记", 136]]],
    ["畅销小说", [["国风古韵", 137], ["青春校园", 138], ["科学幻想", 139], ["官场商战", 140], ["军事谍战", 141],
                  ["悬疑推理", 142], ["现代都市", 143], ["怪奇物语", 144], ["侠义江湖", 335]]],
    ["职场财经", [["创业学院", 148], ["职场指南", 149], ["商界大咖", 150], ["金融理财", 151]]],
    ["少儿教育", [["儿童文学", 152], ["童话名著", 153], ["国学启蒙", 154], ["儿歌故事", 155], ["百科知识", 156],
                  ["亲子教育", 157]]],
    ["文化历史", [["民俗文化", 161], ["世界之窗", 163], ["哲学思想", 164], ["古代历史", 165], ["近现代史", 166],
                  ["世界历史", 167], ["传奇史话", 168]]],
    ["军事", [["军事纪实", 173], ["战争烽火", 174], ["革命先驱", 176], ["政治领袖", 177]]],
    ["生活", [["养生保健", 181], ["养颜减肥", 182], ["食疗课堂", 183], ["孕产育儿", 184], ["心理健康", 185],
              ["婚恋家庭", 186], ["心灵励志", 187], ["生活百科", 188], ["娱乐休闲", 189]]],
]

def getj(url):
    try:
        r = requests.get(url, headers=HDR, timeout=14)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None

def mkb(bid, name, author, pic, chapters, cat):
    return {"vod_id": "ss:yuntu:" + str(bid), "vod_name": name, "vod_pic": pic,
            "vod_remarks": "共 %s 章" % chapters if chapters else "", "vod_actor": author,
            "vod_content": cat, "style": {"type": "rect", "ratio": 1.0}}

class Spider(BaseSpider):
    def getName(self): return "☁️云图有声"
    def init(self, extend=""): pass

    def homeContent(self, filter=False):
        cls = []
        for g in CATS:
            for c in g[1]:
                cls.append({"type_id": str(c[1]), "type_name": "☁️ " + c[0], "land": 1, "ratio": 1.0})
        lst = []
        j = getj(YU + "getBookListByType/%s/125?pageNum=1&pageSize=20" % WX)
        for b in ((j or {}).get("data") or {}).get("list") or []:
            x = mkb(b.get("bookId"), b.get("bookName") or "", b.get("authorName") or "",
                    ("https:" + b["cover"]) if str(b.get("cover") or "").startswith("//") else b.get("cover") or "",
                    b.get("chapters") or "", "豆瓣高分")
            if x: lst.append(x)
        return {"class": cls, "list": lst, "filters": {}}

    def homeVideoContent(self): return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        p = max(int(pg or 1), 1)
        j = getj(YU + "getBookListByType/%s/%s?pageNum=%s&pageSize=20" % (WX, requests.utils.quote(str(tid)), p))
        out = []
        for b in ((j or {}).get("data") or {}).get("list") or []:
            x = mkb(b.get("bookId"), b.get("bookName") or "", b.get("authorName") or "",
                    ("https:" + b["cover"]) if str(b.get("cover") or "").startswith("//") else b.get("cover") or "",
                    b.get("chapters") or "", tid)
            if x: out.append(x)
        return {"list": out, "page": p, "pagecount": p + 1 if out else p, "limit": 20, "total": len(out)}

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        bid = vid.split(":")[-1]
        eps = []
        total = 1
        for p in range(1, 21):
            j = getj(YU + "getChapters/%s/%s/true/asc?pageSize=200&pageNum=%d" % (WX, bid, p))
            q = ((j or {}).get("data") or {}).get("pageQuery")
            if not q or not q.get("list"): break
            total = int(q.get("totalPage") or 1)
            for c in q.get("list"):
                u = str(c.get("audioUrl") or "")
                if u:
                    eps.append("%s$%s" % (str(c.get("name") or "第 %d 章" % (len(eps) + 1)).replace("$", " ").replace("#", " "), u))
            if p >= total: break
            time.sleep(0.12)
        vod = {"vod_id": vid, "vod_name": "", "vod_pic": "", "type_name": "听书",
               "vod_play_from": "云图有声", "vod_play_url": "#".join(eps),
               "vod_remarks": "%d 集" % len(eps) if eps else "暂无章节"}
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        p = max(int(pg or 1), 1)
        j = getj(YU + "search/%s/%s?pageSize=20&pageNum=%d" % (WX, requests.utils.quote(str(key or "")), p))
        out = []
        for b in ((j or {}).get("data") or {}).get("list") or []:
            x = mkb(b.get("bookId"), b.get("bookName") or "", b.get("authorName") or "",
                    ("https:" + b["cover"]) if str(b.get("cover") or "").startswith("//") else b.get("cover") or "",
                    b.get("chapters") or "", "搜索")
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
