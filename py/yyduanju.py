# -*- coding: utf-8 -*-
# yy短剧[官方] Spider — YY直播官方短剧平台
# 站点: https://yy-playlet.yy.com
# 说明: 接口完全直链, 无加密签名(仅需官方 App UA + 设备参数)
#   分类:  GET /homepage/playlet-list/{type}/{page}/18 → data.result[]  (type=1男频/2女频/4都市/5虐恋/7古装/10战神)
#   搜索:  GET https://searchservice.yy.com/search?keyword=xx&typ=playlet → response.playlet.docs[]
#   详情:  GET /playlet/video-list?pid=xx → data (第1集 + 元信息)
#   全集:  GET /playlet/next-video-list?pid=xx&seq=游标 → data.videos[] (每页30集, seq游标分页)
#   播放:  data.videos[].videoUrl = mp4直链 (免费集), 付费集用 videoPreviewUrl

import ast
import html as html_module
import json
import random
import re
import time
import urllib.parse
from base.spider import Spider as BaseSpider

# 用 urllib 发请求(无外部依赖, 更适合海阔py引擎)
try:
    import urllib.request
    import urllib.error
except ImportError:
    urllib.request = None

YY_UA = "Platform/Android10 APP/yymand8.60.1 Model/MI 8 Browser/None HostVersion/8.60.1 HostName/yy HostId/1"
YY_VERSION = "8.60.1"
YY_CHANNEL = "1505"
YY_APPID = "yym"
API_HOST = "https://yy-playlet.yy.com"
SEARCH_HOST = "https://searchservice.yy.com"


class Spider(BaseSpider):
    def __init__(self):
        super().__init__()
        self._hdid = self._rand_hex(32)
        self._device_score = "0.517"
        self._last_pid = ""

    # ---------- 基础工具 ----------
    @staticmethod
    def _rand_hex(n):
        return "".join(random.choice("0123456789abcdef") for _ in range(n))

    @staticmethod
    def _clean(s):
        """清理HTML/空白"""
        s = re.sub(r"<[^>]+>", "", str(s or ""))
        return re.sub(r"\s+", " ", s).strip()

    def _base_params(self):
        return {
            "deviceScore": self._device_score,
            "netType": "2",
            "deviceDay": "1",
            "hdid": self._hdid,
            "supportSwan": "false",
            "channel": YY_CHANNEL,
            "launch": "0",
            "yyVersion": YY_VERSION,
            "uid": "0",
            "deviceTotalLevel": "2",
            "osVersion": "10",
            "appid": YY_APPID,
            "deviceLevel": "2",
            "sdkVersion": YY_VERSION,
            "ispType": "4",
        }

    def _build_url(self, base, params):
        p = self._base_params()
        p.update(params or {})
        sep = "&" if "?" in base else "?"
        return base + sep + urllib.parse.urlencode(p)

    def _get_json(self, base, params=None, timeout=15):
        """发请求并解析JSON (失败重试1次)"""
        url = self._build_url(base, params or {})
        for _ in range(2):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": YY_UA})
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    raw = r.read().decode("utf-8", errors="ignore")
                if raw.strip().startswith("{"):
                    return json.loads(raw)
                return None
            except Exception:
                time.sleep(1.0)
        return None

    # ---------- 通用卡片 ----------
    def _build_vod(self, item):
        pid = str(item.get("pid") or item.get("id") or "")
        name = str(item.get("name") or item.get("title") or "")
        pic = str(item.get("snapshotUrl") or item.get("cover") or "")
        intro = self._clean(item.get("intro") or item.get("description") or "")
        watch = str(item.get("watchCount") or item.get("totalWatchCount") or "0")
        cats_parts = []
        for c in (item.get("categories") or []):
            n = str(c.get("name") or "").strip()
            if n and n not in cats_parts:
                cats_parts.append(n)
        remarks = "🔥" + watch
        if cats_parts:
            remarks += " · " + " ".join(cats_parts)
        return {
            "vod_id": pid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": remarks,
            "vod_content": intro,
        }

    # ---------- 首页 / 分类 ----------
    def init(self, extend=""):
        return self.homeContent(extend)

    def homeContent(self, filter=False):
        # 首页直接给分类 + 男频推荐
        cat = self.categoryContent("1", "1", False)
        return {"class": cat.get("class", []), "list": cat.get("list", [])}

    def homeVodContent(self, page=1, filter=False):
        return self.categoryContent("1", str(page), False)

    def categoryContent(self, tid, pg, filter=False, extend=""):
        page = str(pg or 1)
        url = "%s/homepage/playlet-list/%s/%s/18" % (API_HOST, tid, page)
        d = self._get_json(url, {})
        classes = [
            {"type_id": "1", "type_name": "男频"},
            {"type_id": "2", "type_name": "女频"},
            {"type_id": "4", "type_name": "都市"},
            {"type_id": "5", "type_name": "虐恋"},
            {"type_id": "7", "type_name": "古装"},
            {"type_id": "10", "type_name": "战神"},
        ]
        if not d:
            return {"class": classes, "list": [], "page": int(page), "pagecount": 1}
        rows = d.get("result") or []
        total_page = d.get("totalPage") or 1
        pagecount = max(int(total_page), 1) if total_page else 1
        vods = [self._build_vod(x) for x in rows if x.get("pid")]
        return {"class": classes, "list": vods, "page": int(page), "pagecount": pagecount}

    # ---------- 详情 ----------
    def detailContent(self, ids):
        pid = str(ids[0]).split("$")[0]
        self._last_pid = pid
        # 元信息(第1集)
        meta = {}
        d = self._get_json("%s/playlet/video-list" % API_HOST,
                           {"pid": pid, "direct": "1", "pageSize": "1", "recommend": "false", "seq": "1"})
        if d and d.get("data"):
            data = d["data"]
            meta = {
                "name": str(data.get("name") or ""),
                "pic": str(data.get("snapshotUrl") or ""),
                "intro": self._clean(data.get("intro") or data.get("description") or ""),
                "watch": str(data.get("watchCount") or "0"),
                "totalNum": data.get("totalNum") or 0,
            }
        # 拉全集
        eps = self._fetch_all_episodes(pid)
        vod = {
            "vod_id": pid,
            "vod_name": meta.get("name") or "短剧",
            "vod_pic": meta.get("pic") or "",
            "vod_remarks": "🔥{} · 共{}集".format(meta.get("watch", "0"), len(eps)) if eps else ("🔥" + meta.get("watch", "0")),
            "vod_content": meta.get("intro") or "",
            "vod_play_from": "YY短剧",
            "vod_play_url": "$$".join("%s#%s" % (i, u) for i, u in eps),
        }
        return [vod]

    def _fetch_all_episodes(self, pid):
        """循环拉全集: 每页30集, seq游标推进"""
        eps = []          # [(seq_str, url)]
        seen = set()      # 去重 seq
        seq = 1
        guard = 0
        while guard < 20:
            guard += 1
            d = self._get_json(API_HOST + "/playlet/next-video-list",
                               {"pid": pid, "pageSize": "30", "direct": "1", "seq": str(seq)},
                               timeout=20)
            if not d or not d.get("data"):
                break
            data = d["data"]
            vs = data.get("videos") or []
            if not vs:
                break
            added = False
            max_seq = 0
            for v in vs:
                s = v.get("seq")
                if s is None:
                    continue
                s = int(s)
                max_seq = max(max_seq, s)
                if s in seen:
                    continue
                url = str(v.get("videoUrl") or "").strip()
                if not url:
                    continue
                seen.add(s)
                eps.append((str(s), url))
                added = True
            if not data.get("hasNextPage") or not added:
                break
            # 游标推进到下一页起点
            seq = max_seq + 1
            time.sleep(0.3)
        # 按集数排序
        def _k(e):
            try:
                return int(e[0])
            except Exception:
                return 0
        eps.sort(key=_k)
        return eps

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        page = str(pg or 1)
        # keyword 放 query 参数
        url = self._build_url(SEARCH_HOST + "/search",
                              {"q": key, "typ": "playlet", "v": "6", "app": "4",
                               "correct": "0", "page": page})
        try:
            req = urllib.request.Request(url, headers={"User-Agent": YY_UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read().decode("utf-8", errors="ignore")
            resp = json.loads(raw)
        except Exception:
            return []
        playlet = (resp.get("response") or {}).get("playlet") or {}
        docs = playlet.get("docs") or []
        return [self._build_vod(x) for x in docs if x.get("pid")]

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags=None):
        """id 是 播放地址(mp4直链), 直接返回"""
        url = str(id or "")
        return {"parse": 0, "jx": 0, "url": url, "header": {"User-Agent": YY_UA, "Referer": API_HOST + "/"}}

    def isVideoFormat(self, url):
        return bool(re.search(r"\.(?:mp4|m3u8|flv|mkv|ts|webm)(?:$|\?)", str(url or ""), re.I))

    def manualVideoCheck(self):
        return False

    def getName(self):
        return "yy短剧"

    def getCategory(self):
        return [{"type_id": "1", "type_name": "男频"},
                {"type_id": "2", "type_name": "女频"},
                {"type_id": "4", "type_name": "都市"},
                {"type_id": "5", "type_name": "虐恋"},
                {"type_id": "7", "type_name": "古装"},
                {"type_id": "10", "type_name": "战神"}]