#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1234sp.cc - 1234影视 Spider（TVBox / 饭搭子影视 同源爬虫框架适配版）

站点: https://www.1234sp.cc
说明: 本源文件是依据你提供的「饭搭子影视.py(fdzys.com)」改造而来，
      用于适配 1234影视(1234sp.cc) 的站点结构。

===================================================================
 站点 URL 结构（实测 1234sp.cc）
===================================================================
   首页：        /
   分类首页：    /list/{分类ID}/1.html
   分类第N页：   /list/{分类ID}/{N}.html
   子分类：      /list/{子分类ID}/1.html   （分类页内的筛选导航，也是 /list/ 形式）
   详情页：      /v/{视频ID}.html
   播放页：      /p/{视频ID}/{线路ID}/{集数}.html
   搜索：        /search/{base64url(关键词)}/1.html  ← 站点对此路径开启了滑块风控

   说明：1234sp.cc 的所有分类/子分类 ID 都是随机串（如 A2ttqWI1YGgTu），
         不像 fdzys 用 movie/tv 这类可读 tid，因此本爬虫把所有分类 ID 直接
         硬编码进 CLASSES / FILTERS，并在 init 里支持 extend 注入自定义 host。

===================================================================
 风控提示（重要）
===================================================================
   站点的 /search/ 路径会被「访问验证」滑块拦截（200 但返回验证页，非 404），
   这是服务端 WAF，单纯改 UA/带 cookie 均无效。因此本 spider 的搜索函数：
     1) 优先尝试直接请求 /search/ 接口；
     2) 若命中验证页（"访问验证"/"请完成"），自动回退到「分类全量列表里
        做本地关键词过滤」—— 即把关键词当作子串在已抓取的分类卡片里匹配，
        保证 TVBox 搜索框仍能出结果（首屏一页，按需翻页逐页扩大召回）。
"""

import re
import json
import base64
import html as html_mod
from urllib.parse import quote, urljoin

try:
    import requests
    import urllib3
    urllib3.disable_warnings()
except ImportError:
    requests = None

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
#   type_id 这里直接存放 1234sp.cc 的真实分类 ID
# ============================================================
CLASSES = [
    {"type_id": "A2xeflx0UY1tu", "type_name": "连续剧"},
    {"type_id": "A2mOC0y4HbZ3l", "type_name": "电影"},
    {"type_id": "A2ttqWI1YGgTu", "type_name": "动漫"},
    {"type_id": "A2b7iFz0ozYru", "type_name": "综艺"},
    {"type_id": "A2XMt0K0jbHHd", "type_name": "伦理"},
]

# 子分类（站点内筛选导航，每个都是独立的 /list/{ID}/1.html）
_SUBCATE = {
    "A2xeflx0UY1tu": [  # 连续剧
        ("A1zZRjN083yIX", "国产剧"), ("A1vocTi262A4n", "港台剧"),
        ("A1d2UDP06Kv5I", "欧美剧"), ("A1ZHexk0TsGRb", "韩国剧"),
        ("A1kY8ij34a2CF", "日本剧"), ("A1gnJT41Wl9SP", "泰国剧"),
        ("A1O1BCl3sXwad", "其他剧"),
    ],
    "A2mOC0y4HbZ3l": [  # 电影
        ("A2idMlJ49C2tX", "喜剧"), ("A2esXVe1UdisF", "动作"),
        ("A2M6PFL1tYL3U", "爱情"), ("A2Tc3kf1UUB3F", "恐怖"),
        ("A2PrEV01jrfYy", "犯罪"), ("A2756Eh1WkGKD", "剧情"),
        ("A23KGz24Mz907", "奇幻"), ("A2Eakk12GoKEK", "战争"),
        ("A2ApvUM3iOu01", "悬疑"), ("A1s3nE31yzGaQ", "动画"),
        ("A2ILZzg2dr1WD", "科幻"), ("A1oIxyO4EmwKm", "其他片"),
    ],
    "A2ttqWI1YGgTu": [  # 动漫
        ("A1KGLx64BWy5k", "国漫"), ("A1VWpi53ICCKJ", "日漫"),
        ("A1Rm0SQ3lvlSz", "其他动漫"),
    ],
    "A2b7iFz0ozYru": [  # 综艺
        ("A0xjOR80zha71", "国产综艺"), ("A15F2wS3VQMBM", "港澳综艺"),
        ("A18zsC70g5g96", "日韩综艺"), ("A1GVWhR1ONhYa", "其他综艺"),
    ],
    "A2XMt0K0jbHHd": [  # 伦理
        ("A1CkhRm4TdHmP", "日韩"), ("A0tyZBT1UNFDf", "港台"),
        ("A0qDjvo2APjcL", "欧美"), ("A11UDgn1IdxK6", "其他伦理"),
    ],
}


def _make_filters(tid):
    opts = [{"n": "全部", "v": tid}] + \
           [{"n": name, "v": sub} for sub, name in _SUBCATE.get(tid, [])]
    return [{"key": "sub", "name": "筛选", "value": opts}]


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


# base64url（无填充）—— 与站点 pixel.js 的 encodeSearchToken 一致
def _b64url_encode(text):
    b = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return b.replace("+", "-").replace("/", "_").rstrip("=")


def _is_captcha(text):
    """判断页面是否被「访问验证」滑块拦截。"""
    if not text:
        return True
    return ("访问验证" in text) or ("请完成访问验证" in text) \
        or ("按住滑块" in text)


# ============================================================
# Spider
# ============================================================
class Spider(BaseSpider):

    def __init__(self):
        super().__init__()
        self.host = "https://www.1234sp.cc"
        self.name = "1234影视"
        self.sourceKey = "1234sp"
        self.timeout = 20
        self.s = None
        if requests:
            self.s = requests.Session()
            self.s.verify = False

    def init(self, extend=""):
        if extend:
            try:
                cfg = json.loads(extend) if isinstance(extend, str) else extend
                if isinstance(cfg, dict) and cfg.get("host"):
                    self.host = cfg["host"].rstrip("/")
            except Exception:
                pass

    def getName(self): return self.name
    def getDependence(self): return []
    def homeLayout(self): return 0

    def isVideoFormat(self, url):
        if not url:
            return False
        p = str(url).lower()
        return any(x in p for x in (".m3u8", ".mp4", ".flv", ".ts"))

    def manualVideoCheck(self): return False
    def localProxy(self, param): return [404, "text/plain", b""]

    # --------------------------------------------------------
    # 请求（PC UA 失败自动降级手机 UA）
    # --------------------------------------------------------
    def _fetch(self, url, ref=None):
        if not self.s:
            print("[fetch] requests not installed")
            return ""
        for attempt, ua in enumerate([UA_PC, UA_MB]):
            headers = {
                "User-Agent": ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Referer": ref or (self.host + "/"),
                "Connection": "keep-alive",
            }
            try:
                r = self.s.get(url, headers=headers, timeout=self.timeout,
                               allow_redirects=True)
                raw = r.content or b""
                print(f"[fetch] #{attempt+1} {r.status_code} raw={len(raw)} {url}")
                if r.status_code != 200 or not raw:
                    continue
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    text = raw.decode("gbk", errors="replace")
                if _is_captcha(text):
                    print(f"[fetch] 命中访问验证（风控），标记空结果")
                    return ""   # 风控页视为无内容
                if len(text) < 300:
                    continue
                return text
            except Exception as e:
                print(f"[fetch] #{attempt+1} ERR {e} {url}")
        return ""

    # --------------------------------------------------------
    # 列表解析（1234sp.cc 卡片结构）
    #   <article class="pixel-card">
    #     <a class="pixel-card__link" href="/v/ID.html" title="片名">
    #       <span class="pixel-poster">
    #         <img src="封面" alt="片名" ...>
    #         <span class="pixel-card__remark">更新至第03集</span>
    #       </span>
    #       <span class="pixel-card__body">
    #         <strong class="pixel-card__title">片名</strong>
    # --------------------------------------------------------
    def _parse_list(self, html):
        result, seen = [], set()
        if not html:
            return result

        # 先按 article 切块，再在块内取值，避免跨卡片串味
        blocks = re.findall(
            r'<article\b[^>]*class="[^"]*\bpixel-card\b[^"]*"[\s\S]*?</article>',
            html)
        if not blocks:
            # 兜底：退化为整页 <a ...>...</a>
            blocks = [html]

        for inner in blocks:
            m_a = re.search(
                r'<a\b[^>]*class="[^"]*\bpixel-card__link\b[^"]*"[^>]*'
                r'href="([^"]+)"', inner)
            if not m_a:
                m_a = re.search(r'<a\b[^>]*href="([^"]+)"', inner)
            if not m_a:
                continue
            href = m_a.group(1).strip()
            if not re.search(r'^/v/[^/?#]+$', href):
                continue

            vid = self.host + href

            # 标题：card__title 优先，其次 a 的 title 属性，再次 img alt
            title = ""
            m = re.search(
                r'<strong\b[^>]*class="[^"]*\bpixel-card__title\b[^"]*"[^>]*>'
                r'([^<]+)</strong>', inner)
            if not m:
                m = re.search(r'<a\b[^>]*title="([^"]+)"', inner)
            if not m:
                m = re.search(r'<img[^>]*\balt="([^"]+)"', inner)
            if m:
                title = _unescape(m.group(1))
            if not title:
                continue

            pic = ""
            m = re.search(r'<img[^>]*\bsrc="([^"]+)"', inner)
            if m:
                pic = _fix_url(m.group(1), self.host)

            remark = ""
            m = re.search(
                r'<span\b[^>]*class="[^"]*\bpixel-card__remark\b[^"]*"[^>]*>'
                r'([^<]+)</span>', inner)
            if m:
                remark = _unescape(m.group(1))

            if vid in seen:
                continue
            seen.add(vid)

            result.append({
                "vod_id": vid,
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
    # 分类 URL 拼接（1234sp.cc: /list/{id}/{page}.html）
    # --------------------------------------------------------
    def _build_category_url(self, tid, page):
        return f"{self.host}/list/{tid}/{page}.html"

    # --------------------------------------------------------
    # 分类（翻页；首页/子分类均逐页请求）
    # --------------------------------------------------------
    def categoryContent(self, tid, pg, filter, extend):
        page = _page(pg)
        tid = str(tid).strip()
        # 若用户用了子分类筛选（extend.sub），则替换为子分类 ID
        sub = str((extend or {}).get("sub") or "").strip()
        if sub and sub != tid:
            tid = sub
        print(f"[category] tid={tid!r} pg={pg!r} page={page} extend={extend!r}")

        u = self._build_category_url(tid, page)
        h = self._fetch(u)
        items = self._parse_list(h) if h else []

        n = len(items)
        out = {
            "list": items,
            "page": page,
            "pagecount": 9999,
            "limit": n or 20,
            "total": 999999,
        }
        if not items:
            out["pagecount"] = page
            out["total"] = page * 20

        print(f"[category] <=== page={page} pagecount={out['pagecount']} "
              f"count={n}")
        return out

    # --------------------------------------------------------
    # 二级详情（1234sp.cc: /v/{id}.html）
    #   线路：<section data-playlist-panel="N"> 内 <h3>线路名</h3>
    #         + <a href="/p/{vid}/{line}/{ep}.html">第xx集</a>
    #   资料：<dl class="pixel-meta"> <dt>主演</dt><dd>...</dd> ...
    # --------------------------------------------------------
    def detailContent(self, ids):
        raw = ids if isinstance(ids, (list, tuple)) else [ids]
        vid = str(raw[0] if raw else "").strip()
        if not vid:
            return {"list": []}

        url = vid if vid.startswith("http") else self.host + vid
        html = self._fetch(url)
        if not html:
            return {"list": []}

        # 标题
        title = ""
        m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        if not m:
            m = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]+)"',
                          html)
        if not m:
            m = re.search(r'<title>([^<]+)</title>', html)
        if m:
            title = _unescape(m.group(1))
            title = re.sub(r'\s*[-|_]\s*(1234影视).*$', '', title,
                           flags=re.I).strip()

        # 封面（取第一张 poster 内 img）
        pic = ""
        m = re.search(
            r'class="[^"]*\bpixel-poster\b[^"]*"[\s\S]*?<img[^>]*\bsrc="([^"]+)"',
            html)
        if not m:
            m = re.search(r'<img[^>]*\bsrc="(https?://[^"]+)"', html)
        if m:
            pic = _fix_url(m.group(1), self.host)

        # 简介
        desc = ""
        m = re.search(
            r'<div\b[^>]*data-vod-intro[^>]*>([\s\S]*?)</div>', html)
        if m:
            desc = _strip_tags(m.group(1))

        # 资料 dt/dd
        def _dd(key):
            m = re.search(
                r'<dt>[^<]*' + re.escape(key) + r'[^<]*</dt><dd>([^<]+)</dd>',
                html)
            return _unescape(m.group(1)) if m else ""

        actor = _dd("主演")
        director = _dd("导演")
        vtype = _dd("类型")
        area_year = _dd("地区 / 年份")
        status = _dd("状态")

        # 地区 / 年份 拆一下
        area, year = "", ""
        if area_year:
            parts = [p.strip() for p in re.split(r'\s*/\s*', area_year)]
            if len(parts) >= 2:
                area, year = parts[0], parts[1]
            elif parts:
                area = parts[0]

        # 线路 + 剧集
        panels = re.findall(
            r'<section[^>]*data-playlist-panel="(\d+)"[^>]*>([\s\S]*?)</section>',
            html)
        play_from, play_url = [], []
        for sid, body in panels:
            h3 = re.search(r'<h3[^>]*>([^<]+)</h3>', body)
            name = _unescape(h3.group(1)) if h3 else f"线路{sid}"
            eps = re.findall(
                r'<a[^>]*href="(/p/[^"]+)"[^>]*>([^<]+)</a>', body)
            if not eps:
                continue
            seen_h = set()
            uniq = []
            for h, n in eps:
                if h in seen_h:
                    continue
                seen_h.add(h)
                uniq.append((self.host + h, _unescape(n)))
            if not uniq:
                continue
            play_from.append(name)
            play_url.append("#".join(f"{n}${h}" for h, n in uniq))

        if not play_from:
            play_from.append("默认")
            play_url.append(f"正片${vid}")

        print(f"[detail] title={title!r} lines={len(play_from)} "
              f"eps={[x.count('#')+1 for x in play_url]}")

        return {"list": [{
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": desc,
            "vod_director": director,
            "vod_actor": actor,
            "vod_area": area,
            "vod_year": year,
            "vod_type": vtype,
            "vod_remarks": status,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_url),
        }]}

    # --------------------------------------------------------
    # 播放（1234sp.cc: /p/{vid}/{line}/{ep}.html）
    #   页面内 <iframe src="第三方播放器"> —— 转交解析(parse=1)
    # --------------------------------------------------------
    def playerContent(self, flag, id, vipFlags=None):
        out = {"parse": 1, "playUrl": "", "url": "", "header": {}}
        pid = str(id or "").strip()
        if not pid:
            return out

        play_url = pid if pid.startswith("http") else self.host + pid
        html = self._fetch(play_url, ref=self.host + "/")

        if html:
            m = re.search(r'<iframe[^>]*\bsrc="([^"]+)"', html)
            if m:
                iframe = _fix_url(m.group(1), self.host)
                out["url"] = iframe
                out["header"] = {"User-Agent": UA_PC, "Referer": play_url}
                print(f"[player] iframe -> {iframe[:90]}")
                return out

            m = re.search(
                r'(https?://[^"\'\s]+?\.(?:m3u8|mp4|flv|ts)[^"\'\s]*)', html)
            if m:
                out["parse"] = 0
                out["url"] = m.group(1)
                out["header"] = {"User-Agent": UA_PC, "Referer": self.host + "/"}
                return out

        # 兜底：直接把播放页交给 TVBox 内置解析
        out["url"] = play_url
        out["header"] = {"User-Agent": UA_PC, "Referer": self.host + "/"}
        return out

    # --------------------------------------------------------
    # 搜索（1234sp.cc 开启滑块风控，做本地回退过滤）
    #   站点格式：/search/{b64url(关键词)}/1.html
    #   若命中「访问验证」则回退到分类全量扫描 + 子串匹配
    # --------------------------------------------------------
    def searchContent(self, key, quick, pg="1"):
        page = _page(pg)
        out = {"list": [], "page": page, "pagecount": 1, "limit": 20, "total": 0}
        kw = str(key or "").strip()
        if not kw:
            return out

        token = _b64url_encode(kw)
        url = f"{self.host}/search/{token}/{page}.html"
        html = self._fetch(url, ref=self.host + "/")

        # 正常返回（未被风控）
        if html and not _is_captcha(html):
            items = self._parse_list(html)
            out["list"] = items
            pgs = re.findall(r'/search/' + re.escape(token) + r'/(\d+)\.html',
                             html)
            if pgs:
                out["pagecount"] = max(int(p) for p in pgs)
            out["total"] = len(items) or 20
            print(f"[search] kw={kw!r} page={page} count={len(items)}")
            return out

        # 回退：逐页扫描全部分类，本地子串匹配（首屏 page 控制召回深度）
        print(f"[search] kw={kw!r} 命中访问验证，回退本地分类扫描")
        seen, collected = set(), []
        # 广度优先：每个分类各取若干页，轮询，避免单分类刷屏
        SCAN_PAGES = 5
        for cat in CLASSES:
            for p in range(1, SCAN_PAGES + 1):
                u = self._build_category_url(cat["type_id"], p)
                h = self._fetch(u)
                if not h:
                    break
                for it in self._parse_list(h):
                    if it["vod_id"] in seen:
                        continue
                    if kw.lower() in it["vod_name"].lower():
                        seen.add(it["vod_id"])
                        collected.append(it)
                if len(collected) >= page * 20:
                    break
            if len(collected) >= page * 20:
                break

        start = (page - 1) * 20
        out["list"] = collected[start:start + 20]
        out["pagecount"] = 9999
        out["total"] = 999999
        print(f"[search] 本地召回 count={len(out['list'])} "
              f"累计命中={len(collected)}")
        return out
