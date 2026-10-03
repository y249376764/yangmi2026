# -*- coding: utf-8 -*-
"""
365ting 听世界 (ting365.py)
----------------------------
站点: https://app.365ting.com/listen/Apitzg2025
K1 免密接口源: 搜索 / 章节 / 音频直链 均为普通 HTTP 接口
- 搜索   GET /appSearch      ?client=babala-android&search={kw}&app_token=abcSEARCH-2025
- 章节   GET /chapter        ?size=6000&page=1&sort=asc&bookId={id}   (一次返回整本书)
- 音频   GET /AppGetChapterUrl2023 ?timeStamp=1770185536963&uid=&chapterId={cid}&addItParapet=8d756c246e866bd7e69ded804c6b4667&bookId={id}
- 固定 Cookie: server_name_session=522a53b7443f493bacf2cfe1b82fd480
- 固定 UA: TingShiJie/1.8.8 (m.i275.com)
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
        {"type_id": "1", "type_name": "听书"},
    ]

    def init(self, extend=''):
        pass

    def _get(self, path, params):
        r = requests.get(self.HOST + path, params=params, timeout=self.timeout, headers={
            "User-Agent": self.UA, "accept-language": "zh-Hans-CN;q=1.0",
            "Cookie": self.COOKIE,
        })
        if r.status_code != 200:
            return {}
        try:
            data = r.json()
            return data if data.get("status") == 0 else {}
        except Exception:
            return {}

    def homeContent(self, filter=False):
        # 首页直接放推荐（热门听书）
        lst = []
        try:
            d = self._get("/appSearch", {"client": "babala-android", "search": "有声小说", "app_token": "abcSEARCH-2025"})
            books = (d.get("data") or {}).get("bookData") or []
            lst = [self._map_book(b) for b in books]
        except Exception:
            pass
        if not lst:
            lst = [{"vod_id": "332", "vod_name": "三体|有声书全本无删减", "vod_pic": "", "vod_remarks": "314集"}]
        return {"class": self.CLASSES, "list": lst, "filters": {}}

    def _map_book(self, item):
        return {
            "vod_id": str(item.get("id")),
            "vod_name": item.get("bookTitle") or "",
            "vod_pic": item.get("bookImage") or "",
            "vod_remarks": f"{item.get('count')}集" if item.get("count") else "",
            "vod_content": item.get("bookDesc") or "",
        }

    def categoryContent(self, tid, pg, filter=False, extend=""):
        return {"list": []}

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
            d = self._get("/appSearch", {"client": "babala-android", "search": key, "app_token": "abcSEARCH-2025"})
            books = (d.get("data") or {}).get("bookData") or []
            lst = [self._map_book(b) for b in books]
        except Exception:
            pass
        return {"list": lst}

    def playerContent(self, flag, id, vipFlags=None):
        try:
            # id 格式: {bookId}_{chapterId} (detailContent 拼接)
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
    print(f"首页: {len(h['list'])} 推荐")
    s = sp.searchContent("三体", True)
    print(f"搜索: {len(s['list'])} 条")
    if s["list"]:
        b = s["list"][0]
        print(f"第一本: {b['vod_name'][:30]} id={b['vod_id']}")
        d = sp.detailContent([b["vod_id"]])
        urls = d["list"][0]["vod_play_url"].split("#")
        print(f"章节: {len(urls)} 集, 第一集: {urls[0][:40]}")
        if urls:
            p = sp.playerContent("", urls[0].split("$")[1])
            print(f"播放: {p.get('url', '')[:70]}")
