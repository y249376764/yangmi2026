VERSION = "v2.0"
# -*- coding: utf-8 -*-
"""
电影人生 (dyrshd.cc) TVBox 蜘蛛 v1
- Tailwind 前端: 首页模块 / 分类 {tag}.html?page=N&sort_field=play_hot
- 详情: #origin-dropdown-menu 线路 + .episode-list 选集
- 播放: 播放页 aa: JSON.parse('{url}') -> /api/m3u8?origin=&url= -> m3u8 直链
- 更多资源请到网站 https://navpage-2026.surge.sh/
"""
import json
import re
from urllib.parse import quote, unquote, urljoin

import requests

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def __init__(self):
            pass

        def getProxyUrl(self):
            return ""


class Spider(BaseSpider):
    DEFAULT_HOST = "https://dyrshd.cc"
    DEFAULT_UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    CLASSES = [
        {"type_name": "电影", "type_id": "dianying"},
        {"type_name": "电视剧", "type_id": "dianshiju"},
        {"type_name": "综艺", "type_id": "zongyi"},
        {"type_name": "动漫", "type_id": "dongman"},
        {"type_name": "短剧", "type_id": "duanju"},
    ]

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self.host = self.DEFAULT_HOST
        self.ua = self.DEFAULT_UA

    def init(self, extend=""):
        return ""

    def getName(self):
        return "小演"

    def getVersion(self):
        return 1

    def destroy(self):
        pass

    def _absolute(self, url, base=None):
        if not url:
            return ""
        url = url.replace("&amp;", "&")
        if url.startswith(("http://", "https://")):
            return url
        if url.startswith("//"):
            return "https:" + url
        return urljoin(base or self.host, url)

    def _get_text(self, url, referer=""):
        headers = {"User-Agent": self.ua}
        if referer:
            headers["Referer"] = referer
        try:
            with requests.get(url, headers=headers, timeout=10, stream=True) as r:
                if r.status_code != 200:
                    return ""
                chunks = []
                total = 0
                for chunk in r.iter_content(chunk_size=65536):
                    chunks.append(chunk)
                    total += len(chunk)
                    if total > 500000:
                        break
                return b"".join(chunks).decode("utf-8", errors="replace")
        except Exception:
            return ""

    def _follow_redirect(self, url, referer=""):
        """跟随 302 到最终内容 URL (最多 5 跳), 返回最终 URL"""
        headers = {"User-Agent": self.ua}
        if referer:
            headers["Referer"] = referer
        cur = url
        try:
            for _ in range(5):
                r = requests.get(cur, headers=headers, timeout=10, allow_redirects=False, stream=True)
                if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("Location"):
                    loc = r.headers["Location"]
                    cur = self._absolute(loc, cur)
                else:
                    r.close()
                    break
                r.close()
            return cur
        except Exception:
            return url

    # ---------------- 首页/分类 ----------------
    def homeContent(self, filter=False):
        return {"class": list(self.CLASSES), "filters": {}}

    def homeVideoContent(self):
        source = self._get_text(self.host + "/", referer=self.host + "/")
        return {"list": self._parse_list(source)[:60]}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        page = int(pg or 1)
        tid = str(tid or "dianying")
        url = f"{self.host}/{tid}.html?page={page - 1}&sort_field=play_hot"
        if tid == "dianying" and page <= 1:
            url = self.host + "/"
        source = self._get_text(url, referer=self.host + "/")
        videos = self._parse_list(source)
        return {
            "list": videos,
            "page": page,
            "pagecount": 9999,
            "limit": len(videos),
            "total": 9999 * max(len(videos), 1),
        }

    def _parse_list(self, html):
        videos = []
        seen = set()
        if not html:
            return videos
        # 卡片: <a href="/movie/hash-id.html"> <img data-src=...> <h3>标题</h3>
        pattern = re.compile(
            r'<a[^>]*href="(/(?:movie|tv|cartoon|variety)/[^"]+)"[^>]*>(.*?)</a>',
            re.I | re.S,
        )
        for m in pattern.finditer(html):
            href = m.group(1)
            # 跳过带 ?origin 的选集链接
            if "?" in href:
                continue
            if href in seen:
                continue
            seen.add(href)
            block = m.group(2)
            tm = re.search(r"<h3[^>]*>(.*?)</h3>", block, re.S)
            title = re.sub(r"<[^>]+>", "", tm.group(1)).strip() if tm else ""
            if not title:
                tm = re.search(r'<img[^>]*alt="([^"]+)"', block)
                title = tm.group(1).strip() if tm else ""
            if not title:
                continue
            pm = re.search(r'<img[^>]*(?:data-src|src)="([^"]+)"', block)
            pic = self._absolute(pm.group(1), self.host) if pm else ""
            # 状态/备注
            rm = re.search(r'<span[^>]*class="[^"]*(?:absolute|top)[^"]*"[^>]*>(.*?)</span>', block, re.S)
            remark = re.sub(r"<[^>]+>", "", rm.group(1)).strip() if rm else ""
            videos.append({
                "vod_id": href,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return videos

    # ---------------- 搜索 ----------------
    def searchContent(self, key, quick, pg="1"):
        page = int(pg or 1)
        keyword = quote(unquote(str(key or "").strip()), safe="")
        if not keyword:
            return {"list": [], "page": page, "pagecount": 1, "limit": 0, "total": 0}
        url = f"{self.host}/s.html?name={keyword}"
        source = self._get_text(url, referer=self.host + "/")
        videos = self._parse_list(source)
        return {
            "list": videos,
            "page": page,
            "pagecount": 1,
            "limit": len(videos),
            "total": len(videos),
        }

    # ---------------- 详情 ----------------
    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        raw_id = str(raw_id or "").strip()
        if not raw_id:
            return {"list": []}
        if not raw_id.startswith("/"):
            raw_id = "/" + raw_id
        url = self._absolute(raw_id, self.host)
        source = self._get_text(url, referer=self.host + "/")
        if not source:
            return {"list": []}
        vod = self._parse_detail(source, url)
        return {"list": [vod]}

    def _parse_detail(self, html, detail_url):
        vod = {
            "vod_id": "",
            "vod_name": "未知影片",
            "vod_pic": "",
            "vod_year": "",
            "vod_area": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": "",
            "vod_play_from": "",
            "vod_play_url": "",
        }
        # 标题
        tm = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        if tm:
            vod["vod_name"] = re.sub(r"<[^>]+>", "", tm.group(1)).strip()
        # 图片
        pm = re.search(r'<main[^>]*>.*?<img[^>]*src="([^"]+)"', html, re.S)
        if pm:
            vod["vod_pic"] = self._absolute(pm.group(1), detail_url)
        if not vod["vod_pic"]:
            om = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html)
            if om:
                vod["vod_pic"] = self._absolute(om.group(1), detail_url)
        # 简介
        cm = re.search(r'<div[^>]*class="[^"]*leading-relaxed[^"]*"[^>]*>(.*?)</div>', html, re.S)
        if cm:
            vod["vod_content"] = re.sub(r"<[^>]+>", "", cm.group(1)).strip()
        if not vod["vod_content"]:
            dm = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]+)"', html)
            if dm:
                vod["vod_content"] = dm.group(1).strip()
        # 线路 + 选集
        play_from, play_url = self._extract_plays(html, detail_url)
        vod["vod_play_from"] = play_from
        vod["vod_play_url"] = play_url
        return vod

    def _extract_plays(self, html, detail_url):
        # 线路: #origin-dropdown-menu 内的 a[data-value] 或同级 span
        lines = []
        for m in re.finditer(
            r'<option[^>]*value="([^"]+)"[^>]*>([^<]*)</option>', html,
        ):
            name = m.group(2).strip()
            if name and name not in lines:
                lines.append(name)
        if not lines:
            # 常见尾wind下拉: button + ul li[data-origin]
            for m in re.finditer(
                r'data-origin="([^"]+)"[^>]*>\s*<span[^>]*>([^<]*)</span>', html,
            ):
                name = m.group(2).strip()
                if name and name not in lines:
                    lines.append(name)
        # 选集: <a href="/movie/hash/id.html?origin=...&p=N" data-title="...">
        eps = []
        seen = set()
        for m in re.finditer(
            r'<a[^>]*href="(/(?:movie|tv|variety|cartoon|search)/[^"]+\?[^"]*)"[^>]*data-title="([^"]*)"',
            html,
        ):
            href = m.group(1)
            if href in seen:
                continue
            seen.add(href)
            label = m.group(2).strip()
            eps.append({"label": label, "url": self._absolute(href, detail_url)})
        if not eps:
            # 兜底: 所有带 ?origin 的 a
            for m in re.finditer(
                r'<a[^>]*href="(/(?:movie|tv|variety|cartoon)/[^"]+\?[^"]*)"[^>]*>(.*?)</a>',
                html, re.S,
            ):
                href = m.group(1)
                if href in seen:
                    continue
                seen.add(href)
                label = re.sub(r"<[^>]+>", "", m.group(2)).strip()
                eps.append({"label": label, "url": self._absolute(href, detail_url)})
        if not eps:
            return "", ""
        if not lines:
            lines = ["线路1"]
        play_from = "$$$".join(lines)
        groups = []
        for i, line in enumerate(lines):
            groups.append("#".join(f"{e['label']}${e['url']}" for e in eps))
        return play_from, "$$$".join(groups)

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        headers = {'User-Agent': self.ua, 'Referer': url}
        raw = id[0] if isinstance(id, (list, tuple)) and id else id
        url = str(raw or "").strip()
        if not url:
            return {"header": headers}
        source = self._get_text(url, referer=url)
        if not source:
            return {"parse": 0, "playUrl": "", "url": url, "header": headers}
        # aa: JSON.parse('{url:...}')
        m = re.search(r"aa:\s*JSON\.parse\('([^']+)'\)", source)
        if m:
            try:
                json_str = m.group(1)
                # JS 单引号字符串里 \uXXXX 是字面量, 手动还原
                json_str = re.sub(r"\\u([0-9a-fA-F]{4})", lambda mm: chr(int(mm.group(1), 16)), json_str)
                json_str = json_str.replace("\\/", "/").replace("\\&", "&")
                data = json.loads(json_str)
                video_url = data.get("url", "")
                if video_url:
                    if not video_url.startswith("http"):
                        video_url = self._absolute(video_url, url)
                    # 跟随中转重定向 -> 拿到最终 m3u8 直链 (能跟随时)
                    final = self._follow_redirect(video_url, url)
                    return {"parse": 0, "playUrl": "", "url": final or video_url, "header": headers}
            except Exception:
                pass
        # m3u8 直链兜底
        candidates = re.findall(r'https?://[^\s"\']+\.(?:m3u8|mp4)[^\s"\']*', source, re.I)
        for c in candidates:
            if c:
                return {"parse": 0, "playUrl": "", "url": c, "header": headers}
        return {"parse": 1, "playUrl": "", "url": url, "header": headers}


if __name__ == "__main__":
    s = Spider()
    print(s.getName(), s.getVersion())
    print("home classes:", s.homeContent())
    lst = s.homeVideoContent()
    print("home videos:", len(lst.get("list", [])))
    if lst.get("list"):
        v = lst["list"][0]
        print("first:", v["vod_name"], v["vod_id"][:70])
        det = s.detailContent([v["vod_id"]])
        d = det["list"][0]
        print("detail:", d["vod_name"], "| from:", d["vod_play_from"][:30], "| eps:", d["vod_play_url"][:100])
        if d["vod_play_url"]:
            first_ep = d["vod_play_url"].split("#")[0].split("$")[1]
            pr = s.playerContent([first_ep], "", [])
            print("play:", pr)
