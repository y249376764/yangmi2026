# -*- coding: utf-8 -*-
"""
拾音音乐 (shiyin_yinyue.py)
---------------------------
站点: https://api.365ting.com  （拾音 App 官方接口，免登录）
更多资源请到网站 navpage-2026.surge.sh

接口:
- 标签列表  GET /api/tags                                    23 个风格标签
- 列表      GET /api/home/recommendations?tag_id={id}&page={n}   30 条/页
            项: id,title,audio_url,duration,user_id,album_id,album_name,user_name
            该接口不带封面，封面靠 /api/users/{uid}/albums 反查 album_id -> cover_url
- 搜索      GET /tingyou-app/search?keyword={kw}&page={n}      查歌单
- 歌单曲目  GET /api/albums/{album_id}/tracks                 仅用户自建歌单有效
- 播放      单曲优先 audio_url 直链；回退 /api/audio/{id}
            歌单曲目 stream?album={album_id}&idx={n}
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
    API = HOST + "/api"
    TP = HOST + "/tingyou-app"
    SITE = "https://api.365ting.com"
    UA = ("Mozilla/5.0 (Linux; Android 12; SM-G975F) "
          "AppleWebKit/537.36 (KHTML, like Gecko) "
          "Chrome/120.0.0.0 Mobile Safari/537.36")

    def __init__(self):
        self.sess = requests.Session()
        self.sess.headers.update({
            "User-Agent": self.UA,
            "Referer": self.SITE + "/",
            "Accept": "application/json, text/plain, */*",
        })
        self._covers = {}

    def getName(self):
        return "拾音音乐"

    def init(self, extend=''):
        pass

    def _get(self, url, timeout=15):
        try:
            r = self.sess.get(url, timeout=timeout)
            if r.status_code != 200:
                return None
            return r.json()
        except Exception:
            return None

    def _tags(self):
        d = self._get(self.API + "/tags")
        out = [{"id": 0, "name": "热歌"}]
        if isinstance(d, dict):
            for it in (d.get("data") or []):
                try:
                    out.append({"id": int(it.get("id")),
                                "name": str(it.get("name") or "")})
                except Exception:
                    continue
        return out

    def _cover_of(self, uid):
        uid = str(uid or "")
        if not uid:
            return {}
        if uid in self._covers:
            return self._covers[uid]
        m = {}
        d = self._get("%s/users/%s/albums" % (self.API, uid))
        if isinstance(d, dict):
            for it in (d.get("data") or []):
                aid = str(it.get("id") or "")
                cu = str(it.get("cover_url") or "")
                if aid and cu:
                    m[aid] = cu
        self._covers[uid] = m
        return m

    @staticmethod
    def _num(v):
        return int(re.sub(r"[^0-9]", "", str(v or "")) or 0)

    def _song_vod(self, it):
        sid = str(it.get("id") or "")
        title = str(it.get("title") or "未知")
        dur = self._num(it.get("duration"))
        aid = str(it.get("album_id") or "")
        aname = str(it.get("album_name") or "")
        uname = str(it.get("user_name") or "")
        au = str(it.get("audio_url") or "")

        pic = ""
        if aid:
            pic = self._cover_of(it.get("user_id")).get(aid, "")

        mm, ss = divmod(dur, 60)
        meta = {"i": sid, "n": title, "p": pic, "a": au, "d": dur,
                "l": aname, "u": uname, "g": aid}
        return {
            "vod_id": _b64(json.dumps(meta, ensure_ascii=False)),
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": ("%d:%02d" % (mm, ss)) if dur else "",
            "vod_content": "歌单：%s　上传：%s" % (aname, uname),
            "vod_actor": uname,
            "type_name": "音乐",
        }

    def _album_vod(self, it):
        aid = str(it.get("id") or "")
        name = str(it.get("title") or "未知歌单")
        teller = str(it.get("teller") or "")
        cover = str(it.get("cover_url") or "")
        cnt = self._num(it.get("count"))
        meta = {"i": aid, "n": name, "p": cover, "t": teller, "k": cnt}
        return {
            "vod_id": _b64(json.dumps(meta, ensure_ascii=False)),
            "vod_name": name,
            "vod_pic": cover,
            "vod_remarks": ("%d首" % cnt) if cnt else "",
            "vod_content": ("作者：%s" % teller) if teller else "",
            "vod_actor": teller,
            "type_name": "歌单",
        }

    def homeContent(self, filter=False):
        tags = self._tags()
        classes = [{"type_id": "t%d" % t["id"], "type_name": t["name"]}
                   for t in tags]
        items = self._list(0, 1)
        return {"class": classes,
                "list": [self._song_vod(x) for x in items],
                "filters": {}}

    def homeVideoContent(self):
        return {"list": [self._song_vod(x) for x in self._list(0, 1)]}

    def _list(self, tag_id, pg):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        d = self._get("%s/home/recommendations?tag_id=%d&page=%d"
                      % (self.API, tag_id, pg))
        if isinstance(d, dict):
            return d.get("data") or []
        return []

    def categoryContent(self, tid, pg, filter=False, extend=''):
        t = str(tid or "t0")
        tag_id = self._num(t[1:]) if t.startswith("t") else self._num(t)
        songs = [self._song_vod(x) for x in self._list(tag_id, pg)]
        try:
            pg_i = int(pg)
        except Exception:
            pg_i = 1
        return {
            "list": songs,
            "page": pg_i,
            "pagecount": (pg_i + 1) if len(songs) >= 20 else pg_i,
            "limit": 30,
            "total": pg_i * 30,
        }

    # 音乐/听书共用同一个搜索接口，结果混在一起。
    # 判定：标题带音乐词 且 集数不超过 80（有声书动辄几百上千集，歌单基本几十首）
    MUSIC_WORDS = ("歌", "曲", "音乐", "金曲", "合集", "精选", "专辑",
                   "榜", "DJ", "dj", "伴奏", "翻唱", "原声", "神曲")
    BOOK_WORDS = ("小说", "有声剧", "演播", "评书", "相声", "玄幻", "官场",
                  "都市", "穿越", "系统", "修仙", "悬疑", "恐怖", "传记")

    def _is_music_album(self, it):
        t = str(it.get("title") or "")
        cnt = self._num(it.get("count"))
        if cnt <= 0 or cnt > 80:
            return False
        for w in self.BOOK_WORDS:
            if w in t:
                return False
        for w in self.MUSIC_WORDS:
            if w in t:
                return True
        return False

    def searchContent(self, key, quick, pg='1'):
        try:
            pg_i = int(pg)
        except Exception:
            pg_i = 1
        url = "%s/search?keyword=%s&page=%d" % (
            self.TP, urllib.parse.quote(str(key)), pg_i)
        d = self._get(url)
        items, has_more = [], False
        if isinstance(d, dict):
            data = d.get("data") or {}
            items = data.get("items") or []
            has_more = bool(data.get("has_more"))
        picks = [x for x in items if self._is_music_album(x)]
        return {
            "list": [self._album_vod(x) for x in picks],
            "page": pg_i,
            "pagecount": (pg_i + 1) if has_more else pg_i,
            "limit": 10,
        }

    def detailContent(self, ids):
        raw = str(ids[0] if isinstance(ids, list) else ids)
        meta = {}
        try:
            meta = json.loads(_unb64(raw))
        except Exception:
            meta = {}
        if not isinstance(meta, dict):
            meta = {}

        # 单曲
        if meta.get("a") or (meta.get("i") and not meta.get("k")):
            n = str(meta.get("n") or "音乐")
            au = str(meta.get("a") or "")
            sid = str(meta.get("i") or "")
            play = (au + "$" + n) if au else ("id:%s@0$%s" % (sid, n))
            return {"list": [{
                "vod_id": raw,
                "vod_name": n,
                "vod_pic": str(meta.get("p") or ""),
                "vod_content": "歌单：%s" % str(meta.get("l") or ""),
                "vod_play_from": "拾音音乐",
                "vod_play_url": play,
            }]}

        # 歌单
        aid = str(meta.get("i") or "")
        name = str(meta.get("n") or "歌单")
        cover = str(meta.get("p") or "")
        cnt = self._num(meta.get("k"))
        songs = []
        if aid:
            d = self._get("%s/albums/%s/tracks"
                          % (self.API, urllib.parse.quote(aid)))
            if isinstance(d, dict):
                songs = d.get("data") or []

        if songs:
            eps = []
            for i, s in enumerate(songs):
                t = str(s.get("title") or ("第%d首" % (i + 1)))
                eps.append("%s@%d$%s" % (aid, i + 1, t))
                if not cover:
                    cover = str(s.get("cover_url") or "")
            return {"list": [{
                "vod_id": raw,
                "vod_name": name,
                "vod_pic": cover,
                "vod_remarks": "%d首" % len(eps),
                "vod_play_from": "拾音音乐",
                "vod_play_url": "#".join(eps),
            }]}

        # 聚合歌单没有曲目接口：按总数生成序号
        if cnt <= 0:
            cnt = 1
        eps = []
        for i in range(cnt):
            eps.append("%s@%d$第%d首" % (aid, i + 1, i + 1))
        return {"list": [{
            "vod_id": raw,
            "vod_name": name,
            "vod_pic": cover,
            "vod_remarks": "%d首" % cnt,
            "vod_play_from": "拾音音乐",
            "vod_play_url": "#".join(eps),
        }]}

    def playerContent(self, flag, id, vipFlags=None):
        raw = str(id or "").strip()

        # 1) audio_url 真实直链
        if raw.startswith("http://") or raw.startswith("https://"):
            return {"parse": 0, "url": raw,
                    "header": {"User-Agent": self.UA,
                               "Referer": self.SITE + "/"}}

        # 2) id:{歌曲id}@n  转码兜底
        if raw.startswith("id:"):
            sid = raw[3:].split("@")[0]
            if sid:
                return {"parse": 0,
                        "url": "%s/audio/%s" % (self.HOST,
                                                urllib.parse.quote(sid)),
                        "header": {"User-Agent": self.UA,
                                   "Referer": self.SITE + "/"}}

        # 3) album@idx
        album, idx = "", "0"
        if "@" in raw:
            seg = raw.split("@")
            album = seg[0]
            idx = seg[1] if len(seg) > 1 else "0"
        elif "##" in raw:
            seg = raw.split("##")
            album = seg[0]
            idx = seg[1] if len(seg) > 1 else "0"
        if not album:
            return {"parse": 0, "url": ""}

        return {
            "parse": 0,
            "url": "%s/tingyou/stream?album=%s&idx=%s"
                   % (self.HOST, urllib.parse.quote(album),
                      urllib.parse.quote(str(idx))),
            "header": {"User-Agent": self.UA, "Referer": self.SITE + "/"},
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