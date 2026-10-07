# -*- coding: utf-8 -*-
"""
4K影视 (4kvms) TVBox 蜘蛛 v1
- 多域名: 4kvms.org / .com / 4kvm.top / .me / .tv / .net (探活自动切换)
- 列表: GET / {classify N} 或 /filter?classify=N&page=P -> 卡片 .movie-card -> /play/{secret}
- 详情: /play/{secret} -> h1 标题 / .video-player[data-poster] 图 / a.episode-link 集数(dataid)
- 播放: 签名 s=HMAC-SHA256(p+':'+t+':'+v, key=v) 前32hex; k=XOR(userlink,'nbmovie2024secretkey') URL-safe b64
        -> /video/play?p&v&q=1080&s&t&k -> JSON quality_urls 取最高 bitrate
- 更多资源请到网站 https://navpage-2026.surge.sh/
"""
import base64
import hashlib
import hmac
import json
import re
import time
from urllib.parse import quote, unquote, urljoin

import requests

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def __init__(self):
            pass


class Spider(BaseSpider):
    DOMAINS = [
        "https://www.4kvms.org",
        "https://www.4kvms.com",
        "https://www.4kvm.top",
        "https://www.4kvm.me",
        "https://www.4kvm.tv",
        "https://www.4kvm.net",
    ]
    XOR_KEY = "nbmovie2024secretkey"
    UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    CLASSES = [
        {"type_name": "电影", "type_id": "classify=1"},
        {"type_name": "剧集", "type_id": "classify=2"},
        {"type_name": "动漫", "type_id": "classify=3"},
        {"type_name": "综艺", "type_id": "classify=4"},
        {"type_name": "4K专区", "type_id": "tags=1"},
        {"type_name": "推荐", "type_id": "home"},
    ]

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        self.host = self._pick_host()

    def _pick_host(self):
        for d in self.DOMAINS:
            try:
                r = self.session.get(d + "/", timeout=6)
                if r.status_code == 200:
                    return d
            except Exception:
                continue
        return self.DOMAINS[0]

    def init(self, extend=""):
        return ""

    def getName(self):
        return "小四K"

    def getVersion(self):
        return 1

    def destroy(self):
        pass

    def _abs(self, url, base=None):
        if not url:
            return ""
        if url.startswith(("http://", "https://")):
            return url
        if url.startswith("//"):
            return "https:" + url
        return urljoin(base or self.host, url)

    def _get(self, url, referer=""):
        headers = {}
        if referer:
            headers["Referer"] = referer
        try:
            r = self.session.get(url, headers=headers, timeout=12)
            if r.status_code == 200:
                return r.text
        except Exception:
            pass
        return ""

    def _enc_userlink(self, ul):
        """userlink 与 key 循环异或后 URL-safe base64 (保留 = 填充, 同 JS B64_ALPHA)"""
        if ul in ("", "0", "undefined", "null"):
            return "0"
        key = self.XOR_KEY
        out = bytearray(len(ul))
        for i, ch in enumerate(ul):
            out[i] = ord(ch) & 0xFF ^ ord(key[i % len(key)]) & 0xFF
        b = base64.urlsafe_b64encode(bytes(out)).decode("ascii")
        return b

    @staticmethod
    def _cookie_t():
        return str(int(time.time() * 1000))

    # ---------------- 首页/分类 ----------------
    def homeContent(self, filter=False):
        return {"class": list(self.CLASSES), "filters": {}}

    def homeVideoContent(self):
        return {"list": self._parse_list(self._get(self.host + "/"))[:60]}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        page = int(pg or 1)
        q = str(tid or "classify=1")
        if q == "home":
            url = self.host + "/"
        else:
            url = f"{self.host}/filter?{q}&page={page}"
        return {"list": self._parse_list(self._get(url)),
                "page": page, "pagecount": 9999, "limit": 60, "total": 99999}

    def _parse_list(self, html):
        videos, seen = [], set()
        if not html:
            return videos
        # 卡片: .movie-card 内含 a[href=/play/secret]  h3标题 img[data-src]
        for m in re.finditer(r'<a[^>]*href="(/play/[^"]+)"[^>]*>(.*?)</a>', html, re.S):
            href = m.group(1)
            if href in seen:
                continue
            seen.add(href)
            block = m.group(2)
            tm = re.search(r"<h3[^>]*>(.*?)</h3>", block, re.S)
            title = re.sub(r"<[^>]+>", "", tm.group(1)).strip() if tm else ""
            if not title:
                am = re.search(r'<img[^>]*alt="([^"]+)"', block)
                title = am.group(1).strip() if am else ""
            if not title:
                continue
            pm = re.search(r'<img[^>]*(?:data-src|src)="([^"]+)"', block)
            pic = self._abs(pm.group(1)) if pm else ""
            sc = re.search(r'text-green-500[^>]*>\s*([\d.]+)', block)
            yr = re.search(r'text-gray-400[^>]*>\s*([^<]+)', block)
            remark = (sc.group(1).strip() if sc else "") + ("·" + yr.group(1).strip() if yr else "")
            videos.append({
                "vod_id": href,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark.strip("·").strip(),
            })
        return videos

    # ---------------- 搜索 ----------------
    def searchContent(self, key, quick, pg="1"):
        kw = quote(unquote(str(key or "").strip()), safe="")
        url = f"{self.host}/search?q={kw}&page={pg}"
        return {"list": self._parse_search(self._get(url)), "page": int(pg or 1),
                "pagecount": 1, "limit": 60, "total": 60}

    def _parse_search(self, html):
        videos, seen = [], set()
        if not html:
            return videos
        for m in re.finditer(r'<div[^>]*class="[^"]*group[^"]*relative[^"]*"[^>]*>(.*?)</div>', html, re.S):
            block = m.group(1)
            am = re.search(r'<a[^>]*href="(/play/[^"]+)"', block)
            if not am:
                continue
            href = am.group(1)
            if href in seen:
                continue
            seen.add(href)
            tm = re.search(r"<h3[^>]*>(.*?)</h3>", block, re.S)
            title = re.sub(r"<[^>]+>", "", tm.group(1)).strip() if tm else ""
            if not title:
                continue
            pm = re.search(r'<img[^>]*(?:data-src|src)="([^"]+)"', block)
            img = self._abs(pm.group(1)) if pm else ""
            yr = re.search(r'<div[^>]*class="[^"]*absolute[^"]*"[^>]*>\s*([^<]+)', block)
            videos.append({
                "vod_id": href, "vod_name": title,
                "vod_pic": img,
                "vod_remarks": yr.group(1).strip() if yr else "",
            })
        return videos

    # ---------------- 详情 ----------------
    def detailContent(self, ids):
        raw = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        raw = str(raw or "").strip()
        if not raw:
            return {"list": []}
        if raw.startswith("/"):
            raw = self.host + raw
        html = self._get(raw, referer=self.host + "/")
        if not html:
            return {"list": []}
        vod = self._parse_detail(html, raw)
        return {"list": [vod]}

    def _parse_detail(self, html, url):
        vod = {
            "vod_id": "", "vod_name": "未知影片", "vod_pic": "",
            "vod_year": "", "vod_area": "", "vod_actor": "", "vod_director": "",
            "vod_content": "", "vod_play_from": "", "vod_play_url": "",
        }
        tm = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
        if tm:
            vod["vod_name"] = re.sub(r"<[^>]+>", "", tm.group(1)).strip()
        pm = (re.search(r'class="[^"]*video-player[^"]*"[^>]*data-poster="([^"]+)"', html)
              or re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html))
        if pm:
            vod["vod_pic"] = self._abs(pm.group(1))
        dm = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]*)"', html)
        if dm:
            vod["vod_content"] = dm.group(1).strip()
        # 集数 (多线路 data-line) - a 属性顺序: href?data-line?data-episode?dataid 不一
        eps = re.findall(
            r'<a[^>]*?data-line="(\d+)"[^>]*?data-episode="(\d+)"[^>]*?dataid="(\d+)"[^>]*>',
            html, re.S,
        )
        if not eps:
            # 兜底: 任意 dataid + data-episode
            eps = re.findall(
                r'data-line="(\d+)"[^>]*data-episode="(\d+)"[^>]*dataid="(\d+)"', html,
            )
        if eps:
            m = re.search(r"/play/([^/?#]+)", url)
            secret = m.group(1) if m else ""
            line_map = {}
            order = {}
            for line, epno, dataid in eps:
                line = line or "1"
                line_map.setdefault(line, [])
                play_href = f"{self.host}/play/{secret}?p={dataid}&v={secret}"
                label2 = f"第{epno}集" if epno else f"第{len(line_map[line])+1}集"
                line_map[line].append(f"{label2}${play_href}")
            lines = list(line_map.keys())
            vod["vod_play_from"] = "$$$".join(f"线路{i+1}" for i in range(len(lines)))
            vod["vod_play_url"] = "$$$".join("#".join(line_map[ln]) for ln in lines)
        return vod

    # ---------------- 播放 ----------------
    def playerContent(self, ids, flag, vipFlags):
        raw = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        url = str(raw or "").strip()
        if not url:
            return {}
        # 从 URL 提取 v=secret 与 p=dataid
        v = ""
        pm = re.search(r"[?&]v=([^&#]+)", url)
        if pm:
            v = pm.group(1)
        pp = re.search(r"[?&]p=(\d+)", url)
        p = pp.group(1) if pp else ""
        if not v or not p:
            # 从 /play/secret 提取
            m = re.search(r"/play/([^/?]+)", url)
            if m:
                v = m.group(1)
        if not p or not v:
            return {"parse": 1, "playUrl": "parse:冰豆", "url": url}
        # 1. 拉取详情/播放页, 取 userlink 和服务器时间戳
        play_page = self._get(self.host + "/play/" + v, referer=self.host + "/")
        if not play_page:
            return {"parse": 1, "playUrl": "parse:冰豆", "url": url}
        um = re.search(r"userlink:'([^']*)'", play_page)
        ul = um.group(1) if um else "0"
        sm = re.search(r'id="nb-st" content="(\d+)"', play_page)
        t1 = int(time.time() * 1000)
        st = int(sm.group(1)) if sm else 0
        # 服务器时间校正: t = 当前时间 + (取页时刻 - 服务器时间戳)
        t = str(int(time.time() * 1000) + (t1 - st if st else 0))
        # 签名
        s = hmac.new(v.encode(), f"{p}:{t}:{v}".encode(), hashlib.sha256).hexdigest()[:32]
        kk = quote(self._enc_userlink(ul), safe="")
        api = f"{self.host}/video/play?p={p}&v={v}&q=1080&s={s}&t={t}&k={kk}"
        resp = self._get(api, referer=self.host + "/play/" + v)
        if not resp:
            return {"parse": 1, "playUrl": "parse:冰豆", "url": url}
        try:
            data = json.loads(resp)
            if data.get("code") == 200 and data.get("data", {}).get("quality_urls"):
                best, best_bit = None, -1
                for qu in data["data"]["quality_urls"]:
                    if qu.get("locked"):
                        continue
                    if not re.match(r"^https?://", qu.get("url", "")):
                        continue
                    bit = qu.get("bitrate", 0) or 0
                    if bit > best_bit:
                        best_bit, best = bit, qu.get("url")
                if best:
                    return {"parse": 0, "playUrl": "", "url": best}
            return {"parse": 1, "playUrl": "parse:冰豆", "url": url}
        except Exception:
            return {"parse": 1, "playUrl": "parse:冰豆", "url": url}


if __name__ == "__main__":
    s = Spider()
    print(s.getName(), s.getVersion(), "host:", s.host)
    hc = s.homeContent()
    print("classes:", hc["class"])
    lst = s.homeVideoContent()
    print("home videos:", len(lst["list"]))
    if lst["list"]:
        v = lst["list"][0]
        print("first:", v["vod_name"], "|", v["vod_id"])
        det = s.detailContent([v["vod_id"]])
        d = det["list"][0]
        print("detail:", d["vod_name"][:20], "| from:", d["vod_play_from"][:20])
        print("eps sample:", d["vod_play_url"][:150])
        if d["vod_play_url"]:
            ep = d["vod_play_url"].split("#")[0].split("$")[1]
            pr = s.playerContent([ep], "", [])
            print("play:", pr["url"][:160])