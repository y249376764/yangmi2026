# -*- coding: utf-8 -*-
"""
海天影视 - www.seaskytv.com
MacCMS 10 + conch 模板（服务端渲染），无滑动验证。

关键结论（已实测验证）：
1. 该站开放了 MacCMS 原生 ajax 数据接口（比扒 HTML 干净）：
   - 列表：/index.php/ajax/data?mid=1&tid={type_id}&page={pg}&limit={n}
          返回 {"page","pagecount","limit","total","list":[vod...]}
   - 详情：/index.php/ajax/data?mid=1&ids={vod_id}
   - 搜索建议：/index.php/ajax/suggest?mid=1&wd={关键词}
          （返回 [{"id","name","en","pic"}]，只给 id/名称，需再取详情）
   ※ /api.php/provide/vod 官方采集接口已关闭（返回 "closed"）。
2. 播放线路与集数不在 JSON 里，需从播放页 HTML 解析：
   - 播放页 /index.php/vod/play/id/{id}/sid/{sid}/nid/{nid}.html
   - 集数：a[href=/index.php/vod/play/id/{id}/sid/{sid}/nid/{nid}.html]，按 sid 分组
   - 线路名：#NumTab .playnow_info 文本（"线路一/线路二"），去掉 icon
   - 播放直链：var player_aaaa={"flag":"play","encrypt":0,"url":"https://.../index.m3u8",...}
     encrypt=0 时 url 即真实直链，parse=0 可直接播放；空则回退页面地址。
3. 详情页 /index.php/vod/detail/id/{id}.html 含片名/演员/导演/年份/地区/剧情等；
   注意详情页 HTML 只给"立即播放"入口，完整集数在播放页，因此本插件用
   详情页(取在线路与元数据) + 播放页(取集数)。
"""
import re
import json
import time
import requests
from urllib.parse import quote

try:
    from base.spider import Spider
except ImportError:
    class Spider(object):
        def __init__(self):
            pass


class Spider(Spider):
    # ==================== 基础配置 ====================
    name = "海天影视"
    base_url = "https://www.seaskytv.com"
    site_url = "https://www.seaskytv.com"

    searchable = 1
    quickSearch = 1
    filterable = 1

    # 主分类（MacCMS type_id）：电影(1)/连续剧(2)/综艺(3)/动漫(4)
    class_name = ["电影", "连续剧", "综艺", "动漫"]
    class_url = ["1", "2", "3", "4"]
    CATEGORY_NAMES = {"1": "电影", "2": "连续剧", "3": "综艺", "4": "动漫"}

    # 子类筛选（电影/剧集题材），来自首页导航实测
    FILTERS = {
        "1": [("6", "动作"), ("7", "喜剧"), ("8", "爱情"), ("9", "科幻"),
              ("10", "恐怖"), ("11", "剧情"), ("12", "战争"), ("21", "悬疑"),
              ("22", "惊悚"), ("23", "犯罪"), ("24", "动画"), ("25", "奇幻")],
        "2": [("13", "国产"), ("14", "港台"), ("15", "日韩"), ("16", "欧美"),
              ("20", "泰剧")],
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://www.seaskytv.com/",
        "Connection": "keep-alive",
    }

    play_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.seaskytv.com/",
        "Accept": "*/*",
    }

    def __init__(self):
        super().__init__()
        self._session = requests.Session()
        self._session.headers.update(self.headers)
        self._play_cache = {}
        self._cache_ttl = 1800
        self._last_req_time = 0
        self._min_req_interval = 0.6

    # ==================== 工具方法 ====================
    def _log(self, msg):
        print("[%s] %s" % (self.name, msg))

    def _clean_html(self, text):
        if not text:
            return ""
        text = re.sub(r'<[^>]+>', '', text)
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
        return re.sub(r'\s+', ' ', text).strip()

    # ==================== 请求基础 ====================
    def _apply_req_delay(self):
        now = time.time()
        elapsed = now - self._last_req_time
        if 0 < elapsed < self._min_req_interval:
            time.sleep(self._min_req_interval - elapsed)
        self._last_req_time = time.time()

    def _get(self, url, max_retry=2, timeout=15):
        for attempt in range(max_retry):
            try:
                self._apply_req_delay()
                resp = self._session.get(url, headers=self.headers, timeout=timeout)
                return resp
            except Exception as e:
                self._log("请求失败 %s (%s/%s): %s" % (url, attempt + 1, max_retry, e))
                if attempt < max_retry - 1:
                    time.sleep(0.8 + attempt)
        return None

    def _get_json(self, url, timeout=15):
        resp = self._get(url, timeout=timeout)
        if resp is None:
            return None
        try:
            return resp.json()
        except Exception:
            return None

    # ==================== 列表解析 ====================
    def _parse_json_item(self, it):
        vod_id = str(it.get("vod_id"))
        remarks = it.get("vod_remarks") or it.get("vod_version") or ""
        return {
            "vod_id": vod_id,
            "vod_name": it.get("vod_name") or "",
            "vod_pic": it.get("vod_pic") or "",
            "vod_remarks": remarks,
        }

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
            filters = {}
            for tid, opts in self.FILTERS.items():
                filters[tid] = [{
                    "key": "tid",
                    "name": "类型",
                    "value": [{"n": n, "v": v} for v, n in opts],
                }]
            result["filters"] = filters
        return result

    def homeVideoContent(self):
        try:
            url = "%s/index.php/ajax/data?mid=1&page=1&limit=30" % self.base_url
            data = self._get_json(url)
            lst = (data or {}).get("list") or []
            return {"list": [self._parse_json_item(x) for x in lst]}
        except Exception as e:
            self._log("homeVideoContent异常: %s" % e)
            return {"list": []}

    def categoryContent(self, tid, pg, filter=False, content=None):
        try:
            pg = max(1, int(pg or 1))
            if str(tid) not in self.CATEGORY_NAMES:
                return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}
            type_id = int(tid)
            if content and isinstance(content, dict) and content.get("tid"):
                try:
                    type_id = int(content["tid"])
                except (TypeError, ValueError):
                    pass
            url = "%s/index.php/ajax/data?mid=1&tid=%s&page=%d&limit=24" % (self.base_url, type_id, pg)
            self._log("分类请求: tid=%s pg=%s" % (type_id, pg))
            data = self._get_json(url)
            if not data:
                return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}
            videos = [self._parse_json_item(x) for x in (data.get("list") or [])]
            return {
                "list": videos,
                "page": pg,
                "pagecount": data.get("pagecount") or 1,
                "limit": 24,
                "total": data.get("total") or 0,
            }
        except Exception as e:
            self._log("categoryContent异常: %s" % e)
            return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}

    def searchContent(self, key, quick=False, pg="1"):
        pg = max(1, int(pg or 1))
        keyword = str(key or "").strip()
        if not keyword:
            return {"page": pg, "pagecount": 1, "limit": 0, "total": 0, "list": []}
        try:
            # suggest 接口：快、只返回 id/名称，适合快速搜索
            url = "%s/index.php/ajax/suggest?mid=1&wd=%s" % (self.base_url, quote(keyword))
            self._log("搜索请求: %s pg=%s" % (keyword, pg))
            data = self._get_json(url)
            lst = (data or {}).get("list") or []
            videos = []
            for it in lst:
                videos.append({
                    "vod_id": str(it.get("id")),
                    "vod_name": it.get("name") or "",
                    "vod_pic": it.get("pic") or "",
                    "vod_remarks": "",
                })
            if not quick:
                key_lower = keyword.lower()

                def _score(v):
                    name = (v.get("vod_name") or "").lower()
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
                "pagecount": 1,
                "limit": len(videos),
                "total": (data or {}).get("total") or len(videos),
            }
        except Exception as e:
            self._log("searchContent异常: %s" % e)
            return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}

    # ==================== 详情 ====================
    def _fetch_play_page(self, vod_id, sid=1, nid=1):
        return "%s/index.php/vod/play/id/%s/sid/%s/nid/%s.html" % (self.base_url, vod_id, sid, nid)

    def _parse_play_sources(self, html, vod_id):
        """从播放页解析线路名与集数（按 sid 分组）"""
        # 线路名
        source_names = []
        m_tab = re.search(r'id="NumTab"[^>]*>(.*?)</div>', html, re.DOTALL)
        if m_tab:
            for m in re.finditer(r'<a[^>]*class="[^"]*playnow_info[^"]*"[^>]*>(.*?)</a>', m_tab.group(1), re.DOTALL):
                inner = m.group(1)
                inner = re.sub(r'<i[^>]*>.*?</i>', '', inner, flags=re.DOTALL)  # 去字体图标
                inner = re.sub(r'&#x[0-9a-fA-F]+;?', '', inner)               # 去图标实体
                nm = re.sub(r'<[^>]+>', '', inner).replace('&nbsp;', ' ').strip()
                if nm:
                    source_names.append(nm)

        # 集数按 sid 分组
        groups = {}
        for m in re.finditer(
                r'/index\.php/vod/play/id/(\d+)/sid/(\d+)/nid/(\d+)\.html"?[^>]*>([^<]{0,40})',
                html, re.DOTALL):
            vid, sid, nid, name = m.groups()
            if str(vid) != str(vod_id):
                continue
            name = re.sub(r'<[^>]+>', '', name).replace('&nbsp;', ' ').strip()
            groups.setdefault(sid, {})[int(nid)] = name  # dict 去重

        if not groups:
            return []
        sorted_sids = sorted(groups.keys(), key=lambda s: (min(groups[s].keys()), int(s) if str(s).isdigit() else 0))
        sources = []
        for i, sid in enumerate(sorted_sids):
            eps = sorted(groups[sid].items(), key=lambda x: x[0])
            name = source_names[i] if i < len(source_names) else "线路%s" % sid
            sources.append({
                "source_name": name,
                "episodes": [
                    {"name": n or ("第%d集" % nid), "link": "%s-%s-%s" % (vod_id, sid, nid)}
                    for nid, n in eps
                ],
            })
        return sources

    def detailContent(self, ids):
        try:
            vod_id = ids[0] if isinstance(ids, list) else str(ids)
            vod_id = str(vod_id).split("-")[0]
            self._log("详情请求: %s" % vod_id)

            # 元数据：详情页 HTML
            url = "%s/index.php/vod/detail/id/%s.html" % (self.base_url, vod_id)
            resp = self._get(url)
            html = resp.text if resp is not None else ""
            if not html:
                return {"list": []}

            title = re.search(r'<title>([^<]*?)(?:_[^<]*)?\s*-\s*[^<]*</title>', html)
            vod_name = self._clean_html(title.group(1)) if title else ""
            if not vod_name:
                tm = re.search(r'<h1[^>]*>([^<]*)</h1>', html)
                if tm:
                    vod_name = self._clean_html(tm.group(1))
            if not vod_name:
                vod_name = "未知"

            vod_pic = ""
            pic = re.search(r'class="[^"]*vodlist_thumb[^"]*"[^>]*(?:data-original|src)="([^"]+)"', html)
            if pic:
                vod_pic = pic.group(1)
            if not vod_pic:
                pic = re.search(r'<img[^>]*(?:data-original|data-src|src)="(https?://[^"]+)"', html)
                if pic:
                    vod_pic = pic.group(1)

            def _grab(label):
                m = re.search(r'<span>%s[：:]</span>\s*(?:<a[^>]*>|<em>)?([^<]*)' % label, html)
                if m:
                    return self._clean_html(m.group(1))
                m = re.search(r'%s[：:]</span>(.*?)</li>' % label, html, re.DOTALL)
                return self._clean_html(m.group(1)) if m else ""

            vod_actor = _grab("主演")
            vod_director = _grab("导演")
            vod_year = ""
            my = re.search(r'/vod/search/year/(\d+)\.html"[^>]*>([^<]*)<', html)
            if my:
                vod_year = my.group(2).strip()
            vod_area = ""
            ma = re.search(r'/vod/search/area/[^"]*"[^>]*>([^<]*)<', html)
            if ma:
                vod_area = ma.group(1).strip()
            vod_remarks = _grab("状态")
            vod_content = ""
            mc = re.search(r'<div[^>]*class="[^"]*content_desc[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
            if not mc:
                mc = re.search(r'<span[^>]*class="[^"]*content_desc[^"]*"[^>]*>(.*?)</span>', html, re.DOTALL)
            if mc:
                vod_content = self._clean_html(mc.group(1))

            # 线路与集数：播放页
            play_url = self._fetch_play_page(vod_id, 1, 1)
            presp = self._get(play_url)
            phtml = presp.text if presp is not None else ""
            sources = self._parse_play_sources(phtml, vod_id)
            if not sources:
                # 兜底：至少给一个可用入口，让 TVBox 能打开播放页
                sources = [{"source_name": "线路1",
                            "episodes": [{"name": "播放", "link": "%s-1" % vod_id}]}]

            from_list = [s["source_name"] for s in sources]
            url_list = ["#".join("%s$%s" % (ep["name"], ep["link"]) for ep in s["episodes"])
                        for s in sources]

            video = {
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_year": str(vod_year or ""),
                "vod_area": vod_area or "",
                "vod_actor": vod_actor or "",
                "vod_director": vod_director or "",
                "vod_content": vod_content or "",
                "vod_remarks": vod_remarks or "",
                "vod_play_from": "$$$".join(from_list),
                "vod_play_url": "$$$".join(url_list),
            }
            self._log("详情解析成功: %s 线路: %s" % (vod_name, "$$$".join(from_list)))
            return {"list": [video]}
        except Exception as e:
            self._log("detailContent异常: %s" % e)
            return {"list": []}

    # ==================== 播放 ====================
    def _extract_player_data(self, html):
        """提取 var player_aaaa={...}（手写 JSON 括号配平）"""
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
        cache_key = "%s-%s-%s" % (vod_id, sid, nid)
        now = time.time()
        if cache_key in self._play_cache:
            url, ts = self._play_cache[cache_key]
            if now - ts < self._cache_ttl:
                return url
        play_page = self._fetch_play_page(vod_id, sid, nid)
        resp = self._get(play_page, timeout=12)
        html = resp.text if resp is not None else ""
        if not html:
            return play_page
        pd = self._extract_player_data(html)
        if not pd:
            return play_page
        url = (pd.get("url") or "").strip()
        encrypt = str(pd.get("encrypt", "0"))
        if encrypt == "1" and url:
            import urllib.parse
            url = urllib.parse.unquote(url)
        if not url:
            iframe = re.search(r'<iframe[^>]*src="([^"]+)"', html)
            if iframe:
                url = iframe.group(1)
            else:
                return play_page
        self._play_cache[cache_key] = (url, now)
        return url

    def playerContent(self, flag, id, vipFlags=None):
        try:
            # id 形如 "{vod_id}-{nid}"，兼容 "{vod_id}-{sid}-{nid}"
            parts = str(id).split("-")
            if len(parts) == 3:
                vod_id, sid, nid = parts
            elif len(parts) == 2:
                vod_id, nid = parts
                sid = "1"
            else:
                return {"parse": 0, "url": "", "header": ""}

            play_url = self._get_play_url(vod_id, sid, nid)
            if not play_url:
                play_url = self._fetch_play_page(vod_id, sid, nid)
            is_direct = bool(re.search(r'\.(m3u8|mp4|flv|ts|mkv)([?#&]|$)', play_url, re.I))
            is_webview = play_url.startswith(self.base_url + "/index.php/vod/play/")
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