# -*- coding: utf-8 -*-
"""
哔哩听书 B站有声 (bilibili_ts.py)
---------------------------------
站点: https://www.bilibili.com
与哔哩听书APP同源, 底层 B站 Web API:
  搜索   /x/web-interface/wbi/search/type   (Wbi 签名)
  章节   /x/player/pagelist                 (免签名)
  音频   /x/player/wbi/playurl              (Wbi 签名, DASH)

关键点:
  1. Cookie 预热: 首页种 buvid3/b_nut + finger/spi 补 buvid4 (缺 buvid4 详情接口必 412)
  2. 请求必须带浏览器 UA + Referer: https://www.bilibili.com/
  3. 听书过滤: 标题/简介含 有声小说/评书/相声/广播剧 等关键词, 时长≥5分钟
  4. B站CDN 防盗链: 拉流带 Referer: https://www.bilibili.com/
"""
import re
import json
import time
import hashlib
import requests
import urllib.parse

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
    HOME = "https://www.bilibili.com"
    API = "https://api.bilibili.com"
    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    timeout = 15

    # Wbi 签名换位表
    MIXIN_KEY_ENC_TAB = [
        46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,
        33,9,42,19,29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,61,
        26,17,0,1,60,51,30,4,22,25,54,21,56,59,6,63,57,62,11,36,
        20,34,44,52,
    ]

    # 听书内容过滤
    AUDIO_HINTS = ["有声小说", "有声书", "有声剧", "有声读物", "有声", "听书", "评书", "相声",
                   "广播剧", "演播", "朗读", "诵读", "长书", "连播", "说书", "单口", "播讲", "多人剧", "小说剧"]
    NOISE_HINTS = ["一口气看完", "漫推", "漫画", "解说", "讲解", "解读", "动画", "鬼畜", "混剪",
                   "沙雕", "速看", "reaction", "预告", "游戏实况", "配音秀"]

    CLASSES = [
        {"type_id": "1", "type_name": "有声小说"},
        {"type_id": "2", "type_name": "评书相声"},
        {"type_id": "3", "type_name": "广播剧"},
        {"type_id": "4", "type_name": "朗读诵读"},
    ]

    def __init__(self):
        self._cookies = {}
        self._wbi = None  # (imgKey, subKey)
        self._day = ""
        self._session = None
        self._last_req_at = 0

    def init(self, extend=''):
        pass

    def _sess(self):
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({"User-Agent": self.UA, "Referer": self.HOME + "/"})
        return self._session

    def _throttle(self):
        gap = time.time() - self._last_req_at
        if gap < 0.4:
            time.sleep(0.4 - gap)
        self._last_req_at = time.time()

    def _ensure_cookies(self):
        s = self._sess()
        if self._cookies.get("buvid3") and self._cookies.get("buvid4"):
            return
        try:
            r = s.get(self.HOME + "/", timeout=12)
            for c in s.cookies:
                self._cookies[c.name] = c.value
            if not self._cookies.get("buvid4"):
                r2 = s.get(self.API + "/x/frontend/finger/spi", timeout=12)
                j = r2.json()
                if j.get("code") == 0 and j.get("data"):
                    self._cookies["buvid3"] = j["data"].get("b_3") or self._cookies.get("buvid3")
                    self._cookies["buvid4"] = j["data"].get("b_4") or ""
        except Exception:
            pass

    def _ensure_wbi(self):
        today = time.strftime("%Y-%m-%d")
        if self._wbi and self._day == today:
            return self._wbi
        try:
            r = self._sess().get(self.API + "/x/web-interface/nav", timeout=12)
            j = r.json()
            img = j.get("data", {}).get("wbi_img", {})
            img_key = img["img_url"].split("/")[-1].split(".")[0]
            sub_key = img["sub_url"].split("/")[-1].split(".")[0]
            self._wbi = (img_key, sub_key)
            self._day = today
            return self._wbi
        except Exception:
            return None

    def _wbi_sign(self, params, keys):
        if not keys:
            return params
        mixin = "".join((keys[0] + keys[1])[i] for i in self.MIXIN_KEY_ENC_TAB)
        params["wts"] = str(int(time.time()))
        arr = [f"{k}={urllib.parse.quote(str(params[k]), safe='')}" for k in sorted(params.keys()) if params[k] is not None]
        params["w_rid"] = hashlib.md5(("&".join(arr) + mixin).encode()).hexdigest()
        return params

    def _api_get(self, path, params, use_wbi=False):
        self._ensure_cookies()
        if use_wbi:
            keys = self._ensure_wbi()
            params = self._wbi_sign(params, keys)
        s = self._sess()
        headers = {}
        ck = "; ".join(f"{k}={v}" for k, v in self._cookies.items())
        if ck:
            headers["Cookie"] = ck
        last_err = None
        for attempt in range(3):
            if attempt > 0:
                time.sleep(1.0)
            self._throttle()
            try:
                r = s.get(self.API + path, params=params, timeout=self.timeout, headers=headers)
                if r.status_code != 200:
                    last_err = "HTTP " + str(r.status_code)
                    continue
                j = r.json()
                code = j.get("code")
                if code != 0:
                    last_err = "code=" + str(code)
                    if code not in (-412, -352):
                        return {}
                    continue
                return j
            except Exception as e:
                last_err = str(e)
                continue
        return {}

    def _strip(self, s):
        return re.sub(r"<[^>]+>", "", str(s or ""))

    def _parse_duration(self, s):
        if not s:
            return 0
        sec = 0
        for p in str(s).split(":"):
            sec = sec * 60 + (int(p) if p.isdigit() else 0)
        return sec

    def _is_audiobook(self, m, keyword):
        title = self._strip(m.get("title"))
        meta = str(m.get("description") or "") + " " + str(m.get("tag") or "")
        if any(h in (title + " " + meta) for h in self.NOISE_HINTS):
            return False
        sec = self._parse_duration(m.get("duration"))
        if any(h in title for h in self.AUDIO_HINTS) and sec >= 300:
            return True
        if str(m.get("typeid")) == "195" and sec >= 600:
            return True
        if any(h in meta for h in self.AUDIO_HINTS) and sec >= 1800:
            return True
        return False

    def _normalize_pic(self, p):
        s = str(p or "")
        if not s:
            return ""
        if s.startswith("//"):
            return "https:" + s
        if s.startswith("http://"):
            return "https://" + s[7:]
        if s.startswith("/"):
            return "https://i0.hdslb.com" + s
        return s

    def _search_raw(self, keyword, page=1, page_size=20):
        query = {
            "search_type": "video", "keyword": keyword, "page": str(page),
            "page_size": str(page_size), "platform": "pc", "web_location": "1430654",
        }
        body = self._api_get("/x/web-interface/wbi/search/type", query, use_wbi=True)
        results = (body.get("data") or {}).get("result") or []
        out = []
        for m in results:
            if not m or not m.get("bvid") or not m.get("aid"):
                continue
            if not self._is_audiobook(m, keyword):
                continue
            out.append({
                "vod_id": m["bvid"],
                "vod_name": self._strip(m.get("title")),
                "vod_pic": self._normalize_pic(m.get("pic")),
                "vod_remarks": m.get("duration") or "",
                "vod_content": self._strip(m.get("description") or ""),
            })
        return out

    def homeContent(self, filter=False):
        lst = []
        try:
            lst = self._search_raw("有声小说 全集", 1, 20)
        except Exception:
            pass
        if not lst:
            lst = [{"vod_id": "BV1cHjn6qExm", "vod_name": "精品有声书《三体》科幻", "vod_pic": "",
                    "vod_remarks": "全本"}]
        return {"class": self.CLASSES, "list": lst, "filters": {}}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        kw = {"1": "有声小说", "2": "评书 相声", "3": "广播剧", "4": "朗读 诵读"}.get(str(tid), "有声小说")
        lst = []
        try:
            lst = self._search_raw(kw + " 全集", int(pg or 1), 20)
        except Exception:
            pass
        return {"list": lst}

    def detailContent(self, ids):
        bvid = str(ids[0]) if ids else ""
        vod = {"vod_id": bvid, "vod_name": "", "vod_pic": "", "type_name": "听书",
               "vod_content": "", "vod_play_from": "哔哩听书", "vod_play_url": ""}
        play_urls = []
        try:
            body = self._api_get("/x/player/pagelist", {"bvid": bvid})
            pages = body.get("data") or []
            if pages:
                for c in pages:
                    if not c.get("cid"):
                        continue
                    play_urls.append(f"{c.get('part') or ('第' + str(c.get('page')) + '话')}${bvid}_{c.get('cid')}")
        except Exception:
            pass
        if play_urls:
            vod["vod_play_url"] = "#".join(play_urls)
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        lst = []
        try:
            lst = self._search_raw(key, int(pg or 1), 20)
            if len(lst) < 6:
                extra = self._search_raw(key + " 有声小说", int(pg or 1), 20)
                seen = {v["vod_id"] for v in lst}
                for v in extra:
                    if v["vod_id"] not in seen:
                        seen.add(v["vod_id"])
                        lst.append(v)
        except Exception:
            pass
        return {"list": lst}

    def playerContent(self, flag, id, vipFlags=None):
        try:
            parts = id.split("_", 1)
            if len(parts) != 2:
                return {"parse": 0, "url": ""}
            bvid, cid = parts[0], parts[1]
            self._ensure_cookies()
            query = {"bvid": bvid, "cid": cid, "qn": "80", "fnval": "4048", "fnver": "0",
                     "fourk": "1", "try_look": "1", "gaia_source": "prefer-ua"}
            body = self._api_get("/x/player/wbi/playurl", query, use_wbi=True)
            dash = (body.get("data") or {}).get("dash") or {}
            tracks = list(dash.get("audio") or [])
            flac = (dash.get("flac") or {}).get("audio")
            if flac:
                tracks.append(flac)
            dolby = (dash.get("dolby") or {}).get("audio") or []
            if dolby:
                tracks.append(dolby[0])
            if not tracks:
                return {"parse": 0, "url": ""}
            # 带宽最高优先
            tracks.sort(key=lambda a: a.get("bandwidth") or 0, reverse=True)
            best = tracks[0]
            url = best.get("base_url") or ((best.get("backup_url") or [""])[0])
            if url:
                return {"parse": 0, "url": url,
                        "header": "{\"User-Agent\": \"" + self.UA + "\", \"Referer\": \"https://www.bilibili.com/\"}"}
        except Exception:
            pass
        return {"parse": 0, "url": ""}

    def homeVideoContent(self):
        return {"list": []}

    def getName(self):
        return "哔哩听书"

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
    for v in h["list"][:3]:
        print(f"  {v['vod_name'][:30]} | {v['vod_remarks']}")
    s = sp.searchContent("三体", True)
    print(f"搜索: {len(s['list'])} 条")
    if s["list"]:
        b = s["list"][0]
        print(f"第一本: {b['vod_name'][:30]}")
        d = sp.detailContent([b["vod_id"]])
        urls = d["list"][0]["vod_play_url"].split("#")
        print(f"章节: {len(urls)} 集")
        if urls:
            p = sp.playerContent("", urls[0].split("$")[1])
            print(f"播放: {p.get('url', '')[:70]}")
