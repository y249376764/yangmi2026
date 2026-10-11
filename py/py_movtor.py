# -*- coding: utf-8 -*-
"""
movtor 电影库 - vipmov.cc
电影站（Cloudflare 前置），自定义模板 movtor + Tailwind，服务端渲染，curl 直连可用，无签名。

关键结论（已实测验证）：
1. 首页 / ：卡片 data-vid="{id}"，内 <a href="/movie/{id}/">、<img data-src="/img/id/{id}.jpg" alt="片名">；
   评分在左上角，画质角标（如 1080p）在右上角，年份在标题下方 <div ...> 1968 </div>。
2. 分类/筛选 /movie?class={类型}&area={地区}&year={年份}&sort_field={排序}&page={n}
   （page 从 0 开始，第1页可省略或 page=0）。类型 20 个、地区 54 个、年份含 2026..2000 与年代。
   sort_field：last_id(最新) / pub_date(上映) / scores.hot24h(热榜) / vote_count(评分)。
3. 详情 /movie/{id}/ ：结构化数据 <script type="application/ld+json"> 内含
   name/datePublished/genre/duration/director/actor/aggregateRating/image/description。
4. 播放 /movie/{id}/play ：页面内联
   const playUrl = "/api/video/play?dir={hash}&format=m3u8&h={h}&w={w}"
   直接请求该接口（注意把页面里的 \u0026 还原为 &）→ 返回 master m3u8
   （Content-Type application/vnd.apple.mpegurl，内含多条线路的 file.php 链接），可直连播放。
5. 搜索 /search?name={关键词}（结果卡片同列表）。
"""
import re
import json
import time
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
    name = "movtor电影库"
    base_url = "https://vipmov.cc"
    site_url = "https://vipmov.cc"

    searchable = 1
    quickSearch = 1
    filterable = 1
    changeable = 1

    class_name = ["电影"]
    class_url = ["movie"]
    CATEGORY_NAMES = {"movie": "电影"}

    # 筛选选项（取自 /movie 页面）
    FILTER_CLASS = ["剧情", "喜剧", "动作", "科幻", "悬疑", "爱情", "动画", "奇幻", "文艺",
                    "犯罪", "西部", "家庭", "冒险", "战争", "恐怖", "音乐", "电视电影",
                    "惊悚", "纪录", "历史"]
    FILTER_AREA = ["中国", "美国", "日本", "韩国", "英国", "法国", "德国", "印度", "泰国",
                   "中国香港", "中国台湾", "意大利", "西班牙", "加拿大", "澳大利亚", "俄罗斯"]
    FILTER_YEAR = ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019", "2018",
                   "2017", "2016", "2015", "2014", "2013", "2012", "2011", "2010"]
    FILTER_SORT = [("last_id", "最新"), ("pub_date", "上映"), ("scores.hot24h", "热榜"),
                   ("vote_count", "评分")]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://vipmov.cc/",
        "Connection": "keep-alive",
    }

    play_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://vipmov.cc/",
        "Accept": "*/*",
    }

    def __init__(self):
        super().__init__()
        self._session = requests.Session()
        self._session.headers.update(self.headers)
        self._play_cache = {}
        self._cache_ttl = 1800
        self._last_req_time = 0
        self._min_req_interval = 0.8

    # ==================== 工具方法 ====================
    def _log(self, msg):
        print("[%s] %s" % (self.name, msg))

    def _clean_html(self, text):
        if not text:
            return ""
        text = re.sub(r'<br\s*/?>', ' ', text)
        text = re.sub(r'<[^>]+>', '', text)
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _fix_pic(self, pic):
        if not pic:
            return ""
        pic = pic.strip()
        if pic.startswith("//"):
            return "https:" + pic
        if pic.startswith("/"):
            return self.base_url + pic
        return pic

    # ==================== 请求基础 ====================
    def _apply_req_delay(self):
        now = time.time()
        elapsed = now - self._last_req_time
        if 0 < elapsed < self._min_req_interval:
            time.sleep(self._min_req_interval - elapsed)
        self._last_req_time = time.time()

    def fetch(self, url, headers=None, timeout=30):
        self._apply_req_delay()
        return self._session.get(url, headers=headers or {}, timeout=timeout)

    def _is_bad_page(self, html):
        if not html:
            return True
        if '404 Not Found' in html or 'System Error' in html:
            return True
        return False

    def _get(self, url, max_retry=3, timeout=15):
        try:
            for attempt in range(max_retry):
                resp = self.fetch(url, headers=self.headers, timeout=timeout)
                html = resp.text
                if self._is_bad_page(html):
                    self._log("页面异常(%s)，重试 %s" % (resp.status_code, url))
                    if attempt < max_retry - 1:
                        time.sleep(1 + attempt)
                        continue
                    return ""
                return html
            return ""
        except Exception as e:
            self._log("请求失败: %s, %s" % (url, e))
            return ""

    # ==================== 列表解析 ====================
    def _parse_video_list(self, html):
        """以 data-vid 为锚点解析卡片（首页/分类/搜索通用）"""
        videos = []
        if not html:
            return videos
        for m in re.finditer(r'data-vid="([A-Za-z0-9]+)"', html):
            vod_id = m.group(1)
            block = html[m.start():m.start() + 1500]
            im = re.search(r'<img[^>]*data-src="([^"]+)"[^>]*alt="([^"]*)"', block)
            if not im:
                im = re.search(r'<img[^>]*alt="([^"]*)"[^>]*data-src="([^"]+)"', block)
                if im:
                    alt, pic = im.group(1), im.group(2)
                else:
                    continue
            else:
                pic, alt = im.group(1), im.group(2)
            tm = re.search(r'title="([^"]*)"', block)
            title = alt.strip() or (tm.group(1).strip() if tm else "")
            if not title:
                continue
            ym = re.search(r'font-semibold[^>]*>\s*(\d{4})\s*<', block)
            qm = re.search(r'tracking-wider rounded">\s*([^<]*?)\s*<', block)
            videos.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": self._fix_pic(pic),
                "vod_remarks": self._clean_html(qm.group(1)) if qm else (ym.group(1) if ym else ""),
            })
        return videos

    # ==================== 播放地址解析 ====================
    def _get_play_url(self, vod_id):
        """访问 /movie/{id}/play 页，取出内联 playUrl，拼成绝对接口地址"""
        cache_key = str(vod_id)
        now = time.time()
        if cache_key in self._play_cache:
            url, ts = self._play_cache[cache_key]
            if now - ts < self._cache_ttl:
                return url
        play_page = "%s/movie/%s/play" % (self.base_url, vod_id)
        try:
            html = self._get(play_page, max_retry=2, timeout=15)
            if not html:
                return ""
            m = re.search(r'const\s+playUrl\s*=\s*"([^"]+)"', html)
            if not m:
                self._log("未找到 playUrl")
                return ""
            path = m.group(1).replace('\\u0026', '&').replace('\\/', '/').strip()
            if path.startswith("//"):
                url = "https:" + path
            elif path.startswith("/"):
                url = self.base_url + path
            else:
                url = path
            self._log("播放接口: %s" % url[:110])
            self._play_cache[cache_key] = (url, now)
            return url
        except Exception as e:
            self._log("获取播放地址异常: %s" % e)
            return ""

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
            class_vals = [{"n": "全部", "v": ""}] + [{"n": c, "v": c} for c in self.FILTER_CLASS]
            area_vals = [{"n": "全部", "v": ""}] + [{"n": a, "v": a} for a in self.FILTER_AREA]
            year_vals = [{"n": "全部", "v": ""}] + [{"n": y, "v": y} for y in self.FILTER_YEAR]
            sort_vals = [{"n": n, "v": v} for v, n in self.FILTER_SORT]
            f = [
                {"key": "class", "name": "类型", "value": class_vals},
                {"key": "area", "name": "地区", "value": area_vals},
                {"key": "year", "name": "年份", "value": year_vals},
                {"key": "sort", "name": "排序", "value": sort_vals},
            ]
            result["filters"] = {tid: f for tid in self.CATEGORY_NAMES}
            result["filter"] = {tid: f for tid in self.CATEGORY_NAMES}
        return result

    def homeVideoContent(self):
        try:
            html = self._get(self.base_url)
            if not html:
                return {"list": []}
            videos = self._parse_video_list(html)
            seen = set()
            dedup = []
            for v in videos:
                if v["vod_id"] not in seen:
                    seen.add(v["vod_id"])
                    dedup.append(v)
            return {"list": dedup[:30]}
        except Exception as e:
            self._log("homeVideoContent异常: %s" % e)
            return {"list": []}

    def _build_movie_url(self, cls="", area="", year="", sort="", page=None):
        params = []
        if cls:
            params.append("class=" + quote(cls))
        if area:
            params.append("area=" + quote(area))
        if year:
            params.append("year=" + quote(year))
        if sort:
            params.append("sort_field=" + sort)
        if page is not None:
            params.append("page=%d" % page)
        qs = ("?" + "&".join(params)) if params else ""
        return "%s/movie%s" % (self.base_url, qs)

    def categoryContent(self, tid, pg, filter=False, content=None):
        try:
            pg = max(1, int(pg or 1))
            if str(tid) not in self.CATEGORY_NAMES:
                return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}
            content = content or {}
            cls = str(content.get("class", "") or "")
            area = str(content.get("area", "") or "")
            year = str(content.get("year", "") or "")
            sort = str(content.get("sort", "") or "")
            # page 从 0 开始：第 1 页用 page=0
            url = self._build_movie_url(cls=cls, area=area, year=year, sort=sort, page=pg - 1)
            self._log("分类请求: " + url)
            html = self._get(url)
            if not html:
                return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}
            videos = self._parse_video_list(html)
            pagecount = 1
            pages = re.findall(r'[?&]page=(\d+)', html)
            if pages:
                pagecount = max(int(x) for x in pages) + 1
            return {
                "list": videos,
                "page": pg,
                "pagecount": pagecount,
                "limit": 24,
                "total": pagecount * 24,
            }
        except Exception as e:
            self._log("categoryContent异常: %s" % e)
            return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            try:
                pg = max(1, int(pg or 1))
            except (TypeError, ValueError):
                pg = 1
            keyword = str(key or "").strip()
            if not keyword:
                return {"page": pg, "pagecount": 1, "limit": 0, "total": 0, "list": []}
            url = "%s/search?name=%s" % (self.base_url, quote(keyword))
            self._log("搜索请求: %s quick=%s" % (url, quick))
            html = self._get(url)
            if not html:
                return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}
            videos = self._parse_video_list(html)
            if not quick:
                key_lower = keyword.lower()

                def _score(v):
                    name = v.get('vod_name', '').lower()
                    if name == key_lower:
                        return 0
                    if name.startswith(key_lower):
                        return 1
                    if key_lower in name:
                        return 2
                    return 3
                videos = sorted(videos, key=_score)
            return {
                "list": videos,
                "page": pg,
                "pagecount": 9999,
                "limit": 24,
                "total": 999999,
            }
        except Exception as e:
            self._log("searchContent异常: %s" % e)
            return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}

    def detailContent(self, ids):
        try:
            vod_id = ids[0] if isinstance(ids, list) else str(ids)
            url = "%s/movie/%s/" % (self.base_url, vod_id)
            self._log("详情请求: " + url)
            html = self._get(url)
            if not html:
                return {"list": []}

            vod_name = ""
            vod_pic = ""
            vod_year = vod_area = vod_actor = vod_director = vod_remarks = vod_content = ""
            vod_score = ""

            # 优先从 ld+json 提取
            m = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
            if m:
                try:
                    d = json.loads(m.group(1).strip())
                    vod_name = d.get("name", "") or ""
                    vod_pic = self._fix_pic(d.get("image", "") or "")
                    pub = d.get("datePublished", "") or ""
                    vod_year = pub[:4] if pub else ""
                    genres = d.get("genre", [])
                    if isinstance(genres, str):
                        genres = [genres]
                    dirs = d.get("director", [])
                    if isinstance(dirs, dict):
                        dirs = [dirs]
                    vod_director = ",".join(x.get("name", "") for x in dirs if isinstance(x, dict))
                    acts = d.get("actor", [])
                    if isinstance(acts, dict):
                        acts = [acts]
                    vod_actor = ",".join(x.get("name", "") for x in acts if isinstance(x, dict))
                    rating = d.get("aggregateRating", {})
                    if isinstance(rating, dict) and rating.get("ratingValue"):
                        vod_score = str(rating.get("ratingValue"))
                    vod_content = self._clean_html(d.get("description", "") or "")
                    vod_remarks = "|".join(genres) if genres else ""
                except Exception as e:
                    self._log("ld+json 解析失败: %s" % e)

            if not vod_name:
                tm = re.search(r'<title>([^<]*)</title>', html)
                if tm:
                    vod_name = self._clean_html(tm.group(1).split("免费")[0].split("在线")[0]).strip()
            if not vod_pic:
                pm = re.search(r'<img[^>]*data-src="([^"]+)"', html)
                if pm:
                    vod_pic = self._fix_pic(pm.group(1))

            if not vod_content:
                dm = re.search(r'<meta name="description" content="([^"]*)"', html)
                if dm:
                    vod_content = self._clean_html(dm.group(1))

            # 单线路：正片
            from_list = ["movtor"]
            url_list = ["正片$%s" % vod_id]

            video = {
                "vod_id": vod_id,
                "vod_name": vod_name or "未知",
                "vod_pic": vod_pic,
                "vod_year": vod_year,
                "vod_area": vod_area,
                "vod_actor": vod_actor,
                "vod_director": vod_director,
                "vod_content": vod_content,
                "vod_remarks": vod_remarks or (("%s分" % vod_score) if vod_score else ""),
                "vod_play_from": "$$$".join(from_list),
                "vod_play_url": "$$$".join(url_list),
            }
            self._log("详情解析成功: %s" % video["vod_name"])
            return {"list": [video]}
        except Exception as e:
            self._log("detailContent异常: %s" % e)
            return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        try:
            vod_id = str(id).split("-")[0].split("$")[-1].strip()
            play_url = self._get_play_url(vod_id)
            if not play_url:
                return {"parse": 0, "url": "", "header": ""}
            return {"parse": 0, "url": play_url, "header": self.play_headers.copy()}
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