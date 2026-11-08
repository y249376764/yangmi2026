# -*- coding: utf-8 -*-
"""
念音听书网 nianyin.com —— 有声小说源（TVBox / 影视仓 py 蜘蛛）

对接站点：https://www.nianyin.com

链路：
  分类   /{cat}/            列表，翻页 /{cat}/index{N}.html
  搜索   /?s=ting-search&wd={kw}
  详情   /{cat}/{id}.html   plist 全集（可上万集）
  播放   /{cat}/{id}/{a}-{b}.html
         页面 meta: _c(xt) / _b(bookId) / _p(isPay) / _l(l) / _cp(page)
         POST /?s=api-getneoplay  头 xt / l，体 bookId&isPay&page -> {url: m4a/mp3}
         CDN 必须带 Referer: https://www.nianyin.com/

@author xinghuo
"""
import json
import re
import time

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
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.71 Mobile Safari/537.36")

HOST = "https://www.nianyin.com"

CLASSES = [
    ("wuxiaxuanhuan", "武侠玄幻"),
    ("kongbulingyi", "恐怖灵异"),
    ("tuilixuanyi", "推理悬疑"),
    ("dushiyanqing", "都市言情"),
    ("jiatinglunli", "家庭伦理"),
    ("wenxuemingzhu", "官场职场"),
    ("jingdianpingshu", "经典评书"),
    ("quyixiqu", "曲艺戏曲"),
    ("xiangshengxiaopin", "相声小品"),
    ("yinyue", "助眠音频"),
]


class Spider(BaseSpider):
    def __init__(self):
        super(Spider, self).__init__()
        self.session = Session()
        self.session.headers.update({
            "User-Agent": UA,
            "Referer": HOST + "/",
        })

    def getName(self):
        return "念音听书"

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

    # ---------- 基础 ----------
    def _get(self, url, tries=2):
        for _ in range(tries):
            try:
                r = self.session.get(url, timeout=15)
                if r.status_code == 200 and len(r.text) > 500:
                    return r.text
            except Exception:
                pass
            time.sleep(0.3)
        return ""

    @staticmethod
    def _clean(t):
        t = re.sub(r"<[^>]+>", "", t or "")
        t = t.replace("&nbsp;", " ").replace("&amp;", "&")
        return re.sub(r"\s+", " ", t).strip()

    def _parse_list(self, html):
        out = []
        seen = set()
        for block in re.findall(r"<li>([\s\S]*?)</li>", html):
            m = re.search(r'<a[^>]+href="(/([a-z]+)/(\d+)\.html)"[^>]*title="([^"]*)"', block)
            if not m:
                continue
            href, cat, bid, name = m.group(1), m.group(2), m.group(3), m.group(4)
            if bid in seen:
                continue
            seen.add(bid)
            pic = ""
            im = re.search(r'<img[^>]*src="([^"]+)"', block)
            if im and "img-book" in im.group(1):
                pic = im.group(1)
            desc = ""
            am = re.search(r"播音：([^<]{0,30})", block)
            if am:
                desc = "播音：" + self._clean(am.group(1))
            rm = re.search(r"状态：([^<]{0,12})", block)
            if rm:
                desc = (desc + " · " if desc else "") + self._clean(rm.group(1))
            out.append({
                "vod_id": href,
                "vod_name": name.strip(),
                "vod_pic": pic,
                "vod_remarks": self._clean(rm.group(1)) if rm else "",
                "vod_content": desc,
            })
        return out

    # ---------- 首页 / 分类 ----------
    def homeContent(self, filter=False):
        classes = [{"type_id": k, "type_name": n} for k, n in CLASSES]
        vods = []
        try:
            for cat in ("wuxiaxuanhuan", "dushiyanqing"):
                html = self._get(HOST + "/%s/" % cat)
                vods.extend(self._parse_list(html)[:12])
                if len(vods) >= 20:
                    break
        except Exception:
            pass
        return {"class": classes, "list": vods, "filters": {}}

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg="1", filter=False, extend=""):
        page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
        cat = str(tid or "").strip().strip("/")
        if cat.startswith("http"):
            url = cat if page <= 1 else cat.rstrip("/") + "/index%d.html" % page
        elif page <= 1:
            url = HOST + "/%s/" % cat
        else:
            url = HOST + "/%s/index%d.html" % (cat, page)
        html = self._get(url)
        vods = self._parse_list(html)
        pagecount = page + 1
        tail = re.findall(r"/%s/index(\d+)\.html" % re.escape(cat), html)
        if tail:
            pagecount = max(int(x) for x in tail)
        return {"list": vods, "page": page, "pagecount": pagecount, "limit": len(vods), "total": pagecount * max(len(vods), 1)}

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        kw = str(key or "").strip()
        if not kw:
            return {"list": []}
        url = HOST + "/?s=ting-search&wd=" + kw
        html = self._get(url)
        vods = self._parse_list(html)
        if not vods:
            seen = set()
            for m in re.finditer(r'<a[^>]+href="(/([a-z]+)/(\d+)\.html)"[^>]*>([^<]{1,40})</a>', html):
                href, bid, name = m.group(1), m.group(3), self._clean(m.group(4))
                if not name or bid in seen:
                    continue
                seen.add(bid)
                vods.append({"vod_id": href, "vod_name": name, "vod_pic": "",
                             "vod_remarks": "", "vod_content": ""})
        return {"list": vods, "page": 1, "pagecount": 1, "limit": len(vods), "total": len(vods)}

    # ---------- 详情 ----------
    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, (list, tuple)) else ids).strip()
        m = re.search(r"(/([a-z]+)/(\d+)\.html)", vid)
        if not m:
            return {"list": []}
        path, cat, bid = m.group(1), m.group(2), m.group(3)
        html = self._get(HOST + path)
        if not html:
            return {"list": []}

        name = ""
        t = re.search(r"<h1[^>]*>([\s\S]{0,80}?)</h1>", html)
        if t:
            name = self._clean(t.group(1))
        name = re.sub(r"(有声小说|在线收听)$", "", name).strip()
        if not name:
            t = re.search(r"<title>([^<]+?)[_\-]", html)
            if t:
                name = self._clean(t.group(1))

        pic = ""
        t = re.search(r'<img[^>]*src="(https://img-book[^"]+)"', html)
        if t:
            pic = t.group(1)

        desc = ""
        t = re.search(r'<div[^>]*class="[^"]*intro[^"]*"[^>]*>([\s\S]*?)</div>', html)
        if t:
            desc = self._clean(t.group(1))[:600]

        eps = []
        seen = set()
        for href, txt in re.findall(r'<a[^>]*class="f"[^>]*href="([^"]+)"[^>]*>([^<]{0,20})</a>', html):
            if href in seen:
                continue
            seen.add(href)
            nm = self._clean(txt) or ("第%d集" % (len(eps) + 1))
            eps.append("%s$%s" % (nm, href))
        if not eps:
            for href in re.findall(r'href="(/%s/%s/\d+-\d+\.html)"' % (cat, bid), html):
                if href in seen:
                    continue
                seen.add(href)
                eps.append("第%d集$%s" % (len(eps) + 1, href))
        if not eps:
            return {"list": []}

        am = re.search(r"播音：([^<]{0,30})", html)
        actor = self._clean(am.group(1)) if am else ""

        return {"list": [{
            "vod_id": path,
            "vod_name": name or bid,
            "vod_pic": pic,
            "vod_remarks": "%d 集" % len(eps),
            "vod_content": desc,
            "vod_actor": actor,
            "vod_play_from": "念音听书",
            "vod_play_url": "#".join(eps),
        }]}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags=None):
        raw = str(id or "").strip()
        if not raw:
            return {"parse": 0, "url": "", "msg": "空"}
        if raw.startswith("http"):
            page_url = raw
        else:
            page_url = HOST + raw

        html = self._get(page_url, tries=2)
        if not html:
            return {"parse": 0, "url": "", "msg": "播放页打不开"}

        meta = dict(re.findall(r'<meta name="(_[a-z]+)" content="([^"]*)"', html))
        xt = meta.get("_c", "")
        bid = meta.get("_b", "")
        cp = meta.get("_cp", "1")
        ispay = meta.get("_p", "0")
        lv = meta.get("_l", "1")

        url = ""
        if xt and bid:
            try:
                r = self.session.post(
                    HOST + "/?s=api-getneoplay",
                    headers={"xt": xt, "l": lv, "X-Requested-With": "XMLHttpRequest",
                             "Referer": page_url},
                    data={"bookId": bid, "isPay": ispay, "page": cp},
                    timeout=15,
                )
                txt = r.text.replace("\ufeff", "").strip()
                try:
                    j = json.loads(txt)
                    url = str(j.get("url") or "")
                except Exception:
                    mm = re.search(r'"url"\s*:\s*"([^"]+)"', txt)
                    if mm:
                        url = mm.group(1).replace("\\/", "/")
            except Exception:
                url = ""

        if not url:
            # 兜底：页面里直接给的音频
            mm = re.search(r'(https?://[^"\']+\.(?:m4a|mp3))', html)
            if mm:
                url = mm.group(1)

        if not url:
            return {"parse": 0, "url": "", "msg": "接口没给地址（可能要会员）"}

        url = url.replace("\\/", "/")
        return {
            "parse": 0,
            "url": url,
            "format": "audio/mpeg",
            "header": {
                "User-Agent": UA,
                "Referer": HOST + "/",
                "Range": "bytes=0-",
            },
            "flag": flag or "念音听书",
        }

    def localProxy(self, param=''):
        return {}
