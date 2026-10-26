#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dmbus.cc - 动漫巴士 Spider（静态缓存版）

站点: https://dmbus.cc

缓存策略：
  首次进分类 → 抓 PRELOAD_PAGES 页合并、去重、写入磁盘 JSON
  再次进分类 → 命中缓存 0 请求，直接返回全部预加载内容
  翻到第 2 页 → 真实请求站点第 (PRELOAD_PAGES + page - 1) 页
  TTL 默认 6 小时，可设 0 永不过期

磁盘缓存路径：
  <cache_dir>/dmbus_cache/{tid}.json
  <cache_dir> 默认用当前脚本目录，可通过 init(cfg) 覆盖

清缓存：
  spider.clearCache()     清全部
  spider.clearCache("2")  清指定分类
"""

import re
import os
import gzip
import json
import time
import html as html_mod
import base64
import hashlib
from urllib.parse import quote, urljoin, unquote

try:
    import requests
    import urllib3
    urllib3.disable_warnings()
except ImportError:
    requests = None

try:
    import zstandard as zstd
    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def init(self, extend=""): pass
        def homeContent(self, filter): return {"class": [], "filters": {}}
        def homeVideoContent(self): return {"list": []}
        def categoryContent(self, tid, pg, filter, extend):
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}
        def detailContent(self, ids): return {"list": []}
        def playerContent(self, flag, id, vipFlags=None):
            return {"parse": 0, "playUrl": "", "url": "", "header": {}}
        def searchContent(self, key, quick, pg="1"):
            return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}
        def isVideoFormat(self, url): return False
        def manualVideoCheck(self): return False
        def localProxy(self, param): return [404, "text/plain", b""]


UA_PC = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
         "AppleWebKit/537.36 (KHTML, like Gecko) "
         "Chrome/120.0.0.0 Safari/537.36")
UA_MB = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
         "AppleWebKit/605.1.15 (KHTML, like Gecko) "
         "Version/16.0 Mobile/15E148 Safari/604.1")


# ============================================================
# 分类 & 筛选配置
# ============================================================
CLASSES = [
    {"type_id": "1", "type_name": "国漫"},
    {"type_id": "2", "type_name": "日漫"},
    {"type_id": "3", "type_name": "欧美动漫"},
    {"type_id": "4", "type_name": "电影"},
]

_MCID_OPTS = [
    {"n": "全部", "v": ""},
    {"n": "冒险", "v": "冒险"}, {"n": "奇幻", "v": "奇幻"},
    {"n": "战斗", "v": "战斗"}, {"n": "后宫", "v": "后宫"},
    {"n": "热血", "v": "热血"}, {"n": "励志", "v": "励志"},
    {"n": "搞笑", "v": "搞笑"}, {"n": "校园", "v": "校园"},
    {"n": "机战", "v": "机战"}, {"n": "悬疑", "v": "悬疑"},
    {"n": "治愈", "v": "治愈"}, {"n": "百合", "v": "百合"},
    {"n": "恐怖", "v": "恐怖"}, {"n": "泡面番", "v": "泡面番"},
    {"n": "恋爱", "v": "恋爱"}, {"n": "推理", "v": "推理"},
    {"n": "玄幻", "v": "玄幻"}, {"n": "科幻", "v": "科幻"},
    {"n": "日常", "v": "日常"},
]

_YEAR_OPTS = [{"n": "全部", "v": ""}] + [
    {"n": str(y), "v": str(y)} for y in range(2026, 2014, -1)
]

_ORDER_OPTS = [
    {"n": "按时间", "v": "time"},
    {"n": "按人气", "v": "hits"},
    {"n": "按评分", "v": "score"},
]


def _make_filters(tid):
    return [
        {"key": "mcid",  "name": "类型", "value": _MCID_OPTS},
        {"key": "year",  "name": "时间", "value": _YEAR_OPTS},
        {"key": "order", "name": "排序", "value": _ORDER_OPTS},
    ]


FILTERS = {c["type_id"]: _make_filters(c["type_id"]) for c in CLASSES}


# ============================================================
# 工具函数
# ============================================================
def _page(pg):
    try:
        v = int(str(pg or "").strip())
        return v if v > 0 else 1
    except Exception:
        return 1


def _fix_url(url, host):
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http"):
        return url
    if url.startswith("/"):
        return urljoin(host, url)
    return urljoin(host + "/", url)


def _unescape(s):
    return html_mod.unescape(s or "").strip()


def _strip_tags(s):
    return _unescape(re.sub(r'<[^>]+>', '', s or ''))


def _smart_decode(raw):
    if not raw:
        return ""
    if raw[:4] == b'\x28\xb5\x2f\xfd':
        print("[decode] raw zstd")
        if HAS_ZSTD:
            try:
                raw = zstd.ZstdDecompressor().decompress(raw)
            except Exception as e:
                print(f"[decode] zstd ERR {e}")
                return ""
        else:
            print("[decode] zstandard NOT installed! pip install zstandard")
            return ""
    elif raw[:2] == b'\x1f\x8b':
        print("[decode] raw gzip")
        try:
            raw = gzip.decompress(raw)
        except Exception as e:
            print(f"[decode] gzip ERR {e}")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("gbk", errors="replace")


# ============================================================
# 磁盘缓存工具
# ============================================================
class DiskCache:
    """简单磁盘 JSON 缓存：<cache_dir>/<key>.json"""

    def __init__(self, cache_dir, ttl=6 * 3600):
        self.cache_dir = cache_dir
        self.ttl = ttl
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
        except Exception as e:
            print(f"[cache] 创建缓存目录失败: {e}")

    def _path(self, key):
        # 保证 key 安全（避免路径穿越）
        safe = hashlib.md5(key.encode("utf-8")).hexdigest()
        return os.path.join(self.cache_dir, safe + ".json")

    def get(self, key):
        """命中返回 dict，否则返回 None"""
        path = self._path(key)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[cache] 读缓存失败 {path}: {e}")
            return None

        # TTL 检查（ttl=0 表示永不过期）
        if self.ttl > 0:
            ts = data.get("ts", 0)
            if time.time() - ts > self.ttl:
                print(f"[cache] 已过期 key={key}")
                try:
                    os.remove(path)
                except Exception:
                    pass
                return None
        return data

    def set(self, key, value):
        path = self._path(key)
        value["ts"] = time.time()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(value, f, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[cache] 写缓存失败 {path}: {e}")
            return False

    def clear(self, key=None):
        try:
            if key:
                p = self._path(key)
                if os.path.exists(p):
                    os.remove(p)
                    print(f"[cache] 删除 {p}")
            else:
                for f in os.listdir(self.cache_dir):
                    if f.endswith(".json"):
                        os.remove(os.path.join(self.cache_dir, f))
                print(f"[cache] 已清空 {self.cache_dir}")
        except Exception as e:
            print(f"[cache] clear ERR {e}")


# ============================================================
# Spider
# ============================================================
class Spider(BaseSpider):

    # 预加载页数
    PRELOAD_PAGES = 5
    # 缓存 TTL（秒），0 = 永不过期
    CACHE_TTL = 6 * 3600
    # 搜索限速
    SEARCH_INTERVAL = 10
    # 缓存目录名（相对脚本所在目录）
    CACHE_DIR_NAME = "dmbus_cache"

    def __init__(self):
        super().__init__()
        self.host = "https://dmbus.cc"
        self.name = "动漫巴士"
        self.sourceKey = "dmbus"
        self.timeout = 20
        self.s = None
        self._last_search_ts = 0

        # 缓存目录：优先脚本同目录，失败则用临时目录
        base_dir = os.path.dirname(os.path.abspath(__file__))
        cache_dir = os.path.join(base_dir, self.CACHE_DIR_NAME)
        try:
            os.makedirs(cache_dir, exist_ok=True)
        except Exception:
            import tempfile
            cache_dir = os.path.join(tempfile.gettempdir(),
                                     self.CACHE_DIR_NAME)
            os.makedirs(cache_dir, exist_ok=True)
        self.cache_dir = cache_dir
        self.cache = DiskCache(cache_dir, ttl=self.CACHE_TTL)
        print(f"[init] 缓存目录: {cache_dir}")

        if requests:
            self.s = requests.Session()
            self.s.verify = False

    def init(self, extend=""):
        if extend:
            try:
                cfg = json.loads(extend) if isinstance(extend, str) else extend
                if isinstance(cfg, dict):
                    if cfg.get("host"):
                        self.host = cfg["host"].rstrip("/")
                    if cfg.get("cache_dir"):
                        self.cache_dir = cfg["cache_dir"]
                        self.cache = DiskCache(self.cache_dir,
                                               ttl=self.CACHE_TTL)
                    if "cache_ttl" in cfg:
                        self.CACHE_TTL = int(cfg["cache_ttl"])
                        self.cache.ttl = self.CACHE_TTL
                    if cfg.get("preload_pages"):
                        self.PRELOAD_PAGES = int(cfg["preload_pages"])
            except Exception as e:
                print(f"[init] cfg parse ERR {e}")

    def getName(self): return self.name
    def getDependence(self): return ["requests", "zstandard"]
    def homeLayout(self): return 0

    def isVideoFormat(self, url):
        if not url:
            return False
        p = str(url).lower()
        return any(x in p for x in (".m3u8", ".mp4", ".flv", ".ts"))

    def manualVideoCheck(self): return False
    def localProxy(self, param): return [404, "text/plain", b""]

    # 手动清缓存
    def clearCache(self, key=None):
        self.cache.clear(key)

    # --------------------------------------------------------
    # 请求
    # --------------------------------------------------------
    def _fetch(self, url, ref=None):
        if not self.s:
            print("[fetch] requests not installed")
            return ""

        # 搜索限速
        if "/s" in url and "wd=" in url:
            now = time.time()
            elapsed = now - self._last_search_ts
            if elapsed < self.SEARCH_INTERVAL:
                wait = self.SEARCH_INTERVAL - elapsed
                print(f"[fetch] 搜索限速，等待 {wait:.1f}s")
                time.sleep(wait)
            self._last_search_ts = time.time()

        for attempt, ua in enumerate([UA_PC, UA_MB]):
            headers = {
                "User-Agent": ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate",
                "Referer": ref or (self.host + "/"),
                "Connection": "keep-alive",
            }
            try:
                r = self.s.get(url, headers=headers, timeout=self.timeout,
                               allow_redirects=True)
                raw = r.content or b""
                enc = (r.headers.get("content-encoding") or "").lower()
                print(f"[fetch] #{attempt+1} {r.status_code} raw={len(raw)} "
                      f"enc={enc or '-'} {url}")
                if r.status_code != 200 or not raw:
                    continue

                if enc in ("", "identity", "gzip", "deflate"):
                    try:
                        text = raw.decode("utf-8")
                    except UnicodeDecodeError:
                        text = _smart_decode(raw)
                else:
                    text = _smart_decode(raw)

                print(f"[fetch] text len={len(text)} head={text[:80]!r}")
                if len(text) < 500 or "<" not in text[:200]:
                    continue
                if "请不要频繁操作" in text:
                    print("[fetch] 触发站点限速")
                    return ""
                return text
            except Exception as e:
                print(f"[fetch] #{attempt+1} ERR {e} {url}")
        return ""

    # --------------------------------------------------------
    # 列表解析
    # --------------------------------------------------------
    def _parse_list(self, html):
        result, seen = [], set()
        if not html:
            return result

        blocks = re.findall(
            r'<li>\s*<div\s+class="item">([\s\S]*?)</div>\s*</li>',
            html)
        print(f"[parse_list] blocks={len(blocks)}")

        for blk in blocks:
            href, title = "", ""
            m = re.search(
                r'<a[^>]*class="title"[^>]*href="([^"]+)"[^>]*title="([^"]+)"',
                blk)
            if m:
                href, title = m.group(1), m.group(2)
            else:
                m1 = re.search(r'<a[^>]*class="title"[^>]*href="([^"]+)"', blk)
                m2 = re.search(r'<a[^>]*class="title"[^>]*title="([^"]+)"', blk)
                if not (m1 and m2):
                    continue
                href, title = m1.group(1), m2.group(1)

            if href.startswith("//"):
                href = "https:" + href
            elif href.startswith("/"):
                href = self.host + href
            elif not href.startswith("http"):
                href = self.host + "/" + href

            if href in seen:
                continue
            seen.add(href)

            pic = ""
            m = re.search(
                r'<a[^>]*class="[^"]*\bcover\b[^"]*"[^>]*\bdata-bg="([^"]+)"',
                blk)
            if not m:
                m = re.search(r'data-bg="([^"]+)"', blk)
            if not m:
                m = re.search(r'<img[^>]*\bdata-src="([^"]+)"', blk)
            if m:
                pic = _fix_url(m.group(1), self.host)

            remark = ""
            m = re.search(r'<span\s+class="desc"[^>]*>([^<]+)</span>', blk)
            if m:
                remark = _unescape(m.group(1))

            title = _unescape(title)
            if not title:
                continue

            result.append({
                "vod_id": href,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
            })

        print(f"[parse_list] parsed={len(result)}")
        return result

    # --------------------------------------------------------
    # 首页
    # --------------------------------------------------------
    def homeContent(self, filter):
        return {"class": CLASSES, "filters": FILTERS}

    def homeVideoContent(self):
        html = self._fetch(self.host + "/")
        return {"list": self._parse_list(html)}

    # --------------------------------------------------------
    # URL 拼接
    # --------------------------------------------------------
    def _build_list_url(self, tid, page):
        if page <= 1:
            return f"{self.host}/list-{tid}.html"
        return f"{self.host}/list-{tid}-{page}.html"

    def _build_filter_url(self, tid, extend):
        area   = str((extend or {}).get("area")   or "").strip()
        order  = str((extend or {}).get("order")  or "").strip()
        mcid   = str((extend or {}).get("mcid")   or "").strip()
        lang   = str((extend or {}).get("lang")   or "").strip()
        year   = str((extend or {}).get("year")   or "").strip()
        letter = str((extend or {}).get("letter") or "").strip()

        return (f"{self.host}/show-{tid}-"
                f"{quote(area, safe='')}-"
                f"{quote(order, safe='')}-"
                f"{quote(mcid, safe='')}-"
                f"{quote(lang, safe='')}-"
                f"{quote(year, safe='')}-"
                f"{quote(letter, safe='')}.html")

    # --------------------------------------------------------
    # 分类（磁盘缓存 + 预加载）
    # --------------------------------------------------------
    def categoryContent(self, tid, pg, filter, extend):
        page = _page(pg)
        tid = str(tid).strip()
        ext = extend or {}
        has_filter = any(
            str(ext.get(k) or "").strip()
            for k in ("mcid", "year", "order", "area", "lang", "letter")
        )

        print(f"[category] ===> tid={tid!r} page={page} "
              f"has_filter={has_filter} extend={ext!r}")

        # ================= 有筛选：直接请求，不缓存 =================
        if has_filter:
            url = self._build_filter_url(tid, ext)
            print(f"[category] 筛选 URL: {url}")
            html = self._fetch(url)
            items = self._parse_list(html) if html else []
            n = len(items)
            print(f"[category] <=== page=1 pagecount=1 count={n}")
            return {
                "list": items,
                "page": 1,
                "pagecount": 1,
                "limit": n or 20,
                "total": n,
            }

        # ================= 无筛选 =================
        cache_key = f"cate:{tid}"

        # ---------- 第 1 页：优先读缓存 ----------
        if page == 1:
            cached = self.cache.get(cache_key)
            if cached and cached.get("list"):
                print(f"[cache] HIT {cache_key} "
                      f"total={len(cached['list'])}")
                items = cached["list"]
                n = len(items)
                return {
                    "list": items,
                    "page": 1,
                    "pagecount": cached.get("pagecount", 9999),
                    "limit": n or 20,
                    "total": n,
                }

            # ---------- 未命中：抓 PRELOAD_PAGES 页合并 ----------
            print(f"[cache] MISS {cache_key} 开始抓取 "
                  f"{self.PRELOAD_PAGES} 页...")
            all_items, seen = [], set()
            pagecount = 9999

            for i in range(1, self.PRELOAD_PAGES + 1):
                u = self._build_list_url(tid, i)
                h = self._fetch(u)
                batch = self._parse_list(h) if h else []
                if not batch:
                    print(f"[cache] 站点第 {i} 页为空，停止")
                    break
                for it in batch:
                    if it["vod_id"] not in seen:
                        seen.add(it["vod_id"])
                        all_items.append(it)
                print(f"[cache] 第 {i}/{self.PRELOAD_PAGES} 页 "
                      f"累计 {len(all_items)} 条")

                # 第一页时顺便提一下站点尾页
                if i == 1 and h:
                    pgs = re.findall(
                        r'/list-' + re.escape(tid) + r'-(\d+)\.html', h)
                    if pgs:
                        site_max = max(int(p) for p in pgs)
                        pagecount = site_max - self.PRELOAD_PAGES + 1
                        if pagecount < 1:
                            pagecount = 1
                        print(f"[cache] 站点尾页={site_max} "
                              f"→ pagecount={pagecount}")

            # 落盘
            self.cache.set(cache_key, {
                "list": all_items,
                "pagecount": pagecount,
            })
            print(f"[cache] WRITE {cache_key} "
                  f"共 {len(all_items)} 条 pagecount={pagecount}")

            n = len(all_items)
            return {
                "list": all_items,
                "page": 1,
                "pagecount": pagecount,
                "limit": n or 20,
                "total": n,
            }

        # ---------- 第 2 页及以后：真实翻页 ----------
        real_page = self.PRELOAD_PAGES + (page - 1)
        u = self._build_list_url(tid, real_page)
        print(f"[category] 翻页请求站点第 {real_page} 页: {u}")
        h = self._fetch(u)
        items = self._parse_list(h) if h else []
        n = len(items)

        # 从缓存拿 pagecount
        cached = self.cache.get(cache_key)
        pagecount = cached.get("pagecount", 9999) if cached else 9999
        if not items:
            pagecount = page

        print(f"[category] <=== page={page} pagecount={pagecount} count={n}")
        return {
            "list": items,
            "page": page,
            "pagecount": pagecount,
            "limit": n or 20,
            "total": pagecount * 20 if pagecount < 9999 else 999999,
        }

    # --------------------------------------------------------
    # 二级详情
    # --------------------------------------------------------
    def detailContent(self, ids):
        raw = ids if isinstance(ids, (list, tuple)) else [ids]
        vid = str(raw[0] if raw else "").strip()
        if not vid:
            return {"list": []}

        url = vid if vid.startswith("http") else \
              self.host + ("" if vid.startswith("/") else "/") + vid
        html = self._fetch(url)
        if not html:
            return {"list": []}

        title = ""
        for pat in (
            r'<h1[^>]*class="[^"]*\bv_title\b[^"]*"[^>]*>\s*<a[^>]*>([^<]+)</a>',
            r'<h1[^>]*class="[^"]*\bv_title\b[^"]*"[^>]*>([^<]+)</h1>',
            r'<h1[^>]*>([^<]+)</h1>',
            r'<meta[^>]*property="og:title"[^>]*content="([^"]+)"',
        ):
            m = re.search(pat, html)
            if m:
                title = _unescape(m.group(1))
                title = re.sub(r'\s*[-|_]\s*(动漫巴士|dmbus).*$', '',
                               title, flags=re.I).strip()
                if title:
                    break

        pic = ""
        for pat in (
            r'<div[^>]*class="[^"]*\bcover\b[^"]*"[^>]*>\s*<img[^>]*\bsrc="([^"]+)"',
            r'<img[^>]*class="[^"]*\blazyload\b[^"]*"[^>]*\bdata-original="([^"]+)"',
            r'<img[^>]*\bdata-original="([^"]+)"',
            r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"',
        ):
            m = re.search(pat, html)
            if m:
                pic = _fix_url(m.group(1), self.host)
                break

        desc = ""
        m = re.search(
            r'<div[^>]*\bid="intro"[^>]*>([\s\S]*?)<div[^>]*\bshow_more\b',
            html)
        if not m:
            m = re.search(
                r'<div[^>]*\bid="intro"[^>]*>([\s\S]*?)</div>',
                html)
        if m:
            txt = m.group(1)
            txt = re.sub(r'^\s*<p[^>]*>\s*剧情：', '', txt)
            desc = _strip_tags(txt)

        year = ""
        area = ""
        m = re.search(
            r'<p[^>]*class="[^"]*\bv_desc\b[^"]*"[^>]*>([\s\S]*?)</p>',
            html)
        if m:
            desc_text = _strip_tags(m.group(1))
            parts = [p.strip() for p in desc_text.split('|')]
            for p in parts:
                if re.fullmatch(r'\d{4}', p):
                    year = p
                elif p in ("大陆", "日本", "欧美", "香港", "台湾",
                           "韩国", "美国", "海外"):
                    area = p

        play_from, play_url = [], []

        line_names = re.findall(
            r'<ul[^>]*class="[^"]*\bplay_from\b[^"]*"[^>]*>([\s\S]*?)</ul>',
            html)
        line_names_list = []
        if line_names:
            line_names_list = re.findall(
                r'<li[^>]*>([^<]+)</li>', line_names[0])
            line_names_list = [_unescape(n) for n in line_names_list]

        play_lists = re.findall(
            r'<ul[^>]*class="[^"]*\bplay_list\b[^"]*"[^>]*>([\s\S]*?)</ul>',
            html)

        for i, pl_content in enumerate(play_lists):
            eps = re.findall(
                r'<a[^>]*href="(/p/[^"#?]+\.html)"[^>]*>([^<]+)</a>',
                pl_content)
            if not eps:
                continue
            line_name = line_names_list[i] if i < len(line_names_list) else f"线路{i+1}"
            parts = []
            seen_h = set()
            for h, nm in eps:
                if h in seen_h:
                    continue
                seen_h.add(h)
                parts.append(f"{_unescape(nm)}${h}")
            if parts:
                play_from.append(line_name)
                play_url.append("#".join(parts))

        if not play_from:
            play_from.append("默认")
            play_url.append(f"正片${vid}")

        print(f"[detail] title={title!r} lines={len(play_from)} "
              f"names={play_from} "
              f"eps={[x.count('#')+1 for x in play_url]}")

        return {"list": [{
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": desc,
            "vod_year": year,
            "vod_area": area,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    # --------------------------------------------------------
    # 播放
    # --------------------------------------------------------
    def playerContent(self, flag, id, vipFlags=None):
        out = {"parse": 0, "playUrl": "", "url": "", "header": {}}
        pid = str(id or "").strip()
        if not pid:
            return out

        if self.isVideoFormat(pid) and pid.startswith("http"):
            out["url"] = pid
            out["header"] = {"User-Agent": UA_PC, "Referer": self.host + "/"}
            return out

        play_url = pid if pid.startswith("http") else \
                   self.host + ("" if pid.startswith("/") else "/") + pid
        html = self._fetch(play_url, ref=self.host + "/")

        if html:
            idx = html.find("player_aaaa")
            if idx == -1:
                idx = html.find("player_data")
            if idx != -1:
                start = html.find("{", idx)
                if start != -1:
                    depth, end = 0, -1
                    for i in range(start, len(html)):
                        c = html[i]
                        if c == "{":
                            depth += 1
                        elif c == "}":
                            depth -= 1
                            if depth == 0:
                                end = i + 1
                                break
                    if end != -1:
                        try:
                            obj = json.loads(html[start:end])
                            vurl = str(obj.get("url") or "").strip()
                            enc = str(obj.get("encrypt", "") or "")
                            if vurl:
                                if enc == "1":
                                    vurl = unquote(vurl)
                                elif enc == "2":
                                    try:
                                        a = unquote(vurl)
                                        b = base64.b64decode(a).decode(
                                            "utf-8", errors="replace")
                                        c = unquote(b)
                                        if c.startswith("http"):
                                            vurl = c
                                    except Exception as e:
                                        print(f"[player] decrypt ERR {e}")
                                if vurl:
                                    print(f"[player] encrypt={enc} "
                                          f"url={vurl[:80]}")
                                    out["url"] = vurl
                                    out["header"] = {
                                        "User-Agent": UA_PC,
                                        "Referer": self.host + "/"
                                    }
                                    return out
                        except Exception as e:
                            print(f"[player] parse player_aaaa ERR {e}")

            m = re.search(r'<iframe[^>]*\bsrc="([^"]+)"', html)
            if m:
                iframe = _fix_url(m.group(1), self.host)
                out["parse"] = 1
                out["url"] = iframe
                out["header"] = {"User-Agent": UA_PC, "Referer": play_url}
                return out

            m = re.search(
                r'(https?://[^"\'\s]+?\.(?:m3u8|mp4|flv|ts)[^"\'\s]*)', html)
            if m:
                out["url"] = m.group(1)
                out["header"] = {"User-Agent": UA_PC, "Referer": self.host + "/"}
                return out

        out["parse"] = 1
        out["url"] = play_url
        out["header"] = {"User-Agent": UA_PC, "Referer": self.host + "/"}
        return out

    # --------------------------------------------------------
    # 搜索
    # --------------------------------------------------------
    def searchContent(self, key, quick, pg="1"):
        page = _page(pg)
        out = {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}
        kw = str(key or "").strip()
        if not kw:
            return out

        url = f"{self.host}/s----------.html?wd={quote(kw)}"
        html = self._fetch(url, ref=self.host + "/")
        if html:
            out["list"] = self._parse_list(html)

        print(f"[search] kw={kw!r} url={url} count={len(out['list'])}")
        return out