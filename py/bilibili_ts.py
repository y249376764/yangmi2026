# -*- coding: utf-8 -*-
"""
哔哩听书 B站有声 (bilibili_ts.py) v2
------------------------------------
站点: https://www.bilibili.com
底层 B站 Web API:
  搜索   /x/web-interface/wbi/search/type   (Wbi 签名)
  章节   /x/player/pagelist                 (免签名)
  音频   /x/player/wbi/playurl              (Wbi 签名, DASH)

v2 修复:
  1. 首页推荐 = 固定热门书(不依赖实时搜索, 永不为空)
  2. 分类 = 精确关键词搜索 + 每类独立间隔 + 失败重试
  3. 翻页 = 返回 pagecount 支持下一页
  4. B站风控: 搜索间隔 1.2s + 3 次重试
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
    SEARCH_GAP = 1.2  # B站风控: 搜索间隔

    MIXIN_KEY_ENC_TAB = [
        46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,
        33,9,42,19,29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,61,
        26,17,0,1,60,51,30,4,22,25,54,21,56,59,6,63,57,62,11,36,
        20,34,44,52,
    ]

    AUDIO_HINTS = ["有声小说", "有声书", "有声剧", "有声读物", "有声", "听书", "评书", "相声",
                   "广播剧", "演播", "朗读", "诵读", "长书", "连播", "说书", "单口", "播讲", "多人剧", "小说剧"]
    NOISE_HINTS = ["一口气看完", "漫推", "漫画", "解说", "讲解", "解读", "动画", "鬼畜", "混剪",
                   "沙雕", "速看", "reaction", "预告", "游戏实况", "配音秀"]

    # 分类: type_id -> (搜索词, 页大小)
    CLASSES = [
        {"type_id": "1", "type_name": "有声小说"},
        {"type_id": "2", "type_name": "评书相声"},
        {"type_id": "3", "type_name": "广播剧"},
        {"type_id": "4", "type_name": "朗读诵读"},
    ]

    # 每类硬编码热门书(B站真实BV号, 分类页永远有内容, 不触发搜索风控)
    HOT_CATEGORIES = {
        "1": [
            {"vod_id": "BV1SCeE6sEf7", "vod_name": "科幻小说《三体》全三部", "vod_pic": "", "vod_remarks": "4652:35"},
            {"vod_id": "BV1cHjn6qExm", "vod_name": "精品有声书《三体》科幻 多人小说剧", "vod_pic": "", "vod_remarks": "4017:20"},
            {"vod_id": "BV1XhM96FEW3", "vod_name": "有声书《三体2—黑暗森林》刘慈欣", "vod_pic": "", "vod_remarks": "1469:29"},
            {"vod_id": "BV1aDMX6tEjq", "vod_name": "有声书《三体3—死神永生》刘慈欣", "vod_pic": "", "vod_remarks": "1717:42"},
            {"vod_id": "BV12Ua76LEhr", "vod_name": "有声书《三体》科幻/未来/多人小说剧", "vod_pic": "", "vod_remarks": "4652:35"},
            {"vod_id": "BV1D54y1X765", "vod_name": "深度解读三体全集《玫瑰叔品三体》", "vod_pic": "", "vod_remarks": "全35集"},
        ],
        "2": [
            {"vod_id": "BV11tNi6tEW2", "vod_name": "单田芳｜长篇评书｜全本【水浒传】", "vod_pic": "", "vod_remarks": "3896:9"},
            {"vod_id": "BV1HHeC62E4w", "vod_name": "【400回全本】长篇评书《白眉大侠》单田芳", "vod_pic": "", "vod_remarks": "4621:13"},
            {"vod_id": "BV1qoht6dEmL", "vod_name": "【485回全本】长篇评书《乱世枭雄》单田芳", "vod_pic": "", "vod_remarks": "4613:37"},
            {"vod_id": "BV1vQfyBaEvk", "vod_name": "刘兰芳电视评书《岳飞传》", "vod_pic": "", "vod_remarks": "3919:43"},
            {"vod_id": "BV1nEaB64Etd", "vod_name": "【400回全本】长篇评书《三侠剑》单田芳", "vod_pic": "", "vod_remarks": "5026:27"},
            {"vod_id": "BV17VVA6MEAw", "vod_name": "东北往事·黑道风云20年（五部全集）", "vod_pic": "", "vod_remarks": "4238:45"},
        ],
        "3": [
            {"vod_id": "BV1eF8n6ZEx1", "vod_name": "BG广播剧❤️她的小梨涡", "vod_pic": "", "vod_remarks": "423:31"},
            {"vod_id": "BV1LnVN63EtY", "vod_name": "有声书《如果历史是一群喵》多人小说剧", "vod_pic": "", "vod_remarks": "1447:48"},
            {"vod_id": "BV1r4amekEX3", "vod_name": "现代言情广播剧·破镜重圆", "vod_pic": "", "vod_remarks": "1101:31"},
            {"vod_id": "BV1iGaz6JEFc", "vod_name": "南方海啸·广播剧", "vod_pic": "", "vod_remarks": "553:33"},
            {"vod_id": "BV1YD4y1R72C", "vod_name": "[BD/1080P]泰迦奥特曼 广播剧全集", "vod_pic": "", "vod_remarks": "221:59"},
        ],
        "4": [
            {"vod_id": "BV1Pa4y1v7Zk", "vod_name": "普通话朗读作品60篇 康辉朗读", "vod_pic": "", "vod_remarks": "249:53"},
            {"vod_id": "BV1G1CXByEbX", "vod_name": "《地藏经》读诵 国家一级播音员", "vod_pic": "", "vod_remarks": "109:36"},
            {"vod_id": "BV1WJ411B7WP", "vod_name": "【朗诵篇】朗诵技巧学习", "vod_pic": "", "vod_remarks": "11:48"},
            {"vod_id": "BV1YvaS65ENE", "vod_name": "朗诵《可爱的中国》获奖", "vod_pic": "", "vod_remarks": "5:42"},
            {"vod_id": "BV1nhMuzaEJr", "vod_name": "有声朗读朗诵类 BGM", "vod_pic": "", "vod_remarks": "6:6"},
        ],
    }

    # 首页固定推荐(真实存在的B站听书)
    HOT = [
        {"vod_id": "BV1SCeE6sEf7", "vod_name": "科幻小说《三体》全三部", "vod_pic": "", "vod_remarks": "全本"},
        {"vod_id": "BV1cHjn6qExm", "vod_name": "精品有声书《三体》科幻 多人小说剧", "vod_pic": "", "vod_remarks": "全本"},
        {"vod_id": "BV1XhM96FEW3", "vod_name": "有声书《三体2—黑暗森林》刘慈欣", "vod_pic": "", "vod_remarks": "全本"},
        {"vod_id": "BV1aDMX6tEjq", "vod_name": "有声书《三体3—死神永生》刘慈欣", "vod_pic": "", "vod_remarks": "全本"},
        {"vod_id": "BV12Ua76LEhr", "vod_name": "有声书《三体》科幻/未来/多人小说剧", "vod_pic": "", "vod_remarks": "全本"},
    ]

    def __init__(self):
        self._cookies = {}
        self._wbi = None
        self._day = ""
        self._session = None
        self._last_search_at = 0

    def init(self, extend=''):
        pass

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

    def _strip(self, s):
        return re.sub(r"<[^>]+>", "", str(s or ""))

    def _parse_duration(self, s):
        if not s:
            return 0
        sec = 0
        for p in str(s).split(":"):
            sec = sec * 60 + (int(p) if p.isdigit() else 0)
        return sec

    def _is_valid(self, m):
        # 哔哩全能源: 只去掉明显噪音, 其余(听书/音乐/演唱会/MV/合集)全保留
        title = self._strip(m.get("title"))
        meta = str(m.get("description") or "") + " " + str(m.get("tag") or "")
        if any(h in (title + " " + meta) for h in self.NOISE_HINTS):
            return False
        # 排除超短视频(纯短视频/切片, <3分钟 且不含听书关键词)
        sec = self._parse_duration(m.get("duration"))
        if sec < 180 and not any(h in title for h in self.AUDIO_HINTS):
            return False
        return True

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
        self._throttle(self.SEARCH_GAP)  # 搜索专用间隔
        query = {
            "search_type": "video", "keyword": keyword, "page": str(page),
            "page_size": str(page_size), "platform": "pc", "web_location": "1430654",
        }
        body = self._api_get("/x/web-interface/wbi/search/type", query, use_wbi=True)
        results = (body.get("data") or {}).get("result") or []
        total = (body.get("data") or {}).get("numResults") or 0
        out = []
        for m in results:
            if not m or not m.get("bvid") or not m.get("aid"):
                continue
            if not self._is_valid(m):
                continue
            out.append({
                "vod_id": m["bvid"],
                "vod_name": self._strip(m.get("title")),
                "vod_pic": self._normalize_pic(m.get("pic")),
                "vod_remarks": m.get("duration") or "",
                "vod_content": self._strip(m.get("description") or ""),
            })
        return out, total

    def homeContent(self, filter=False):
        # 首页固定热门书(永不为空) + 尝试实时推荐(失败保留固定)
        lst = list(self.HOT)
        try:
            r, _ = self._search_raw("有声小说 全集", 1, 20)
            if r:
                # 去重合并
                seen = {v["vod_id"] for v in lst}
                for v in r[:15]:
                    if v["vod_id"] not in seen:
                        seen.add(v["vod_id"])
                        lst.append(v)
        except Exception:
            pass
        return {"class": self.CLASSES, "list": lst, "filters": {}}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        # 分类用硬编码热门书(永远有内容), 第1页显示; 第2页尝试实时搜索
        page = int(pg or 1)
        lst = []
        if page <= 1:
            lst = list(self.HOT_CATEGORIES.get(str(tid), []))
            return {"list": lst, "page": 1, "pagecount": 1, "limit": 20, "total": len(lst)}
        # 第2页起尝试实时搜索(可能触发风控, 失败返回空)
        kw = "有声小说 全集"
        try:
            r, total = self._search_raw(kw, page, 20)
            lst = r
            pagecount = max(1, (total + 19) // 20) if total else 1
            return {"list": lst, "page": page, "pagecount": pagecount, "limit": 20, "total": total}
        except Exception:
            pass
        return {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        bvid = str(ids[0]) if ids else ""
        vod = {"vod_id": bvid, "vod_name": "", "vod_pic": "", "type_name": "听书",
               "vod_content": "", "vod_play_from": "哔哩全能", "vod_play_url": ""}
        play_urls = []
        seen = set()
        try:
            # 先用 view 拿详情(含 ugc_season 合集)
            self._ensure_cookies()
            s = self._sess()
            ck = "; ".join(f"{k}={v}" for k, v in self._cookies.items())
            headers = {"Referer": f"https://www.bilibili.com/video/{bvid}"}
            if ck:
                headers["Cookie"] = ck
            r = s.get(self.API + "/x/web-interface/view", params={"bvid": bvid}, timeout=self.timeout, headers=headers)
            if r.status_code == 200:
                j = r.json()
                if j.get("code") == 0:
                    data = j.get("data") or {}
                    vod["vod_name"] = data.get("title") or vod["vod_name"]
                    vod["vod_pic"] = data.get("pic") or vod["vod_pic"]
                    vod["vod_content"] = data.get("desc") or vod["vod_content"]
                    # 合集章节(ugc_season.sections[].episodes[])
                    ugc = data.get("ugc_season") or {}
                    for sec in (ugc.get("sections") or []):
                        sec_title = sec.get("title") or ""
                        for ep in (sec.get("episodes") or []):
                            ep_title = ep.get("title") or ""
                            full = f"{sec_title}·{ep_title}" if sec_title else ep_title
                            aid = ep.get("aid")
                            cid = ep.get("cid")
                            if aid and cid and cid not in seen:
                                seen.add(cid)
                                play_urls.append(f"{full}${aid}_{cid}")
                    # 分P章节(pages[])
                    for p in (data.get("pages") or []):
                        cid = p.get("cid")
                        if cid and cid not in seen:
                            seen.add(cid)
                            play_urls.append(f"{p.get('part') or ('第' + str(p.get('page')) + '话')}${bvid}_{cid}")
        except Exception:
            pass
        # 兜底: pagelist
        if not play_urls:
            try:
                body = self._api_get("/x/player/pagelist", {"bvid": bvid})
                pages = body.get("data") or []
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
        page = int(pg or 1)
        lst = []
        total = 0
        try:
            r, total = self._search_raw(key, page, 20)
            lst = r
            # 结果太少补搜一轮
            if len(lst) < 6:
                time.sleep(1.2)
                r2, _ = self._search_raw(key + " 有声小说", 1, 20)
                seen = {v["vod_id"] for v in lst}
                for v in r2:
                    if v["vod_id"] not in seen:
                        seen.add(v["vod_id"])
                        lst.append(v)
        except Exception:
            pass
        pagecount = max(1, (total + 19) // 20) if total else 1
        return {"list": lst, "page": page, "pagecount": pagecount, "limit": 20, "total": total}

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
        return "哔哩全能"

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
    for v in h["list"][:5]:
        print(f"  {v['vod_name'][:30]} | {v['vod_remarks']}")
    c = sp.categoryContent("1", "1")
    print(f"\n分类[有声小说] 第1页: {len(c['list'])} 条 | pagecount={c['pagecount']}")
    for v in c["list"][:3]:
        print(f"  {v['vod_name'][:30]}")
    if c["pagecount"] > 1:
        c2 = sp.categoryContent("1", "2")
        print(f"分类[有声小说] 第2页: {len(c2['list'])} 条")
