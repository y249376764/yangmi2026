VERSION = "v2.0"
# -*- coding: utf-8 -*-
"""
玄武影视 (pywxw) TVBox 蜘蛛 v1
- 需要手机 UA (桌面 UA 403)
- stui 模板: 分类 movtype/{id}.html | 详情 movdetail/{id}.html | 播放 movplay/{id}-{sid}-{nid}.html
- 播放: player_aaaa JSON 里的 url 字段 (m3u8 直链)
- 更多资源请到网站 https://navpage-2026.surge.sh/
"""
import json
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
    HOST = "https://www.pywxw.com"
    UA_MOBILE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                 "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1")
    CLASSES = [
        {"type_name": "电影", "type_id": "1"},
        {"type_name": "电视剧", "type_id": "2"},
        {"type_name": "综艺", "type_id": "5"},
        {"type_name": "动漫", "type_id": "29"},
        {"type_name": "短剧", "type_id": "37"},
    ]

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.UA_MOBILE})

    def init(self, extend=""):
        return ""

    def getName(self):
        return "小玄"

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
            r = self.session.get(url, headers=headers, timeout=12, verify=False)
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
        url = f"{self.HOST}/movtype/{tid}.html?page={page}"
        return {"list": self._parse_list(self._get(url)),
                "page": page, "pagecount": 9999, "limit": 60, "total": 99999}

    def _parse_list(self, html):
        videos, seen = [], set()
        if not html:
            return videos
        for m in re.finditer(
            r'<a[^>]*href="(/movdetail/[^"]+)"[^>]*title="([^"]+)"[^>]*(?:data-original|data-src)="([^"]*)"',
            html,
        ):
            href, title, pic = m.group(1), m.group(2), m.group(3)
            if href in seen:
                continue
            seen.add(href)
            videos.append({
                "vod_id": href,
                "vod_name": title.strip(),
                "vod_pic": self._abs(pic) if pic else "",
                "vod_remarks": "",
            })
        return videos

    # ---------------- 搜索 ----------------
    def searchContent(self, key, quick, pg="1"):
        kw = re.sub(r"\s+", "", str(key or "").strip())
        if not kw:
            return {"list": [], "page": int(pg or 1), "pagecount": 1, "limit": 0, "total": 0}
        url = f"{self.HOST}/search.php?kw={kw}"
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
        og = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html)
        if og:
            vod["vod_pic"] = self._abs(og.group(1))
        om = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]+)"', html)
        if om:
            vod["vod_name"] = om.group(1).strip()
        dm = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]*)"', html)
        if dm:
            vod["vod_content"] = dm.group(1).strip()
        # 主演
        am = re.search(r"主演：</span>(.*?)</", html, re.S)
        if am:
            vod["vod_actor"] = re.sub(r"<[^>]+>", "", am.group(1)).strip()
        # 选集: ul.stui-content__playlist li a[href=/movplay/{id}-{sid}-{nid}.html]
        eps = re.findall(
            r'<a[^>]*href="(/movplay/\d+-(\d+)-(\d+)\.html)"[^>]*>\s*([^<]+?)\s*</a>', html,
        )
        if eps:
            m = re.search(r"/movdetail/(\d+)", raw)
            line_map = {}
            for href, sid, nid, label in eps:
                line_map.setdefault(sid, [])
                label = label.strip()
                if not label:
                    label = f"第{int(nid)}集" if nid else f"第{len(line_map[sid])+1}集"
                line_map[sid].append(f"{label}${self._abs(href, raw)}")
            mp = re.search(r"/movdetail/(\d+)", self.HOST + raw)
            vid = re.search(r"movdetail/(\d+)", raw)
            vname = re.search(r'(\d+)', vid.group(1)) if vid else ""
            vod["vod_play_from"] = "$$$".join(f"线路{i+1}" for i in range(len(line_map)))
            vod["vod_play_url"] = "$$$".join("#".join(line_map[k]) for k in line_map)
        return {"list": [vod]}

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        raw = id[0] if isinstance(id, (list, tuple)) and id else id
        url = str(raw or "").strip()
        headers = {'User-Agent': self.UA_MOBILE, 'Referer': url}
        if not url:
            return {"header": headers}
        html = self._get(url, referer=url)
        if not html:
            return {"parse": 1, "playUrl": "", "url": url, "header": headers}
        # player_aaaa JSON, 提取 url 字段
        pm = re.search(r"var player_aaaa\s*=\s*(\{[^<]*?\});?\s*</script>", html, re.S)
        if pm:
            try:
                # JSON 里 \/ 和 \uXXXX 转义
                js = pm.group(1)
                data = json.loads(js)
                u = data.get("url", "")
                if u:
                    return {"parse": 0, "playUrl": "", "url": u, "header": headers}
                # vod_data.url 备选
                vd = data.get("vod_data") or {}
                u2 = vd.get("url") or data.get("url_next") or ""
                if u2:
                    return {"parse": 0, "playUrl": "", "url": u2, "header": headers}
            except Exception:
                pass
        # 兜底 m3u8
        c = re.findall(r'https?://[^\s"\']+\.(?:m3u8|mp4)[^\s"\']*', html, re.I)
        for x in c:
            if x:
                return {"parse": 0, "playUrl": "", "url": x, "header": headers}
        return {"parse": 1, "playUrl": "", "url": url, "header": headers}


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
        print("detail:", d["vod_name"][:20], "| from:", d["vod_play_from"][:20])
        print("eps:", d["vod_play_url"][:130])
        if d["vod_play_url"]:
            ep = d["vod_play_url"].split("#")[0].split("$")[1]
            pr = s.playerContent([ep], "", [])
            print("play:", pr["url"][:160])