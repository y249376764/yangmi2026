# -*- coding: utf-8 -*-
"""
听书网 tingshuwang.cc —— 有声小说源（TVBox / 影视仓 py 蜘蛛）

对接站点：https://www.tingshuwang.cc

链路：
  分类   /book/{分类}/            翻页 /book/{分类}/index_2.html
  搜索   /plus/search.php?q=关键字
  详情   /book/{slug}/            章节 /book/{slug}/{id}.html（站点倒序，这里翻正）
  播放   章节页里就是静态 mp3：/d/file/yt/{id}/{xx}.mp3  无需 Referer，实测 206

@author xinghuo
"""
import re
from urllib.parse import quote

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


UA = ("Mozilla/5.0 (Linux; Android 12; Pixel 6 Build/SQ3A.220705.004) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")
HOST = "https://www.tingshuwang.cc"

CLASSES = [
    ("xuanhuanwuxia", "玄幻武侠"),
    ("kongbuxuanyi", "恐怖悬疑"),
    ("dushiyanqing", "都市言情"),
    ("zhichangshangzhan", "职场商战"),
    ("tuilixiaoshuo", "推理小说"),
    ("junshilishi", "军事历史"),
    ("wangyoujingji", "网游竞技"),
    ("zongyiyule", "综艺娱乐"),
]


class Spider(BaseSpider):
    def __init__(self):
        super(Spider, self).__init__()
        self.session = Session()
        self.session.headers.update({
            "User-Agent": UA,
            "Referer": HOST + "/",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })

    def getName(self):
        return "听书网"

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

    def _get(self, url, tries=2):
        for _ in range(tries):
            try:
                r = self.session.get(url, timeout=20)
                if r.status_code == 200 and len(r.text) > 800:
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
        # <li> ... <a class="full-link" href="/book/SLUG/" title="书名"> ... cover ... <em>更新到…</em>
        for m in re.finditer(
                r'<a href="(/book/([A-Za-z0-9]+)/)"\s+class="full-link"\s+title="([^"]*)"[\s\S]{0,600}?'
                r'<img[^>]*src="([^"]*)"[\s\S]{0,300}?(?:<em>([^<]*)</em>)?', html):
            href, slug, name, pic, note = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
            if slug in seen or not name.strip():
                continue
            seen.add(slug)
            out.append({
                "vod_id": href,
                "vod_name": name.strip(),
                "vod_pic": pic.strip(),
                "vod_remarks": self._clean(note or "")[:24],
                "vod_content": "",
            })
        if not out:
            for href, slug, name in re.findall(r'href="(/book/([A-Za-z0-9]+)/)"[^>]*title="([^"]+)"', html):
                if slug in seen:
                    continue
                seen.add(slug)
                out.append({"vod_id": href, "vod_name": name.strip(), "vod_pic": "",
                            "vod_remarks": "", "vod_content": ""})
        return out

    def homeContent(self, filter=False):
        classes = [{"type_id": k, "type_name": n} for k, n in CLASSES]
        vods = []
        try:
            for cat in ("xuanhuanwuxia", "dushiyanqing"):
                vods.extend(self._books(self._get(HOST + "/book/%s/" % cat))[:10])
        except Exception:
            pass
        return {"class": classes, "list": vods, "filters": {}}

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg="1", filter=False, extend=""):
        cat = str(tid or "xuanhuanwuxia").strip().strip("/")
        page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
        if cat in ("lianzai", "wanjie"):
            base = HOST + "/book/%s/" % cat
        else:
            base = HOST + "/book/%s/" % cat
        url = base if page <= 1 else base + "index_%d.html" % page
        html = self._get(url)
        vods = self._books(html)
        pages = [int(x) for x in re.findall(r"index_(\d+)\.html", html)]
        pagecount = max(pages) if pages else page + 1
        return {"list": vods, "page": page, "pagecount": max(pagecount, page),
                "limit": len(vods), "total": pagecount * max(len(vods), 1)}

    def searchContent(self, key, quick, pg="1"):
        kw = str(key or "").strip()
        if not kw:
            return {"list": []}
        html = self._get(HOST + "/plus/search.php?q=" + quote(kw))
        vods = self._books(html)
        if not vods:
            seen = set()
            for href, slug, name in re.findall(r'href="(/book/([A-Za-z0-9]+)/)"[^>]*title="([^"]+)"', html):
                if slug in seen:
                    continue
                seen.add(slug)
                vods.append({"vod_id": href, "vod_name": name.strip(), "vod_pic": "",
                             "vod_remarks": "", "vod_content": ""})
        return {"list": vods, "page": 1, "pagecount": 1, "limit": len(vods), "total": len(vods)}

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, (list, tuple)) else ids).strip()
        m = re.search(r"(/book/([A-Za-z0-9]+)/)", vid)
        if not m:
            return {"list": []}
        path, slug = m.group(1), m.group(2)
        html = self._get(HOST + path)
        if not html:
            return {"list": []}

        name = ""
        t = re.search(r"<h1[^>]*>([\s\S]{0,60}?)</h1>", html)
        if t:
            name = self._clean(t.group(1))
        if not name:
            t = re.search(r"<title>([^<]+)</title>", html)
            if t:
                name = re.split(r"[_\-]", self._clean(t.group(1)))[0].strip()

        pic = ""
        pm = re.search(r'<img[^>]*src="(https?://[^"]*cover[^"]*)"', html)
        if pm:
            pic = pm.group(1)

        desc = ""
        dm = re.search(r'<div[^>]*class="[^"]*(?:desc|intro|book-intro)[^"]*"[^>]*>([\s\S]{0,800}?)</div>', html)
        if dm:
            desc = self._clean(dm.group(1))[:600]

        eps, seen = [], set()
        for href, txt in re.findall(
                r'<a[^>]*href="(/book/%s/\d+\.html)"[^>]*>([^<]{1,40})</a>' % re.escape(slug), html):
            if href in seen:
                continue
            seen.add(href)
            eps.append("%s$%s" % (self._clean(txt) or ("第%d集" % (len(eps) + 1)), href))
        if not eps:
            for href in re.findall(r'href="(/book/%s/\d+\.html)"' % re.escape(slug), html):
                if href in seen:
                    continue
                seen.add(href)
                eps.append("第%d集$%s" % (len(eps) + 1, href))
        if not eps:
            return {"list": []}
        # 站点章节列表是倒序（新→旧），翻成正序
        def _num(x):
            mm = re.search(r"/(\d+)\.html", x)
            return int(mm.group(1)) if mm else 0
        eps.sort(key=_num)

        return {"list": [{
            "vod_id": path,
            "vod_name": name or slug,
            "vod_pic": pic,
            "vod_remarks": "%d 集" % len(eps),
            "vod_content": desc,
            "vod_play_from": "听书网",
            "vod_play_url": "#".join(eps),
        }]}

    def playerContent(self, flag, id, vipFlags=None):
        raw = str(id or "").strip()
        page_url = raw if raw.startswith("http") else HOST + raw
        html = self._get(page_url)
        if not html:
            return {"parse": 0, "url": "", "msg": "章节页打不开"}
        audio = ""
        m = re.search(r'<audio[^>]*src="([^"]+)"', html)
        if m:
            audio = m.group(1)
        if not audio:
            m = re.search(r'(https?://[^\s"\'<>]+\.(?:mp3|m4a)[^\s"\'<>]*)', html)
            if m:
                audio = m.group(1)
        if not audio:
            m = re.search(r'(?:url|src|mp3)\s*[:=]\s*["\']([^"\']+\.(?:mp3|m4a)[^"\']*)["\']', html)
            if m:
                audio = m.group(1)
        if not audio:
            return {"parse": 0, "url": "", "msg": "没找到音频"}
        if audio.startswith("//"):
            audio = "https:" + audio
        return {"parse": 0, "url": audio, "format": "audio/mpeg",
                "header": {"User-Agent": UA, "Referer": HOST + "/"},
                "flag": flag or "听书网"}
