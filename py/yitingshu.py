# -*- coding: utf-8 -*-
# 易听书网 (yitingshu.com) - TVBox 音频爬虫 (纯正则版, 无 bs4 依赖)
# 适用于 默影视/影视仓/TVBox 听书

import re
import requests
from urllib.parse import quote, urljoin
from base.spider import Spider


class Spider(Spider):
    def getName(self):
        return "易听书网"

    def init(self, extend=""):
        self.host = "https://www.yitingshu.com"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Linux; Android 12; M2104K10AC) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0 Mobile Safari/537.36",
            "Referer": self.host + "/",
        })
        self.class_map = {
            "言情": "1",
            "武侠": "2",
            "悬疑": "3",
            "历史": "4",
            "军事": "5",
            "评书": "6",
            "相声小品": "7",
            "商业财经": "9",
        }

    def _fix_url(self, url):
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("http"):
            return url
        return urljoin(self.host, url)

    def _fetch(self, url, timeout=15):
        try:
            resp = self.session.get(url, timeout=timeout)
            if resp.status_code == 200:
                resp.encoding = "utf-8"
                return resp.text
            return ""
        except Exception as e:
            print(f"[{self.getName()}] 请求失败: {e}")
            return ""

    def _extract_audios(self, html, is_search=False):
        """提取音频列表（首页、分类、搜索通用）- 纯正则"""
        audios = []
        seen = set()

        # 每个条目: <li> ... <a href="/tingshu/ID.html" title="..."> <img data-original="..." src="...">
        # 匹配 li 块
        li_pattern = re.compile(
            r'<li[^>]*>(.*?)</li>', re.S)
        for li in li_pattern.finditer(html):
            block = li.group(1)

            # 详情链接
            href_m = re.search(r'href="([^"]*?/tingshu/(\d+)\.html)"', block)
            if not href_m:
                continue
            href = href_m.group(1)
            vod_id = href_m.group(2)
            if vod_id in seen:
                continue
            seen.add(vod_id)

            # 封面
            pic = ""
            img_m = re.search(r'<img[^>]*?(?:data-original="([^"]*)"|src="([^"]*)")', block)
            if img_m:
                pic = img_m.group(1) or img_m.group(2) or ""

            # 标题: a title 属性优先, 其次 h4 a 文本
            title = ""
            title_m = re.search(r'href="[^"]*?"[^>]*?title="([^"]*)"', block)
            if title_m:
                title = title_m.group(1).strip()
            if not title:
                h4_m = re.search(r'<h4[^>]*>\s*<a[^>]*>(.*?)</a>', block, re.S)
                if h4_m:
                    title = re.sub(r'<[^>]+>', '', h4_m.group(1)).strip()
            if not title:
                # 列表页图片 alt
                alt_m = re.search(r'<img[^>]*?alt="([^"]*)"', block)
                if alt_m:
                    title = alt_m.group(1).strip()

            # 备注 (pic-text span / 作者 p)
            remarks = ""
            pt_m = re.search(r'<span class="pic-text"[^>]*>(.*?)</span>', block, re.S)
            if pt_m:
                remarks = re.sub(r'<[^>]+>', '', pt_m.group(1)).strip()
            if not remarks:
                p_m = re.search(r'<p class="text-muted"[^>]*>(.*?)</p>', block, re.S)
                if p_m:
                    remarks = re.sub(r'<[^>]+>', '', p_m.group(1)).strip()

            if pic and not pic.startswith("http"):
                pic = self._fix_url(pic)

            audios.append({
                "vod_id": vod_id,
                "vod_name": title or f"音频{vod_id}",
                "vod_pic": pic,
                "vod_remarks": remarks,
            })

        return audios

    def _extract_pagecount(self, html):
        """提取分页总数"""
        # <a href="/yi/1-2.html">2</a> 或 尾页
        nums = re.findall(r'href="[^"]*?-(\d+)\.html"', html)
        if nums:
            return max(int(x) for x in nums)
        return 1

    def homeContent(self, filter=False):
        classes = [{"type_id": v, "type_name": k} for k, v in self.class_map.items()]
        return {"class": classes}

    def homeVideoContent(self):
        """首页推荐: 各分类第一页前几条"""
        result = []
        seen = set()
        for cat_id in list(self.class_map.values())[:4]:
            url = f"{self.host}/yi/{cat_id}-1.html"
            html = self._fetch(url)
            if not html:
                continue
            for item in self._extract_audios(html):
                if item["vod_id"] in seen:
                    continue
                seen.add(item["vod_id"])
                result.append(item)
                if len(result) >= 24:
                    break
            if len(result) >= 24:
                break
        return {"list": result}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        try:
            pg = int(pg) if str(pg).isdigit() else 1
            cat_name = ""
            for k, v in self.class_map.items():
                if v == tid:
                    cat_name = k
                    break
            if not cat_name:
                cat_name = tid

            url = f"{self.host}/yi/{tid}-{pg}.html"
            html = self._fetch(url)
            if not html:
                return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}

            audios = self._extract_audios(html)
            pagecount = self._extract_pagecount(html)

            return {
                "list": audios,
                "page": pg,
                "pagecount": pagecount if pagecount > 1 else pg + 1,
                "limit": 24,
                "total": pagecount * 24 if pagecount > 1 else len(audios),
            }
        except Exception as e:
            print(f"[{self.getName()}] categoryContent 异常: {e}")
            return {"list": [], "page": pg, "pagecount": 1, "limit": 24, "total": 0}

    def detailContent(self, ids):
        try:
            vod_id = ids[0]
            if "/tingshu/" in vod_id:
                m = re.search(r"/tingshu/(\d+)\.html", vod_id)
                if m:
                    vod_id = m.group(1)

            url = f"{self.host}/tingshu/{vod_id}.html"
            html = self._fetch(url)
            if not html:
                return {"list": []}

            # 标题
            title = ""
            h1_m = re.search(r'<h1[^>]*class="title"[^>]*>(.*?)</h1>', html, re.S)
            if h1_m:
                title = re.sub(r'<[^>]+>', '', h1_m.group(1)).strip()
            if not title:
                t_m = re.search(r'<title>(.*?)</title>', html, re.S)
                if t_m:
                    title = t_m.group(1).strip()

            # 封面
            pic = ""
            img_m = re.search(r'<img[^>]*?(?:data-original="([^"]*)"|src="([^"]*)")[^>]*class="[^"]*lazyload[^"]*"', html)
            if not img_m:
                img_m = re.search(r'<div class="stui-content__thumb"[^>]*>.*?<img[^>]*?(?:data-original="([^"]*)"|src="([^"]*)")', html, re.S)
            if img_m:
                pic = img_m.group(1) or img_m.group(2) or img_m.group(3) or img_m.group(4) or ""
            pic = self._fix_url(pic)

            # 作者
            author = ""
            au_m = re.search(r'<p class="data"[^>]*>.*?</span>(.*?)</p>', html, re.S)
            if au_m:
                author = re.sub(r'<[^>]+>', '', au_m.group(1)).strip()

            # 简介
            desc = ""
            desc_m = re.search(r'<div id="desc"[^>]*>(.*?)</div>', html, re.S)
            if desc_m:
                desc = re.sub(r'<[^>]+>', '', desc_m.group(1)).strip()
            if not desc:
                dc_m = re.search(r'<span class="detail-content"[^>]*>(.*?)</span>', html, re.S)
                if dc_m:
                    desc = re.sub(r'<[^>]+>', '', dc_m.group(1)).strip()

            # 播放列表: <div class="stui-content__playlist"> <a href="/tingshu/ID.html">第X集</a>
            episodes = []
            ep_pat = re.compile(r'href="(/play/\d+-\d+-\d+\.html|[^"]*?/tingshu/\d+\.html)"[^>]*>(.*?)</a>', re.S)
            for m in ep_pat.finditer(html):
                ep_url = m.group(1)
                ep_name = re.sub(r'<[^>]+>', '', m.group(2)).strip()
                if not ep_name:
                    continue
                episodes.append(f"{ep_name}${ep_url}")

            vod = {
                "vod_id": str(vod_id),
                "vod_name": title,
                "vod_pic": pic,
                "type_name": author,
                "vod_actor": author,
                "vod_content": desc,
                "vod_play_from": "易听书网",
                "vod_play_url": "#".join(episodes) if episodes else "",
            }
            return {"list": [vod]}
        except Exception as e:
            print(f"[{self.getName()}] detailContent 异常: {e}")
            return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        try:
            result = {"parse": 0, "playUrl": "", "url": "", "header": {}}
            if not id or id == "#":
                return result

            # 音频直链直接返回
            if id.startswith("http") and any(f in id for f in [".mp3", ".m4a", ".aac", ".ogg", ".m3u8"]):
                result["url"] = id
                result["header"] = {
                    "Referer": self.host + "/",
                    "User-Agent": self.session.headers.get("User-Agent", "Mozilla/5.0"),
                }
                return result

            # 播放页链接
            if "/tingshu/" in id or "/play/" in id:
                if not id.startswith("http"):
                    id = self._fix_url(id)
                html = self._fetch(id)
                if not html:
                    return result
                # 找音频直链: mp3/m4a 等
                audio_m = re.search(r'https?://[^"\'\s<>]+?\.(?:mp3|m4a|aac|ogg)(?:\?[^"\'\s<>]*)?', html)
                if audio_m:
                    result["url"] = audio_m.group(0)
                    result["header"] = {
                        "Referer": self.host + "/",
                        "User-Agent": self.session.headers.get("User-Agent", "Mozilla/5.0"),
                    }
                    return result
                # 找 m3u8
                m3u8_m = re.search(r'https?://[^"\'\s<>]+?\.m3u8(?:\?[^"\'\s<>]*)?', html)
                if m3u8_m:
                    result["url"] = m3u8_m.group(0)
                    result["header"] = {
                        "Referer": self.host + "/",
                        "User-Agent": self.session.headers.get("User-Agent", "Mozilla/5.0"),
                    }
                    return result

            return result
        except Exception as e:
            print(f"[{self.getName()}] playerContent 异常: {e}")
            return {"parse": 0, "playUrl": "", "url": "", "header": {}}

    def searchContent(self, key, quick):
        try:
            url = f"{self.host}/search.php?wd={quote(str(key))}"
            html = self._fetch(url)
            if not html:
                return {"list": []}
            audios = self._extract_audios(html, is_search=True)
            return {"list": audios}
        except Exception as e:
            print(f"[{self.getName()}] searchContent 异常: {e}")
            return {"list": []}

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        if self.session:
            self.session.close()
