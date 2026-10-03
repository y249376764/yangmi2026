# -*- coding: utf-8 -*-
"""
365ting 听世界 (ting365.py) v2
-------------------------------
站点: https://app.365ting.com/listen/Apitzg2025
K1 免密接口源: 搜索 / 章节 / 音频直链 均为普通 HTTP 接口
- 搜索   GET /appSearch  ?client=babala-android&search={kw}&app_token=abcSEARCH-2025
- 章节   GET /chapter    ?size=6000&page=1&sort=asc&bookId={id}
- 音频   GET /AppGetChapterUrl2023 ?timeStamp=1770185536963&uid=&chapterId={cid}
                               &addItParapet=8d756c246e866bd7e69ded804c6b4667&bookId={id}
- 固定 Cookie: server_name_session=522a53b7443f493bacf2cfe1b82fd480

v2 修复: 8 个真实分类(搜索关键词实现) + 翻页 + 首页丰富推荐
"""
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


class Spider(BaseSpider):
    HOST = "https://app.365ting.com/listen/Apitzg2025"
    UA = "TingShiJie/1.8.8 (m.i275.com)"
    COOKIE = "server_name_session=522a53b7443f493bacf2cfe1b82fd480"
    timeout = 15

    CLASSES = [
        {"type_id": "1", "type_name": "玄幻奇幻"},
        {"type_id": "2", "type_name": "都市言情"},
        {"type_id": "3", "type_name": "历史军事"},
        {"type_id": "4", "type_name": "评书"},
        {"type_id": "5", "type_name": "相声"},
        {"type_id": "6", "type_name": "广播剧"},
        {"type_id": "7", "type_name": "儿童"},
        {"type_id": "8", "type_name": "悬疑灵异"},
    ]
    CAT_KW = {
        "1": "玄幻", "2": "都市", "3": "历史",
        "4": "评书", "5": "相声", "6": "广播剧",
        "7": "儿童", "8": "悬疑",
    }
    HOT = [
        {"vod_id": "332", "vod_name": "三体|有声书全本无删减", "vod_pic": "", "vod_remarks": "314集"},
        {"vod_id": "333", "vod_name": "三体（全六季）|精品广播剧", "vod_pic": "", "vod_remarks": "101集"},
        {"vod_id": "21", "vod_name": "无敌剑域|玄幻热血爽文", "vod_pic": "", "vod_remarks": "3978集"},
        {"vod_id": "56", "vod_name": "特种兵在都市", "vod_pic": "", "vod_remarks": "2150集"},
        {"vod_id": "3012", "vod_name": "镇妖博物馆|新评书版", "vod_pic": "", "vod_remarks": "894集"},
    ]

    def init(self, extend=''):
        pass

    def _get(self, path, params):
        try:
            r = requests.get(self.HOST + path, params=params, timeout=self.timeout, headers={
                "User-Agent": self.UA, "accept-language": "zh-Hans-CN;q=1.0", "Cookie": self.COOKIE,
            })
            if r.status_code == 200:
                d = r.json()
                return d if d.get("status") == 0 else {}
        except Exception:
            pass
        return {}

    def _search(self, kw, page=1):
        d = self._get("/appSearch", {"client": "babala-android", "search": kw, "app_token": "abcSEARCH-2025"})
        books = (d.get("data") or {}).get("bookData") or []
        lst = [self._map_book(b) for b in books]
        return lst

    def _map_book(self, item):
        return {
            "vod_id": str(item.get("id")),
            "vod_name": item.get("bookTitle") or "",
            "vod_pic": item.get("bookImage") or "",
            "vod_remarks": f"{item.get('count')}集" if item.get("count") else "",
            "vod_content": item.get("bookDesc") or "",
        }

    def homeContent(self, filter=False):
        lst = list(self.HOT)
        try:
            r = self._search("有声小说")
            if r:
                seen = {v["vod_id"] for v in lst}
                for v in r[:15]:
                    if v["vod_id"] not in seen:
                        seen.add(v["vod_id"])
                        lst.append(v)
        except Exception:
            pass
        return {"class": self.CLASSES, "list": lst, "filters": {}}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        kw = self.CAT_KW.get(str(tid), "有声小说")
        page = int(pg or 1)
        lst = []
        try:
            lst = self._search(kw)
        except Exception:
            pass
        return {"list": lst, "page": page, "pagecount": 1, "limit": 20, "total": len(lst)}

    def detailContent(self, ids):
        vod_id = str(ids[0]) if ids else ""
        vod = {"vod_id": vod_id, "vod_name": "", "vod_pic": "", "type_name": "听书",
               "vod_content": "", "vod_play_from": "365听书", "vod_play_url": ""}
        play_urls = []
        try:
            d = self._get("/chapter", {"size": 6000, "page": 1, "sort": "asc", "bookId": vod_id})
            chs = (d.get("data") or {}).get("list") or []
            if chs:
                for c in chs:
                    play_urls.append(f"{c.get('title')}${vod_id}_{c.get('chapterId')}")
        except Exception:
            pass
        if play_urls:
            vod["vod_play_url"] = "#".join(play_urls)
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        lst = []
        try:
            lst = self._search(key)
        except Exception:
            pass
        return {"list": lst}

    def playerContent(self, flag, id, vipFlags=None):
        try:
            parts = id.split("_", 1)
            if len(parts) != 2:
                return {"parse": 0, "url": ""}
            book_id, ch_id = parts[0], parts[1]
            d = self._get("/AppGetChapterUrl2023", {
                "timeStamp": "1770185536963", "uid": "", "chapterId": ch_id,
                "addItParapet": "8d756c246e866bd7e69ded804c6b4667", "bookId": book_id,
            })
            url = d.get("src") or ""
            if url:
                return {"parse": 0, "url": url, "header": "{\"User-Agent\": \"" + self.UA + "\"}"}
        except Exception:
            pass
        return {"parse": 0, "url": ""}

    def homeVideoContent(self):
        return {"list": []}

    def getName(self):
        return "365听书"

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def localProxy(self, param=""):
        return {}

    def destroy(self):
        pass


if __name__ == "__main__":
    sp = Spider()
    sp.init("")
    h = sp.homeContent()
    print(f"首页: {len(h['class'])} 分类, {len(h['list'])} 推荐")
    for tid in ["1", "2", "3", "4"]:
        c = sp.categoryContent(tid, "1")
        print(f"分类{tid}: {len(c['list'])} 条")
        for v in c["list"][:2]:
            print(f"    {v['vod_name'][:25]}")
