# -*- coding: utf-8 -*-
"""
书音FM shuyinfm.com —— 有声小说源（默影视 / TVBox py 蜘蛛）

对接站点：https://www.shuyinfm.com （后端 m.mekui.com）
更多资源：https://navpage-2026.surge.sh

链路：
  分类  /listinfo-{cid}-{page}.html  帝国CMS
  详情  /album/{分类}-{专辑}.html
  章节  /audio/{分类}-{专辑}-{idx}.html (idx从0起)  详情页 #playlist 内
  播放  GET m.mekui.com/ecmsapi/index.php?act=wapseries&mod=movie&id={专辑}
        &movieId={集号1起}&t=2000000000&token=md5('act=wapseries&id={专辑}&mod=movie&movieId={集}&t=2000000000&token={SEC}')
        SEC = 056a308c515e16b2fe5a5c631319339cbc60a8ee0e03d016
        返回 data.SeriesUrl (api.aikeu.com) 302 -> 酷我CDN真MP3 (audio/mpeg 支持Range)
        signed_urls 直接500只能兜底；约20%概率502需重试

@author xinghuo
"""
import re
import hashlib
import time
import json

import requests
from requests import Session

from base.spider import Spider as BaseSpider


UA = ("Mozilla/5.0 (Windows NT 10.0 Win64 x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

HOST = "https://www.shuyinfm.com"
API_HOST = "https://m.mekui.com"

# 站点密钥（来自前端JS，实机验证）
SEC = "056a308c515e16b2fe5a5c631319339cbc60a8ee0e03d016"
TS = "2000000000"

# 分类: id -> 名称 (25个)
CLASSES = [
    ("1", "言情"), ("2", "玄幻"), ("5", "恐怖"), ("7", "穿越"), ("8", "都市"),
    ("16", "历史"), ("31", "百家讲坛"), ("33", "悬疑"), ("34", "养生"), ("35", "娱乐"),
    ("38", "文学"), ("39", "推理"), ("40", "军事"), ("41", "职场"), ("56", "反腐"),
    ("58", "人物"), ("59", "粤语"), ("60", "修真"), ("63", "网游"), ("66", "车载"),
    ("81", "戏曲"), ("91", "相声小品"), ("92", "武侠"), ("98", "音乐"), ("100", "儿童"),
]


class Spider(BaseSpider):
    """书音FM spider 入口。"""

    def __init__(self):
        super().__init__()
        self.session = Session()
        self.session.headers.update({
            "User-Agent": UA,
            "Referer": HOST + "/",
        })

    def getName(self):
        return "书音FM"

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

    @staticmethod
    def _md5(x):
        return hashlib.md5(x.encode()).hexdigest()

    def _get(self, url):
        try:
            r = self.session.get(url, timeout=15)
            return r.text
        except Exception:
            return ""

    # ---- 首页 ----
    def homeContent(self, filter=False):
        classes = []
        for cid, name in CLASSES:
            classes.append({"type_id": cid, "type_name": name})
        # 首页推荐: 言情+玄幻 前几条
        vods = []
        try:
            for cid in ("1", "2"):
                html = self._get(HOST + "/listinfo-%s-0.html" % cid)
                items = self._parse_list(html)
                vods.extend(items[:10])
                if len(vods) >= 20:
                    break
        except Exception:
            pass
        return {"class": classes, "list": vods, "filters": {}}

    def homeVideoContent(self):
        return {"list": []}

    # ---- 列表解析 ----
    def _parse_list(self, html):
        """分类页/搜索页书籍列表。结构: li > div.pic > a > img + div.txt > span.s-tit > a"""
        out = []
        seen = set()
        # 主结构: <li> ... <a href="/album/X-Y.html"> <img src="封面"> ... <span class="s-tit"><a href="...">书名</a>
        blocks = re.findall(
            r'<li[^>]*>[\s\S]*?href="(/album/\d+-\d+\.html)"[^>]*>'
            r'[\s\S]*?<img[^>]*src="([^"]+)"[^>]*>'
            r'[\s\S]*?s-tit[^>]*>\s*<a[^>]*href="[^"]*"[^>]*>([\s\S]*?)</a>',
            html)
        for href, pic, name_html in blocks:
            if href in seen:
                continue
            seen.add(href)
            name = re.sub(r"<[^>]+>", "", name_html).strip()
            name = re.sub(r"(有声小说|广播剧|评书)$", "", name).strip()
            if not name:
                continue
            pic = pic if pic.startswith("http") else (HOST + pic if pic.startswith("/") else "")
            out.append({
                "vod_id": href,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": "",
                "vod_content": "",
            })
        # 兜底: 任意 album 链接
        if not out:
            for m in re.finditer(r'href="(/album/(\d+)-(\d+)\.html)"[^>]*>([^<]{2,60})<', html):
                href = m.group(1)
                name = re.sub(r"(有声小说|广播剧|评书)$", "", m.group(4).strip()).strip()
                if not name or href in seen:
                    continue
                seen.add(href)
                out.append({
                    "vod_id": href,
                    "vod_name": name,
                    "vod_pic": "",
                    "vod_remarks": "",
                    "vod_content": "",
                })
        return out

    # ---- 分类 ----
    def categoryContent(self, tid, pg="1", filter=False, extend=""):
        page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
        cid = str(tid)
        url = HOST + "/listinfo-%s-%d.html" % (cid, page - 1)
        html = self._get(url)
        vods = self._parse_list(html)
        # 翻页判断: 帝国CMS 有总页数
        pagecount = page + 1
        pm = re.search(r'/listinfo-%s-(\d+)\.html[^>]*>(\d+)</a>' % cid, html)
        if pm:
            pagecount = max(int(pm.group(1)) + 1, page + 1)
        return {"list": vods, "page": page, "pagecount": pagecount}

    # ---- 搜索 ----
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
        # POST /e/search/index.php (keyboard + show)
        try:
            r = self.session.post(HOST + "/e/search/index.php",
                                  data={"keyboard": str(key), "show": "title,newstext,player,playadmin"},
                                  timeout=15, allow_redirects=True)
            html = r.text
        except Exception:
            return {"list": [], "page": page, "pagecount": page + 1}
        vods = self._parse_list(html)
        return {"list": vods, "page": page, "pagecount": page + 1}

    # ---- 详情 ----
    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, (list, tuple)) else ids)
        m = re.search(r"/album/(\d+)-(\d+)\.html", vid)
        if not m:
            return {"list": []}
        cat_id, aid = m.group(1), m.group(2)
        html = self._get(HOST + "/album/%s-%s.html" % (cat_id, aid))

        # 书名 / 封面 / 简介
        name = ""
        t = re.search(r'<h1>([\s\S]*?)</h1>', html)
        if t:
            name = re.sub(r"<[^>]+>", "", t.group(1)).strip()
        name = re.sub(r"(有声小说|广播剧|评书)$", "", name).strip()
        pic = ""
        t = re.search(r'<dt>\s*<img src="([^"]+)"', html)
        if not t:
            t = re.search(r'class="bookprofile"[\s\S]*?<img src="([^"]+)"', html)
        if t:
            pic = t.group(1)
        desc = ""
        t = re.search(r'id="book_intro"[\s\S]*?<dd>([\s\S]*?)</dd>', html)
        if t:
            desc = re.sub(r"<[^>]+>", "", t.group(1)).replace("&nbsp;", " ").strip()[:500]

        # 章节: #playlist 内 <li><a href="/audio/{cat}-{aid}-{idx}.html">集名</a>
        eps = []
        pm = re.search(r'id="playlist"([\s\S]*?)</ul>', html)
        seg = pm.group(1) if pm else html
        for m2 in re.finditer(
                r'<a href="[^"]*/audio/\d+-\d+-(\d+)\.html"[^>]*>([\s\S]*?)</a>', seg):
            idx = int(m2.group(1))
            et = re.sub(r"<[^>]+>", "", m2.group(2)).replace("&nbsp;", " ").replace("&amp;", "&").strip()
            ep = idx + 1  # movieId 从1起
            # 生成播放 API (token签名)
            tk = self._md5("act=wapseries&id=%s&mod=movie&movieId=%d&t=%s&token=%s" % (aid, ep, TS, SEC))
            api = ("%s/ecmsapi/index.php?act=wapseries&mod=movie&id=%s&movieId=%d&t=%s&token=%s"
                   % (API_HOST, aid, ep, TS, tk))
            # 集名纯数字简约
            num = re.sub(r"\D", "", et)
            display = num if num else str(ep)
            eps.append("%s$%s" % (display, api))

        if not eps:
            return {"list": [{
                "vod_id": vid,
                "vod_name": name or vid,
                "vod_remarks": "暂无章节",
                "vod_content": desc,
            }]}

        return {"list": [{
            "vod_id": vid,
            "vod_name": name or vid,
            "vod_pic": pic,
            "vod_remarks": "%d 集" % len(eps),
            "vod_content": desc,
            "vod_play_from": "书音FM",
            "vod_play_url": "#".join(eps),
        }]}

    # ---- 播放 ----
    def playerContent(self, flag, id, vipFlags=None):
        raw = str(id or "").strip()
        # id 是 ecmsapi 播放 API
        if not raw.startswith("http"):
            return {"parse": 0, "url": "", "msg": "无效播放参数"}

        # 请求 ecmsapi 拿 SeriesUrl (约20% 502, 重试)
        series_url = ""
        for _ in range(5):
            try:
                r = self.session.get(raw, timeout=15)
                if r.status_code != 200:
                    time.sleep(0.3)
                    continue
                data = r.json()
                if data.get("code") == 1 and data.get("data"):
                    series_url = data["data"].get("SeriesUrl") or ""
                    if series_url:
                        break
            except Exception:
                pass
            time.sleep(0.3)

        if not series_url:
            return {"parse": 0, "url": "", "msg": "解析播放链接失败"}

        return {
            "parse": 0,
            "url": series_url,
            "format": "audio/mpeg",
            "header": {
                "User-Agent": UA,
                "Referer": HOST + "/",
                "Range": "bytes=0-",
            },
            "flag": flag or "书音FM",
        }
