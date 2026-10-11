# -*- coding: utf-8 -*-
"""
粤漫之家 - ymvid.com
Vue SPA 前端 + 服务端渲染列表页 + XXTEA 加密接口。

已实测验证的关键结论：
1. 站点为 Vue SPA，但「首页 / 分类页 / 详情页 / 搜索页」都是服务端渲染 HTML，
   可直接 curl 抓取解析；只有「播放地址」需要走加密接口。
2. 请求必须携带 Cookie ``browser-code-v1``。
   该值 = XXTEA_encrypt(visitorId + "_" + UTC日期)，密钥 "RuoYi_XXTEA_Key1"，
   输出 URL-safe Base64 且去掉 '=' 填充。visitorId 为任意 32 位十六进制串即可。
3. 风控：请求头带 ``Accept: application/json`` 或 ``Browser-Code`` 会被 403；
   播放接口 ``/allocate/playlist`` 还必须带上面的 Cookie，否则返回空。
4. 分类页 /list/{pg}/c{c}-s{s}-v{v}-l{l}-t{t}-y{y}/time_desc
   卡片：<a href=".../play/{id}"><img src alt> <span class="tips">更新到xx集</span>
5. 详情页 /play/{id}（301 到 /play/{id}/{sid}）：
   标题 <h1>；封面 og:image；类型/播出/状态/简介在 meta description。
   剧集：<li class="item" data-series-id=".." data-play-url="加密串">
        <a href=".../play/{id}/{seriesId}" data-num="0"><em>01</em></a>
6. 播放链路：
   play-url(加密) --XXTEA解密--> base("/allocate/playlist/{hash}?t=..")
   GET /allocate/secure_key --XXTEA解密--> sk
   GET base + "?t=sk&vId={id}" --> 直接返回 m3u8 文本（分片为绝对地址，无需二次处理）
"""
import re
import os
import json
import math
import time
import base64
import datetime
import urllib.parse
import html as html_mod
import requests
from urllib.parse import quote

try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def __init__(self):
            pass


# ==================== XXTEA（纯 Python，对齐前端 xxtea.js） ====================
_DELTA = 0x9e3779b9
_MASK = 0xffffffff
_XXTEA_KEY = b"RuoYi_XXTEA_Key1"


def _to_words(data, include_len):
    n = len(data)
    nw = (n >> 2) if (n & 3) == 0 else (n >> 2) + 1
    arr = [0] * (nw + 1) if include_len else [0] * nw
    if include_len:
        arr[nw] = n
    for i in range(n):
        arr[i >> 2] |= (data[i] & 0xff) << ((i & 3) << 3)
    return [x & _MASK for x in arr]


def _to_bytes(v, include_len):
    length = len(v) << 2
    if include_len:
        length -= 4
        last = v[-1]
        if last < length - 3 or last > length:
            return None
        length = last
    return bytes((v[i >> 2] >> ((i & 3) << 3)) & 0xff for i in range(length))


def _mx(s, y, z, p, e, k):
    a = (((z >> 5) ^ (y << 2)) + ((y >> 3) ^ (z << 4))) & _MASK
    b = ((s ^ y) + (k[(p & 3) ^ e] ^ z)) & _MASK
    return (a ^ b) & _MASK


def xxtea_encrypt(text, key=_XXTEA_KEY):
    v = _to_words(text.encode("utf-8"), True)
    k = _to_words(key, False)
    n = len(v) - 1
    if n >= 1:
        q = 6 + 52 // (n + 1)
        sm = 0
        z = v[n]
        for _ in range(q):
            sm = (sm + _DELTA) & _MASK
            e = (sm >> 2) & 3
            for p in range(n):
                y = v[p + 1]
                v[p] = (v[p] + _mx(sm, y, z, p, e, k)) & _MASK
                z = v[p]
            y = v[0]
            v[n] = (v[n] + _mx(sm, y, z, n, e, k)) & _MASK
            z = v[n]
    return base64.urlsafe_b64encode(_to_bytes(v, False)).decode().rstrip("=")


def xxtea_decrypt(cipher, key=_XXTEA_KEY):
    try:
        t = str(cipher).replace("-", "+").replace("_", "/")
        while len(t) % 4:
            t += "="
        v = _to_words(base64.b64decode(t), False)
        k = _to_words(key, False)
        n = len(v) - 1
        if n >= 1:
            q = 6 + 52 // (n + 1)
            sm = (q * _DELTA) & _MASK
            y = v[0]
            while sm != 0:
                e = (sm >> 2) & 3
                for p in range(n, 0, -1):
                    z = v[p - 1]
                    v[p] = (v[p] - _mx(sm, y, z, p, e, k)) & _MASK
                    y = v[p]
                z = v[n]
                v[0] = (v[0] - _mx(sm, y, z, 0, e, k)) & _MASK
                y = v[0]
                sm = (sm - _DELTA) & _MASK
        b = _to_bytes(v, True)
        return b.decode("utf-8") if b else None
    except Exception:
        return None


class Spider(Spider):
    # ==================== 基础配置 ====================
    name = "粤漫之家"
    base_url = "https://www.ymvid.com"
    site_url = "https://www.ymvid.com"

    searchable = 1
    quickSearch = 1
    filterable = 1
    changeable = 1

    ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

    # 首页/分类入口 -> 筛选参数串（c分类-s状态-v版本-l字母-t类型-y年份）
    DEFAULT_SEG = "c0-s0-v0-l0-t0-y0"
    TYPE_MAP = {
        "anime":   "c0-s0-v0-l0-t0-y0",   # 全部动画
        "yue":     "c1-s0-v0-l0-t0-y0",   # 粤语动画
        "guo":     "c2-s0-v0-l0-t0-y0",   # 国语动画
        "tv":      "c0-s0-v1-l0-t0-y0",   # TV动画
        "movie":   "c0-s0-v2-l0-t0-y0",   # 剧场版
        "ova":     "c0-s0-v3-l0-t0-y0",   # OVA
    }
    CATEGORY_NAMES = {
        "anime": "全部动画",
        "yue": "粤语动画",
        "guo": "国语动画",
        "tv": "TV动画",
        "movie": "剧场版",
        "ova": "OVA",
    }
    # 筛选维度选项（值为完整片段，直接参与 URL 拼接）
    FILTER_DEF = [
        ("c", "分类", [("全部", "c0"), ("粤语", "c1"), ("国语", "c2")]),
        ("s", "状态", [("全部", "s0"), ("连载", "s1"), ("完结", "s2"), ("未播放", "s3")]),
        ("v", "版本", [("全部", "v0"), ("TV", "v1"), ("剧场版", "v2"), ("OVA", "v3"), ("其他", "v5")]),
        ("y", "年份", [("全部", "y0"), ("2026", "y27"), ("2025", "y26"), ("2024", "y25"),
                       ("2023", "y24"), ("2022", "y23"), ("2021", "y22"), ("2020", "y21"),
                       ("2019", "y20"), ("2018", "y19"), ("2017", "y18"), ("2016", "y17"),
                       ("更早", "y1")]),
        ("t", "类型", [("全部", "t0"), ("搞笑", "t1"), ("运动", "t2"), ("励志", "t3"),
                       ("热血", "t4"), ("战斗", "t5"), ("校园", "t7"), ("青春", "t8"),
                       ("爱情", "t9"), ("冒险", "t10"), ("后宫", "t11"), ("百合", "t12"),
                       ("治愈", "t13"), ("魔法", "t15"), ("悬疑", "t16"), ("推理", "t17"),
                       ("奇幻", "t18"), ("科幻", "t19"), ("神魔", "t21"), ("恐怖", "t22"),
                       ("机器人", "t24"), ("战争", "t25"), ("犯罪", "t26"), ("历史", "t27"),
                       ("社会", "t28"), ("职场", "t29"), ("剧情", "t30"), ("亲子", "t35"),
                       ("真人", "t36"), ("歌舞", "t37"), ("美少女", "t39"), ("竞技", "t40"),
                       ("吸血鬼", "t41"), ("泡面番", "t43")]),
    ]

    def __init__(self):
        super().__init__()
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": self.ua})
        self._bc = ""
        self._bc_date = ""
        self._last_req_time = 0
        self._min_req_interval = 0.6
        self._session.cookies.set("browser-code-v1", self._browser_code(),
                                  domain="www.ymvid.com")

        self._re_card = re.compile(
            r'<a[^>]*href="(?:https?://www\.ymvid\.com)?/play/(\d+)"[^>]*>(.*?)</a>',
            re.S)
        self._re_img = re.compile(r'<img[^>]*>', re.S)
        self._re_play_item = re.compile(
            r'<li[^>]*class="[^"]*\bitem\b[^"]*"[^>]*data-series-id="(\d+)"[^>]*'
            r'data-play-url="([^"]+)"[^>]*>(.*?)</li>', re.S)

    # ==================== 工具方法 ====================
    def _log(self, msg):
        print("[%s] %s" % (self.name, msg))

    def _browser_code(self):
        """Cookie browser-code-v1 = XXTEA(visitorId_UTC日期)"""
        today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        if self._bc and self._bc_date == today:
            return self._bc
        visitor = os.urandom(16).hex()
        self._bc = xxtea_encrypt(visitor + "_" + today)
        self._bc_date = today
        return self._bc

    @staticmethod
    def _attr(tag, name):
        m = re.search(r'%s\s*=\s*"([^"]*)"' % name, tag)
        return m.group(1) if m else ""

    def _clean_text(self, text):
        if not text:
            return ""
        # 先反转义（搜索页片名会把 <span> 高亮标签编码进 alt），再去标签
        text = html_mod.unescape(text)
        text = re.sub(r'<[^>]+>', '', text)
        text = text.replace('\u00a0', ' ')
        return re.sub(r'\s+', ' ', text).strip()

    def _apply_req_delay(self):
        now = time.time()
        elapsed = now - self._last_req_time
        if 0 < elapsed < self._min_req_interval:
            time.sleep(self._min_req_interval - elapsed)
        self._last_req_time = time.time()

    # ==================== 请求基础 ====================
    def _get(self, url, max_retry=2, timeout=15):
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
                return resp.text
            except Exception as e:
                self._log("请求失败: %s, %s" % (url, e))
                if attempt < max_retry - 1:
                    time.sleep(1 + attempt)
        return ""

    def _get_secure_key(self):
        # 注意：secure_key 是【一次性】的，每次播放都必须重新获取，不能缓存。
        try:
            self._apply_req_delay()
            resp = self._session.get(self.base_url + "/allocate/secure_key", timeout=15)
            data = json.loads(resp.text).get("data", "")
            sk = xxtea_decrypt(data)
            if sk:
                self._sk = sk
            return sk or ""
        except Exception as e:
            self._log("获取 secure_key 失败: %s" % e)
            return ""

    # ==================== 列表解析 ====================
    def _parse_cards(self, html):
        """统一解析卡片（首页/分类/搜索通用）"""
        videos = []
        seen = set()
        if not html:
            return videos
        for m in self._re_card.finditer(html):
            vod_id, inner = m.group(1), m.group(2)
            im = self._re_img.search(inner)
            if not im:
                continue
            if vod_id in seen:
                continue
            img_tag = im.group(0)
            pic = self._attr(img_tag, "src") or self._attr(img_tag, "data-src")
            name = self._clean_text(self._attr(img_tag, "alt"))
            note = ""
            nm = re.search(r'class="[^"]*(?:tips|yue|tag)[^"]*"[^>]*>([^<]*)<', inner)
            if nm:
                note = self._clean_text(nm.group(1))
            if pic.startswith("//"):
                pic = "https:" + pic
            seen.add(vod_id)
            videos.append({
                "vod_id": vod_id,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": note,
            })
        return videos

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
            for tid in self.CATEGORY_NAMES:
                filters[tid] = [
                    {"key": k, "name": n,
                     "value": [{"n": vn, "v": vv} for vn, vv in opts]}
                    for k, n, opts in self.FILTER_DEF
                ]
            result["filters"] = filters
        return result

    def homeVideoContent(self):
        try:
            html = self._get(self.base_url)
            return {"list": self._parse_cards(html)[:30]}
        except Exception as e:
            self._log("homeVideoContent异常: %s" % e)
            return {"list": []}

    def categoryContent(self, tid, pg, filter=False, content=None):
        try:
            pg = max(1, int(pg or 1))
            seg = self.TYPE_MAP.get(str(tid), self.DEFAULT_SEG)
            parts = dict(zip(["c", "s", "v", "l", "t", "y"], seg.split("-")))
            ext = {}
            if filter and isinstance(filter, dict):
                ext = filter
            elif isinstance(content, dict):
                ext = content
            for k in ("c", "s", "v", "l", "t", "y"):
                if k in ext and ext[k]:
                    parts[k] = str(ext[k])
            seg = "-".join(parts[k] for k in ("c", "s", "v", "l", "t", "y"))
            url = "%s/list/%d/%s/time_desc" % (self.base_url, pg, seg)
            self._log("分类请求: " + url)
            html = self._get(url)
            videos = self._parse_cards(html)

            total = 0
            mt = re.search(r'data-total="(\d+)"', html)
            if mt:
                total = int(mt.group(1))
            per = len(videos) or 24
            pagecount = max(1, int(math.ceil(total / float(per)))) if total else 1
            return {
                "list": videos,
                "page": pg,
                "pagecount": pagecount,
                "limit": per,
                "total": total or len(videos),
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
            url = "%s/search?keyword=%s" % (self.base_url, quote(keyword))
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
            return {
                "list": videos,
                "page": pg,
                "pagecount": 1,
                "limit": 30,
                "total": len(videos),
            }
        except Exception as e:
            self._log("searchContent异常: %s" % e)
            return {"list": [], "page": 1, "pagecount": 1, "limit": 30, "total": 0}

    def detailContent(self, ids):
        try:
            vod_id = str(ids[0] if isinstance(ids, list) else ids)
            url = "%s/play/%s" % (self.base_url, vod_id)
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
                m = re.search(r'property="og:title"[^>]*content="([^"]*)"', html)
                if m:
                    vod_name = self._clean_text(m.group(1).split("|")[0])
            # 封面
            vod_pic = ""
            m = re.search(r'property="og:image"[^>]*content="([^"]*)"', html)
            if m:
                vod_pic = m.group(1)
            # 简介 / 类型 / 年份 / 状态
            vod_content = vod_year = vod_remarks = ""
            m = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]*)"', html)
            if m:
                desc = html_mod.unescape(m.group(1))
                dm = re.search(r'简介[:：]\s*(.+)$', desc, re.S)
                if dm:
                    vod_content = self._clean_text(dm.group(1))
                ym = re.search(r'播出[:：]\s*([^\s]+)', desc)
                if ym:
                    vod_year = ym.group(1).strip()
                sm = re.search(r'状态[:：]\s*([^\s]+)', desc)
                if sm:
                    vod_remarks = sm.group(1).strip()

            # 剧集（单线路：所有集数同属一条播放线路）
            eps = []
            seen = set()
            for m in self._re_play_item.finditer(html):
                series_id, play_url, inner = m.group(1), m.group(2), m.group(3)
                if series_id in seen:
                    continue
                seen.add(series_id)
                em = re.search(r'<em[^>]*>([^<]*)</em>', inner)
                num = self._clean_text(em.group(1)) if em else series_id
                eps.append((num, "%s:%s" % (vod_id, play_url)))

            if not eps:
                # 兜底：从 <a href=".../play/{id}/{sid}"> 直接构造（无加密串则不可播）
                self._log("未解析到剧集")
                return {"list": []}

            from_list = ["线路1"]
            url_list = ["#".join("%s$%s" % (n, link) for n, link in eps)]

            video = {
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_year": vod_year,
                "vod_area": "",
                "vod_actor": "",
                "vod_director": "",
                "vod_content": vod_content,
                "vod_remarks": vod_remarks,
                "vod_play_from": "$$$".join(from_list),
                "vod_play_url": "$$$".join(url_list),
            }
            self._log("详情解析成功: %s 集数=%d" % (vod_name, len(eps)))
            return {"list": [video]}
        except Exception as e:
            self._log("detailContent异常: %s" % e)
            return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        try:
            sid = str(id)
            if ":" not in sid:
                return {"parse": 0, "url": "", "header": ""}
            vod_id, enc = sid.split(":", 1)
            dec = xxtea_decrypt(enc)
            if not dec:
                self._log("播放地址解密失败")
                return {"parse": 0, "url": "", "header": ""}
            base = dec.split("?")[0]
            if base.startswith("/"):
                base = self.base_url + base
            sk = self._get_secure_key()
            if not sk:
                return {"parse": 0, "url": "", "header": ""}
            url = "%s?t=%s&vId=%s" % (base, quote(sk, safe=""), vod_id)
            self._log("播放URL: %s..." % url[:90])
            return {"parse": 0, "url": url, "header": self._play_header()}
        except Exception as e:
            self._log("playerContent异常: %s" % e)
            return {"parse": 0, "url": "", "header": ""}

    def _play_header(self):
        return {
            "User-Agent": self.ua,
            "Cookie": "browser-code-v1=" + self._browser_code(),
        }

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
