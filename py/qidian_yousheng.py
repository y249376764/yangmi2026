# -*- coding: utf-8 -*-
"""
起点有声 qdysw.com —— 有声小说源（默影视 / TVBox py 蜘蛛）

对接站点：https://www.qdysw.com
更多资源：https://navpage-2026.surge.sh

链路：
  分类  /book/{cat}/lastupdate.html
  详情  /book/{id}.html           #playlist 最新列表 + bookdir 完整目录(?page=N&sort=asc 每页50)
  章节  /tingshu/{id}/{ep}.html   ptcms cookie 校验(解混淆JS取token)
  播放  player.html?nid=&cid=&site= → jPlayer 直链 car-lv.kuwo.cn / car-er.kuwo.cn mp3

@author xinghuo
"""
import re
import base64
import time
import urllib.parse

import requests
from requests import Session

from base.spider import Spider as BaseSpider


UA = ("Mozilla/5.0 (Linux; Android 12; Pixel 6 Build/SQ3A.220705.004) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.71 Mobile Safari/537.36")

HOST = "https://www.qdysw.com"

# 分类: key -> (名称, 目录)
CLASSES = [
    ("xhqh", "玄幻奇幻"),
    ("wxxx", "武侠仙侠"),
    ("ysyz", "影视原著"),
    ("pingshu", "长篇评书"),
    ("cyjk", "穿越架空"),
    ("xytl", "悬疑推理"),
    ("khjj", "科幻竞技"),
    ("lsjs", "历史军事"),
    ("xdyq", "现代言情"),
    ("qcxy", "青春校园"),
    ("hxyq", "幻想言情"),
    ("gdyq", "古代言情"),
    ("wxmz", "文学名著"),
    ("xcsh", "乡村生活"),
    ("ertong", "儿童频道"),
    ("gxjd", "国学经典"),
    ("bxzt", "博闻杂谈"),
    ("zcgh", "职场干货"),
    ("mjcj", "名家传记"),
    ("dajs", "档案纪实"),
    ("xsqy", "相声曲艺"),
    ("zwts", "自我提升"),
    ("mxdt", "明星电台"),
    ("qita", "其他有声"),
]


class Spider(BaseSpider):
    """起点有声 spider 入口。"""

    def __init__(self):
        super().__init__()
        self.session = Session()
        self.session.headers.update({
            "User-Agent": UA,
            "Referer": HOST + "/",
        })

    def getName(self):
        return "起点有声"

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

    # ---- ptcms cookie 校验 ----
    def _solve(self, url, tries=3):
        """带 ptcms cookie 校验的 GET。"""
        for i in range(tries):
            try:
                r = self.session.get(url, timeout=12)
            except Exception:
                return None
            html = r.text
            m = re.search(r'var reversed = "([^"]+)"', html)
            if not m:
                return r
            # 解混淆 JS -> token -> 设 cookie
            try:
                code = base64.b64decode(m.group(1)[::-1]).decode("utf-8", "ignore")
                tm = re.search(r"var token = '([^']+)'", code)
                if tm:
                    self.session.cookies.set("pt_guid",
                                             urllib.parse.quote(tm.group(1)),
                                             domain="www.qdysw.com")
                self.session.cookies.set("ptcms_guard_retry", "1", domain="www.qdysw.com")
            except Exception:
                pass
            time.sleep(0.3)
        return None

    def _get(self, url):
        r = self._solve(url)
        if r is None:
            return ""
        return r.text

    # ---- 首页 ----
    def homeContent(self, filter=False):
        classes = []
        for key, name in CLASSES:
            classes.append({"type_id": key, "type_name": name})
        # 首页推荐: 玄幻 + 武侠 前几条
        vods = []
        try:
            for key in ("xhqh", "wxxx"):
                html = self._get(HOST + "/book/%s/lastupdate.html" % key)
                items = self._parse_book_list(html)
                vods.extend(items[:10])
                if len(vods) >= 20:
                    break
        except Exception:
            pass
        return {"class": classes, "list": vods, "filters": {}}

    def homeVideoContent(self):
        return {"list": []}

    # ---- 列表解析 ----
    @staticmethod
    def _parse_book_list(html):
        """分类页书籍列表 -> vod 数组。"""
        out = []
        seen = set()
        # 匹配 li 块: href=/book/{id}.html + title + img
        blocks = re.findall(
            r'<li[^>]*>.*?href="(/book/\d+\.html)"[^>]*>.*?'
            r'(?:title="([^"]*)"|>([^<]{2,50})<).*?'
            r'<img[^>]*src="([^"]+)"',
            html, re.S)
        for href, t1, t2, pic in blocks:
            vid = href
            if vid in seen:
                continue
            seen.add(vid)
            name = (t1 or t2 or "").strip()
            # 清理书名后缀 "有声小说"
            name = re.sub(r"(有声小说|章节_在线收听)$", "", name).strip()
            if not name:
                name = href
            pic = pic if pic.startswith("http") else ("https://www.qdysw.com" + pic if pic.startswith("/") else "")
            if pic.endswith("demo1.jpg"):
                pic = ""
            out.append({
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": "",
                "vod_content": "",
            })
        return out

    # ---- 分类 ----
    def categoryContent(self, tid, pg="1", filter=False, extend=""):
        page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
        if tid in dict(CLASSES):
            url = HOST + "/book/%s/lastupdate.html" % tid
        elif tid.startswith("/"):
            url = HOST + tid
        else:
            url = HOST + "/book/%s/lastupdate.html" % tid
        html = self._get(url)
        vods = self._parse_book_list(html)
        # 分类页分页(如果有)
        pages = re.findall(r'href="(/book/%s/lastupdate/(\d+)\.html)"' % tid, html)
        pagecount = max(int(p) for _, p in pages) if pages else page + 1
        return {"list": vods, "page": page, "pagecount": pagecount}

    # ---- 搜索 ----
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
        # 站点搜索: POST /search.html 字段 searchword
        url = HOST + "/search.html"
        html = ""
        try:
            r = self.session.post(url, data={"searchword": str(key), "page": page},
                                   timeout=12, allow_redirects=True)
            html = r.text
        except Exception:
            pass
        # 搜索结果是列表页结构
        vods = self._parse_book_list(html)
        if not vods:
            # 兜底: 直接解析任意 book 链接
            books = re.findall(r'href="(/book/(\d+)\.html)"[^>]*>(?:<[^>]+>)*([^<]{0,60})<', html)
            seen = set()
            for href, bid, name in books:
                name = re.sub(r"(有声小说|在线收听)$", "", name.strip()).strip()
                if not name or href in seen:
                    continue
                seen.add(href)
                vods.append({
                    "vod_id": href,
                    "vod_name": name,
                    "vod_pic": "",
                    "vod_remarks": "",
                    "vod_content": "",
                })
        return {"list": vods, "page": page, "pagecount": page + 1}

    # ---- 详情 ----
    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, (list, tuple)) else ids)
        m = re.search(r"/book/(\d+)\.html", vid)
        if not m:
            return {"list": []}
        book_id = m.group(1)
        html = self._get(HOST + "/book/%s.html" % book_id)

        # 书名 / 封面 / 简介
        name = ""
        t = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        if t:
            name = t.group(1).strip()
        if not name:
            t = re.search(r'<title>([^<]+?)(?:_有声小说)?</title>', html)
            if t:
                name = t.group(1).strip()
        # 清理书名冗余后缀
        name = re.sub(r"(有声小说|在线收听)$", "", name).strip()
        pic = ""
        t = re.search(r'<img[^>]*class="[^"]*"[^>]*src="(/public/cover/[^"]+)"', html)
        if not t:
            t = re.search(r'<img[^>]*src="(/public/cover/[^"]+)"', html)
        if t:
            pic = HOST + t.group(1)
        desc = ""
        t = re.search(r'<div[^>]*class="[^"]*intro[^"]*"[^>]*>(.*?)</div>', html, re.S)
        if t:
            desc = re.sub(r"<[^>]+>", "", t.group(1)).strip()[:500]
        author = ""
        for m2 in re.finditer(r'<a[^>]*href="/boyin/\d+\.html"[^>]*>([^<]+)</a>', html):
            author = m2.group(1).strip()
            break

        # 章节: 优先完整目录 bookdir
        eps = []
        dm = re.search(r'href="(/bookdir/[^"]+\.html)"[^>]*>查看全部章节', html)
        if dm:
            dir_url = dm.group(1)
            eps = self._parse_dir(HOST + dir_url)
        if not eps:
            # 兜底: 详情页最新列表
            eps = self._parse_latest(html)
        if not eps:
            return {"list": []}

        play_url = "#".join(eps)
        return {"list": [{
            "vod_id": vid,
            "vod_name": name or str(book_id),
            "vod_pic": pic,
            "vod_remarks": "%d 集" % len(eps),
            "vod_content": desc,
            "vod_actor": author,
            "vod_play_from": "起点有声",
            "vod_play_url": play_url,
        }]}

    def _parse_latest(self, html):
        """详情页最新列表。"""
        out = []
        links = re.findall(
            r'<a[^>]*href=["\']?(/tingshu/(\d+)/(\d+)\.html)["\']?[^>]*>([^<]{0,60})</a>',
            html)
        # 倒序 -> 正序
        links.reverse()
        for href, bid, eid, text in links:
            name = re.sub(r"^第(\d+)(?:集|章).*", lambda m: m.group(1), text.strip())
            if not name:
                name = text.strip()
            out.append("%s$%s" % (name, href))
        # 去重(详情页最新列表可能有重复)
        seen = set()
        uniq = []
        for e in out:
            if e not in seen:
                seen.add(e)
                uniq.append(e)
        return uniq

    def _parse_dir(self, dir_url, max_pages=5):
        """完整目录(bookdir), 每页50集, sort=asc 正序。默认抓5页=250集。"""
        eps = []
        seen = set()
        # 第一页 (无参数时可能是倒序, 用 sort=asc)
        url = dir_url + ("&" if "?" in dir_url else "?") + "sort=asc"
        for pg in range(1, max_pages + 1):
            u = url + ("&page=%d" % pg if pg > 1 else "")
            html = self._get(u)
            links = re.findall(
                r'<a[^>]*href=["\']?(/tingshu/(\d+)/(\d+)\.html)["\']?[^>]*>([^<]{0,60})</a>',
                html)
            if not links:
                break
            for href, bid, eid, text in links:
                key = href
                if key in seen:
                    continue
                seen.add(key)
                name = re.sub(r"^第(\d+)(?:集|章).*", lambda m: m.group(1), text.strip())
                if not name:
                    name = text.strip()
                eps.append("%s$%s" % (name, href))
            # 是否有下一页
            if ('page=%d' % (pg + 1)) not in html and ('page=%d' % pg) not in html:
                break
            time.sleep(0.2)
        return eps

    # ---- 播放 ----
    def playerContent(self, flag, id, vipFlags=None):
        raw = str(id or "").strip()
        m = re.search(r"/tingshu/(\d+)/(\d+)\.html", raw)
        if not m:
            return {"parse": 0, "url": "", "msg": "无效播放参数"}
        nid, cid = m.group(1), m.group(2)

        # 1. 章节页(过 cookie 校验) 拿 player iframe
        html = self._get(HOST + "/tingshu/%s/%s.html" % (nid, cid))
        pm = re.search(r'<iframe[^>]*src="([^"]*player[^"]*)"', html)
        if not pm:
            return {"parse": 0, "url": "", "msg": "未找到播放器"}
        p_url = HOST + pm.group(1)

        # 2. player 页拿直链 (偶发返回无直链版本, 重试)
        audio = ""
        for _ in range(3):
            p_html = self._get(p_url)
            # 注意: url\d+ 会误匹配 murl\d+ 里的子串, 必须排除 m 前缀
            um = re.search(r"(?<!m)url\d+\s*=\s*'(https?://[^']+)'", p_html)
            if um:
                audio = um.group(1)
                # 若主体不带扩展名, 补 murl 后缀
                if not re.search(r"\.(mp3|m4a|aac|wav)$", audio, re.I):
                    suffix = re.search(r"murl\d+\s*=\s*'([^']+)'", p_html)
                    audio += suffix.group(1) if suffix else ".mp3"
                break
            else:
                um2 = re.search(r"(?<!m)url\d+\s*=\s*'([^']+\.mp3)'", p_html)
                if um2:
                    audio = um2.group(1)
                    break
            time.sleep(0.4)
        if not audio:
            return {"parse": 0, "url": "", "msg": "直链解析失败"}
        if not audio.startswith("http"):
            audio = HOST + audio

        return {
            "parse": 0,
            "url": audio,
            "format": "audio/mpeg",
            "header": {
                "User-Agent": UA,
                "Referer": "https://www.qdysw.com/",
                "Range": "bytes=0-",
            },
            "flag": flag or "起点有声",
        }
