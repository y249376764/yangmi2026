# -*- coding: utf-8 -*-
"""
看片狂人 (kpkuang) TVBox 蜘蛛 v1
- 多域名: .us / .cfd / .fyi / .org (探活自动切换)
- MacCMS fed 模板: 列表 /voddetail/{id}/ | 播放 /vodplay/{vid}-{sid}-{n}.html
- 播放: 播放页正则提取 m3u8/mp4 直链; 失败返回播放页地址交由解析器兜底
- 更多资源请到网站 https://navpage-2026.surge.sh/
"""
import re
import time
from urllib.parse import quote, unquote, urljoin, urlparse

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
    DOMAINS = [
        "https://www.kpkuang.us",
        "https://www.kpkuang.cfd",
        "https://kpkuang.fyi",
        "https://kpkuang.org",
    ]
    DEFAULT_HOST = DOMAINS[0]
    DEFAULT_UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    CLASSES = [
        {"type_name": "电影", "type_id": "1"},
        {"type_name": "连续剧", "type_id": "2"},
        {"type_name": "综艺", "type_id": "3"},
        {"type_name": "动漫", "type_id": "4"},
        {"type_name": "短剧", "type_id": "37"},
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
        return "小狂"

    def getVersion(self):
        return 1

    def destroy(self):
        pass

    def _absolute(self, url, base=None):
        if not url:
            return ""
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

    def _try_domains(self, path):
        """多域名探活: 先试当前 host, 失败换下一个可用域名"""
        domains = list(self.DOMAINS)
        if self.host in domains:
            domains.remove(self.host)
            domains.insert(0, self.host)
        for host in domains:
            text = self._get_text(host + path, referer=host + "/")
            if text and len(text) > 500:
                if self.host != host:
                    self.host = host
                return text
        return ""

    # ---------------- 首页/分类 ----------------
    def homeContent(self, filter=False):
        return {"class": list(self.CLASSES), "filters": {}}

    def homeVideoContent(self):
        source = self._try_domains("/vodtype/1.html")
        return {"list": self._parse_list(source)[:60]}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        page = int(pg or 1)
        tid = str(tid or "1")
        path = f"/vodtype/{tid}.html"
        if page > 1:
            path = f"/vodtype/{tid}-{page}.html"
        source = self._try_domains(path)
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
        pattern = re.compile(
            r"<a[^>]*href=\"(/voddetail/[^\"]+)\"[^>]*>(.*?)</a>",
            re.I | re.S,
        )
        for m in pattern.finditer(html):
            href = m.group(1)
            if href in seen:
                continue
            seen.add(href)
            block = m.group(0) + m.group(2)
            title = ""
            tm = re.search(r'title="([^"]+)"', block, re.I)
            if tm:
                title = tm.group(1)
            if not title:
                tm = re.search(r"<img[^>]*alt=\"([^\"]+)\"", block, re.I)
                if tm:
                    title = tm.group(1)
            title = title.strip()
            if not title:
                continue
            pic = ""
            pm = re.search(r"(?:data-original|data-src|data-lazy|src)=\"([^\"]+)\"", block, re.I)
            if pm:
                pic = self._absolute(pm.group(1), self.host)
            remark = ""
            rm = re.search(r'<span[^>]*class="[^"]*fed-list-remarks[^"]*"[^>]*>(.*?)</span>', block, re.I | re.S)
            if rm:
                remark = re.sub(r"<[^>]+>", "", rm.group(1)).strip()
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
        path = f"/vodsearch/{keyword}-------------.html"
        if page > 1:
            path = f"/vodsearch/{keyword}-------------.html?page={page}"
        source = self._try_domains(path)
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
        if raw_id.startswith("/voddetail/"):
            pass
        elif raw_id.isdigit():
            raw_id = f"/voddetail/{raw_id}/"
        detail_url = self._absolute(raw_id, self.host)
        source = self._try_domains(urlparse(detail_url).path if detail_url.startswith(self.host) else raw_id)
        if not source:
            source = self._get_text(detail_url, referer=self.host + "/")
        if not source:
            return {"list": []}

        vod = self._parse_detail(source, detail_url)
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
        tm = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
        if tm:
            name = re.sub(r"<[^>]+>", "", tm.group(1)).strip()
            name = re.sub(r"\s*\(\d{4}\)\s*$", "", name)
            vod["vod_name"] = name
        # 年份
        ym = re.search(r"<h1[^>]*>.*?\((\d{4})\)", html, re.I | re.S)
        if ym:
            vod["vod_year"] = ym.group(1)
        # 图片
        pm = re.search(r'(?:data-original|data-src|src)="([^"]+)"', html, re.I)
        if pm:
            vod["vod_pic"] = self._absolute(pm.group(1), detail_url)
        if not vod["vod_pic"]:
            om = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html, re.I)
            if om:
                vod["vod_pic"] = self._absolute(om.group(1), detail_url)
        # 简介
        cm = re.search(r'<div[^>]*class="[^"]*fed-part-tips[^"]*"[^>]*>(.*?)</div>', html, re.I | re.S)
        if cm:
            vod["vod_content"] = re.sub(r"<[^>]+>", "", cm.group(1)).strip()
        if not vod["vod_content"]:
            dm = re.search(r"以下是剧情简介：\s*(.{10,400})", re.sub(r"<[^>]+>", " ", html))
            if dm:
                vod["vod_content"] = re.sub(r"\s+", " ", dm.group(1)).strip()
        # 线路 + 选集
        play_from, play_url = self._extract_plays(html, detail_url)
        vod["vod_play_from"] = play_from
        vod["vod_play_url"] = play_url
        return vod

    def _extract_plays(self, html, detail_url):
        # 线路名与选集: 每个「XX的播放列表」标题后跟一个 ul.fed-part-rows 选集块
        # 选集 a.fed-btns-info[href=/vodplay/...]
        line_pat = re.compile(
            r'<span[^>]*>([^<]+)</span>\s*的播放列表.*?<ul class="fed-part-rows"[^>]*>(.*?)</ul>',
            re.I | re.S,
        )
        groups = []          # [(line_name, [ep,...])]
        seen_lines = set()
        for m in line_pat.finditer(html):
            name = re.sub(r"\s+", "", m.group(1))
            if not name or name in seen_lines:
                continue
            seen_lines.add(name)
            block = m.group(2)
            eps = []
            seen_ep = set()
            for am in re.finditer(
                r'<a[^>]*class="[^"]*fed-btns-info[^"]*"[^>]*href="(/vodplay/[^"]+)"[^>]*>(.{0,200}?)</a>',
                block, re.I | re.S,
            ):
                href = am.group(1)
                if href in seen_ep:
                    continue
                seen_ep.add(href)
                label = re.sub(r"<[^>]+>", "", am.group(2)).strip()
                label = re.sub(r"\s+", "", label)
                if not label:
                    continue
                # 集数: 提取数字 (EP5 / 第5集 / 05), 无则用链接尾数
                parts = href.rstrip(".html").rsplit("-", 2)
                num = parts[-1] if len(parts) >= 3 else ""
                eps.append({"label": label, "num": num, "url": self._absolute(href, detail_url)})
            if eps:
                groups.append({"name": name, "eps": eps})
        if not groups:
            return "", ""
        play_from = "$$$".join(g["name"] for g in groups)
        groups_str = []
        for g in groups:
            # 同 num 去重(多个片源只留第一个)
            seen_num = set()
            final = []
            for e in g["eps"]:
                k = e["num"] or e["label"]
                if k in seen_num:
                    continue
                seen_num.add(k)
                final.append(e)
            groups_str.append("#".join(f"{e['label']}${e['url']}" for e in final))
        return play_from, "$$$".join(groups_str)

    # ---------------- 播放 ----------------
    def playerContent(self, ids, flag, vipFlags):
        raw = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        url = str(raw or "").strip()
        if not url:
            return {}
        source = self._get_text(url, referer=url)
        if not source:
            return {"parse": 1, "playUrl": "", "url": url}
        # Cloudflare 验证页
        if "Just a moment" in source or "challenge-platform" in source:
            return {"parse": 1, "playUrl": "", "url": url}
        # 提取直链: m3u8 / mp4 / flv 等
        candidates = re.findall(r'https?://[^\s"\']+\.(?:m3u8|mp4|flv|mkv|ts)[^\s"\']*', source, re.I)
        for c in candidates:
            c = c.replace("\\/", "/")
            if c:
                return {"parse": 0, "playUrl": "", "url": c}
        # 播放器变量 player_aaaa
        pm = re.search(r'var player_aaaa\s*=\s*(\{[\s\S]*?\});?\s*</script>', source)
        if pm:
            try:
                import json
                p = json.loads(pm.group(1))
                u = p.get("url", "")
                if u:
                    return {"parse": 0, "playUrl": "", "url": u}
            except Exception:
                pass
        # 兜底: 返回播放页地址, 交给解析器
        return {"parse": 1, "playUrl": "", "url": url}


if __name__ == "__main__":
    s = Spider()
    print(s.getName(), s.getVersion())
    print("home classes:", s.homeContent())
    lst = s.homeVideoContent()
    print("home videos:", len(lst.get("list", [])))
    if lst.get("list"):
        v = lst["list"][0]
        print("first:", v["vod_name"], v["vod_id"][:60])
        det = s.detailContent([v["vod_id"]])
        print("detail:", det["list"][0]["vod_name"], "| from:", det["list"][0]["vod_play_from"][:50], "| url:", det["list"][0]["vod_play_url"][:80])
