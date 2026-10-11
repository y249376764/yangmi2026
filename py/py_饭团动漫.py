# -*- coding: utf-8 -*-
"""
饭团动漫 - acgfta.com
MacCMS（PHP，Cloudflare 后端）+ ft-v2 模板，服务端渲染，无签名/无加密。

已实测验证的关键结论：
1. 站点为 MacCMS，数据全部服务端渲染 HTML，直接 curl 抓取解析即可。
   另有原生 ajax 列表接口 /index.php/ajax/data?mid=1&page=N&limit=M 可用
   （返回 JSON，含 vod_id/vod_name/vod_pic/vod_remarks/vod_blurb 等，分页精确）。
   注意：搜索接口 /index.php/ajax/suggest 与 ajax/data?wd= 均返回 400，
   搜索必须走伪静态页 /search.html?wd=。
2. 路由（自定义伪静态）：
   首页      /
   全部动漫  /index.php/ajax/data?mid=1&page={n}&limit=24   （原生 ajax，主分类）
   最近更新  /ft/recent.html          分页 /ft/recent/file/recent/page/{n}.html
   剧场版    /ft/top-movie.html       分页 /ft/top-movie/file/top-movie/page/{n}.html
   榜单      /ft/leaderboard.html     参数 ?l=day|week|month
   详情页    /anime/{id}.html
   播放页    /play/{id}-{sid}-{nid}.html
   搜索      /search.html?wd=关键词    分页 /search/page/{n}/wd/{关键词}.html
   （注：/ft/archive.html 是季番索引页，不含影片卡片，不适合做影片分类。）
3. 卡片结构（以 a.stretched-link 为锚点通用解析，兼容两种）：
   A. 列表卡（recent/top-movie/search）：
      <div class="col anime-card">
        <img class="anime-cover" alt="片名" data-src="封面">
        <p class="semibold mb-0">更新至第xx集</p>
        <a class="stretched-link" href="/anime/{id}.html">片名</a>
   B. 榜单卡（leaderboard，链接 a 内文本为空、片名在 img alt / p 里）：
      <div class="leaderboard-card ..."> ... <a class="stretched-link" href="/anime/{id}.html"></a></div>
4. 详情页：
   标题 <h1> 或 detail 区首个标题；封面 img.anime-cover 的 data-src；
   简介 div.detail-anime-intro；年份等元信息在文本里。
   线路：<button data-bs-target="#线路一">（线路一..六）
   集数：<div class="anime-episode ... tab-pane" id="线路一">
         <a class="btn btn-episode" href="/play/{id}-{sid}-{nid}.html">第01集</a>
   **注意**：tab 顺序与 sid 不对应（线路一的 sid 可能不是 1），必须按 pane 里的 href 实际取值。
5. 播放页 /play/{id}-{sid}-{nid}.html：
   var player_aaaa={...,"encrypt":0,"url":"https://.../index.m3u8",...}
   encrypt=0 时 url 即真实直链（m3u8），无需 Referer，可直接播放。
"""
import re
import json
import time
import html as html_mod
import requests
from urllib.parse import quote

try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def __init__(self):
            pass


class Spider(Spider):
    # ==================== 基础配置 ====================
    name = "饭团动漫"
    base_url = "https://acgfta.com"
    site_url = "https://acgfta.com"

    searchable = 1
    quickSearch = 1
    filterable = 1
    changeable = 1

    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://acgfta.com/",
    }

    play_headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
        "Accept": "*/*",
    }

    # 分类定义：type_id -> (名称, 列表路径, 分页路径模板)
    CATEGORY_NAMES = {
        "all": "全部动漫",
        "recent": "最近更新",
        "top-movie": "剧场版",
        "leaderboard": "榜单",
    }

    def __init__(self):
        super().__init__()
        self._session = requests.Session()
        self._session.headers.update(self.headers)
        self._play_cache = {}
        self._cache_ttl = 1800
        self._last_req_time = 0
        self._min_req_interval = 0.6

        self._re_card = re.compile(
            r'<div class="col anime-card">(.*?)<a class="stretched-link"[^>]*'
            r'href="(?:https?://acgfta\.com)?/anime/(\d+)\.html"[^>]*>\s*([^<]*?)\s*</a>',
            re.S)

    # ==================== 工具方法 ====================
    def _log(self, msg):
        print("[%s] %s" % (self.name, msg))

    @staticmethod
    def _attr(tag, name):
        m = re.search(r'%s\s*=\s*"([^"]*)"' % name, tag)
        return m.group(1) if m else ""

    def _clean_text(self, text):
        if not text:
            return ""
        text = html_mod.unescape(text)
        text = re.sub(r'<[^>]+>', '', text)
        return re.sub(r'\s+', ' ', text).strip()

    def _apply_req_delay(self):
        now = time.time()
        elapsed = now - self._last_req_time
        if 0 < elapsed < self._min_req_interval:
            time.sleep(self._min_req_interval - elapsed)
        self._last_req_time = time.time()

    # ==================== 请求基础 ====================
    def _is_bad_page(self, html):
        if not html:
            return True
        if '<title>404' in html or 'Not Found' in html[:2000] and len(html) < 3000:
            return True
        return False

    def _get(self, url, max_retry=2, timeout=20):
        for attempt in range(max_retry):
            self._apply_req_delay()
            try:
                resp = self._session.get(url, timeout=timeout, allow_redirects=True)
                if resp.status_code >= 400:
                    self._log("HTTP %s: %s" % (resp.status_code, url))
                    if attempt < max_retry - 1:
                        time.sleep(1 + attempt)
                        continue
                    return ""
                html = resp.text
                if self._is_bad_page(html):
                    if attempt < max_retry - 1:
                        time.sleep(1 + attempt)
                        continue
                    return ""
                return html
            except Exception as e:
                self._log("请求失败: %s, %s" % (url, e))
                if attempt < max_retry - 1:
                    time.sleep(1 + attempt)
        return ""

    # ==================== 列表解析 ====================
    def _parse_cards(self, html):
        """
        通用卡片解析：以 <a class="stretched-link" href="/anime/{id}.html"> 为锚点分段，
        兼容「最近更新 / 剧场版」（锚点带文本）与「榜单」（锚点文本为空、片名在 img alt）两种结构。
        """
        videos = []
        seen = set()
        if not html:
            return videos
        anchors = list(re.finditer(
            r'<a[^>]*class="[^"]*stretched-link[^"]*"[^>]*'
            r'href="(?:https?://acgfta\.com)?/anime/(\d+)\.html"[^>]*>\s*([^<]*?)\s*</a>',
            html))
        prev_end = 0
        for m in anchors:
            seg = html[prev_end:m.end()]
            prev_end = m.end()
            vod_id = m.group(1)
            name = self._clean_text(m.group(2))
            if vod_id in seen:
                continue
            im = re.search(r'<img[^>]*class="[^"]*anime-cover[^"]*"[^>]*>', seg)
            pic = ""
            if im:
                pic = self._attr(im.group(0), "data-src") or self._attr(im.group(0), "src")
            if not name and im:
                name = self._clean_text(self._attr(im.group(0), "alt"))
            note = ""
            nm = re.search(r'<p[^>]*>(更新至[^<]*)</p>', seg) or re.search(r'更新至\d+[集话]', seg)
            if nm:
                note = self._clean_text(nm.group(1) if nm.groups() else nm.group(0))
            seen.add(vod_id)
            videos.append({
                "vod_id": vod_id,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": note,
            })
        return videos

    def _parse_ajax_list(self, data):
        videos = []
        for x in (data or {}).get("list", []):
            pic = x.get("vod_pic") or ""
            if pic.startswith("/"):
                pic = self.base_url + pic
            videos.append({
                "vod_id": str(x.get("vod_id")),
                "vod_name": x.get("vod_name") or "",
                "vod_pic": pic,
                "vod_remarks": x.get("vod_remarks") or "",
            })
        return videos

    def _max_page(self, html):
        pages = [int(x) for x in re.findall(r'/page/(\d+)\.html', html)]
        return max(pages) if pages else 1

    # ==================== 播放地址解析 ====================
    def _extract_player_data(self, html):
        """提取 var player_aaaa={...}（JSON）"""
        if not html:
            return None
        m = re.search(r'var\s+player_aaaa\s*=\s*', html)
        if not m:
            return None
        start = m.end()
        while start < len(html) and html[start] != '{':
            start += 1
        if start >= len(html):
            return None
        depth = 1
        i = start + 1
        in_string = False
        escape = False
        while i < len(html) and depth > 0:
            c = html[i]
            if in_string:
                if escape:
                    escape = False
                elif c == '\\':
                    escape = True
                elif c == '"':
                    in_string = False
            else:
                if c == '"':
                    in_string = True
                elif c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
            i += 1
        if depth == 0:
            try:
                return json.loads(html[start:i])
            except Exception:
                pass
        return None

    def _get_play_url(self, vod_id, sid, nid):
        play_page = "%s/play/%s-%s-%s.html" % (self.base_url, vod_id, sid, nid)
        cache_key = "%s-%s-%s" % (vod_id, sid, nid)
        now = time.time()
        if cache_key in self._play_cache:
            url, ts = self._play_cache[cache_key]
            if now - ts < self._cache_ttl:
                return url
        try:
            html = self._get(play_page, max_retry=2, timeout=15)
            if not html:
                return play_page
            pd = self._extract_player_data(html)
            if not pd:
                return play_page
            enc_url = (pd.get("url") or "").strip()
            encrypt = str(pd.get("encrypt", "0"))
            self._log("player encrypt=%s url=%s..." % (encrypt, enc_url[:60]))
            if encrypt == "1":
                import urllib.parse
                enc_url = urllib.parse.unquote(enc_url)
            elif encrypt == "2":
                import base64
                import urllib.parse
                try:
                    enc_url = urllib.parse.unquote(base64.b64decode(enc_url).decode('utf-8'))
                except Exception:
                    pass
            if not enc_url:
                iframe = re.search(r'<iframe[^>]*src="([^"]+)"', html)
                if iframe:
                    enc_url = iframe.group(1)
                else:
                    return play_page
            self._play_cache[cache_key] = (enc_url, now)
            return enc_url
        except Exception as e:
            self._log("获取播放地址异常: %s" % e)
            return play_page

    # ==================== TVBox 核心方法 ====================
    def init(self, extend=''):
        self._log("初始化完成")

    def homeContent(self, filter=False):
        result = {
            "class": [
                {"type_id": tid, "type_name": name}
                for tid, name in self.CATEGORY_NAMES.items()
            ]
        }
        if filter:
            result["filters"] = {}
        return result

    def homeVideoContent(self):
        try:
            html = self._get(self.base_url + "/ft/recent.html")
            return {"list": self._parse_cards(html)[:30]}
        except Exception as e:
            self._log("homeVideoContent异常: %s" % e)
            return {"list": []}

    def categoryContent(self, tid, pg, filter=False, content=None):
        try:
            pg = max(1, int(pg or 1))
            tid = str(tid)
            if tid == "all":
                # 原生 MacCMS ajax 列表接口，分页精确
                ajax = "%s/index.php/ajax/data?mid=1&page=%d&limit=24" % (self.base_url, pg)
                self._log("分类请求: " + ajax)
                self._apply_req_delay()
                resp = self._session.get(ajax, timeout=20)
                data = json.loads(resp.text)
                videos = self._parse_ajax_list(data)
                return {
                    "list": videos,
                    "page": pg,
                    "pagecount": int(data.get("pagecount") or 1),
                    "limit": int(data.get("limit") or 24),
                    "total": int(data.get("total") or len(videos)),
                }
            if tid == "recent":
                url = ("%s/ft/recent.html" % self.base_url) if pg == 1 else \
                    ("%s/ft/recent/file/recent/page/%d.html" % (self.base_url, pg))
            elif tid == "top-movie":
                url = ("%s/ft/top-movie.html" % self.base_url) if pg == 1 else \
                    ("%s/ft/top-movie/file/top-movie/page/%d.html" % (self.base_url, pg))
            elif tid == "leaderboard":
                url = "%s/ft/leaderboard.html" % self.base_url
            else:
                url = "%s/ft/recent.html" % self.base_url
            self._log("分类请求: " + url)
            html = self._get(url)
            videos = self._parse_cards(html)
            pagecount = self._max_page(html) if tid in ("recent", "top-movie") else 1
            return {
                "list": videos,
                "page": pg,
                "pagecount": pagecount,
                "limit": len(videos) or 24,
                "total": len(videos) * pagecount,
            }
        except Exception as e:
            self._log("categoryContent异常: %s" % e)
            return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            pg = max(1, int(pg or 1))
            keyword = str(key or "").strip()
            if not keyword:
                return {"page": pg, "pagecount": 1, "limit": 0, "total": 0, "list": []}
            if pg == 1:
                url = "%s/search.html?wd=%s" % (self.base_url, quote(keyword))
            else:
                url = "%s/search/page/%d/wd/%s.html" % (self.base_url, pg, quote(keyword))
            self._log("搜索请求: %s" % url)
            html = self._get(url)
            videos = self._parse_cards(html)
            if not quick:
                key_lower = keyword.lower()

                def _score(v):
                    name = v.get("vod_name", "").lower()
                    if name == key_lower:
                        return 0
                    if name.startswith(key_lower):
                        return 1
                    if key_lower in name:
                        return 2
                    return 3
                videos = sorted(videos, key=_score)
            pagecount = self._max_page(html)
            return {
                "list": videos,
                "page": pg,
                "pagecount": pagecount,
                "limit": len(videos) or 30,
                "total": len(videos) * pagecount,
            }
        except Exception as e:
            self._log("searchContent异常: %s" % e)
            return {"list": [], "page": pg, "pagecount": 1, "limit": 30, "total": 0}

    def detailContent(self, ids):
        try:
            vod_id = str(ids[0] if isinstance(ids, list) else ids)
            url = "%s/anime/%s.html" % (self.base_url, vod_id)
            self._log("详情请求: " + url)
            html = self._get(url, max_retry=2, timeout=20)
            if not html:
                return {"list": []}

            # 标题
            vod_name = ""
            m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
            if m:
                vod_name = self._clean_text(m.group(1))
            if not vod_name:
                m = re.search(r'<title>([^<]*)', html)
                if m:
                    vod_name = self._clean_text(m.group(1).split("-")[0])
            # 封面
            vod_pic = ""
            m = re.search(r'<img[^>]*class="[^"]*anime-cover[^"]*"[^>]*>', html)
            if m:
                vod_pic = self._attr(m.group(0), "data-src") or self._attr(m.group(0), "src")
            # 简介
            vod_content = ""
            m = re.search(r'class="[^"]*detail-anime-intro[^"]*"[^>]*>(.*?)</div>', html, re.S)
            if m:
                vod_content = self._clean_text(m.group(1))
            # 年份
            vod_year = ""
            m = re.search(r'年份[：:]\s*([0-9]{4})', html)
            if m:
                vod_year = m.group(1)

            # 线路与集数：按 tab-pane 分组（id=线路名），解析其中 a.btn-episode
            sources = []
            for pm in re.finditer(
                    r'<div class="[^"]*anime-episode[^"]*tab-pane[^"]*"[^>]*id="([^"]+)"[^>]*>(.*?)</div>',
                    html, re.S):
                source_name, body = pm.group(1), pm.group(2)
                episodes = []
                for em in re.finditer(
                        r'<a[^>]*class="[^"]*btn-episode[^"]*"[^>]*href="[^"]*/play/(\d+)-(\d+)-(\d+)\.html"[^>]*>([^<]*)</a>',
                        body):
                    _, sid, nid, epname = em.groups()
                    episodes.append({
                        "name": self._clean_text(epname) or ("第%s集" % nid),
                        "link": "%s-%s-%s" % (vod_id, sid, nid),
                    })
                if episodes:
                    sources.append({"source_name": source_name, "episodes": episodes})

            if not sources:
                self._log("未能解析到播放源")
                return {"list": []}

            from_list = [s["source_name"] for s in sources]
            url_list = ["#".join("%s$%s" % (ep["name"], ep["link"]) for ep in s["episodes"])
                        for s in sources]

            video = {
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_year": vod_year,
                "vod_area": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": vod_content,
                "vod_remarks": "",
                "vod_play_from": "$$$".join(from_list),
                "vod_play_url": "$$$".join(url_list),
            }
            self._log("详情解析成功: %s 线路=%d" % (vod_name, len(sources)))
            return {"list": [video]}
        except Exception as e:
            self._log("detailContent异常: %s" % e)
            return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        try:
            parts = str(id).split("-")
            if len(parts) != 3:
                return {"parse": 0, "url": "", "header": ""}
            vod_id, sid, nid = parts
            play_url = self._get_play_url(vod_id, sid, nid)
            if not play_url:
                play_url = "%s/play/%s-%s-%s.html" % (self.base_url, vod_id, sid, nid)
            is_direct = bool(re.search(r'\.(m3u8|mp4|flv|ts|mkv)([?#&]|$)', play_url, re.I))
            is_webview = play_url.startswith(self.base_url + "/play/")
            parse_flag = 0 if (is_direct or not is_webview) else 1
            self._log("播放URL: %s... parse=%d" % (play_url[:80], parse_flag))
            if parse_flag == 0:
                return {"parse": 0, "url": play_url, "header": self.play_headers.copy()}
            return {"parse": 1, "url": play_url, "header": ""}
        except Exception as e:
            self._log("playerContent异常: %s" % e)
            return {"parse": 0, "url": "", "header": ""}

    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    def localProxy(self, param):
        pass