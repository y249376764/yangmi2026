VERSION = "v2.0"
# 全看网 py 蜘蛛 - 网飞式播放(带header防盗链)
# 更多资源请到网站 https://navpage-2026.surge.sh/
# -*- coding: utf-8 -*-
"""
全看网 (91qkw) TVBox 蜘蛛 v1
- 站: pcduan.91qkw.cc (PC 端, 同一电影库)
- stui 模板: 分类 /type/{id}.html | 详情 /vod/detail/{code}.html | 播放 /vod/play/{code}-{line}-{n}.html
- 播放: player_aaaa encrypt:3 加密 -> 返回播放页地址, 交给解析器 parse 兜底
- 更多资源请到网站 https://navpage-2026.surge.sh/
"""
import re
from urllib.parse import unquote, urljoin

import requests

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def __init__(self):
            pass


class Spider(BaseSpider):
    HOST = "https://pcduan.91qkw.cc"
    UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    CLASSES = [
        {"type_name": "电影", "type_id": "1"},
        {"type_name": "电视剧", "type_id": "2"},
        {"type_name": "综艺", "type_id": "3"},
        {"type_name": "动漫", "type_id": "4"},
        {"type_name": "短剧", "type_id": "28"},
    ]

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.UA})

    def init(self, extend=""):
        return ""

    def getName(self):
        return "小看"

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
        return urljoin(base or self.HOST, url)

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

    # ---------------- 首页/分类 ----------------
    def homeContent(self, filter=False):
        return {"class": list(self.CLASSES), "filters": {}}

    def homeVideoContent(self):
        return {"list": self._parse_list(self._get(self.HOST + "/"))[:60]}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        page = int(pg or 1)
        url = f"{self.HOST}/type/{tid}.html"
        if page > 1:
            url = f"{self.HOST}/type/{tid}-{page}.html"
        return {"list": self._parse_list(self._get(url)),
                "page": page, "pagecount": 9999, "limit": 60, "total": 99999}

    def _parse_list(self, html):
        videos, seen = [], set()
        if not html:
            return videos
        for m in re.finditer(
            r'<a[^>]*class="[^"]*stui-vodlist__thumb[^"]*"[^>]*href="(/vod/detail/[^"]+)"[^>]*title="([^"]+)"[^>]*(?:data-original|data-src)="([^"]*)"[^>]*>(.*?)</a>',
            html, re.S,
        ):
            href, title, pic, blk = m.group(1), m.group(2), m.group(3), m.group(4)
            if href in seen:
                continue
            seen.add(href)
            rm = re.search(r'pic-text[^>]*>([^<]+)<', blk)
            remark = rm.group(1).strip() if rm else ""
            videos.append({
                "vod_id": href,
                "vod_name": title.strip(),
                "vod_pic": self._abs(pic) if pic else "",
                "vod_remarks": remark,
            })
        return videos

    # ---------------- 搜索 (m 站) ----------------
    def searchContent(self, key, quick, pg="1"):
        kw = re.sub(r"\s+", "", str(key or "").strip())
        if not kw:
            return {"list": [], "page": int(pg or 1), "pagecount": 1, "limit": 0, "total": 0}
        # PC 站搜索
        url = f"{self.HOST}/search/{kw}.html"
        return {"list": self._parse_list(self._get(url)), "page": int(pg or 1),
                "pagecount": 1, "limit": 60, "total": 60}

    # ---------------- 详情 ----------------
    def detailContent(self, ids):
        raw = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        raw = str(raw or "").strip()
        if not raw:
            return {"list": []}
        if raw.startswith("/"):
            raw = self.HOST + raw
        html = self._get(raw, referer=self.HOST + "/")
        if not html:
            return {"list": []}
        vod = {
            "vod_id": "", "vod_name": "未知影片", "vod_pic": "",
            "vod_year": "", "vod_area": "", "vod_actor": "", "vod_director": "",
            "vod_content": "", "vod_play_from": "", "vod_play_url": "",
        }
        og = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]+)"', html)
        if og:
            vod["vod_name"] = og.group(1).strip()
        if vod["vod_name"] == "未知影片":
            h1 = re.search(r'<h[123][^>]*class="[^"]*title[^"]*"[^>]*>\s*(?:<strong>)?([^<]+?)(?:</strong>)?\s*<', html, re.S)
            if h1:
                vod["vod_name"] = h1.group(1).strip()
        oi = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html)
        if oi:
            vod["vod_pic"] = self._abs(oi.group(1))
        if not vod["vod_pic"]:
            dp = re.search(r'data-pic="([^"]+)"', html)
            if dp:
                vod["vod_pic"] = self._abs(dp.group(1))
        dm = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]*)"', html)
        if dm:
            vod["vod_content"] = dm.group(1).strip()
        # 选集: /vod/play/{code}-{line}-{n}.html
        eps = re.findall(r'<a[^>]*href="(/vod/play/([^"-]+)-(\d+)-(\d+)\.html)"[^>]*>([^<]+?)</a>', html)
        if eps:
            line_map = {}
            for href, code, line, nid, label in eps:
                line_map.setdefault(line, [])
                label = label.strip()
                if not label:
                    label = f"第{int(nid)}集"
                line_map[line].append(f"{label}${self._abs(href, raw)}")
            vod["vod_play_from"] = "$$$".join(f"线路{k}" for k in line_map)
            vod["vod_play_url"] = "$$$".join("#".join(line_map[k]) for k in line_map)
        else:
            # 兜底: 任意 /vod/play/
            eps2 = re.findall(r'href="(/vod/play/[^"]+)"[^>]*>([^<]+?)</a>', html)
            seen2 = set()
            items = []
            for href, label in eps2:
                if href in seen2:
                    continue
                seen2.add(href)
                items.append(f"{label.strip()}${self._abs(href, raw)}")
            if items:
                vod["vod_play_from"] = "线路1"
                vod["vod_play_url"] = "#".join(items)
        return {"list": [vod]}

    # ---------------- 播放 (encrypt, parse 兜底) ----------------
    def playerContent(self, flag, id, vipFlags):
        raw = id[0] if isinstance(id, (list, tuple)) and id else id
        url = str(raw or "").strip()
        if not url:
            return {}
        headers = {"User-Agent": self.UA, "Referer": url}
        html = self._get(url, referer=url)
        if not html:
            return {"parse": 1, "jx": 0, "url": url, "header": headers}
        # 明文 m3u8/mp4 直链
        c = re.findall(r'https?://[^\s"\']+\.(?:m3u8|mp4)[^\s"\']*', html, re.I)
        for x in c:
            if x:
                return {"parse": 0, "jx": 0, "url": x, "header": headers}
        # player_aaaa encrypt:3
        m = re.search(r'var player_aaaa=({.*?});', html, re.S)
        if m:
            try:
                import json as _json
                data = _json.loads(m.group(1))
                enc = data.get("encrypt", 0)
                pd = data.get("play_data", "")
                if pd and enc == 0:
                    return {"parse": 0, "jx": 0, "url": pd if pd.startswith("http") else self._abs(pd, url), "header": headers}
            except Exception:
                pass
        return {"parse": 1, "jx": 0, "url": url, "header": headers}


if __name__ == "__main__":
    s = Spider()
    print(s.getName(), s.getVersion())
    print("home:", s.homeContent()["class"])
    lst = s.homeVideoContent()
    print("home videos:", len(lst["list"]))
    if lst["list"]:
        v = lst["list"][0]
        print("first:", v["vod_name"], v["vod_id"])
        det = s.detailContent([v["vod_id"]])
        d = det["list"][0]
        print("detail:", d["vod_name"][:20], "| from:", d["vod_play_from"][:30])
        print("eps:", d["vod_play_url"][:120])