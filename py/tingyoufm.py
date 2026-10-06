# -*- coding: utf-8 -*-
"""
听友FM 听书蜘蛛 v2 (tingyoufm.py)
--------------------------------
站点: https://tingyou.fm (2026-10-06 新 H5 协议)
数据源: 听友FM H5 API (多域名自动切换)

接口协议 (2026-10-06 实测):
  filters  GET {api}/h5/listening/filters                    -> 分类ID映射
  分类     GET {api}/h5/listening/category?type_id={id}&sort=comprehensive&page={pg} -> data[]
  榜单     GET {api}/h5/listening/rank?page={pg}             -> items[]
  详情     GET {api}/h5/listening/album/{id}                 -> {title,author,teller,cover_url,count,synopsis}
  章节     GET {api}/h5/listening/chapters/{id}              -> chapters[] {id,index,title,duration}
  搜索     POST {api}/h5/listening/search {"keyword","page"} -> results[]
  播放     POST {api}/h5/listening/play {"album_id","chapter_idx"} -> {play_url} 直链

API 域名池 (自动切换):
  https://api-preview.toulaopao.cc
  https://laopaoaappi.oobyvy.vip
  https://toudnbbaa.toulaopao1.cc

无加密、免登录、直链播放。
"""
import json
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
    API_HOSTS = [
        "https://api-preview.toulaopao.cc",
        "https://laopaoaappi.oobyvy.vip",
        "https://toudnbbaa.toulaopao1.cc",
    ]
    UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
    timeout = 12

    # 分类硬编码 (不依赖网络, 保证首页永远有分类)
    CLASSES = [
        {"type_id": "2", "type_name": "有声小说"},
        {"type_id": "46", "type_name": "玄幻奇幻"},
        {"type_id": "11", "type_name": "武侠小说"},
        {"type_id": "19", "type_name": "言情通俗"},
        {"type_id": "14", "type_name": "恐怖惊悚"},
        {"type_id": "17", "type_name": "官场商战"},
        {"type_id": "15", "type_name": "历史军事"},
        {"type_id": "16", "type_name": "刑侦反腐"},
        {"type_id": "10", "type_name": "有声文学"},
        {"type_id": "36", "type_name": "广播剧"},
        {"type_id": "1", "type_name": "评书"},
    ]

    def __init__(self):
        self._api_idx = 0
        self._last_album_id = None

    def getName(self):
        return "听友FM"

    def init(self, extend=''):
        pass

    # ---------- API host 切换 ----------
    def _api_base(self):
        return self.API_HOSTS[self._api_idx % len(self.API_HOSTS)]

    def _headers(self):
        return {
            "User-Agent": self.UA,
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://tingyou.fm/listening",
            "Origin": "https://tingyou.fm",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
        }

    def _api_get(self, path):
        """GET 请求, 失败自动切换域名"""
        last_err = None
        for i in range(len(self.API_HOSTS)):
            idx = (self._api_idx + i) % len(self.API_HOSTS)
            base = self.API_HOSTS[idx]
            try:
                r = requests.get(base + path, timeout=self.timeout,
                                 headers=self._headers())
                if r.status_code == 200:
                    self._api_idx = idx
                    return r.json()
                last_err = f"HTTP {r.status_code}"
            except Exception as e:
                last_err = str(e)[:60]
        # 全部失败
        return {}

    def _api_post(self, path, obj):
        """POST 请求, 失败自动切换域名"""
        last_err = None
        for i in range(len(self.API_HOSTS)):
            idx = (self._api_idx + i) % len(self.API_HOSTS)
            base = self.API_HOSTS[idx]
            try:
                hdrs = self._headers()
                hdrs["Content-Type"] = "application/json"
                r = requests.post(base + path, json=obj, timeout=self.timeout, headers=hdrs)
                if r.status_code == 200:
                    self._api_idx = idx
                    return r.json()
                last_err = f"HTTP {r.status_code}"
            except Exception as e:
                last_err = str(e)[:60]
        return {}

    # ---------- 数据映射 ----------
    def _map_book(self, item):
        return {
            "vod_id": str(item.get("id") or item.get("album_id") or ""),
            "vod_name": item.get("title") or item.get("name") or "",
            "vod_pic": item.get("cover_url") or item.get("cover") or "",
            "vod_remarks": f"{item.get('count', '')}集" if item.get("count") else "",
            "vod_actor": item.get("teller") or "",
            "vod_director": item.get("author") or "",
        }

    # ---------- Spider 接口 ----------
    def homeContent(self, filter=False):
        # 用排行榜(最新)作为首页内容
        lst = []
        err = ""
        try:
            d = self._api_get("/api/h5/listening/rank?page=1")
            items = d.get("items") or []
            lst = [self._map_book(it) for it in items if it.get("id")]
            if not lst:
                # 兜底: 分类第一页
                d2 = self._api_get("/api/h5/listening/category?sort=comprehensive&page=1")
                arr = d2.get("data") or []
                lst = [self._map_book(it) for it in arr if it.get("id")]
        except Exception as e:
            err = str(e)[:40]
        return {"class": self.CLASSES, "list": lst, "filters": {}}

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend=''):
        lst = []
        try:
            if tid == "2":
                # 有声小说大类: 综合排序
                d = self._api_get(f"/api/h5/listening/category?sort=comprehensive&page={pg}")
            else:
                d = self._api_get(f"/api/h5/listening/category?type_id={tid}&sort=comprehensive&page={pg}")
            items = d.get("data") or []
            lst = [self._map_book(it) for it in items if it.get("id")]
        except Exception:
            pass
        return {"list": lst}

    def detailContent(self, ids):
        vod_id = ids[0] if ids else ""
        self._last_album_id = vod_id
        vod = {"vod_id": vod_id, "vod_name": "", "vod_pic": "", "type_name": "听书",
               "vod_content": "", "vod_play_from": "听友FM", "vod_play_url": ""}
        try:
            d = self._api_get(f"/api/h5/listening/album/{vod_id}")
            if d:
                vod["vod_name"] = d.get("title") or vod["vod_name"]
                vod["vod_pic"] = d.get("cover_url") or vod["vod_pic"]
                vod["vod_content"] = d.get("synopsis") or vod["vod_content"]
                vod["vod_actor"] = d.get("teller") or ""
                vod["vod_director"] = d.get("author") or ""
            # 章节
            c = self._api_get(f"/api/h5/listening/chapters/{vod_id}")
            chs = c.get("chapters") or []
            if chs:
                chs.sort(key=lambda x: int(x.get("index") or 0))
                play_urls = []
                for ch in chs:
                    idx = int(ch.get("index") or 0)
                    name = ch.get("title") or f"第{idx}集"
                    play_urls.append(f"{name}${idx}")
                vod["vod_play_url"] = "#".join(play_urls)
                vod["vod_remarks"] = f"{len(chs)}集"
        except Exception:
            pass
        return {"list": [vod]}

    def searchContent(self, key, quick, pg='1'):
        lst = []
        try:
            d = self._api_post("/api/h5/listening/search", {"keyword": key, "page": int(pg) if pg else 1})
            items = d.get("results") or d.get("list") or []
            lst = [self._map_book(it) for it in items if it.get("id")]
        except Exception:
            pass
        return {"list": lst}

    def playerContent(self, flag, id, vipFlags=None):
        try:
            album_id = getattr(self, "_last_album_id", None)
            if not album_id:
                return {"parse": 0, "url": ""}
            chapter_idx = int(id)
            d = self._api_post("/api/h5/listening/play",
                               {"album_id": album_id, "chapter_idx": chapter_idx})
            url = d.get("play_url") or (d.get("data") or {}).get("play_url") or ""
            if url:
                return {"parse": 0, "url": url, "header": "User-Agent:" + self.UA}
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
