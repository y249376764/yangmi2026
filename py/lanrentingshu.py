# -*- coding: utf-8 -*-
"""
懒人听书 蜘蛛版 (lanrentingshu.py)
----------------------------------
站点: 聆阅后端 (backend.appmiaoda.com) 聚合懒人听书
2026-10-04 实测:
  * 首页     GET /lrts-home                    -> {books:[120], sections:[15分类]}
  * 分类     GET /lrts-home##分类名             -> sections[].books (常用小说分类)
  * 详情     GET /lrts-book?bookId={id}        -> {meta, chapters:[{id,title,duration}]}
  * 搜索     GET /lrts-search?name={kw}&page=N -> {books:[...]}
  * 播放     GET http://www.tingshu8.top/yuan1/lrts.php?id={chapterId}
             (需带 Referer: http://www.tingshu8.top/) -> {data:{url: m4a直链}}

说明:
  * 播放直链 m4a 需带 Referer (防盗链)
  * 聆阅后端为 Supabase 免费代理, 有频率限制(429), 重试等待
"""
import re
import json
import time

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
    BASE = "https://backend.appmiaoda.com/projects/supabase345057433544081408/functions/v1"
    PLAY = "http://www.tingshu8.top/yuan1/lrts.php?id="
    UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    timeout = 15

    # 懒人听书官方常用分类 (lrts-home sections label)
    CLASSES = [
        {"type_id": "听友推荐", "type_name": "听友推荐"},
        {"type_id": "都市传说", "type_name": "都市传说"},
        {"type_id": "玄幻奇幻", "type_name": "玄幻奇幻"},
        {"type_id": "历史幻想", "type_name": "历史幻想"},
        {"type_id": "武侠仙侠", "type_name": "武侠仙侠"},
        {"type_id": "悬疑爱情", "type_name": "悬疑爱情"},
        {"type_id": "官场商战", "type_name": "官场商战"},
        {"type_id": "幻想言情", "type_name": "幻想言情"},
        {"type_id": "科幻空间", "type_name": "科幻空间"},
        {"type_id": "青春校园", "type_name": "青春校园"},
        {"type_id": "穿越架空", "type_name": "穿越架空"},
        {"type_id": "网游竞技", "type_name": "网游竞技"},
        {"type_id": "热血军事", "type_name": "热血军事"},
        {"type_id": "次元专区", "type_name": "次元专区"},
        {"type_id": "乡村生活", "type_name": "乡村生活"},
    ]

    def _get(self, url, headers=None, retries=3):
        h = {"User-Agent": self.UA}
        if headers:
            h.update(headers)
        for i in range(retries):
            try:
                r = requests.get(url, headers=h, timeout=self.timeout)
                if r.status_code == 200:
                    return r
                if r.status_code == 429 and i < retries - 1:
                    time.sleep(3)
                    continue
            except Exception:
                if i < retries - 1:
                    time.sleep(2)
                    continue
        return None

    def init(self, extend=''):
        pass

    def getName(self):
        return "懒人听书"

    def homeContent(self, filter=False):
        classes = [{"type_id": c["type_id"], "type_name": c["type_name"]} for c in self.CLASSES]
        # 首页默认: 听友推荐 120 本
        lst = self._category_books("听友推荐")
        vod_list = self._build_vods(lst)
        return {"class": classes, "list": vod_list, "filters": {}}

    def _category_books(self, cat_name):
        """从 lrts-home 的 sections 里取指定分类的书"""
        r = self._get(f"{self.BASE}/lrts-home")
        if not r:
            return []
        try:
            d = r.json()
        except Exception:
            return []
        secs = d.get("sections", [])
        for s in secs:
            if s.get("label") == cat_name:
                return s.get("books", [])
        return []

    def _build_vods(self, books):
        out = []
        for b in books or []:
            bid = str(b.get("id", ""))
            if not bid:
                continue
            out.append({
                "vod_id": bid,
                "vod_name": b.get("title", ""),
                "vod_pic": b.get("cover", ""),
                "vod_remarks": b.get("author", ""),
                "vod_content": b.get("description", ""),
                "type_name": (b.get("categories") or [""])[0],
            })
        return out

    def categoryContent(self, tid, pg, filter=False, extend=''):
        books = self._category_books(tid)
        vods = self._build_vods(books)
        return {"list": vods, "page": int(pg or 1), "pagecount": 1}

    def detailContent(self, ids):
        bid = ids[0]
        r = self._get(f"{self.BASE}/lrts-book?bookId={bid}")
        if not r:
            return {"list": []}
        try:
            d = r.json()
        except Exception:
            return {"list": []}
        meta = d.get("meta", {})
        chapters = d.get("chapters", [])
        vod = {
            "vod_id": bid,
            "vod_name": meta.get("name", ""),
            "vod_pic": meta.get("cover", ""),
            "vod_actor": meta.get("author", ""),
            "vod_content": meta.get("description", ""),
        }
        vod_play = []
        for c in chapters:
            cid = str(c.get("id", ""))
            if not cid:
                continue
            vod_play.append(f"{c.get('title','')}${self.PLAY}{cid}")
        vod["vod_play_from"] = "m4a"
        vod["vod_play_url"] = "#".join(vod_play)
        return {"list": [vod]}

    def searchContent(self, key, quick, pg='1'):
        import urllib.parse
        url = f"{self.BASE}/lrts-search?name={urllib.parse.quote(key)}&page={pg}"
        r = self._get(url)
        if not r:
            return {"list": []}
        try:
            d = r.json()
        except Exception:
            return {"list": []}
        books = d.get("books", [])
        return {"list": self._build_vods(books)}

    def playerContent(self, flag, id, vipFlags=None):
        # id 已经是 tingshu8 播放 URL
        r = self._get(id, headers={"Referer": "http://www.tingshu8.top/"})
        if not r:
            return {"parse": 0, "url": ""}
        try:
            d = r.json()
            url = d.get("data", {}).get("url", "")
            if url:
                return {"parse": 0, "url": url}
        except Exception:
            pass
        return {"parse": 0, "url": ""}

    def localProxy(self, param=''):
        return {}

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass
