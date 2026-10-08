# -*- coding: utf-8 -*-
"""听友FM 听书蜘蛛 v3 (2026-10-08 重写)
站点: https://tingyou.fm
协议: H5 多域名明文 JSON (2026-10-06 站方迁移后)
"""
import requests, re

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        def homeContent(self, filter=False): return {"class": [], "list": [], "filters": {}}
        def categoryContent(self, tid, pg, filter=False, extend=''): return {"list": []}
        def detailContent(self, ids): return {"list": []}
        def searchContent(self, key, quick, pg='1'): return {"list": []}
        def playerContent(self, flag, id, vipFlags=None): return {"parse": 0, "url": ""}
        def init(self, extend=''): pass
        def destroy(self): pass

class Spider(BaseSpider):
    NAME = "听友FM"
    UA = "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36"
    POOLS = ["https://api-preview.toulaopao.cc", "https://laopaoaappi.oobyvy.vip", "https://toudnbbaa.toulaopao1.cc"]
    HEADERS = {
        "Origin": "https://tingyou.fm",
        "Referer": "https://tingyou.fm/",
        "User-Agent": "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-Mode": "cors",
    }
    TIMEOUT = 15
    _pool = 0

    def _base(self):
        return self.POOLS[self._pool % len(self.POOLS)]

    def _get(self, path, params=None):
        url = self._base() + path
        try:
            r = requests.get(url, params=params, headers=self.HEADERS, timeout=self.TIMEOUT)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        # 换池重试
        self._pool += 1
        try:
            url = self._base() + path
            r = requests.get(url, params=params, headers=self.HEADERS, timeout=self.TIMEOUT)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {}

    def _post(self, path, data):
        url = self._base() + path
        try:
            r = requests.post(url, json=data, headers=self.HEADERS, timeout=self.TIMEOUT)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        self._pool += 1
        try:
            url = self._base() + path
            r = requests.post(url, json=data, headers=self.HEADERS, timeout=self.TIMEOUT)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {}

    def init(self, extend=''):
        pass

    def homeContent(self, filter=False):
        cls_ = [
            {"type_id": "46", "type_name": "玄幻奇幻"},
            {"type_id": "11", "type_name": "武侠小说"},
            {"type_id": "19", "type_name": "言情通俗"},
            {"type_id": "14", "type_name": "恐怖灵异"},
            {"type_id": "17", "type_name": "官场商战"},
            {"type_id": "15", "type_name": "历史军事"},
            {"type_id": "16", "type_name": "刑侦推理"},
            {"type_id": "10", "type_name": "文学名著"},
            {"type_id": "36", "type_name": "广播剧"},
        ]
        lst = []
        try:
            d = self._get("/h5/listening/rank", {"page": 1})
            items = d.get("items") or d.get("data") or []
            for it in items[:20]:
                lst.append({
                    "vod_id": str(it.get("id", "")),
                    "vod_name": it.get("title", it.get("name", "")),
                    "vod_pic": it.get("cover_url", it.get("pic", "")),
                    "vod_remarks": it.get("count_desc", ""),
                })
        except Exception:
            pass
        if not lst:
            lst = [{"vod_id": "3879657962", "vod_name": "三体(1-3部)", "vod_pic": "https://file.tingyou8.vip/pic/5DD07C7E68BF50C.jpg", "vod_remarks": "261集"}]
        return {"class": cls_, "list": lst, "filters": {}}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        lst = []
        try:
            d = self._get("/h5/listening/category", {"type_id": str(tid), "sort": "comprehensive", "page": str(pg)})
            items = d.get("data") or d.get("items") or []
            for it in items:
                lst.append({
                    "vod_id": str(it.get("id", "")),
                    "vod_name": it.get("title", it.get("name", "")),
                    "vod_pic": it.get("cover_url", it.get("pic", "")),
                    "vod_remarks": it.get("count_desc", ""),
                })
        except Exception:
            pass
        if not lst:
            lst = [{"vod_id": tid, "vod_name": f"分类{tid}暂无内容", "vod_pic": "", "vod_remarks": ""}]
        return {"list": lst}

    def detailContent(self, ids):
        vod_id = ids[0] if ids else ""
        info = {}
        try:
            info = self._get(f"/h5/listening/album/{vod_id}")
        except Exception:
            pass
        vod = {
            "vod_id": vod_id,
            "vod_name": info.get("title", vod_id),
            "vod_pic": info.get("cover_url", ""),
            "vod_actor": info.get("teller", ""),
            "vod_content": info.get("synopsis", ""),
            "vod_play_from": "听友FM",
        }
        try:
            d = self._get(f"/h5/listening/chapters/{vod_id}")
            chapters = d.get("chapters") or d.get("data") or []
            eps = []
            for i, ch in enumerate(chapters):
                eps.append(f"{ch.get('index', i+1)}${vod_id}_{ch.get('id', i)}")
            vod["vod_play_url"] = "#".join(eps)
        except Exception:
            vod["vod_play_url"] = "第1集$" + vod_id + "_0"
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        lst = []
        try:
            d = self._post("/h5/listening/search", {"keyword": key, "page": int(pg or 1)})
            items = d.get("results") or d.get("data") or []
            for it in items:
                lst.append({
                    "vod_id": str(it.get("id", "")),
                    "vod_name": it.get("title", it.get("name", "")),
                    "vod_pic": it.get("cover_url", it.get("pic", "")),
                    "vod_remarks": it.get("count_desc", ""),
                })
        except Exception:
            pass
        return {"list": lst}

    def playerContent(self, flag, id, vipFlags=None):
        try:
            parts = id.split("_")
            album_id, chapter_id = parts[0], parts[1]
            d = self._post("/h5/listening/play", {"album_id": album_id, "chapter_idx": int(chapter_id)})
            play_url = d.get("play_url", "")
            if play_url:
                return {"parse": 0, "url": play_url}
        except Exception:
            pass
        return {"parse": 0, "url": "https://tingyou.fm"}

    def destroy(self):
        pass
