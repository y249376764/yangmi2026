# -*- coding: utf-8 -*-
# YouTube 蜘蛛 (innertube API) - 适配默影视 WebHomeTV
# 基于 YouTube.html 网页源逻辑移植
# 代理: extend 传 proxy, 默认 socks5://127.0.0.1:7897 (本机 Clash)
# 取流: streamingData.formats / hlsManifestUrl → 直链

import re
import json
import requests
from urllib.parse import quote, urljoin

from base.spider import Spider


class Spider(Spider):
    def getName(self):
        return "YouTube"

    def init(self, extend=""):
        self.YT = "https://www.youtube.com"
        self.API = "https://www.youtube.com/youtubei/v1"
        self.KEY_FALLBACK = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
        self.CVER = "2.20260801.00.00"
        self.DEF_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        self.hl = "zh-CN"
        self.gl = "US"

        # 代理: extend 可传 proxy=xxx
        self.proxy = None
        if extend:
            m = re.search(r"proxy=([^\s,]+)", extend)
            if m:
                self.proxy = m.group(1)
        if not self.proxy:
            self.proxy = "socks5://127.0.0.1:7897"

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.DEF_UA,
            "Accept-Language": self.hl,
            "Origin": self.YT,
            "Referer": self.YT + "/",
        })
        if self.proxy:
            self.session.proxies = {"http": self.proxy, "https": self.proxy}

        self.ytcfg = {"key": "", "visitor": "", "ts": 0}

        # 分类: 对齐网页源 tabs
        self.class_map = {
            "推荐": "rec",
            "臻彩4K": "4k",
            "直播": "live",
            "音乐MV": "music",
            "电影": "movies",
            "连续剧": "shows",
            "综艺": "ent",
        }

    # ---------- 抓 ytcfg (key + visitorData) ----------
    def _load_ytcfg(self):
        if self.ytcfg["key"] and (self.ytcfg["ts"] and (self.ytcfg["ts"] > 0)):
            # 缓存 6 小时内有效
            import time
            if time.time() - self.ytcfg["ts"] < 21600:
                return True
        # 抓 sw.js (几十KB, 带 key + visitorData)
        for url in [
            self.YT + "/sw.js",
            self.YT + "/embed/",
            self.YT,
        ]:
            try:
                r = self.session.get(url, timeout=12)
                if r.status_code != 200:
                    continue
                text = r.text
                # ytcfg 提取
                key = ""
                m = re.search(r'INNERTUBE_API_KEY["\']?\s*[:=]\s*["\']([A-Za-z0-9_-]+)["\']', text)
                if m:
                    key = m.group(1)
                if not key:
                    m = re.search(r'"INNERTUBE_API_KEY":"([A-Za-z0-9_-]+)"', text)
                    if m:
                        key = m.group(1)
                visitor = ""
                m2 = re.search(r'visitorData["\']?\s*[:=]\s*["\']([A-Za-z0-9%+\-_=]+)["\']', text)
                if m2:
                    visitor = m2.group(1)
                if key:
                    self.ytcfg["key"] = key
                    self.ytcfg["visitor"] = visitor
                    self.ytcfg["ts"] = __import__("time").time()
                    return True
            except Exception:
                continue
        # fallback
        if not self.ytcfg["key"]:
            self.ytcfg["key"] = self.KEY_FALLBACK
        return bool(self.ytcfg["key"])

    # ---------- innertube 请求 ----------
    def _innertube(self, endpoint, body, timeout=15):
        self._load_ytcfg()
        url = f"{self.API}/{endpoint}?key={self.ytcfg['key']}&prettyPrint=false"
        context = {
            "client": {
                "clientName": "WEB",
                "clientVersion": self.CVER,
                "hl": self.hl,
                "gl": self.gl,
                "userAgent": self.DEF_UA,
                "visitorData": self.ytcfg.get("visitor") or "",
            }
        }
        payload = dict(body)
        payload["context"] = context
        try:
            r = self.session.post(url, json=payload, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            return None
        except Exception:
            return None

    # ---------- 列表解析 (browse/search 通用) ----------
    def _parse_videos(self, j):
        """从 innertube 响应提取视频列表 (全树递归找 videoRenderer)"""
        videos = []
        seen = set()

        def walk(node):
            if isinstance(node, dict):
                # 直接命中 video 渲染器
                for key in ("videoRenderer", "gridVideoRenderer", "compactVideoRenderer"):
                    vr = node.get(key)
                    if vr and isinstance(vr, dict):
                        vid = vr.get("videoId", "")
                        if not vid:
                            return
                        if vid in seen:
                            return
                        seen.add(vid)
                        # 标题
                        title = ""
                        tt = vr.get("title", {})
                        if isinstance(tt, dict):
                            if tt.get("runs"):
                                title = "".join(r.get("text", "") for r in tt["runs"])
                            else:
                                title = tt.get("simpleText", "")
                        # 封面
                        pic = ""
                        th = vr.get("thumbnail", {}).get("thumbnails", [])
                        if th:
                            pic = th[-1].get("url", "")
                            if pic.startswith("//"):
                                pic = "https:" + pic
                        # 时长
                        length = ""
                        lt = vr.get("lengthText", {})
                        if isinstance(lt, dict):
                            length = lt.get("simpleText", "")
                        # 观看数
                        views = ""
                        vt = vr.get("viewCountText", {})
                        if isinstance(vt, dict):
                            views = vt.get("simpleText", "")
                        remarks = (length + " " + views).strip()
                        # 直播标记
                        badges = vr.get("badges") or []
                        for b in badges:
                            if isinstance(b, dict):
                                bl = b.get("liveBroadcastBadgeRenderer") or b.get("badgeRenderer")
                                if bl:
                                    t = bl.get("label") or bl.get("text") or {}
                                    if isinstance(t, dict):
                                        t = t.get("simpleText", "")
                                    if t:
                                        remarks = (t + " " + remarks).strip()
                        videos.append({
                            "vod_id": vid,
                            "vod_name": title,
                            "vod_pic": pic,
                            "vod_remarks": remarks,
                        })
                        return
                # 递归子节点
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(j)
        return videos

    # ---------- 首页 ----------
    def homeContent(self, filter=False):
        classes = [{"type_id": k, "type_name": v} for k, v in self.class_map.items()]
        # 推荐
        vod_list = []
        try:
            j = self._innertube("browse", {"browseId": "FEwhat_to_watch"})
            if j:
                vod_list = self._parse_videos(j)
        except Exception:
            pass
        return {"class": classes, "list": vod_list[:24], "filters": {}}

    def homeVideoContent(self):
        try:
            j = self._innertube("browse", {"browseId": "FEwhat_to_watch"})
            if j:
                return {"list": self._parse_videos(j)}
        except Exception:
            pass
        return {"list": []}

    # ---------- 分类 ----------
    def categoryContent(self, tid, pg, filter=False, extend=None):
        try:
            pg = int(pg) if str(pg).isdigit() else 1
            if pg > 1:
                return {"list": [], "page": pg, "pagecount": pg, "limit": 24, "total": 0}

            # 分类 → 搜索词
            search_map = {
                "4k": "4K 电影",
                "live": "直播",
                "music": "音乐 MV",
                "movies": "电影",
                "shows": "连续剧",
                "ent": "综艺",
            }
            kw = search_map.get(tid)
            if kw:
                j = self._innertube("search", {"query": kw})
            else:
                j = self._innertube("browse", {"browseId": "FEwhat_to_watch"})
            videos = self._parse_videos(j) if j else []
            return {"list": videos, "page": pg, "pagecount": 1, "limit": 24, "total": len(videos)}
        except Exception:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}

    # ---------- 详情 ----------
    def detailContent(self, ids):
        try:
            vid = ids[0]
            if "/" in vid:
                vid = vid.split("/")[-1].replace("watch?v=", "")
            url = f"https://www.youtube.com/watch?v={vid}"
            vod = {
                "vod_id": vid,
                "vod_name": "YouTube " + vid[:8],
                "vod_pic": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                "vod_play_from": "YouTube",
                "vod_play_url": f"播放${vid}",
                "vod_content": "",
            }
            return {"list": [vod]}
        except Exception:
            return {"list": []}

    # ---------- 播放 (innertube player → 直链) ----------
    def playerContent(self, flag, id, vipFlags=None):
        result = {"parse": 0, "playUrl": "", "url": "", "header": {}}
        try:
            vid = id
            if ":" in vid:
                vid = vid.split(":")[-1]
            if "/" in vid:
                vid = vid.split("/")[-1].replace("watch?v=", "")
            if "播放$" in vid:
                vid = vid.split("播放$")[-1]

            # player 接口
            body = {
                "videoId": vid,
                "playbackContext": {"contentPlaybackContext": {"html5Preference": "HTML5_PREF_WANTS"}},
                "contentCheckOk": True,
                "racyCheckOk": True,
            }
            j = self._innertube("player", body)
            if not j:
                return result

            sd = j.get("streamingData") or {}
            # 1) HLS manifest
            hls = sd.get("hlsManifestUrl", "")
            if hls:
                result["url"] = hls
                result["header"] = {
                    "User-Agent": self.DEF_UA,
                    "Referer": self.YT + "/",
                }
                return result
            # 2) formats: 优先 mp4 / 高码率
            fmts = sd.get("formats") or []
            afmts = sd.get("adaptiveFormats") or []
            best = None
            for f in fmts + afmts:
                u = f.get("url", "")
                if not u and f.get("signatureCipher"):
                    continue
                mime = f.get("mimeType", "")
                if "video/mp4" in mime:
                    if best is None or (f.get("qualityLabel") or "") > (best.get("qualityLabel") or ""):
                        best = f
            if best:
                result["url"] = best.get("url", "")
                result["header"] = {
                    "User-Agent": self.DEF_UA,
                    "Referer": self.YT + "/",
                }
                return result
            # 3) 任意 format
            for f in fmts + afmts:
                if f.get("url"):
                    result["url"] = f["url"]
                    result["header"] = {
                        "User-Agent": self.DEF_UA,
                        "Referer": self.YT + "/",
                    }
                    return result
            return result
        except Exception:
            return result

    # ---------- 搜索 ----------
    def searchContent(self, key, quick):
        try:
            j = self._innertube("search", {"query": str(key)})
            videos = self._parse_videos(j) if j else []
            return {"list": videos}
        except Exception:
            return {"list": []}

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        if self.session:
            self.session.close()
