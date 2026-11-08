# -*- coding: utf-8 -*-
"""
单田芳评书网 pingshu5.net —— 评书源（TVBox / 影视仓 py 蜘蛛）

对接站点：http://www.pingshu5.net

链路：
  分类   /pbook/  单田芳评书      /ykc/  袁阔成评书      /llr/  连丽如评书
  书目录 /pbook/{slug}/           回目链接 /pbook/{id}.html
  播放   /pbook/{id}.html         <audio src="...m4a|mp3">

@author xinghuo
"""
import re

from requests import Session

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        def getName(self):
            return ''

        def init(self, extend=''):
            pass

        def homeContent(self, filter=False):
            return {"class": [], "list": [], "filters": {}}

        def homeVideoContent(self):
            return {"list": []}

        def categoryContent(self, tid, pg, filter=False, extend=''):
            return {"list": []}

        def detailContent(self, ids):
            return {"list": []}

        def searchContent(self, key, quick, pg='1'):
            return {"list": []}

        def playerContent(self, flag, id, vipFlags=None):
            return {"parse": 0, "url": ""}

        def localProxy(self, param=''):
            return {}

        def isVideoFormat(self, url):
            return False

        def manualVideoCheck(self):
            return False

        def destroy(self):
            pass


UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
HOST = "http://www.pingshu5.net"

CLASSES = [
    ("pbook", "单田芳评书"),
    ("ykc", "袁阔成评书"),
    ("llr", "连丽如评书"),
    ("bank", "排行榜"),
]


class Spider(BaseSpider):
    def __init__(self):
        super(Spider, self).__init__()
        self.session = Session()
        self.session.headers.update({"User-Agent": UA, "Referer": HOST + "/"})
        self.timeout = 15

    def getName(self):
        return "单田芳评书"

    def init(self, extend=""):
        pass

    def destroy(self):
        try:
            self.session.close()
        except Exception:
            pass

    def isVideoFormat(self, url):
        return True

    def manualVideoCheck(self):
        return True

    def _get(self, url):
        try:
            r = self.session.get(url, timeout=self.timeout)
            if r.status_code == 200:
                r.encoding = r.apparent_encoding or "utf-8"
                return r.text
        except Exception:
            pass
        return ""

    @staticmethod
    def _clean(t):
        t = re.sub(r"<[^>]+>", "", t or "")
        return re.sub(r"\s+", " ", t.replace("&nbsp;", " ")).strip()

    def _books(self, html):
        out, seen = [], set()
        for href, title, img in re.findall(
                r'<a href="(/[a-z]+/[a-z0-9]+/)"[^>]*title="([^"]*)"[\s\S]{0,200}?<img[^>]*src="([^"]+)"',
                html):
            if href in seen:
                continue
            seen.add(href)
            out.append({"vod_id": href, "vod_name": title.strip(),
                        "vod_pic": img.strip(), "vod_remarks": "", "vod_content": ""})
        if not out:
            for href, title in re.findall(r'<a href="(/[a-z]+/[a-z0-9]+/)"[^>]*title="([^"]*)"', html):
                if href in seen or not title.strip():
                    continue
                seen.add(href)
                out.append({"vod_id": href, "vod_name": title.strip(),
                            "vod_pic": "", "vod_remarks": "", "vod_content": ""})
        return out

    def homeContent(self, filter=False):
        classes = [{"type_id": k, "type_name": n} for k, n in CLASSES]
        vods = []
        try:
            vods = self._books(self._get(HOST + "/pbook/"))[:20]
        except Exception:
            pass
        return {"class": classes, "list": vods, "filters": {}}

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg="1", filter=False, extend=""):
        cat = str(tid or "pbook").strip().strip("/")
        page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
        urls = [HOST + "/%s/" % cat]
        if page > 1:
            urls = [HOST + "/%s/index_%d.html" % (cat, page),
                    HOST + "/%s/list_%d.html" % (cat, page)]
        vods = []
        for u in urls:
            vods = self._books(self._get(u))
            if vods:
                break
        return {"list": vods, "page": page, "pagecount": page + 1,
                "limit": len(vods), "total": 9999}

    def searchContent(self, key, quick, pg="1"):
        kw = str(key or "").strip()
        if not kw:
            return {"list": []}
        try:
            from urllib.parse import quote
            html = self._get(HOST + "/plus/search.php?keyword=" + quote(kw))
        except Exception:
            html = ""
        vods = []
        for href, title in re.findall(r'<a href="(/pbook/[a-z0-9]+/)"[^>]*title="([^"]*)"', html):
            if not title.strip():
                continue
            vods.append({"vod_id": href, "vod_name": title.strip(), "vod_pic": "",
                         "vod_remarks": "", "vod_content": ""})
        return {"list": vods, "page": 1, "pagecount": 1, "limit": len(vods), "total": len(vods)}

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, (list, tuple)) else ids).strip()
        m = re.search(r"(/[a-z]+/[a-z0-9]+/)", vid)
        if not m:
            return {"list": []}
        path = m.group(1)
        html = self._get(HOST + path)
        if not html:
            return {"list": []}
        name = ""
        t = re.search(r"<title>([^<]+)</title>", html)
        if t:
            name = self._clean(t.group(1))
            name = re.split(r"评书|全集|免费|在线", name)[0].strip() or name
        if not name or name.endswith("评书网"):
            h1 = re.search(r"<h1[^>]*>([\s\S]{0,60}?)</h1>", html)
            if h1:
                name = self._clean(h1.group(1)) or name
        pic = ""
        pm = re.search(r'<img[^>]*src="(http://img\.pingshu5\.net[^"]+)"', html)
        if pm:
            pic = pm.group(1)

        eps, seen = [], set()
        for href, txt in re.findall(r'<a[^>]*href="(/pbook/\d+\.html)"[^>]*>([^<]{1,40})</a>', html):
            if href in seen:
                continue
            seen.add(href)
            eps.append("%s$%s" % (self._clean(txt) or ("第%d回" % (len(eps) + 1)), href))
        # 排序：按回目数字
        def _num(x):
            m2 = re.search(r"(\d+)", x.split("$")[0])
            return int(m2.group(1)) if m2 else 999999
        eps.sort(key=_num)
        if not eps:
            return {"list": []}
        return {"list": [{
            "vod_id": path, "vod_name": name or path.strip("/").split("/")[-1], "vod_pic": pic,
            "vod_remarks": "%d 回" % len(eps), "vod_content": "",
            "vod_play_from": "单田芳评书", "vod_play_url": "#".join(eps),
        }]}

    def playerContent(self, flag, id, vipFlags=None):
        raw = str(id or "").strip()
        url = raw if raw.startswith("http") else HOST + raw
        html = self._get(url)
        if not html:
            return {"parse": 0, "url": "", "msg": "播放页打不开"}
        audio = ""
        m = re.search(r'<audio[^>]*src="([^"]+)"', html)
        if m:
            audio = m.group(1)
        if not audio:
            m = re.search(r'src="(https?://[^"]+\.(?:mp3|m4a)[^"]*)"', html)
            if m:
                audio = m.group(1)
        if not audio:
            m = re.search(r'(https?://[^\s"\'<>]+\.(?:mp3|m4a)[^\s"\'<>]*)', html)
            if m:
                audio = m.group(1)
        if not audio:
            return {"parse": 0, "url": "", "msg": "没找到音频"}
        if audio.startswith("//"):
            audio = "http:" + audio
        return {"parse": 0, "url": audio, "format": "audio/mpeg",
                "header": {"User-Agent": UA, "Referer": url}, "flag": flag or "单田芳评书"}
