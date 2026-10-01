# -*- coding: utf-8 -*-
"""
喜马拉雅 有声小说/听书 蜘蛛版 (ximalaya.py)
--------------------------------------------
接口全部免登录, 2026-10-01 实测可用:

  分类分组        GET https://www.ximalaya.com/revision/metadata/v2/group/all
  分组专辑列表    GET https://www.ximalaya.com/revision/metadata/v2/channel/albums?groupId={id}&pageNum={p}&pageSize=20&sort=2
  首页推荐        GET https://www.ximalaya.com/revision/explore/v2/getRecommend?useCache=true&clientType=1
  专辑搜索        GET https://www.ximalaya.com/revision/search/seo?core=album&kw={词}&page={p}&rows=30&device=iPhone&condition=relation
  声音搜索        GET https://www.ximalaya.com/revision/search/seo?core=track&kw={词}&page={p}&rows=15&device=iPhone&condition=relation
  专辑详情        GET https://www.ximalaya.com/revision/album/v1/simple?albumId={id}
  专辑声音列表    GET http://mobwsa.ximalaya.com/mobile/playlist/album/page?albumId={id}&pageId={p}   (Android UA, 每页20, maxPageId翻页)
  声音直链        GET https://mobile.ximalaya.com/v1/track/baseInfo?device=iPhone&trackId={id}       (Android UA, 返回playPathAacv224/playUrl64, 302到CDN m4a)

说明:
  * 免费专辑的 playlist 里 playUrl64 直接是直链; 付费/VIP 声音 playUrl64 为空,
    播放时用 baseInfo 接口取 playPathAacv224 (redirect 接口会 302 到带签名 CDN 直链)。
  * 声音直链是 .m4a, TVBox 音频播放器可直接播。
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
    host = "https://www.ximalaya.com"
    # 移动端接口用 Android App UA
    UA_ANDROID = "ting_6.3.60(sdk,Android16)"
    UA_PC = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    timeout = 12

    # 首页分类: 取喜马拉雅"分组"前 N 个作为分类(小说/评书/相声/儿童/历史...)
    HOME_CLASS_GROUPS = [
        (7, "小说"), (10, "评书"), (9, "相声小品"), (11, "儿童"),
        (19, "音乐"), (16, "历史"), (14, "悬疑"), (17, "人文"),
    ]

    # ------------------------------------------------------------
    # 基础请求
    # ------------------------------------------------------------
    def _get(self, url, android=False, referer=None):
        headers = {"User-Agent": self.UA_ANDROID if android else self.UA_PC}
        if referer:
            headers["Referer"] = referer
        try:
            r = requests.get(url, headers=headers, timeout=self.timeout)
            if r.status_code != 200:
                return None
            return r
        except Exception:
            return None

    def _get_json(self, url, android=False, referer=None):
        r = self._get(url, android=android, referer=referer)
        if r is None:
            return None
        try:
            return r.json()
        except Exception:
            return None

    def _fix_pic(self, u):
        """封面补全"""
        if not u:
            return ""
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("http://imagev2.xmcdn.com") or u.startswith("http://fdfs.xmcdn.com"):
            return u.replace("http://", "https://")
        if u.startswith("/"):
            return "https://imagev2.xmcdn.com" + u
        return u

    def _album_to_vod(self, a):
        """专辑 -> vod 条目"""
        album_id = a.get("albumId") or a.get("id")
        title = a.get("albumTitle") or a.get("title") or ""
        pic = self._fix_pic(a.get("albumCoverPath") or a.get("coverPath") or "")
        nick = a.get("albumUserNickName") or a.get("nickname") or ""
        play_count = a.get("albumPlayCount") or a.get("playCount") or 0
        track_count = a.get("albumTrackCount") or 0
        remark = ""
        if track_count:
            remark = f"{track_count}集"
        if play_count:
            remark = (remark + " " if remark else "") + f"{self._fmt_num(play_count)}播放"
        return {
            "vod_id": f"album_{album_id}",
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": remark,
            "vod_actor": nick,
            "vod_content": (a.get("intro") or "").strip(),
        }

    def _track_to_vod(self, t, album_title=""):
        """声音 -> vod 条目(用于声音搜索)"""
        track_id = t.get("id")
        title = t.get("title") or ""
        pic = self._fix_pic(t.get("cover_url") or t.get("coverPath") or "")
        nick = t.get("nickname") or t.get("albumUserNickName") or ""
        dur = t.get("duration") or 0
        remark = f"{int(dur)}秒" if dur else ""
        return {
            "vod_id": f"track_{track_id}",
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": remark,
            "vod_actor": nick,
            "vod_content": f"声音ID:{track_id}",
        }

    @staticmethod
    def _fmt_num(n):
        try:
            n = int(n or 0)
        except Exception:
            return str(n)
        if n >= 100000000:
            return f"{n / 100000000:.1f}亿"
        if n >= 10000:
            return f"{n / 10000:.1f}万"
        return str(n)

    # ------------------------------------------------------------
    # 基本方法
    # ------------------------------------------------------------
    def init(self, extend=""):
        pass

    def getName(self):
        return "喜马拉雅[py]"

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    # ------------------------------------------------------------
    # 首页
    # ------------------------------------------------------------
    def homeContent(self, filter):
        classes = []
        for gid, name in self.HOME_CLASS_GROUPS:
            classes.append({"type_id": str(gid), "type_name": name})
        # 首页内容: 推荐接口的专辑
        vods = []
        d = self._get_json(self.host + "/revision/explore/v2/getRecommend?useCache=true&clientType=1", referer=self.host + "/")
        if d and d.get("ret") == 200:
            cards = (d.get("data") or {}).get("cards") or []
            for card in cards:
                for a in (card.get("albumList") or []):
                    vods.append(self._album_to_vod(a))
        return {"class": classes, "list": vods, "filters": {}}

    def homeVideoContent(self):
        vods = []
        d = self._get_json(self.host + "/revision/explore/v2/getRecommend?useCache=true&clientType=1", referer=self.host + "/")
        if d and d.get("ret") == 200:
            cards = (d.get("data") or {}).get("cards") or []
            for card in cards:
                for a in (card.get("albumList") or []):
                    vods.append(self._album_to_vod(a))
        return {"list": vods}

    # ------------------------------------------------------------
    # 分类内容: groupId 分组专辑列表
    # ------------------------------------------------------------
    def categoryContent(self, tid, pg, filter=False, extend=""):
        page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
        url = (f"{self.host}/revision/metadata/v2/channel/albums"
               f"?groupId={tid}&pageNum={page}&pageSize=20&sort=2")
        d = self._get_json(url, referer=f"{self.host}/category/")
        vods = []
        total = 0
        if d and d.get("ret") == 200:
            data = d.get("data") or {}
            total = data.get("total") or 0
            for a in (data.get("albums") or []):
                vods.append(self._album_to_vod(a))
        pagecount = max(1, (total + 19) // 20) if total else 1
        return {"list": vods, "page": page, "pagecount": pagecount, "limit": 20, "total": total}

    # ------------------------------------------------------------
    # 搜索: 专辑 + 声音
    # ------------------------------------------------------------
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
        vods = []
        # 专辑搜索
        url = (f"{self.host}/revision/search/seo?core=album&kw={requests.utils.quote(key)}"
               f"&page={page}&rows=30&spellchecker=true&condition=relation&device=iPhone&isGrayFilter=true")
        d = self._get_json(url, referer=f"{self.host}/search/{requests.utils.quote(key)}")
        if d and d.get("ret") == 200:
            docs = (((d.get("data") or {}).get("album") or {}).get("docs")) or []
            for a in docs:
                vods.append(self._album_to_vod(a))
        # 声音搜索
        url2 = (f"{self.host}/revision/search/seo?core=track&kw={requests.utils.quote(key)}"
                f"&page={page}&rows=15&spellchecker=true&condition=relation&device=iPhone")
        d2 = self._get_json(url2, referer=f"{self.host}/search/{requests.utils.quote(key)}")
        if d2 and d2.get("ret") == 200:
            docs = (((d2.get("data") or {}).get("track") or {}).get("docs")) or []
            for t in docs:
                vods.append(self._track_to_vod(t))
        return {"list": vods, "page": page, "pagecount": 1, "limit": 50, "total": len(vods)}

    # ------------------------------------------------------------
    # 详情: 专辑声音列表 / 单声音
    # ------------------------------------------------------------
    def detailContent(self, ids):
        vid = str(ids[0]) if isinstance(ids, (list, tuple)) else str(ids)
        if vid.startswith("track_"):
            return self._detail_track(vid[6:])
        if vid.startswith("album_"):
            return self._detail_album(vid[6:])
        # 裸数字按专辑处理
        return self._detail_album(vid)

    def _detail_track(self, track_id):
        """单声音详情 -> 直接一集可播"""
        vod = {
            "vod_id": f"track_{track_id}",
            "vod_name": f"声音{track_id}",
            "vod_pic": "",
            "vod_play_from": "直链",
            "vod_play_url": f"第1集${track_id}",
        }
        return {"list": [vod]}

    def _detail_album(self, album_id):
        """专辑详情 + 声音列表(playlist 20/页, 全部拉取)"""
        vod = {"vod_id": f"album_{album_id}", "vod_name": f"专辑{album_id}", "vod_pic": ""}
        # 专辑信息
        d = self._get_json(self.host + f"/revision/album/v1/simple?albumId={album_id}", referer=self.host + f"/album/{album_id}")
        if d and d.get("ret") == 200:
            main = (d.get("data") or {}).get("albumPageMainInfo") or {}
            vod["vod_name"] = main.get("albumTitle") or vod["vod_name"]
            vod["vod_pic"] = self._fix_pic(main.get("cover"))
            vod["vod_actor"] = main.get("anchorName") or ""
            intro = main.get("shortIntro") or main.get("albumIntro") or ""
            if intro:
                vod["vod_content"] = intro.strip()
            vod["vod_remarks"] = f"{main.get('albumTrackCount') or 0}集"
        # 声音列表: playlist pageId 从0开始, 每页20; 最多拉100页=2000集(实际由maxPageId决定)
        episodes = []
        for page in range(0, 100):
            url = (f"http://mobwsa.ximalaya.com/mobile/playlist/album/page"
                   f"?albumId={album_id}&pageId={page}")
            r = self._get(url, android=True, referer="http://mobwsa.ximalaya.com/")
            if r is None:
                break
            try:
                pj = r.json()
            except Exception:
                break
            lst = pj.get("list") or []
            if not lst:
                break
            for t in lst:
                track_id = t.get("trackId")
                if not track_id:
                    continue
                # 免费专辑 playlist 里 playUrl64 直接可用; 否则播放时走 baseInfo
                episodes.append(f"{t.get('title') or track_id}${track_id}")
            max_page = pj.get("maxPageId") or 0
            if page + 1 >= max_page:
                break
        if episodes:
            vod["vod_play_from"] = "喜马拉雅"
            vod["vod_play_url"] = "#".join(episodes)
        return {"list": [vod]}

    # ------------------------------------------------------------
    # 播放: baseInfo 取直链
    # ------------------------------------------------------------
    def playerContent(self, flag, id, vipFlags=None):
        track_id = str(id)
        # 尝试1: baseInfo 接口拿直链
        url = (f"https://mobile.ximalaya.com/v1/track/baseInfo"
               f"?device=iPhone&trackId={track_id}")
        d = self._get_json(url, android=True, referer="https://m.ximalaya.com/")
        if d:
            # 优先高音质(/1结尾): playUrl64/downloadUrl/playPathAacv164, 其次 playPathAacv224(/0)
            play_url = (d.get("playUrl64")
                        or d.get("downloadUrl")
                        or d.get("downloadAacUrl")
                        or d.get("playPathAacv164")
                        or d.get("playPathAacv224")
                        or "")
            if play_url:
                return {"parse": 0, "url": play_url, "header": {"User-Agent": self.UA_ANDROID}}
        # 尝试2: tracks/{id}.json 老接口(免费声音常有效)
        r = self._get(f"https://m.ximalaya.com/tracks/{track_id}.json", android=True, referer="https://m.ximalaya.com/")
        if r is not None:
            try:
                tj = r.json()
                p64 = tj.get("play_path_64") or tj.get("play_path_32") or tj.get("play_path") or ""
                if p64:
                    return {"parse": 0, "url": p64, "header": {"User-Agent": self.UA_ANDROID}}
            except Exception:
                pass
        return {"parse": 0, "url": ""}

    def localProxy(self, param=""):
        return {}

    def destroy(self):
        pass
