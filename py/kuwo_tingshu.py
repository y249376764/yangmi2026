# -*- coding: utf-8 -*-
"""
酷我听书 听书蜘蛛版 (kuwo_tingshu.py)
--------------------------------------
来源: 酷我听书 (tingshu.kuwo.cn), 接口提取自 Timbre .jdr 接口源 (kuwo_tingshu.js), 2026-10-03 实测:

  * 搜索   GET https://tingshu.kuwo.cn/tingshu/api/search/Search
             ?kweexVersion=1.0.2&pn={页}&rn=10&type=album&version=8.5.6.1&wd={关键词}
          返回 JSON: data.total, data.data[] -> { albumId, albumName, coverImg, author, count }
  * 章节   GET http://search.kuwo.cn/r.s?stype=albuminfo&loginUid=0&loginSid=null
             &prod=kwplayer_ar_9.1.7.0&bkprod=kwbook_ar_9.1.7.0
             &source=kwplayer_ar_9.1.7.0_t18.apk&bksource=kwbook_ar_9.1.7.0_t18.apk
             &corp=kuwo&albumid={id}&pn={页}&rn=100&show_copyright_off=1
             &vipver=MUSIC_8.2.0.0_BCS17&mobi=1&sortby=3&iskwbook=1
          返回 JSON: { musiclist:[{ id, name, ... }], songnum(总集数) }
  * 播放   GET http://antiserver.kuwo.cn/anti.s
             ?type=convert_url&rid={musiclist[].id}&format=mp3&response=url
          返回纯文本 mp3/m4a 直链, 无需 Referer, 无需签名.

无守卫, 纯 JSON API, 无需登录。
分类: 酷我听书 App 的分类接口需专用签名(时刻在变), 用人气搜索词做"分类/榜单"入口更稳。
"""
import re
import json
import time
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
    TS_HOST = "https://tingshu.kuwo.cn"
    ANTI_HOST = "http://antiserver.kuwo.cn"
    UA = ("Mozilla/5.0 (Linux; Android 12; M2101K9C) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Version/4.0 Chrome/96.0.4664.99 Mobile Safari/537.36")
    timeout = 12

    # 固定热门题材词做"分类/榜单" (酷我听书 App 分类接口需签名, 搜索词最稳定)
    CLASSES = [
        {"type_id": "玄幻", "type_name": "玄幻"},
        {"type_id": "都市", "type_name": "都市"},
        {"type_id": "悬疑", "type_name": "悬疑"},
        {"type_id": "历史", "type_name": "历史"},
        {"type_id": "武侠", "type_name": "武侠"},
        {"type_id": "言情", "type_name": "言情"},
        {"type_id": "科幻", "type_name": "科幻"},
        {"type_id": "相声", "type_name": "相声"},
        {"type_id": "评书", "type_name": "评书"},
        {"type_id": "儿童", "type_name": "儿童"},
    ]

    def _get(self, url, referer="https://tingshu.kuwo.cn/"):
        h = {"User-Agent": self.UA, "Referer": referer}
        try:
            r = requests.get(url, headers=h, timeout=self.timeout)
            if r.status_code == 200:
                return r
        except Exception:
            return None
        return None

    def _get_json(self, url):
        r = self._get(url)
        if r is None:
            return {}
        txt = r.text
        if txt.startswith('\ufeff'):
            txt = txt[1:]
        txt = txt.strip()
        # 剥 JSONP 包裹 (如果有)
        if txt.startswith('{') or txt.startswith('['):
            try:
                return json.loads(txt)
            except Exception:
                pass
        m = re.search(r'^\s*[^(]*\((.*)\)\s*;?\s*$', txt, re.S)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
        return {}

    # ---------------- 搜索/分类 ----------------
    def _search_list(self, kw, page):
        from urllib.parse import quote
        url = (f"{self.TS_HOST}/tingshu/api/search/Search"
               f"?kweexVersion=1.0.2&pn={page}&rn=20&type=album&version=8.5.6.1&wd={quote(kw)}")
        j = self._get_json(url)
        data = j.get("data") or {}
        arr = data.get("data") or data.get("list") or []
        out = []
        for it in arr:
            if not isinstance(it, dict):
                continue
            aid = it.get("albumId") or it.get("id")
            if not aid:
                continue
            aid = str(aid)
            name = it.get("albumName") or it.get("name") or aid
            pic = it.get("coverImg") or it.get("img") or ""
            author = it.get("artist") or it.get("author") or it.get("albumAnchor") or ""
            hots = it.get("hot") or it.get("playcnt") or it.get("heat") or ""
            cnt = it.get("count") or it.get("songnum") or ""
            out.append({
                "vod_id": aid,
                "vod_name": str(name).split("|")[0].strip() if name else aid,
                "vod_pic": str(pic) if str(pic).startswith("http") else "",
                "vod_remarks": "",
                "vod_content": "",
                "vod_year": "",
                "vod_director": str(author).strip(),
                "vod_actor": str(author).strip()[:40],
            })
        return out

    # ---------------- 章节列表 ----------------
    def _album_info(self, album_id, page):
        q = (f"stype=albuminfo&loginUid=0&loginSid=null&prod=kwplayer_ar_9.1.7.0"
             f"&bkprod=kwbook_ar_9.1.7.0"
             f"&source=kwplayer_ar_9.1.7.0_t18.apk&bksource=kwbook_ar_9.1.7.0_t18.apk"
             f"&corp=kuwo&albumid={album_id}&pn={page}&rn=100&show_copyright_off=1"
             f"&vipver=MUSIC_8.2.0.0_BCS17&mobi=1&sortby=3&iskwbook=1")
        return self._get_json("http://search.kuwo.cn/r.s?" + q)

    # ---------------- 标准接口 ----------------
    def init(self, extend=""):
        pass

    def getName(self):
        return "酷我听书[py]"

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def homeContent(self, filter):
        vods = []
        for kw in ["玄幻", "都市", "悬疑", "完本"]:
            for it in self._search_list(kw, 1)[:8]:
                if it and it["vod_id"] not in [v["vod_id"] for v in vods]:
                    vods.append(it)
            if len(vods) >= 40:
                break
        return {"class": self.CLASSES, "list": vods, "filters": {}}

    def homeVideoContent(self):
        vods = []
        for kw in ["玄幻", "都市"]:
            vods.extend(self._search_list(kw, 1)[:8])
        return {"list": vods}

    def categoryContent(self, tid, pg="1", filter=False, extend=""):
        page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
        return {"list": self._search_list(str(tid), page), "page": page, "pagecount": page + 1}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
        return {"list": self._search_list(str(key), page)}

    def detailContent(self, ids):
        vid = str(ids[0]) if isinstance(ids, (list, tuple)) else str(ids)
        url_eps = []
        songnum = 0
        seen = set()
        album_name = ""
        for pg in range(0, 20):  # 上限 2000 集
            j = self._album_info(vid, pg)
            if not album_name:
                album_name = str(j.get("name") or j.get("album") or "").split("|")[0].strip()
            ml = j.get("musiclist") or []
            if not ml:
                break
            songnum = int(j.get("songnum") or 0)
            got_new = False
            for it in ml:
                if not isinstance(it, dict):
                    continue
                cid = it.get("id") or it.get("audio_id") or it.get("musicrid")
                nm = it.get("name") or it.get("songname") or it.get("fsongname")
                if not cid or not nm:
                    continue
                cid = str(cid)
                if cid in seen:
                    continue
                seen.add(cid)
                got_new = True
                # 清洗标题: "第001集 xxx" -> 纯数字 "1", 或保留简洁标题
                title = re.sub(r'^\s*第\s*0*(\d+)\s*集.*$', r'\1', str(nm).strip())
                if title == str(nm).strip():
                    # 不是"第X集"格式, 去掉多余前缀, 截断
                    title = re.sub(r'^0*(\d+)\s*[-_]?\s*', r'\1', str(nm).strip())
                title = re.sub(r'[#$\r\n]', '', title).strip()
                if not title:
                    title = f"{len(url_eps)+1}"
                url_eps.append(f"{title}${cid}")
            if not songnum or (pg + 1) * 100 >= songnum:
                break
            if not got_new:
                break
        vod = {"vod_id": vid, "vod_name": album_name or vid, "vod_pic": "", "vod_content": "",
               "vod_remarks": f"{len(url_eps)}集" if url_eps else ""}
        if url_eps:
            vod["vod_play_from"] = "酷我听书"
            vod["vod_play_url"] = "#".join(url_eps)
        return {"list": [vod]}

    # ---------------- 播放 ----------------
    def playerContent(self, flag, ids, vipFlags=None):
        parts = str(ids).split("$$")
        chapter_id = parts[-1] if parts else ""
        if not chapter_id:
            return {"parse": 0, "url": ""}
        # antiserver 换取 mp3/m4a 直链 (无需签名)
        for fmt in ["mp3", "mp4", "aph"]:
            u = self.ANTI_HOST + f"/anti.s?type=convert_url&rid={chapter_id}&format={fmt}&response=url"
            r = self._get(u)
            if r:
                txt = r.text.strip().replace("\n", "").replace("\r", "").replace(" ", "")
                if txt.startswith("http"):
                    return {"parse": 0, "url": txt, "format": "audio/mpeg",
                            "header": {"User-Agent": self.UA, "Referer": "https://tingshu.kuwo.cn/"},
                            "flag": "酷我听书"}
        return {"parse": 0, "url": ""}

    def localProxy(self, param=""):
        return {}

    def destroy(self):
        pass