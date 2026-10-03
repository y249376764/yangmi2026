# -*- coding: utf-8 -*-
"""
哔哩有声 蜘蛛版 (bilibili_audio.py)
------------------------------------
照搬海阔视界"哔哩有声"规则 (home_rule_v2), 2026-10-03 实现:

  * 搜索/分类  GET https://api.bilibili.com/x/web-interface/wbi/search/type
               ?search_type=video&keyword={kw}&page={p}&page_size=20
               (实测无需 WBI 签名, code 0 正常返回)
  * 详情      GET https://api.bilibili.com/x/web-interface/view/detail
               ?bvid={bvid}&p=1&platform=h5
               -> data.View: { title, pic, desc, aid, pages[] }
  * 播放      GET https://api.bilibili.com/x/player/playurl
               ?avid={aid}&cid={cid}&qn=16&fnval=16&fnver=0&fourk=1
               (不能带 platform=html5, 会禁掉 dash) -> data.dash.audio[].baseUrl

全部走音频播放器: B站音视频分离(dash), 纯音频流远小于 mux mp4 (大合集 1.59GB 视频
              -> 295MB 音频, 快 5 倍)。2 条音频线路: 高清音频(最高码率) / 流畅音频(最低码率)。
              每集 id 格式 "part$aid$$cid$${1|0}"。无 dash 音频时 fallback durl 视频流。

分类: 有声小说 / 有声漫画 / 广播剧 / 经典老歌 / 音乐推荐 (搜索词即分类)
说明: B 站音频类内容多为视频封面音轨, 直链为 mp4, 播放器可直接播放。
"""
import re
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
    API = "https://api.bilibili.com"
    UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    timeout = 12

    CLASSES = [
        {"type_id": "有声小说", "type_name": "有声小说"},
        {"type_id": "有声漫画", "type_name": "有声漫画"},
        {"type_id": "广播剧", "type_name": "广播剧"},
        {"type_id": "经典老歌", "type_name": "经典老歌"},
        {"type_id": "音乐推荐", "type_name": "音乐推荐"},
    ]

    def _get(self, url, referer="https://www.bilibili.com/"):
        h = {"User-Agent": self.UA, "Referer": referer}
        try:
            r = requests.get(url, headers=h, timeout=self.timeout)
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

    # ---------------- 搜索/分类 ----------------
    def _search_list(self, kw, page):
        from urllib.parse import quote
        url = (f"{self.API}/x/web-interface/wbi/search/type"
               f"?search_type=video&keyword={quote(kw)}&page={page}&page_size=20")
        j = self._get_json(url)
        res = j.get("data", {}).get("result") or []
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
        return out

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
        for kw in ["有声小说", "有声漫画", "广播剧", "经典老歌"]:
            for it in self._search_list(kw, 1)[:8]:
                if it and it["vod_id"] not in [v["vod_id"] for v in vods]:
                    vods.append(it)
            if len(vods) >= 32:
                break
        return {"class": self.CLASSES, "list": vods, "filters": {}}

    def homeVideoContent(self):
        vods = []
        for kw in ["有声小说", "广播剧"]:
            vods.extend(self._search_list(kw, 1)[:8])
        return {"list": vods}

    def categoryContent(self, tid, pg="1", filter=False, extend=""):
        page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
        return {"list": self._search_list(str(tid), page), "page": page, "pagecount": page + 1}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
        return {"list": self._search_list(str(key), page)}

    def localProxy(self, param=""):
        return {}

    def destroy(self):
        pass