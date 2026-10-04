# -*- coding: utf-8 -*-
# 果果短剧[py] Spider — https://www.mochadj.com (MacCMS 短剧站)
# 特性: 直链 master m3u8 (1080x1920, AES-128), 原生全屏播放(同围观), 绕开 jar 内置 csp_XBPQ 的复杂跳转
# 链路:
#   分类:  https://www.mochadj.com/i/{cid}-{pg}.html → 详情卡 (a.stui-vodlist__thumb)
#   详情:  https://www.mochadj.com/dj/{id}.html → var vod_name/vod_pic + 立即播放 /play/{id}-0-0.html
#   播放:  https://www.mochadj.com/play/{id}-0-0.html → 正则抓 master m3u8

import re
import time
import urllib.parse
import urllib.request
from base.spider import Spider as BaseSpider

HOST = "https://www.mochadj.com"
UA = "Mozilla/5.0 (Linux; Android 10; MI 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36"

CATS = [
    ("1", "重生"), ("2", "穿越"), ("3", "爽剧"), ("4", "言情"),
    ("5", "都市"), ("6", "古装"), ("7", "悬疑"), ("8", "剧情"),
]


def _strip(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    return re.sub(r"\s+", " ", s).strip()


class Spider(BaseSpider):
    name = "果果短剧v2"

    def __init__(self):
        self.host = HOST
        self.ua = UA

    # ---------- 基础工具 ----------
    def _get(self, url, ref=None):
        for _ in range(2):
            try:
                h = {"User-Agent": self.ua}
                if ref:
                    h["Referer"] = ref
                req = urllib.request.Request(url, headers=h)
                with urllib.request.urlopen(req, timeout=20) as r:
                    return r.read().decode("utf-8", errors="ignore")
            except Exception:
                time.sleep(1.0)
        return ""

    @staticmethod
    def _abs(url, base):
        u = str(url or "").strip()
        if not u:
            return ""
        return u if u.startswith("http") else urllib.parse.urljoin(base, u)

    def _make_vod(self, href, title, pic):
        m = re.search(r"/dj/(\d+)\.html", href)
        vid = m.group(1) if m else href
        return {
            "vod_id": vid,
            "vod_name": title.strip(),
            "vod_pic": pic,
            "vod_remarks": "短剧",
        }

    # ---------- 首页 / 分类 ----------
    def init(self, extend=""):
        return self.homeContent(extend)

    def homeContent(self, filter=False):
        return {"class": [{"type_id": c, "type_name": n} for c, n in CATS]}

    def homeVodContent(self, page=1, filter=False):
        return self.categoryContent("1", str(page), False)

    def categoryContent(self, tid, pg, filter=False, extend=""):
        page = str(pg or 1)
        url = "%s/i/%s-%s.html" % (self.host, tid, page)
        html = self._get(url, self.host + "/")
        vods = []
        if html:
            for m in re.finditer(
                r'<a[^>]*class="[^"]*stui-vodlist__thumb[^"]*"[^>]*href="(/dj/\d+\.html)"[^>]*title="([^"]*)"[^>]*data-original="([^"]*)"',
                html,
            ):
                href, title, pic = m.group(1), m.group(2) or "", m.group(3) or ""
                if href and title:
                    vods.append(self._make_vod(href, title, self._abs(pic, self.host)))
            if not vods:
                for m in re.finditer(r'<a[^>]*href="(/dj/\d+\.html)"[^>]*>([^<]{2,50})</a>', html):
                    vods.append(self._make_vod(m.group(1), m.group(2), ""))
        pagecount = int(page)
        if re.search(r"/i/%s-%d\.html" % (re.escape(tid), int(page) + 1), html):
            pagecount = int(page) + 1
        return {"list": vods, "page": int(page), "pagecount": max(pagecount, 1)}

    # ---------- 详情 ----------
    def detailContent(self, ids):
        vid = str(ids[0]).split("$")[0]
        detail_url = "%s/dj/%s.html" % (self.host, vid)
        html = self._get(detail_url, self.host + "/")
        name = pic = intro = ""
        h1 = re.search(r"<h1[^>]*>([^<]+)</h1>", html)
        if h1:
            name = h1.group(1).strip()
        if not name:
            t = re.search(r"<title>(.*?)</title>", html, re.S)
            if t:
                name = t.group(1).split("_")[0].strip()
        m = re.search(r'data-original="([^"]+)"', html)
        if m:
            pic = m.group(1)
        di = html.find("简介")
        if di >= 0:
            # 跳过"简介："冒号
            j = di + 2
            while j < len(html) and html[j] in " ：: \t\r\n":
                j += 1
            frag = html[j:j + 800]
            end = frag.find("<")
            if end > 0:
                intro = _strip(frag[:end])
        pm = re.search(r'href="(/play/%s-\d+-\d+\.html)"' % re.escape(vid), html)
        play_path = pm.group(1) if pm else "/play/%s-0-0.html" % vid
        play_full = self._abs(play_path, self.host)
        m3u8 = self._resolve_m3u8(play_full)
        vod = {
            "vod_id": vid,
            "vod_name": name or "短剧",
            "vod_pic": self._abs(pic, self.host),
            "vod_content": intro,
            "vod_play_from": "果果直链v2",
            "vod_play_url": m3u8 or play_full,
        }
        return {"list": [vod]}

    def _resolve_m3u8(self, play_full):
        html = self._get(play_full, play_full)
        if not html:
            return ""
        m = re.search(r'(https?://[^"\'\s<>]+?\.m3u8[^"\'\s<>]*)', html)
        return m.group(1) if m else ""

    def searchContent(self, key, quick, pg="1"):
        return []

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags=None):
        url = str(id or "").strip()
        return {"parse": 0, "jx": 0, "playUrl": "", "url": url, "header": {}}

    def isVideoFormat(self, url):
        return bool(re.search(r"\.(?:m3u8|mp4|flv|mkv|ts|webm)(?:$|\?)", str(url or ""), re.I))

    def manualVideoCheck(self):
        return False

    def getName(self):
        return "果果短剧v2"

    def getCategory(self):
        return [{"type_id": c, "type_name": n} for c, n in CATS]