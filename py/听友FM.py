# -*- coding: utf-8 -*-
"""听友FM 听书蜘蛛 v4 (2026-10-11 重写)
站点: https://www.tingyou.fm
协议: 官方 listening-api 明文 JSON（直连，不再用第三方代理池）
接口: rank / search / album / chapters / play
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
    API = "https://www.tingyou.fm/listening-api"
    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    HEADERS = {
        "User-Agent": UA,
        "Referer": "https://www.tingyou.fm/",
        "Origin": "https://www.tingyou.fm",
    }
    TIMEOUT = 15
    # 分类：与海阔规则 v25 一致（latest/hot/recommend/serial/storytelling）
    SECTIONS = {
        "最新": "latest",
        "最热": "hot",
        "推荐": "recommend",
        "连载": "serial",
        "评书": "storytelling",
    }

    def init(self, extend=''):
        pass

    def _get(self, path, params=None):
        url = self.API + path
        try:
            r = requests.get(url, params=params, headers=self.HEADERS, timeout=self.TIMEOUT)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {}

    def _post_form(self, path, data):
        url = self.API + path
        try:
            r = requests.post(url, data=data, headers={**self.HEADERS, "Content-Type": "application/x-www-form-urlencoded"}, timeout=self.TIMEOUT)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {}

    def _post_json(self, path, data):
        url = self.API + path
        try:
            r = requests.post(url, json=data, headers={**self.HEADERS, "Content-Type": "application/json"}, timeout=self.TIMEOUT)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {}

    def homeContent(self, filter=False):
        classes = [{"type_id": k, "type_name": k} for k in self.SECTIONS.keys()]
        lst = []
        try:
            d = self._get("/rank", {"section": "latest", "page": 1})
            items = d.get("items") or d.get("data") or []
            for it in items[:20]:
                lst.append({
                    "vod_id": str(it.get("id", "")),
                    "vod_name": it.get("title", it.get("name", "")),
                    "vod_pic": it.get("cover_url", it.get("pic", "")),
                    "vod_remarks": str(it.get("count", "")) + "集" if it.get("count") else "",
                })
        except Exception:
            pass
        return {"class": classes, "list": lst, "filters": {}}

    def homeVideoContent(self):
        d = self._get("/rank", {"section": "latest", "page": 1})
        items = d.get("items") or d.get("data") or []
        lst = []
        for it in items[:24]:
            lst.append({
                "vod_id": str(it.get("id", "")),
                "vod_name": it.get("title", it.get("name", "")),
                "vod_pic": it.get("cover_url", it.get("pic", "")),
                "vod_remarks": str(it.get("count", "")) + "集" if it.get("count") else "",
            })
        return {"list": lst}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        try:
            pg = int(pg) if str(pg).isdigit() else 1
            section = self.SECTIONS.get(str(tid), "latest")
            d = self._get("/rank", {"section": section, "page": pg})
            items = d.get("items") or d.get("data") or []
            lst = []
            for it in items:
                lst.append({
                    "vod_id": str(it.get("id", "")),
                    "vod_name": it.get("title", it.get("name", "")),
                    "vod_pic": it.get("cover_url", it.get("pic", "")),
                    "vod_remarks": str(it.get("count", "")) + "集" if it.get("count") else "",
                })
            has_more = d.get("has_more", False)
            return {
                "list": lst,
                "page": pg,
                "pagecount": pg + 1 if has_more else pg,
                "limit": 20,
                "total": len(items),
            }
        except Exception as e:
            print(f"[{self.NAME}] categoryContent 异常: {e}")
            return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        try:
            vod_id = str(ids[0])
            if not vod_id.isdigit():
                m = re.search(r"(\d+)", vod_id)
                if m:
                    vod_id = m.group(1)
            d = self._get("/album/" + vod_id)
            if not d or not d.get("title"):
                return {"list": []}
            # 章节
            chapters = []
            try:
                c = self._get("/chapters/" + vod_id)
                chapters = c.get("chapters", [])
            except Exception:
                pass
            ep_list = []
            for ch in chapters:
                idx = ch.get("index", 0)
                if not idx:
                    idx = len(ep_list) + 1
                title = ch.get("title", f"第{idx}集")
                ep_list.append(f"{title}${vod_id}_{idx}")
            vod = {
                "vod_id": vod_id,
                "vod_name": d.get("title", ""),
                "vod_pic": d.get("cover_url", ""),
                "type_name": d.get("cat", ""),
                "vod_actor": d.get("teller", d.get("author", "")),
                "vod_director": d.get("author", ""),
                "vod_content": d.get("synopsis", ""),
                "vod_play_from": "官方",
                "vod_play_url": "#".join(ep_list) if ep_list else "",
            }
            return {"list": [vod]}
        except Exception as e:
            print(f"[{self.NAME}] detailContent 异常: {e}")
            return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        try:
            result = {"parse": 0, "playUrl": "", "url": "", "header": {}}
            if not id or id == "#":
                return result
            # id 格式: <album_id>_<chapter_idx>
            parts = str(id).split("_")
            if len(parts) < 2:
                return result
            album_id = parts[0]
            chapter_idx = parts[1]
            d = self._post_form("/play", {"album_id": album_id, "chapter_idx": chapter_idx})
            url = d.get("play_url", "")
            if url:
                result["url"] = url
                result["header"] = {
                    "Referer": "https://www.tingyou.fm/",
                    "User-Agent": self.UA,
                }
            return result
        except Exception as e:
            print(f"[{self.NAME}] playerContent 异常: {e}")
            return {"parse": 0, "playUrl": "", "url": "", "header": {}}

    def searchContent(self, key, quick, pg='1'):
        try:
            d = self._post_json("/search", {"keyword": str(key), "page": int(pg or 1)})
            items = d.get("results") or d.get("items") or []
            lst = []
            for it in items:
                lst.append({
                    "vod_id": str(it.get("id", "")),
                    "vod_name": it.get("title", it.get("name", "")),
                    "vod_pic": it.get("cover_url", it.get("pic", "")),
                    "vod_remarks": str(it.get("count", "")) + "集" if it.get("count") else "",
                })
            return {"list": lst}
        except Exception as e:
            print(f"[{self.NAME}] searchContent 异常: {e}")
            return {"list": []}

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass
