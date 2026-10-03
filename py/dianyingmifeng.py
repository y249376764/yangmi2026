# -*- coding: utf-8 -*-
"""
电影蜜蜂 影视蜘蛛版 (dianyingmifeng.py)
----------------------------------------
站点: https://www.meituuan.com/  (茶杯狐 cupfox 模板 MacCMS)

接口(全部 GET, 无需登录):
  首页           https://www.meituuan.com/
  分类列表       https://www.meituuan.com/mevodshow/{cateId}--------{pg}---.html
  搜索           https://www.meituuan.com/mevodsearch/{词}-------------.html   (词需URL编码)
  详情页         https://www.meituuan.com/mevoddetail/{id}.html
  播放页         https://www.meituuan.com/mevodplay/{id}-{line}-{ep}.html

列表卡片:  data-original="图片"  +  href="/mevoddetail/{id}.html"  +  title="片名"
详情播放列表: <div id="playlist1"> 内 <li><a href="/mevodplay/{id}-{line}-{ep}.html">第N集</a>
播放页: 页面内嵌 "url":"https://...m3u8"  变量(JSON格式, 反斜杠转义)

分类(ext 配置): 电影$1#电视剧$2#综艺$3#樱花动漫$4#
"""
import re
import json

import requests

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        def getName(self): return ''
        def init(self, extend=''): pass
        def homeContent(self, filter=False): return {"class": [], "list": [], "filters": {}}
        def homeVideoContent(self): return {"list": []}
        def categoryContent(self, tid, pg, filter=False, extend=''): return {"list": []}
        def detailContent(self, ids): return {"list": []}
        def searchContent(self, key, quick, pg='1'): return {"list": []}
        def playerContent(self, flag, id, vipFlags=None): return {"parse": 0, "url": ""}
        def localProxy(self, param=''): return {}
        def isVideoFormat(self, url): return False
        def manualVideoCheck(self): return False
        def destroy(self): pass


class Spider(BaseSpider):
    host = "https://www.meituuan.com"
    UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    timeout = 12

    # 分类: 电影/电视剧/综艺/樱花动漫
    HOME_CLASS = [
        (1, "电影"), (2, "电视剧"), (3, "综艺"), (4, "樱花动漫"),
    ]

    # ------------------------------------------------------------
    def _get(self, url, referer=None):
        headers = {"User-Agent": self.UA}
        if referer:
            headers["Referer"] = referer
        try:
            r = requests.get(url, headers=headers, timeout=self.timeout)
            if r.status_code != 200:
                return None
            return r
        except Exception:
            return None

    def _parse_cards(self, html):
        """从列表页解析卡片: 图片/链接/标题"""
        items = []
        for m in re.finditer(r'data-original="([^"]+)".*?href="([^"]+)".*?title="([^"]+)"', html, re.S):
            pic, href, title = m.group(1), m.group(2), m.group(3)
            vid = ""
            mm = re.search(r'/mevoddetail/(\d+)\.html', href)
            if mm:
                vid = mm.group(1)
            if not vid:
                continue
            items.append({
                "vod_id": vid,
                "vod_name": title.strip(),
                "vod_pic": pic,
                "vod_remarks": "",
            })
        return items

    # ------------------------------------------------------------
    def init(self, extend=""):
        pass

    def getName(self):
        return "电影蜜蜂[py]"

    def isVideoFormat(self, url):
        return True

    def manualVideoCheck(self):
        return False

    # ------------------------------------------------------------
    # 首页: 分类 + 推荐
    # ------------------------------------------------------------
    def homeContent(self, filter):
        classes = [{"type_id": str(cid), "type_name": name} for cid, name in self.HOME_CLASS]
        vods = []
        d = self._get(self.host + "/", referer=self.host + "/")
        if d:
            vods = self._parse_cards(d.text)
        return {"class": classes, "list": vods[:20], "filters": {}}

    def homeVideoContent(self):
        d = self._get(self.host + "/", referer=self.host + "/")
        vods = []
        if d:
            vods = self._parse_cards(d.text)
        return {"list": vods[:20]}

    # ------------------------------------------------------------
    # 分类内容
    # ------------------------------------------------------------
    def categoryContent(self, tid, pg, filter=False, extend=""):
        page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
        url = f"{self.host}/mevodshow/{tid}--------{page}---.html"
        d = self._get(url, referer=self.host + "/")
        vods = []
        if d:
            vods = self._parse_cards(d.text)
        return {"list": vods, "page": page, "pagecount": 999, "limit": 24, "total": len(vods)}

    # ------------------------------------------------------------
    # 搜索
    # ------------------------------------------------------------
    def searchContent(self, key, quick, pg="1"):
        url = f"{self.host}/mevodsearch/{requests.utils.quote(key)}-------------.html"
        d = self._get(url, referer=self.host + "/")
        vods = []
        if d:
            vods = self._parse_cards(d.text)
        return {"list": vods, "page": 1, "pagecount": 1, "limit": len(vods), "total": len(vods)}

    # ------------------------------------------------------------
    # 详情
    # ------------------------------------------------------------
    def detailContent(self, ids):
        vid = str(ids[0]) if isinstance(ids, (list, tuple)) else str(ids)
        d = self._get(f"{self.host}/mevoddetail/{vid}.html", referer=self.host + "/")
        vod = {"vod_id": vid, "vod_name": f"影片{vid}", "vod_pic": "", "vod_play_from": "", "vod_play_url": ""}
        if d is None:
            return {"list": [vod]}
        html = d.text

        # 标题
        m = re.search(r'<h1[^>]*>([^<]+)</h1>', html, re.S)
        if m:
            vod["vod_name"] = m.group(1).strip()

        # 图片
        m = re.search(r'data-original="([^"]+)"', html)
        if not m:
            m = re.search(r'<img[^>]*src="([^"]+)"[^>]*class="[^"]*lazyload[^"]*"', html)
        if m:
            vod["vod_pic"] = m.group(1)

        # 简介
        m = re.search(r'(?:剧情|简介)[：:]\s*</[^>]+>\s*<p[^>]*>([^<]*)</p>', html, re.S)
        if m:
            vod["vod_content"] = m.group(1).strip()

        # 播放列表: 线路容器
        lines = []  # (线路名, [(集名, 播放页URL)])
        # 找所有播放列表容器: id="playlistN"
        for lm in re.finditer(r'<div[^>]*id="playlist(\d+)"[^>]*>(.*?)</div>', html, re.S):
            line_no = lm.group(1)
            line_html = lm.group(2)
            eps = []
            for em in re.finditer(r'href="(/mevodplay/[^"]+)"[^>]*>([^<]+)</a>', line_html):
                eps.append((em.group(2).strip(), em.group(1)))
            if eps:
                lines.append((f"线路{line_no}", eps))

        # 线路名: 找线路标题(通常在播放列表上方)
        for i, (name, eps) in enumerate(lines):
            # 尝试从容器前找标题
            lines[i] = (f"线路{i+1}", eps)

        # 组播放串
        play_from = []
        play_url = []
        for name, eps in lines:
            play_from.append(name)
            play_url.append("#".join(f"{n}${u}" for n, u in eps))
        if play_from:
            vod["vod_play_from"] = "$$$".join(play_from)
            vod["vod_play_url"] = "$$$".join(play_url)

        return {"list": [vod]}

    # ------------------------------------------------------------
    # 播放: 从播放页提取 m3u8/mp4 直链
    # ------------------------------------------------------------
    def playerContent(self, flag, id, vipFlags=None):
        # id = /mevodplay/{vid}-{line}-{ep}.html
        if not id.startswith("/"):
            id = "/" + id
        d = self._get(self.host + id, referer=self.host + "/")
        if d is None:
            return {"parse": 0, "url": ""}
        html = d.text

        # 播放页内嵌 "url":"https:\/\/...\/index.m3u8" (JSON转义)
        url = ""
        # 精确: 找含 m3u8/mp4 的 url 字段 (跳过 www.cupfoxl.com 等站点信息)
        for m in re.finditer(r'"url"\s*:\s*"([^"]+)"', html):
            cand = m.group(1).replace("\\/", "/")
            if "m3u8" in cand or "mp4" in cand or "m3u" in cand:
                url = cand
                break
        # 兜底: 直接找 m3u8/mp4
        if not url:
            m = re.search(r'https?://[^"\'<> ]+\.(?:m3u8|mp4)[^"\'<> ]*', html)
            if m:
                url = m.group(0)

        return {"parse": 0, "url": url}

    def localProxy(self, param=""):
        return {}

    def destroy(self):
        pass
