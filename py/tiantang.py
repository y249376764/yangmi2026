# -*- coding: utf-8 -*-
"""
天堂影视 py 源（自写版）
站点：奈飞工厂 netflixgc.com（MacCMS 变体，m3u8 直链可播）
列表：POST /index.php/ds_api/vod {type,class,area,year,lang,version,state,letter,by,page} → JSON
详情：/voddetail/{id}.html 解析简介/演员/资源列表（多源多集）
播放：/vodplay/{id}-{sid}-{nid}.html，player_aaaa encrypt:2 → unescape(base64decode(url)) → m3u8
搜索：/vodsearch/-------------.html?wd= 解析内嵌结果
老式 CSP 接口（兼容 xs.jar / 1.jar）：init/homeContent/homeVideoContent/categoryContent/detailContent/searchContent/playerContent
"""
import re
import json
import base64
import urllib.parse
import requests

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        def __init__(self):
            pass

        def getProxyUrl(self):
            return ""


class Spider(BaseSpider):
    HOST = "https://www.netflixgc.com"
    UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"

    # 5个分类（MacCMS type id）
    CATS = [
        {"type_id": "1", "type_name": "电影"},
        {"type_id": "2", "type_name": "连续剧"},
        {"type_id": "24", "type_name": "纪录片"},
        {"type_id": "3", "type_name": "漫剧"},
        {"type_id": "23", "type_name": "综艺"},
    ]

    FILTERS = {
        "class": {"key": "class", "name": "类型", "value": [
            {"n": "全部", "v": ""}, {"n": "剧情", "v": "剧情"}, {"n": "动作", "v": "动作"}, {"n": "爱情", "v": "爱情"},
            {"n": "科幻", "v": "科幻"}, {"n": "喜剧", "v": "喜剧"}, {"n": "悬疑", "v": "悬疑"}, {"n": "惊悚", "v": "惊悚"},
            {"n": "战争", "v": "战争"}, {"n": "犯罪", "v": "犯罪"}, {"n": "恐怖", "v": "恐怖"}, {"n": "冒险", "v": "冒险"},
            {"n": "动画", "v": "动画"}, {"n": "纪录", "v": "纪录"}, {"n": "奇幻", "v": "奇幻"},
        ]},
        "area": {"key": "area", "name": "地区", "value": [
            {"n": "全部", "v": ""}, {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"}, {"n": "台湾", "v": "台湾"},
            {"n": "美国", "v": "美国"}, {"n": "韩国", "v": "韩国"}, {"n": "日本", "v": "日本"}, {"n": "英国", "v": "英国"},
            {"n": "法国", "v": "法国"}, {"n": "泰国", "v": "泰国"}, {"n": "印度", "v": "印度"}, {"n": "其他", "v": "其他"},
        ]},
        "year": {"key": "year", "name": "年份", "value": [
            {"n": "全部", "v": ""}, {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"}, {"n": "2024", "v": "2024"},
            {"n": "2023", "v": "2023"}, {"n": "2022", "v": "2022"}, {"n": "2021", "v": "2021"}, {"n": "2020", "v": "2020"},
            {"n": "2019", "v": "2019"}, {"n": "2018", "v": "2018"}, {"n": "2017", "v": "2017"}, {"n": "更早", "v": "2016"},
        ]},
        "lang": {"key": "lang", "name": "语言", "value": [
            {"n": "全部", "v": ""}, {"n": "国语", "v": "国语"}, {"n": "粤语", "v": "粤语"}, {"n": "英语", "v": "英语"},
            {"n": "日语", "v": "日语"}, {"n": "韩语", "v": "韩语"}, {"n": "法语", "v": "法语"}, {"n": "其他", "v": "其他"},
        ]},
    }

    def init(self, extend=""):
        self.host = self.HOST
        try:
            if extend and str(extend).strip().startswith("{"):
                ext = json.loads(str(extend))
                if ext.get("host"):
                    self.host = str(ext["host"]).rstrip("/")
        except Exception:
            pass
        self.headers = {
            "User-Agent": self.UA,
            "Referer": self.host + "/",
            "X-Requested-With": "XMLHttpRequest",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }

    def getName(self):
        return "天堂"

    def _clean(self, s):
        if not s:
            return ""
        t = re.sub(r"<[^>]+>", "", str(s))
        t = t.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
        return re.sub(r"\s+", " ", t).strip()

    def _get(self, url, post_data=None):
        try:
            headers = dict(self.headers)
            if post_data:
                headers["Content-Type"] = "application/x-www-form-urlencoded"
                r = requests.post(url, data=post_data, headers=headers, timeout=15, verify=False)
            else:
                r = requests.get(url, headers=headers, timeout=15, verify=False)
            # 强制 UTF-8（源站 meta 明确 UTF-8，防 charset_normalizer 误判西里尔乱码）
            return r.content.decode("utf-8", "ignore")
        except Exception:
            return ""

    # ============ 首页 ============
    def homeContent(self, filter):
        return {"class": self.CATS, "list": self._home_list(), "filters": self.FILTERS}

    def homeVideoContent(self):
        return {"list": self._home_list()}

    def _home_list(self):
        try:
            data = self._fetch_list("", 1)
            return data.get("list", [])
        except Exception:
            return []

    def _fetch_list(self, type_id, pg, filter_map=None):
        """POST ds_api/vod 拿 JSON 列表"""
        filter_map = filter_map or {}
        data = (
            "type=" + str(type_id or "")
            + "&class=" + urllib.parse.quote(str(filter_map.get("class", "")))
            + "&area=" + urllib.parse.quote(str(filter_map.get("area", "")))
            + "&year=" + urllib.parse.quote(str(filter_map.get("year", "")))
            + "&lang=" + urllib.parse.quote(str(filter_map.get("lang", "")))
            + "&version=&state=&letter=&by=time&level=0&weekday=&page=" + str(pg or 1)
        )
        html = self._get(self.host + "/index.php/ds_api/vod", data)
        lst = []
        pagecount = 1
        try:
            d = json.loads(html)
            if d and d.get("code") == 1:
                pagecount = d.get("pagecount") or 1
                for v in d.get("list", []):
                    lst.append({
                        "vod_id": str(v.get("vod_id", "")),
                        "vod_name": v.get("vod_name", "") or "",
                        "vod_pic": v.get("vod_pic", "") or "",
                        "vod_remarks": v.get("vod_remarks", "") or (v.get("vod_score") or ""),
                        "vod_actor": v.get("vod_actor", "") or "",
                    })
        except Exception:
            pass
        return {"list": lst, "page": int(pg or 1), "pagecount": pagecount}

    # ============ 分类 ============
    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(str(pg or 1))
        except Exception:
            pg = 1
        fmap = {}
        try:
            if isinstance(filter, dict):
                fmap.update(filter)
        except Exception:
            pass
        try:
            if isinstance(extend, dict):
                for k, v in extend.items():
                    if v not in (None, "") and k not in fmap:
                        fmap[k] = v
        except Exception:
            pass
        r = self._fetch_list(str(tid or ""), pg, fmap)
        return {"list": r["list"], "page": r["page"], "pagecount": r["pagecount"], "limit": len(r["list"]), "total": r["pagecount"] * max(len(r["list"]), 1)}

    # ============ 搜索 ============
    def searchContent(self, key, quick, pg="1"):
        kw = urllib.parse.quote(str(key or "").strip(), safe="")
        if not kw:
            return {"list": [], "page": 1, "pagecount": 1}
        html = self._get(self.host + "/vodsearch/-------------.html?wd=" + kw)
        lst = []
        # 搜索卡片
        re_card = re.compile(r'<div class="detail-pic">[\s\S]*?data-src="([^"]+)"[\s\S]*?alt="([^"]*)"[\s\S]*?<a[^>]+href="/voddetail/(\d+)\.html"[^>]*>[\s\S]*?<h3[^>]*>([^<]*)</h3>')
        seen = set()
        for m in re_card.finditer(html):
            vid = m.group(3)
            if vid in seen:
                continue
            seen.add(vid)
            lst.append({
                "vod_id": vid,
                "vod_name": self._clean(m.group(4)) or self._clean(m.group(2)),
                "vod_pic": m.group(1),
                "vod_remarks": "",
            })
        # 兜底：任意 voddetail 链接
        if not lst:
            re2 = re.compile(r'<a[^>]+href="/voddetail/(\d+)\.html"[^>]*>([^<]{2,40})</a>')
            for m in re2.finditer(html):
                vid = m.group(1)
                if vid in seen:
                    continue
                seen.add(vid)
                lst.append({"vod_id": vid, "vod_name": self._clean(m.group(2)), "vod_pic": "", "vod_remarks": ""})
        return {"list": lst, "page": 1, "pagecount": 1}

    # ============ 详情 ============
    def detailContent(self, ids):
        vid = ""
        try:
            vid = re.sub(r"\D", "", str(ids[0] if isinstance(ids, (list, tuple)) else ids))
        except Exception:
            pass
        if not vid:
            return {"list": []}
        html = self._get(self.host + "/voddetail/%s.html" % vid)
        if not html:
            return {"list": []}
        vod = {"vod_id": vid, "vod_name": "", "vod_pic": "", "vod_content": "", "vod_actor": "", "vod_director": "", "vod_remarks": "", "vod_play_url": "", "vod_play_from": ""}

        m = re.search(r"<h1[^>]*>([^<]{2,50})</h1>", html)
        if not m:
            m = re.search(r"<title>([^<]{2,50})", html)
        if m:
            vod["vod_name"] = re.sub(r"_电影.*|_连续剧.*|_纪录片.*|_综艺.*|_漫剧.*", "", self._clean(m.group(1)))

        # 封面
        m = re.search(r'<img[^>]+class="lazy[^"]*"[^>]+src="data:image[^"]*"[^>]*data-src="([^"]+)"', html)
        if not m:
            m = re.search(r'detail-pic[\s\S]*?<img[^>]+data-src="([^"]+)"', html)
        if not m:
            m = re.search(r'<img[^>]+data-src="([^"]+\.(?:jpg|jpeg|png|webp))"', html)
        if m:
            vod["vod_pic"] = m.group(1)

        m = re.search(r'id="height_limit"[^>]*>([\s\S]*?)</div>', html)
        if m:
            vod["vod_content"] = self._clean(m.group(1))
        m = re.search(r"导演\s*:\s*</strong>([\s\S]*?)</div>", html)
        if m:
            vod["vod_director"] = self._clean(m.group(1))
        m = re.search(r"演员\s*:\s*</strong>([\s\S]*?)</div>", html)
        if m:
            vod["vod_actor"] = self._clean(m.group(1))
        m = re.search(r"更新：</em>([^<]+)", html)
        if m:
            vod["vod_remarks"] = self._clean(m.group(1))

        # 资源列表：源 tab + 集数 box
        src_names = []
        tab_m = re.search(r'<div class="anthology-tab[\s\S]*?<div class="swiper-wrapper">([\s\S]*?)</div></div>', html)
        if tab_m:
            slide_re = re.compile(r'<a class="swiper-slide">[\s\S]*?</i>&nbsp;([^<]+?)(?:<span class="badge">\d+</span>)?</a>')
            for sm in slide_re.finditer(tab_m.group(1)):
                n = self._clean(sm.group(1))
                if n and n not in src_names:
                    src_names.append(n)

        box_re = re.compile(r'<div class="anthology-list-box[^"]*">[\s\S]*?<ul class="anthology-list-play[^"]*">([\s\S]*?)</ul>')
        boxes = [bm.group(1) for bm in box_re.finditer(html)]

        play_from, play_url = [], []
        line_count = max(len(src_names), len(boxes))
        ep_re = re.compile(r'<a[^>]+href="/vodplay/\d+-(\d+)-(\d+)\.html"[^>]*>([^<]*)</a>')
        for li in range(line_count):
            name = src_names[li] if li < len(src_names) else "线路%d" % (li + 1)
            box = boxes[li] if li < len(boxes) else ""
            eps = []
            for em in ep_re.finditer(box):
                title = self._clean(em.group(3)) or em.group(2)
                eps.append(title + "$" + self.host + "/vodplay/%s-%s-%s.html" % (vid, em.group(1), em.group(2)))
            if eps:
                play_from.append(name)
                play_url.append("#".join(eps))

        # 兜底：直接按 sid 分组
        if not play_from:
            all_ep_re = re.compile(r'<a[^>]+href="/vodplay/(\d+)-(\d+)-(\d+)\.html"[^>]*>([^<]*)</a>')
            groups = {}
            for em in all_ep_re.finditer(html):
                sid, nid = em.group(2), em.group(3)
                title = self._clean(em.group(4)) or nid
                groups.setdefault(sid, []).append(title + "$" + self.host + "/vodplay/%s-%s-%s.html" % (vid, sid, nid))
            for idx, sid in enumerate(groups.keys()):
                play_from.append("线路%d" % (idx + 1))
                play_url.append("#".join(groups[sid]))

        vod["vod_play_from"] = "$$$".join(play_from)
        vod["vod_play_url"] = "$$$".join(play_url)
        return {"list": [vod]}

    # ============ 播放 ============
    def playerContent(self, flag, id, vipFlags=None):
        url = str(id or "").strip()
        if not url:
            return {"parse": 0, "url": ""}
        if not url.startswith("http"):
            url = self.host + url
        html = self._get(url)
        # player_aaaa encrypt:2 → base64decode → unquote（花括号配对解析，防内层 } 截断）
        idx = html.find("player_aaaa")
        if idx >= 0:
            seg = html[idx:idx + 3000]
            start = seg.find("{")
            if start >= 0:
                depth = 0
                raw = ""
                for i in range(start, len(seg)):
                    ch = seg[i]
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            raw = seg[start:i + 1]
                            break
                if raw:
                    try:
                        cfg = json.loads(raw)
                        enc = cfg.get("encrypt")
                        raw_url = cfg.get("url", "")
                        if enc == 2 and raw_url:
                            try:
                                dec = base64.b64decode(raw_url).decode("utf-8", "ignore")
                                dec = urllib.parse.unquote(dec)
                                if dec:
                                    return {"parse": 0, "url": dec, "header": {"User-Agent": self.UA, "Referer": self.host + "/"}}
                            except Exception:
                                pass
                    except Exception:
                        pass
        # 兜底：页面内任意 m3u8/mp4
        m = re.search(r'https?://[^\s"\'<>]+\.(?:m3u8|mp4)[^\s"\'<>]*', html.replace("\\/", "/"))
        if m:
            return {"parse": 0, "url": m.group(0).strip(), "header": {"User-Agent": self.UA, "Referer": self.host + "/"}}
        # 最后：返回播放页让 App 嗅探
        return {"parse": 1, "url": url, "header": {"User-Agent": self.UA, "Referer": self.host + "/"}}

    def isVideoFormat(self, url):
        try:
            s = str(url or "").lower()
            return ".m3u8" in s or ".mp4" in s or ".flv" in s
        except Exception:
            return False

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    def destroy(self):
        return None
