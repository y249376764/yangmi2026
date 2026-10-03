# -*- coding: utf-8 -*-
"""
哔哩有声 蜘蛛版 (bilibili_audio.py) v2
------------------------------------
站点: https://www.bilibili.com
底层 B站 Web API:
  搜索   /x/web-interface/wbi/search/type   (WBI 签名 + cookie 预热, 官方全量搜索)
  详情   /x/web-interface/view/detail       (免签名)
  音频   /x/player/playurl                  (免签名, DASH 纯音频流)

v2 搜索修复 (2026-10-03):
  1. 搜索链路升级为 WBI 签名 + cookie 预热 (与 bilibili_ts.py 验证过的方案一致)
     - 预热: 首页种 buvid3/b_nut -> finger/spi 补 buvid4 -> nav 拿 wbi 密钥+更多cookie
     - 搜索: /x/web-interface/wbi/search/type + wts/w_rid 签名, 免 v_voucher 风控
  2. v_voucher 风控检测: 返回空 result 且带 v_voucher 字段时自动重试一次
  3. 会话复用: 同一个 Session 保持 cookie, 避免每次裸请求
  4. 官方全量: 官方搜索接口直接返回全部结果(不做过滤), 单页 20 条 = B站官方硬限制,
     翻页 pagecount 用官方 numResults 真实计算
  5. 播放不变: 纯音频 dash 流(最快最省流量), 2 线路(高清/流畅)

分类: 有声小说 / 有声漫画 / 广播剧 / 经典老歌 / 音乐推荐 (搜索词即分类)
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
    UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    timeout = 15
    SEARCH_GAP = 1.2  # B站风控: 搜索间隔

    MIXIN_KEY_ENC_TAB = [
        46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,
        33,9,42,19,29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,61,
        26,17,0,1,60,51,30,4,22,25,54,21,56,59,6,63,57,62,11,36,
        20,34,44,52,
    ]

    CLASSES = [
        {"type_id": "有声小说", "type_name": "有声小说"},
        {"type_id": "有声漫画", "type_name": "有声漫画"},
        {"type_id": "广播剧", "type_name": "广播剧"},
        {"type_id": "经典老歌", "type_name": "经典老歌"},
        {"type_id": "音乐推荐", "type_name": "音乐推荐"},
    ]

    def __init__(self):
        self._cookies = {}
        self._wbi = None
        self._day = ""
        self._session = None
        self._last_search_at = 0

    def _sess(self):
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({"User-Agent": self.UA, "Referer": self.HOME + "/"})
        return self._session

    def _throttle(self, gap=0.4):
        t = time.time()
        d = t - self._last_search_at
        if d < gap:
            time.sleep(gap - d)
        self._last_search_at = time.time()

    # ---------------- cookie 预热 (免风控关键) ----------------
    def _ensure_cookies(self):
        s = self._sess()
        if self._cookies.get("buvid3") and self._cookies.get("buvid4"):
            return
        try:
            # 预热1: 首页种 buvid3/b_nut
            r = s.get(self.HOME + "/", timeout=12)
            for c in s.cookies:
                self._cookies[c.name] = c.value
            # 预热2: finger/spi 补 buvid4 (缺了详情接口必 412)
            if not self._cookies.get("buvid4"):
                r2 = s.get(self.API + "/x/frontend/finger/spi", timeout=12)
                j = r2.json()
                if j.get("code") == 0 and j.get("data"):
                    self._cookies["buvid3"] = j["data"].get("b_3") or self._cookies.get("buvid3")
                    self._cookies["buvid4"] = j["data"].get("b_4") or ""
            # 预热3: nav 拿 wbi 密钥 + 更多 cookie
            r3 = s.get(self.API + "/x/web-interface/nav", timeout=12)
            for c in s.cookies:
                self._cookies[c.name] = c.value
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

    def _api_get(self, path, params, use_wbi=False, referer="https://www.bilibili.com/"):
        self._ensure_cookies()
        if use_wbi:
            keys = self._ensure_wbi()
            params = self._wbi_sign(params, keys)
        s = self._sess()
        headers = {"Referer": referer}
        ck = "; ".join(f"{k}={v}" for k, v in self._cookies.items())
        if ck:
            headers["Cookie"] = ck
        for attempt in range(3):
            if attempt > 0:
                time.sleep(1.2)
            self._throttle(0.3)
            try:
                r = s.get(self.API + path, params=params, timeout=self.timeout, headers=headers)
                if r.status_code != 200:
                    continue
                j = r.json()
                code = j.get("code")
                if code != 0:
                    if code in (-412, -352):
                        continue
                    return {}
                return j
            except Exception:
                continue
        return {}

    def _get(self, url, referer="https://www.bilibili.com/"):
        try:
            r = requests.get(url, headers={"User-Agent": self.UA, "Referer": referer}, timeout=self.timeout)
            if r.status_code == 200:
                return r
        except Exception:
            return None
        return None

    def _get_json(self, url):
        r = self._get(url)
        if r is None:
            return {}
        try:
            return json.loads(r.text)
        except Exception:
            return {}

    @staticmethod
    def _clean_title(s):
        """去掉搜索结果的 <em class=keyword> 高亮标签"""
        if not s:
            return ''
        return re.sub(r'<em class="keyword">', '', s).replace('</em>', '').strip()

    # ---------------- 搜索/分类 (官方全量) ----------------
    def _search_list(self, kw, page, page_size=20):
        """官方 WBI 签名搜索接口, 全量返回不过滤"""
        self._throttle(self.SEARCH_GAP)
        query = {
            "search_type": "video", "keyword": str(kw),
            "page": str(page), "page_size": str(page_size),
        }
        j = self._api_get("/x/web-interface/wbi/search/type", query, use_wbi=True,
                          referer="https://search.bilibili.com/")
        data = j.get("data") or {}
        res = data.get("result") or []
        total = data.get("numResults") or 0
        # v_voucher 风控: 无 result 且带 v_voucher 字段, 重试一次
        if not res and data.get("v_voucher"):
            time.sleep(2.0)
            j = self._api_get("/x/web-interface/wbi/search/type", query, use_wbi=True,
                              referer="https://search.bilibili.com/")
            data = j.get("data") or {}
            res = data.get("result") or []
            total = data.get("numResults") or 0
        out = []
        for it in res:
            if not isinstance(it, dict):
                continue
            bvid = it.get("bvid")
            if not bvid:
                continue
            title = self._clean_title(it.get("title"))
            pic = it.get("pic") or ""
            if pic and pic.startswith("//"):
                pic = "https:" + pic
            play = it.get("play") or it.get("danmaku") or 0
            like = it.get("like") or 0
            duration = it.get("duration") or ""
            out.append({
                "vod_id": bvid,
                "vod_name": title or bvid,
                "vod_pic": pic,
                "vod_remarks": f"{duration}",
                "vod_content": f"▶{play} ❤{like}",
                "vod_actor": it.get("author") or "",
                "vod_director": "",
            })
        return out, total

    # ---------------- 详情 ----------------
    def detailContent(self, ids):
        bvid = str(ids[0]) if isinstance(ids, (list, tuple)) else str(ids)
        j = self._get_json(f"{self.API}/x/web-interface/view/detail?bvid={bvid}&p=1&platform=h5")
        view = j.get("data", {}).get("View") or {}
        vod = {
            "vod_id": bvid,
            "vod_name": self._clean_title(view.get("title")) or bvid,
            "vod_pic": view.get("pic") or "",
            "vod_content": view.get("desc") or "",
            "vod_remarks": "",
            "vod_actor": view.get("owner", {}).get("name") if isinstance(view.get("owner"), dict) else "",
        }
        aid = view.get("aid")
        pages = view.get("pages") or []
        if not aid or not pages:
            return {"list": [vod]}
        # 2 条音频线路: 高清音频(最高码率) / 流畅音频(最低码率, 最省流量)
        lines = [("高清音频", 1), ("流畅音频", 0)]
        froms, urls = [], []
        for line_name, qn in lines:
            eps = []
            for p in pages:
                cid = p.get("cid")
                part = p.get("part") or f"P{p.get('page', '')}"
                if cid is not None and part:
                    # 每集 id 携带 qn, 播放时直接换清晰度
                    eps.append(f"{part}${aid}$${cid}$${qn}")
            if eps:
                froms.append(line_name)
                urls.append("#".join(eps))
        if froms:
            vod["vod_play_from"] = "$$$".join(froms)
            vod["vod_play_url"] = "$$$".join(urls)
            vod["vod_remarks"] = f"{len(pages)}P · {len(froms)}线路"
        return {"list": [vod]}

    # ---------------- 播放 ----------------
    def playerContent(self, flag, ids, vipFlags=None):
        # id 格式: "part$aid$$cid$${策略}"  (1=高清音频最高码率, 0=流畅音频最低码率)
        parts = str(ids).split("$$")
        mode = 1  # 默认高清音频
        if len(parts) >= 3:
            try:
                mode = int(parts[2])
            except Exception:
                mode = 1
        cid = parts[1] if len(parts) > 1 else ""
        aid_part = parts[0] if parts else ""
        aid = aid_part.split("$")[-1] if aid_part else ""
        if not cid or not aid:
            return {"parse": 0, "url": ""}
        # 全部走音频: 请求 dash (fnval=16) 拿纯音频流, 文件小加载快
        # 大合集视频 1.59GB mux mp4 -> 295MB 音频流, 快 5 倍
        j = self._get_json(f"{self.API}/x/player/playurl?avid={aid}&cid={cid}&qn=16&fnval=16&fnver=0&fourk=1")
        data = j.get("data", {}) or {}
        dash = data.get("dash") or {}
        audio = dash.get("audio") or []
        if audio:
            # 高清=最高码率, 流畅=最低码率 (B站音频多为 30216/30232/30280)
            if mode == 0:
                pick = min(audio, key=lambda a: a.get("bandwidth") or 0)
            else:
                pick = max(audio, key=lambda a: a.get("bandwidth") or 0)
            url = pick.get("baseUrl") or pick.get("base_url") or ""
            if not url and len(audio) > 1:
                url = audio[1].get("baseUrl", "")
            if url:
                return {"parse": 0, "url": url, "flag": flag or "哔哩有声",
                        "format": "audio/mp4",
                        "header": {"User-Agent": self.UA, "Referer": "https://www.bilibili.com/"}}
        # fallback: 无 dash 音频则用 durl 视频流(视频播放器)
        durl = data.get("durl") or []
        if durl:
            url = durl[0].get("url", "")
            if url:
                return {"parse": 0, "url": url, "flag": flag or "哔哩有声",
                        "format": "video/mp4",
                        "header": {"User-Agent": self.UA, "Referer": "https://www.bilibili.com/"}}
        return {"parse": 0, "url": ""}

    # ---------------- 标准接口 ----------------
    def init(self, extend=""):
        pass

    def getName(self):
        return "哔哩有声[py]"

    def isVideoFormat(self, url):
        return True

    def manualVideoCheck(self):
        return False

    def homeContent(self, filter):
        vods = []
        seen = set()
        for kw in ["有声小说", "有声漫画", "广播剧", "经典老歌"]:
            items, _ = self._search_list(kw, 1)
            for it in items[:8]:
                if it and it["vod_id"] not in seen:
                    seen.add(it["vod_id"])
                    vods.append(it)
            if len(vods) >= 32:
                break
        return {"class": self.CLASSES, "list": vods, "filters": {}}

    def homeVideoContent(self):
        vods = []
        for kw in ["有声小说", "广播剧"]:
            items, _ = self._search_list(kw, 1)
            vods.extend(items[:8])
        return {"list": vods}

    def categoryContent(self, tid, pg="1", filter=False, extend=""):
        page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
        lst, total = self._search_list(str(tid), page)
        pagecount = max(1, (total + 19) // 20) if total else page + 1
        return {"list": lst, "page": page, "pagecount": pagecount, "limit": 20, "total": total}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
        lst, total = self._search_list(str(key), page)
        pagecount = max(1, (total + 19) // 20) if total else 1
        return {"list": lst, "page": page, "pagecount": pagecount, "limit": 20, "total": total}

    def localProxy(self, param=""):
        return {}

    def destroy(self):
        pass


if __name__ == "__main__":
    import sys
    sp = Spider()
    sp.init("")
    kw = sys.argv[1] if len(sys.argv) > 1 else "三体 有声小说"
    r = sp.searchContent(kw, False, "1")
    print(f"搜索 [{kw}]: {len(r['list'])} 条 | pagecount={r['pagecount']} | total={r['total']}")
    for v in r["list"][:5]:
        print(f"  {v['vod_name'][:36]} | {v['vod_remarks']} | {v['vod_id']}")
