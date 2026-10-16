# -*- coding: utf-8 -*-
"""😴 懒人听书 (lrts.py) —— 默影视听书蜘蛛
m.lrts.me 公开 JSON 接口：搜索/分类/章节/免费集直链
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

UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
LR = "https://m.lrts.me"
HDR = {"User-Agent": UA, "Referer": "https://m.lrts.me/", "Accept": "application/json, text/plain, */*"}

CATS = [
    ["有声小说", [["玄幻奇幻", 11], ["都市传说", 8], ["穿越架空", 3109], ["武侠仙侠", 14], ["青春校园", 3106],
                  ["历史幻想", 12], ["科幻空间", 3021], ["网游竞技", 9042], ["热血军事", 9041], ["官场商战", 44]]],
    ["人文", [["心理百科", 9045], ["科学科普", 9046], ["人物传记", 17], ["纪实传奇", 3063], ["哲学宗教", 1026],
              ["文艺文化", 9044], ["公开课", 109]]],
    ["财经", [["投资理财", 3059], ["股市", 3058], ["商业智慧", 3057], ["管理营销", 16], ["创业", 9048]]],
    ["儿童", [["益智故事", 63], ["儿童文学", 3027], ["国学启蒙", 9031], ["卡通动画", 9029], ["少儿名著", 9245],
              ["少儿科普", 64], ["少儿英语", 68]]],
    ["曲艺戏曲", [["戏曲名家", 9060], ["豫剧", 95], ["京剧", 89], ["黄梅戏", 93], ["越剧", 90], ["鼓书琴书", 67]]],
]

def getj(url):
    try:
        r = requests.get(url, headers=HDR, timeout=14)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None

def cover(u):
    u = str(u or "")
    if u and "180" not in u:
        d = u.rfind(".")
        if d > 0: u = u[:d] + "_180x254" + u[d:]
    return u

def mkb(n):
    if not n or not n.get("id"): return None
    title = str(n.get("name") or "")
    tags = str(n.get("tags") or "")
    if "VIP" in tags: title = "[VIP] " + title
    elif "精品" in tags: title = "[精品] " + title
    sec = n.get("sections")
    it = str(n.get("recReason") or "")
    if not it or it == "null": it = str(n.get("desc") or "")
    st = "完本" if n.get("state") == 2 else "连载"
    return {"vod_id": "ss:lrts:" + str(n["id"]), "vod_name": title, "vod_pic": cover(n.get("cover") or ""),
            "vod_remarks": ("%s · %d 集" % (st, sec)) if sec else st, "vod_actor": n.get("author") or "",
            "vod_content": "作者%s · 演播%s · %s" % (n.get("author") or "", n.get("announcer") or "", it[:160]),
            "style": {"type": "rect", "ratio": 1.0}}

class Spider(BaseSpider):
    def getName(self): return "😴懒人听书"
    def init(self, extend=""): pass

    def homeContent(self, filter=False):
        cls = []
        for g in CATS:
            for c in g[1]:
                cls.append({"type_id": str(c[1]), "type_name": "😴 " + c[0], "land": 1, "ratio": 1.0})
        lst = []
        j = getj(LR + "/ajax/search?keyWord=%s&pageSize=20&pageNum=1&searchOption=1" % requests.utils.quote("玄幻小说"))
        for b in ((((j or {}).get("data") or {}).get("bookResult") or {}).get("list") or []):
            x = mkb(b)
            if x: lst.append(x)
        return {"class": cls, "list": lst, "filters": {}}

    def homeVideoContent(self): return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        p = max(int(pg or 1), 1)
        if p > 1: return {"list": [], "page": p, "pagecount": p, "limit": 20, "total": 0}
        j = getj(LR + "/ajax/getResourceList?dsize=20&entityId=%s&entityType=1&pageNum=1&showFilters=1" % requests.utils.quote(str(tid)))
        if not j: return {"list": [], "page": p, "pagecount": p, "limit": 20, "total": 0}
        use = int(j.get("albumCount") or 0) > 0
        arr = (j.get("albums") if use else j.get("books")) or []
        out = []
        for b in arr:
            x = mkb(b)
            if x: out.append(x)
        return {"list": out, "page": p, "pagecount": p, "limit": 20, "total": len(out)}

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        bid = vid.split(":")[-1]
        f = getj(LR + "/ajax/getBookMenu?bookId=%s&pageNum=1&pageSize=50&sortType=0" % bid)
        if not f or (not f.get("list") and f.get("msg")):
            return {"list": [{"vod_id": vid, "vod_name": "", "vod_pic": "", "vod_remarks": "接口无返回", "vod_play_url": ""}]}
        sec = f.get("sections") or (f.get("list") and len(f.get("list"))) or 0
        pages = min(max(1, -(-sec // 50)), 20)
        eps = []

        def push(j):
            for t in (j or {}).get("list") or []:
                free = int(t.get("payType") or 0) == 0
                cid = (LR + "/ajax/getPlayPath?entityId=%s&entityType=3&opType=1&sections=[%s]&type=0" % (bid, t.get("section"))) if free else \
                      (LR + "/player?index=%d&entityType=3&sonId=%s&id=%s" % (len(eps), t.get("id"), bid))
                eps.append(("%s$%s" % (str(t.get("name") or "").replace("$", " ").replace("#", " "), cid)))
        push(f)
        for p in range(2, pages + 1):
            j = getj(LR + "/ajax/getBookMenu?bookId=%s&pageNum=%s&pageSize=50&sortType=0" % (bid, p))
            if not j or not j.get("list"): break
            push(j)
            time.sleep(0.12)
        info = getj(LR + "/ajax/getBookInfo?id=%s" % bid)
        meta = {"intro": "", "artist": "", "cover": ""}
        if info:
            meta = {"intro": str(((info.get("extraInfos") or [{}])[0]).get("content") or ""),
                    "artist": info.get("announcer") or "", "author": info.get("author") or "",
                    "cover": cover(info.get("bestCover") or "")}
        vod = {"vod_id": vid, "vod_name": "", "vod_pic": meta.get("cover") or "", "type_name": "听书",
               "vod_content": meta.get("intro") or "", "vod_actor": meta.get("artist") or meta.get("author") or "",
               "vod_play_from": "懒人听书", "vod_play_url": "#".join(eps),
               "vod_remarks": "%d 集" % len(eps) if eps else "暂无章节"}
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        p = max(int(pg or 1), 1)
        j = getj(LR + "/ajax/search?keyWord=%s&pageSize=40&pageNum=%d&searchOption=1" % (requests.utils.quote(str(key or "")), p))
        out = []
        for b in ((((j or {}).get("data") or {}).get("bookResult") or {}).get("list") or []):
            x = mkb(b)
            if x: out.append(x)
        return {"list": out, "page": p, "pagecount": p + 1 if out else p, "limit": 40, "total": len(out)}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, id, vipFlags=None):
        cid = str(id or "")
        if "getPlayPath" in cid:
            j = getj(cid)
            u = ((j or {}).get("list") or [{}])[0].get("path")
            if u:
                return {"parse": 0, "url": u, "header": '{"User-Agent": "%s", "Referer": "https://m.lrts.me/", "Range": "bytes=0-"}' % UA}
            return {"parse": 0, "url": "", "msg": "未取到播放地址：%s\n免费集可直接播放；[VIP]/[精品] 集需先登录懒人听书账号。" % str((j or {}).get("msg") or "接口无返回")}
        return {"parse": 0, "url": ""}

    def isVideoFormat(self, url): return False
    def manualVideoCheck(self): return False
    def localProxy(self, param=""): return {}
    def destroy(self): pass
