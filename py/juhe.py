#coding=utf-8
#!/usr/bin/python
# 自研聚合蜘蛛: 并发聚合多个 MacCMS 采集站, 慢源自动跳过, 线路名=站名
import sys
import json
import re
import threading
import urllib.request
import urllib.parse

sys.path.append('..')
from base.spider import Spider

# ============ 聚合源配置(站名 -> api) ============
SOURCES = [
    ("猫眼", "https://api.maoyanapi.top/api.php/provide/vod/"),
    ("牛牛", "https://api.niuniuzy.me/api.php/provide/vod/"),
    ("非凡", "http://cj.ffzyapi.com/api.php/provide/vod/"),
    ("暴风", "https://bfzyapi.com/api.php/provide/vod/"),
    ("量子", "https://cj.lziapi.com/api.php/provide/vod/"),
    ("丫丫", "https://cj.yayazy.net/api.php/provide/vod/"),
    ("樱花", "https://m3u8.apiyhzy.com/api.php/provide/vod/"),
    ("极速", "https://jszyapi.com/api.php/provide/vod"),
    ("闪电", "http://sdzyapi.com/api.php/provide/vod/"),
    ("速博", "https://subocaiji.com/api.php/provide/vod/"),
    ("百度", "https://api.apibdzy.com/api.php/provide/vod/"),
    ("虎牙", "https://www.huyaapi.com/api.php/provide/vod/"),
    ("火狐", "https://hhzyapi.com/api.php/provide/vod/"),
    ("最大", "https://api.zuidapi.com/api.php/provide/vod/from/zuidam3u8/"),
    ("新浪", "https://api.xinlangapi.com/xinlangapi.php/provide/vod/"),
    ("建安", "http://154.219.117.232:9981/jacloudapi.php/provide/vod/"),
]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
TIMEOUT = 3          # 单站超时(秒)
MAX_WORKERS = 8      # 并发数
# 通用分类(统一 ID -> 名称)
CATS = [("1", "电影"), ("2", "电视剧"), ("3", "综艺"), ("4", "动漫")]


class Spider(Spider):
    def getName(self):
        return "自研聚合"

    def init(self, extend=""):
        self._class_map = None   # {站名: {大类名: 站type_id}}
        self._api = {name: api for name, api in SOURCES}
        self._jxs = ["https://jx.xmflv.com/?url=", "https://json.ovvo.pro/jx.php?url=", "https://jx.77flv.cc/?url="]
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    # ---------- HTTP 工具 ----------
    def _http(self, url, timeout=TIMEOUT):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            resp = urllib.request.urlopen(req, timeout=timeout)
            return resp.read().decode("utf-8", "ignore")
        except Exception:
            return ""

    def _fetch_json(self, url, timeout=TIMEOUT):
        txt = self._http(url, timeout)
        if not txt:
            return None
        try:
            return json.loads(txt)
        except Exception:
            # 去掉可能的 BOM / 前缀
            try:
                return json.loads(txt.lstrip("\ufeff"))
            except Exception:
                return None

    def _multi(self, jobs, worker=MAX_WORKERS):
        """并发执行: jobs=[(name, fn)] -> {name: result}, 异常为None"""
        out = {}
        lock = threading.Lock()
        def run(name, fn):
            try:
                r = fn()
            except Exception:
                r = None
            with lock:
                out[name] = r
        threads = []
        for name, fn in jobs:
            t = threading.Thread(target=run, args=(name, fn))
            t.start()
            threads.append(t)
            if len(threads) >= worker:
                for t2 in threads:
                    t2.join()
                threads = []
        for t2 in threads:
            t2.join()
        return out

    # ---------- 分类映射 ----------
    def _load_classes(self):
        if self._class_map is not None:
            return self._class_map
        cmap = {}
        # 并发拉各站分类, 慢站自动跳过
        jobs = []
        for name, api in self._api.items():
            def _f(a=api):
                return self._fetch_json(a + ("&" if "?" in a else "?") + "ac=list")
            jobs.append((name, _f))
        res = self._multi(jobs, worker=12)
        for name, d in res.items():
            if not d or "class" not in d:
                continue
            m = {}
            for c in d["class"]:
                tn = str(c.get("type_name", "")).strip()
                tid = str(c.get("type_id", "")).strip()
                if tn == "电影" or tn == "电影片":
                    m.setdefault("电影", tid)
                elif tn in ("连续剧", "电视剧", "剧集", "国产剧", "港台剧"):
                    m.setdefault("电视剧", tid)
                elif tn == "综艺" or tn == "真人秀":
                    m.setdefault("综艺", tid)
                elif tn == "动漫" or tn == "动画" or tn == "动漫片":
                    m.setdefault("动漫", tid)
            if m:
                cmap[name] = m
        self._class_map = cmap
        return cmap

    # ---------- 首页 ----------
    def homeContent(self, filter):
        classes = [{"type_id": tid, "type_name": tn} for tid, tn in CATS]
        result = {"class": classes}
        return result

    def homeVideoContent(self):
        # 并发拉各站首页第一页, 合并去重
        jobs = []
        for name, api in self._api.items():
            jobs.append((name, (lambda a: (lambda: self._page_list(a, 1, None)))(api)))
        res = self._multi(jobs)
        lists = []
        seen = set()
        for name in [n for n, _ in SOURCES]:
            data = res.get(name)
            if not data:
                continue
            for v in data:
                vn = str(v.get("vod_name", "")).strip()
                if not vn or vn in seen:
                    continue
                seen.add(vn)
                vid = name + "|" + str(v.get("vod_id", ""))
                lists.append(self._mkvod(v, vid, v.get("vod_remarks", "")))
                if len(lists) >= 60:
                    break
            if len(lists) >= 60:
                break
        return {"list": lists}

    def _page_list(self, api, pg, t):
        url = api + ("&" if "?" in api else "?") + "ac=detail&pg=" + str(pg)
        if t:
            url += "&t=" + str(t)
        d = self._fetch_json(url)
        if not d:
            return None
        return d.get("list") or []

    def _mkvod(self, v, vid, rem=None):
        return {
            "vod_id": vid,
            "vod_name": str(v.get("vod_name", "")),
            "vod_pic": str(v.get("vod_pic", "")),
            "vod_remarks": rem if rem else str(v.get("vod_remarks", "")),
            "vod_year": str(v.get("vod_year", "")),
            "vod_actor": str(v.get("vod_actor", "")),
        }

    # ---------- 分类 ----------
    def categoryContent(self, tid, pg, filter, extend):
        extend = extend or {}
        cmap = self._load_classes()
        # tid: "1"电影 "2"电视剧 "3"综艺 "4"动漫
        cn = dict(CATS).get(str(tid), "电影")
        jobs = []
        for name, api in self._api.items():
            stid = cmap.get(name, {}).get(cn)
            if not stid:
                continue
            jobs.append((name, (lambda a, s: (lambda: self._page_list(a, int(pg), s)))(api, stid)))
        res = self._multi(jobs)
        lists = []
        seen = set()
        for name in [n for n, _ in SOURCES]:
            data = res.get(name)
            if not data:
                continue
            for v in data:
                vn = str(v.get("vod_name", "")).strip()
                if not vn or vn in seen:
                    continue
                seen.add(vn)
                vid = name + "|" + str(v.get("vod_id", ""))
                lists.append(self._mkvod(v, vid, v.get("vod_remarks", "")))
        return {"list": lists, "page": int(pg), "pagecount": 9999, "limit": len(lists), "total": 999999}

    # ---------- 搜索 ----------
    def searchContent(self, key, quick):
        jobs = []
        for name, api in self._api.items():
            jobs.append((name, (lambda a, k: (lambda: self._page_list(a, 1, None) if False else self._search(a, k)))(api, key)))
        res = self._multi(jobs)
        lists = []
        seen = set()
        for name in [n for n, _ in SOURCES]:
            data = res.get(name)
            if not data:
                continue
            for v in data:
                vn = str(v.get("vod_name", "")).strip()
                if not vn or vn in seen:
                    continue
                seen.add(vn)
                vid = name + "|" + str(v.get("vod_id", ""))
                lists.append(self._mkvod(v, vid, v.get("vod_remarks", "")))
        return {"list": lists}

    def _search(self, api, key):
        url = api + ("&" if "?" in api else "?") + "ac=detail&wd=" + urllib.parse.quote(key)
        d = self._fetch_json(url)
        if not d:
            return None
        return d.get("list") or []

    # ---------- 详情(多线路=多站) ----------
    def detailContent(self, ids):
        # ids = "站名|原始id"
        parts = ids.split("|", 1)
        name0 = parts[0] if parts else ""
        rid = parts[1] if len(parts) > 1 else ids
        api = self._api.get(name0)
        if not api:
            # 找不到来源站, 试全站
            for n, a in self._api.items():
                d = self._detail(a, rid)
                if d and d.get("list"):
                    name0, api = n, a
                    break
        if not api:
            return {"list": [{"vod_id": ids, "vod_name": "", "vod_pic": "", "vod_actor": "", "vod_director": "", "vod_content": "", "vod_year": "", "vod_remarks": ""}]}
        data = self._detail(api, rid)
        if not data or not data.get("list"):
            return {"list": [{"vod_id": ids, "vod_name": "", "vod_pic": "", "vod_actor": "", "vod_director": "", "vod_content": "", "vod_year": "", "vod_remarks": ""}]}
        item = data["list"][0]
        vod = {
            "vod_id": ids,
            "vod_name": str(item.get("vod_name", "")),
            "vod_pic": str(item.get("vod_pic", "")),
            "vod_actor": str(item.get("vod_actor", "")),
            "vod_director": str(item.get("vod_director", "")),
            "vod_content": str(item.get("vod_content", "")),
            "vod_year": str(item.get("vod_year", "")),
            "vod_remarks": str(item.get("vod_remarks", "")),
        }
        # 该站的全部线路(vod_play_from 多线路, vod_play_url 对应组)
        pf = str(item.get("vod_play_from", "") or "线路")
        pu = str(item.get("vod_play_url", "") or "")
        raw_froms = [x.strip() for x in re.split(r"[,\s]+", pf.replace("$$$", ",")) if x.strip()]
        raw_urls = [x.strip() for x in pu.split("$$$") if x.strip()]
        if len(raw_urls) == 1 and len(raw_froms) > 1:
            raw_urls = [raw_urls[0]] * len(raw_froms)
        plays_from, plays_url = [], []
        for i, u in enumerate(raw_urls):
            if not u:
                continue
            lname = (raw_froms[i] if i < len(raw_froms) else "线路") or "线路"
            lname = re.sub(r"[\s\[\]（）()]+", "", lname) or "线路"
            # 线路名 = 站名-线路名
            plays_from.append(f"{name0}-{lname}")
            plays_url.append(u)
        vod["vod_play_from"] = ",".join(plays_from)
        vod["vod_play_url"] = "$$$".join(plays_url)
        return {"list": [vod]}

    def _detail(self, api, rid):
        url = api + ("&" if "?" in api else "?") + "ac=videolist&ids=" + str(rid)
        d = self._fetch_json(url)
        if not d:
            return None
        return d

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags):
        # id 是具体播放地址
        url = str(id or "")
        low = url.lower()
        if url.startswith("http") and (".m3u8" in low or ".mp4" in low or ".flv" in low or ".ts" in low or "m3u8" in low):
            return {"parse": 0, "url": url, "header": {"User-Agent": UA}}
        # 网页播放页 -> 尝试通用解析
        if url.startswith("http"):
            jx = self._jxs[0] + urllib.parse.quote(url, safe="")
            return {"parse": 1, "url": jx, "header": {"User-Agent": UA}}
        return {"parse": 0, "url": url}
