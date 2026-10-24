# -*- coding: utf-8 -*-
"""
拾音听书 (shiyin_tingshu.py)
----------------------------
站点: https://api.365ting.com  （拾音 App 官方接口，免登录）
更多资源请到网站 navpage-2026.surge.sh

接口:
- 搜索/分类  GET /tingyou-app/search?keyword={kw}&page={pg}   10 条/页
             items[]{id,title,author,teller,count,cover_url} / total / has_more
- 音频        GET /tingyou/stream?album={id}&idx={n}   Range 206 audio/mp4
             单集约 25kbps，直接可播，无需二次解析
- 没有专辑详情接口：集数用搜索返回的 count，章节序号 1..count

vod_id 约定: base64(id|title|teller|cover|count)
这样详情页不用二次搜索就能拿到书名/封面/集数。
"""
import base64
import json
import re
import urllib.parse

import requests

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


def _b64(s):
    try:
        return base64.b64encode(str(s).encode('utf-8')).decode('ascii')
    except Exception:
        return ''


def _unb64(s):
    try:
        pad = '=' * (-len(s) % 4)
        return base64.b64decode(str(s) + pad).decode('utf-8', 'ignore')
    except Exception:
        return ''


class Spider(BaseSpider):
    HOST = "https://api.365ting.com"
    API = HOST + "/tingyou-app"
    SITE = "https://api.365ting.com"
    UA = ("Mozilla/5.0 (Linux; Android 12; SM-G975F) "
          "AppleWebKit/537.36 (KHTML, like Gecko) "
          "Chrome/120.0.0.0 Mobile Safari/537.36")

    CATS = [
        ("评书", "评书"), ("相声", "相声"), ("小说", "小说"), ("儿童", "儿童"),
        ("历史", "历史"), ("悬疑", "悬疑"), ("玄幻", "玄幻"), ("都市", "都市"),
        ("言情", "言情"), ("科幻", "科幻"), ("军事", "军事"), ("武侠", "武侠"),
        ("仙侠", "仙侠"), ("恐怖", "恐怖"), ("纪实", "纪实"), ("脱口秀", "脱口秀"),
        ("百家讲坛", "百家讲坛"), ("戏曲", "戏曲"), ("睡前故事", "睡前故事"),
        ("英语", "英语"),
    ]

    def __init__(self):
        self.sess = requests.Session()
        self.sess.headers.update({
            "User-Agent": self.UA,
            "Referer": self.SITE + "/",
            "Accept": "application/json, text/plain, */*",
        })

    def getName(self):
        return "拾音听书"

    def init(self, extend=''):
        pass

    # ---------- 基础 ----------
    def _get(self, url, timeout=15):
        try:
            r = self.sess.get(url, timeout=timeout)
            if r.status_code != 200:
                return None
            return r.json()
        except Exception:
            return None

    def _search(self, kw, pg=1):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        url = "%s/search?keyword=%s&page=%d" % (
            self.API, urllib.parse.quote(str(kw)), pg)
        d = self._get(url)
        if not isinstance(d, dict):
            return [], False, 0
        data = d.get("data") or {}
        items = data.get("items") or []
        has_more = bool(data.get("has_more"))
        total = int(data.get("total") or 0)
        return items, has_more, total

    @staticmethod
    def _num(v):
        return int(re.sub(r"[^0-9]", "", str(v or "")) or 0)

    def _vod(self, it):
        vid = str(it.get("id") or "")
        name = str(it.get("title") or "未知")
        teller = str(it.get("teller") or "")
        author = str(it.get("author") or "")
        count = self._num(it.get("count"))
        cover = str(it.get("cover_url") or "")
        token = _b64(json.dumps({"i": vid, "n": name, "t": teller,
                                 "c": cover, "k": count},
                                ensure_ascii=False))
        return {
            "vod_id": token or vid,
            "vod_name": name,
            "vod_pic": cover,
            "vod_remarks": ("%d集" % count) if count else "",
            "vod_content": "演播：%s　作者：%s" % (teller, author),
            "vod_actor": teller,
            "vod_director": author,
            "type_name": "有声书",
        }

    # ---------- 首页 ----------
    def homeContent(self, filter=False):
        classes = [{"type_id": k, "type_name": n} for k, n in self.CATS]
        items, _, _ = self._search("评书", 1)
        return {"class": classes,
                "list": [self._vod(x) for x in items],
                "filters": {}}

    def homeVideoContent(self):
        items, _, _ = self._search("评书", 1)
        return {"list": [self._vod(x) for x in items]}

    # ---------- 分类 ----------
    def categoryContent(self, tid, pg, filter=False, extend=''):
        items, has_more, total = self._search(str(tid or "评书"), pg)
        try:
            pg_i = int(pg)
        except Exception:
            pg_i = 1
        return {
            "list": [self._vod(x) for x in items],
            "page": pg_i,
            "pagecount": (pg_i + 1) if has_more else pg_i,
            "limit": 10,
            "total": total or (pg_i * 10),
        }

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg='1'):
        items, has_more, _ = self._search(key, pg)
        try:
            pg_i = int(pg)
        except Exception:
            pg_i = 1
        return {
            "list": [self._vod(x) for x in items],
            "page": pg_i,
            "pagecount": (pg_i + 1) if has_more else pg_i,
            "limit": 10,
        }

    # ---------- 详情 ----------
    def detailContent(self, ids):
        raw = str(ids[0] if isinstance(ids, list) else ids)
        vid, title, teller, cover, count = raw, "有声书", "", "", 0
        try:
            meta = json.loads(_unb64(raw))
            if isinstance(meta, dict):
                vid = str(meta.get("i") or raw)
                title = str(meta.get("n") or "有声书")
                teller = str(meta.get("t") or "")
                cover = str(meta.get("c") or "")
                count = self._num(meta.get("k"))
        except Exception:
            pass
        if not vid:
            return {"list": []}
        if count <= 0:
            count = 1

        eps = []
        for i in range(1, count + 1):
            eps.append("%s@%d$第%d集" % (vid, i, i))

        vod = {
            "vod_id": raw,
            "vod_name": title or "有声书",
            "vod_pic": cover,
            "vod_remarks": "%d集" % count,
            "vod_content": ("演播：%s" % teller) if teller else "",
            "vod_actor": teller,
            "vod_play_from": "拾音听书",
            "vod_play_url": "#".join(eps),
        }
        return {"list": [vod]}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags=None):
        raw = str(id or "")
        album, idx = raw, "1"
        if "@" in raw:
            seg = raw.split("@")
            album = seg[0]
            idx = seg[1] if len(seg) > 1 else "1"
        elif "$" in raw:
            album = raw.split("$")[0]
        elif "##" in raw:
            seg = raw.split("##")
            album = seg[0]
            idx = seg[1] if len(seg) > 1 else "1"
        album = album.split("|")[0]

        if not album:
            return {"parse": 0, "url": ""}
        url = "%s/tingyou/stream?album=%s&idx=%s" % (
            self.HOST, urllib.parse.quote(album), urllib.parse.quote(str(idx)))
        return {
            "parse": 0,
            "url": url,
            "header": {
                "User-Agent": self.UA,
                "Referer": self.SITE + "/",
            },
        }

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        try:
            self.sess.close()
        except Exception:
            pass