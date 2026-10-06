# -*- coding: utf-8 -*-
"""
酷我听书 听书蜘蛛版 v2 (kuwo_tingshu.py)
----------------------------------------
来源: 「声阅APP」home_rule_v2 规则 py 化, 2026-10-06 实测接口全部存活.

接口 (纯 JSON, 无需登录):
  * 官方分类  GET http://tingshu.kuwo.cn/v2/api/search/filter/albums
                ?classifyId={id}&sortType=pubDate&rn=20&pn={页}
                (相声评书加 &categoryId=5, 亲子儿童加 &categoryId=1)
              返回 data.total + data.data[] -> { albumId, albumName, coverImg, vip, songNum, playCnt }
  * 排行榜    GET http://tingshu.kuwo.cn/v2/api/product/rank/dataList
                ?tabId={榜Id}&id={二级Id}&rn=20&pn={页}
              返回 data.rankDataList[] -> { albumId, albumName, albumImg, songNum, playCnt }
  * 推荐位    GET http://tingshu.kuwo.cn/v2/api/product/change/data
                ?...uid=2744049313&id=873&currentPage={页}&rn=12&platform=1
              返回 data.data[] -> { moduleTitle, moduleImg, moduleUrl(专辑ID) }
  * 搜索      GET http://search.kuwo.cn/r.s?client=kt&all={词}&ft=album&newsearch=1
                &itemset=web_2013&pn={页-1}&rn=100&rformat=json&encoding=utf8&mobi=1
              返回 data.albumlist[] -> { name, artist, img, albumid, musiccnt, info }
  * 章节      GET http://search.kuwo.cn/r.s?stype=albuminfo&loginUid=0&loginSid=null
                &prod=kwplayer_ar_9.1.7.0&bkprod=kwbook_ar_9.1.7.0&corp=kuwo
                &albumid={专辑ID}&pn={页}&rn=100&show_copyright_off=1&mobi=1&sortby=3&iskwbook=1
              返回 name + musiclist[] -> { id, name }, songnum 总集数
  * 播放(签名) GET http://mobi.kuwo.cn/mobi.s?f=web&user=0&source=kwplayercar_ar_6.0.0.9_B_jiakong_vh.apk
                &type=convert_url_with_sign&rid={id}&br=128kmp3
                返回 data.url mp3 直链(带时间戳, 会过期)
  * 播放(兜底) GET http://antiserver.kuwo.cn/anti.s?type=convert_url&rid={id}&format=mp3&response=url
                纯文本干净直链(首选)

无守卫, 无需登录. 章节分页上限 20 页(2000 集).
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
    TS_HOST = "https://tingshu.kuwo.cn"
    ANTI_HOST = "http://antiserver.kuwo.cn"
    UA = ("Mozilla/5.0 (Linux; Android 12; M2101K9C) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Version/4.0 Chrome/96.0.4664.99 Mobile Safari/537.36")
    MNAME = "酷我听书"
    timeout = 12

    # 官方一级分类 (classifyId) + 特辑 (categoryId)
    CLASSES = [
        {"type_id": "c_44", "type_name": "玄幻奇幻"},
        {"type_id": "c_48", "type_name": "武侠仙侠"},
        {"type_id": "c_52", "type_name": "穿越架空"},
        {"type_id": "c_42", "type_name": "都市传说"},
        {"type_id": "c_57", "type_name": "科幻竞技"},
        {"type_id": "c_169", "type_name": "幻想言情"},
        {"type_id": "c_170", "type_name": "独家定制"},
        {"type_id": "c_207", "type_name": "古代言情"},
        {"type_id": "c_213", "type_name": "影视原著"},
        {"type_id": "c_45", "type_name": "悬疑推理"},
        {"type_id": "c_56", "type_name": "历史军事"},
        {"type_id": "c_41", "type_name": "现代言情"},
        {"type_id": "c_55", "type_name": "青春校园"},
        {"type_id": "c_61", "type_name": "文学名著"},
        {"type_id": "c_0_5", "type_name": "相声评书"},
        {"type_id": "c_0_1", "type_name": "亲子儿童"},
    ]

    # 排行榜 (一级7榜, 二级子类)
    RANKS = [
        {"type_id": "rank_15", "type_name": "热播榜"},
        {"type_id": "rank_16", "type_name": "免费榜"},
        {"type_id": "rank_2", "type_name": "畅销榜"},
        {"type_id": "rank_20", "type_name": "男频VIP榜"},
        {"type_id": "rank_21", "type_name": "女频VIP榜"},
        {"type_id": "rank_8", "type_name": "新品榜"},
        {"type_id": "rank_23", "type_name": "精品榜"},
    ]

    # 榜单二级子类表 (与声阅APP一致)
    RANK_SUBS = {
        "15": [["有声小说", "123"], ["相声评书", "126"], ["历史", "140"], ["影视原声", "141"],
               ["两性情感", "129"], ["人文", "137"], ["音乐调频", "131"], ["戏曲", "139"],
               ["国漫游戏", "130"], ["畅销书", "127"], ["脱口秀", "785"], ["娱乐段子", "132"],
               ["个人提升", "133"], ["儿童", "125"], ["学科教育", "128"], ["商业财经", "134"], ["外语", "138"]],
        "16": [["热门", "475"], ["有声小说", "476"], ["相声评书", "477"], ["戏曲", "478"],
               ["历史", "479"], ["人文", "480"], ["儿童", "481"], ["影视原声", "482"],
               ["两性情感", "483"], ["国漫游戏", "484"], ["音乐调频", "485"], ["脱口秀", "786"],
               ["学科教育", "487"], ["个人提升", "488"], ["商业财经", "489"], ["外语", "490"]],
        "2": [["热门", "91"], ["都市传说", "72"], ["玄幻奇幻", "69"], ["现代言情", "73"],
              ["悬疑推理", "76"], ["古代言情", "74"], ["武侠仙侠", "75"], ["历史军事", "77"], ["儿童", "16"]],
        "20": [["男频热播", "839"], ["都市传说", "842"], ["玄幻仙侠", "843"], ["恐怖悬疑", "844"], ["历史军事", "846"]],
        "21": [["女频热播", "848"], ["总裁萌宝", "850"], ["穿越重生", "852"], ["中短篇", "854"]],
        "8": [["热门", "92"], ["有声小说", "93"], ["相声", "594"], ["评书", "595"], ["历史", "596"],
              ["人文", "597"], ["儿童", "95"], ["影视原声", "568"], ["两性情感", "98"], ["音乐调频", "564"],
              ["广播剧", "593"], ["教育", "565"], ["畅销书", "96"]],
        "23": [["全部", "861"], ["都市传说", "856"], ["玄幻仙侠", "857"], ["悬疑灵异", "858"],
               ["言情精选", "859"], ["历史军事", "860"]],
    }

    def __init__(self):
        pass

    def init(self, extend=""):
        pass

    def getName(self):
        return self.MNAME

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    # ---------- 请求 ----------
    def _get(self, url, referer="https://tingshu.kuwo.cn/"):
        h = {"User-Agent": self.UA, "Referer": referer}
        try:
            r = requests.get(url, headers=h, timeout=self.timeout)
            if r.status_code == 200:
                return r
        except Exception:
            pass
        return None

    def _get_json(self, url):
        r = self._get(url)
        if r is None:
            return {}
        txt = r.text
        if txt.startswith("\ufeff"):
            txt = txt[1:]
        txt = txt.strip()
        if txt.startswith("{") or txt.startswith("["):
            try:
                return json.loads(txt)
            except Exception:
                pass
        m = re.search(r"^\s*[^(]*\((.*)\)\s*;?\s*$", txt, re.S)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
        return {}

    @staticmethod
    def _norm(s):
        if not s:
            return ""
        return str(s).split("|")[0].strip()

    # ---------- 专辑->vod ----------
    def _to_vod(self, a):
        aid = a.get("albumId") or a.get("albumid") or a.get("id")
        if not aid:
            return None
        name = a.get("albumName") or a.get("name") or str(aid)
        pic = (a.get("coverImg") or a.get("albumImg") or a.get("img")
               or a.get("hts_img") or "")
        author = a.get("artist") or a.get("albumAnchor") or a.get("aartist") or ""
        cnt = (a.get("songNum") or a.get("songTotal") or a.get("songnum")
               or a.get("musiccnt") or a.get("count") or "")
        play = a.get("playCnt") or a.get("playcnt") or a.get("PLAYCNT") or ""
        remarks = f"{cnt}集" if cnt else ""
        if play:
            try:
                p = int(play)
                if p >= 10000:
                    remarks = (remarks + " ") if remarks else ""
                    remarks += f"♪{round(p / 10000, 1)}万播"
            except Exception:
                pass
        return {
            "vod_id": str(aid),
            "vod_name": self._norm(name),
            "vod_pic": str(pic) if str(pic).startswith("http") else "",
            "vod_remarks": remarks.strip(),
            "vod_content": "",
            "vod_year": "",
            "vod_director": str(author).strip()[:40],
            "vod_actor": "",
        }

    # ---------- 官方分类 ----------
    def _filter_albums(self, classify_id, page, category_id=""):
        q = (f"/v2/api/search/filter/albums?classifyId={classify_id}&sortType=pubDate"
             f"&rn=20&pn={page}")
        if category_id:
            q += f"&categoryId={category_id}"
        j = self._get_json(self.TS_HOST + q)
        arr = j.get("data", {}).get("data") or []
        out = []
        for x in arr:
            v = self._to_vod(x)
            if v:
                out.append(v)
        return out

    # ---------- 排行榜 ----------
    def _rank_list(self, tab_id, sub_id, page=1):
        j = self._get_json(
            f"{self.TS_HOST}/v2/api/product/rank/dataList?tabId={tab_id}&id={sub_id}&rn=20&pn={page}")
        arr = j.get("data", {}).get("rankDataList") or []
        out = []
        for x in arr:
            v = self._to_vod(x)
            if v:
                out.append(v)
        return out

    # ---------- 推荐位 ----------
    def _recommend(self, page=1):
        url = (f"{self.TS_HOST}/v2/api/product/change/data?uid=2744049313&appuid=2744049313"
               f"&bksource=kwbook_ar_9.1.8.1_tunknown.apk&id=873&notrace=0"
               f"&source=kwplayer_ar_9.1.8.1_tunknown.apk&currentPage={page}&rn=12"
               f"&platform=1&kweexVersion=1.1.5")
        j = self._get_json(url)
        arr = j.get("data", {}).get("data") or []
        out = []
        for x in arr:
            aid = x.get("moduleUrl")
            if not aid or not str(aid).isdigit():
                continue
            out.append({
                "vod_id": str(aid),
                "vod_name": self._norm(x.get("moduleTitle") or aid),
                "vod_pic": str(x.get("moduleImg") or ""),
                "vod_remarks": "推荐",
                "vod_content": "",
                "vod_year": "",
                "vod_director": "",
                "vod_actor": "",
            })
        return out

    # ---------- 标准接口 ----------
    def homeContent(self, filter=False):
        vods = []
        for rec in self._recommend(1):
            vods.append(rec)
            if len(vods) >= 40:
                break
        if not vods:
            # 兜底: 分类首页
            for c in self.CLASSES[:3]:
                for v in self._filter_albums(c["type_id"].replace("c_", "").replace("_", "&categoryId="), 1)[:6]:
                    pass
            for v in self._filter_albums("44", 1)[:20]:
                if v and v["vod_id"] not in [x["vod_id"] for x in vods]:
                    vods.append(v)
        classes = []
        for c in self.CLASSES:
            classes.append({"type_id": c["type_id"], "type_name": c["type_name"]})
        for r in self.RANKS:
            classes.append({"type_id": r["type_id"], "type_name": "榜·" + r["type_name"]})
        return {"class": classes, "list": vods, "filters": {}}

    def homeVideoContent(self):
        return {"list": self._recommend(1)[:10]}

    def categoryContent(self, tid, pg="1", filter=False, extend=""):
        page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
        t = str(tid)
        arr = []
        if t.startswith("rank_"):
            rid = t[5:]
            subs = self.RANK_SUBS.get(rid, [["热门", "123"]])
            # 榜单: 展平第一个子类(页面顶部), 其余子类做成页码占位
            sub_id = subs[0][1]
            arr = self._rank_list(rid, sub_id, page)
        elif t.startswith("c_"):
            parts = t.split("_")  # c_44 或 c_0_5
            cid = parts[1]
            cat = parts[2] if len(parts) > 2 else ""
            arr = self._filter_albums(cid, page, cat)
        else:
            arr = self._filter_albums(t, page, "")
        return {"list": arr, "page": page, "pagecount": page + 1}

    # ---------- 详情 ----------
    def _album_info(self, album_id, page):
        q = (f"stype=albuminfo&loginUid=0&loginSid=null&prod=kwplayer_ar_9.1.7.0"
             f"&bkprod=kwbook_ar_9.1.7.0&source=kwplayer_ar_9.1.7.0_t18.apk"
             f"&bksource=kwbook_ar_9.1.7.0_t18.apk&corp=kuwo&albumid={album_id}"
             f"&pn={page}&rn=100&show_copyright_off=1&vipver=MUSIC_8.2.0.0_BCS17"
             f"&mobi=1&sortby=3&iskwbook=1")
        return self._get_json("http://search.kuwo.cn/r.s?" + q)

    @staticmethod
    def _is_ad(name):
        """酷我听书广告集特征: 极速30s/30秒/预告/宣传等"""
        s = str(name or "")
        if re.search(r"极速\s*\d+\s*s", s, re.I):
            return True
        if re.search(r"\d+\s*秒", s):
            return True
        if re.search(r"(预告|宣传|推广|花絮)", s):
            return True
        return False

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, (list, tuple)) else ids)
        album_name = ""
        album_pic = ""
        url_eps = []
        songnum = 0
        seen = set()
        for pg in range(0, 20):
            j = self._album_info(vid, pg)
            if not album_name:
                album_name = self._norm(j.get("name") or j.get("album") or vid)
            if not album_pic:
                album_pic = j.get("img") or j.get("pic") or ""
            ml = j.get("musiclist") or []
            if not ml:
                break
            songnum = int(j.get("songnum") or 0)
            got_new = False
            for it in ml:
                if not isinstance(it, dict):
                    continue
                cid = it.get("id") or it.get("musicrid") or it.get("audio_id")
                nm = it.get("name") or it.get("songname") or it.get("fsongname") or ""
                if not cid or not nm or str(cid) in seen:
                    continue
                if self._is_ad(nm):
                    continue
                seen.add(str(cid))
                got_new = True
                # 集数纯数字: "第001集 xxx" -> "1" ; "001-xxx" -> "1"
                title = re.sub(r"^\s*第\s*0*(\d+)\s*集.*$", r"\1", str(nm).strip())
                if title == str(nm).strip():
                    title = re.sub(r"^\s*0*(\d+)\s*[-_:\s]", r"\1", str(nm).strip())
                title = re.sub(r"[#$]", "", title).strip()
                if not title:
                    title = str(len(seen))
                url_eps.append(f"{title}${str(cid)}")
            if not songnum or (pg + 1) * 100 >= songnum:
                break
            if not got_new:
                break
        vod = {"vod_id": vid, "vod_name": album_name or vid,
               "vod_pic": str(album_pic) if str(album_pic).startswith("http") else "",
               "vod_content": "", "vod_remarks": f"{len(url_eps)}集" if url_eps else "",
               "vod_director": "", "vod_actor": ""}
        if url_eps:
            vod["vod_play_from"] = self.MNAME
            vod["vod_play_url"] = "#".join(url_eps)
        return {"list": [vod]}

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        from urllib.parse import quote
        page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
        url = (f"http://search.kuwo.cn/r.s?client=kt&all={quote(key)}&ft=album&newsearch=1"
               f"&itemset=web_2013&pn={page - 1}&rn=100&rformat=json&encoding=utf8"
               f"&show_series_listen=1&mobi=1")
        j = self._get_json(url)
        arr = j.get("albumlist") or []
        out = []
        for it in arr:
            if not isinstance(it, dict):
                continue
            aid = it.get("albumid") or it.get("id")
            if not aid:
                continue
            name = it.get("name") or it.get("albumName") or str(aid)
            img = it.get("img") or it.get("hts_img") or ""
            author = it.get("artist") or ""
            cnt = it.get("musiccnt") or ""
            out.append({
                "vod_id": str(aid),
                "vod_name": str(name).split("|")[0].strip(),
                "vod_pic": str(img) if str(img).startswith("http") else "",
                "vod_remarks": f"{cnt}集" if cnt else "",
                "vod_content": it.get("info") or "",
                "vod_year": "",
                "vod_director": str(author).strip()[:40],
                "vod_actor": "",
            })
        return {"list": out}

    # ---------- 播放 ----------
    def playerContent(self, flag, ids, vipFlags=None):
        parts = str(ids).split("$")
        chapter_id = parts[-1].strip() if parts else ""
        if not chapter_id:
            return {"parse": 0, "url": ""}
        # 首选 mobi.s 签名接口 (海阔声阅APP同款, 返回每集真实音频; antiserver 老接口对
        # VIP/收费章节只返回同一个11秒试听片段)
        u2 = (f"http://mobi.kuwo.cn/mobi.s?f=web&user=0&source=kwplayercar_ar_6.0.0.9_B_jiakong_vh.apk"
              f"&type=convert_url_with_sign&rid={chapter_id}&br=128kmp3")
        j = self._get_json(u2)
        d = j.get("data") or {}
        u3 = d.get("url")
        if u3 and str(u3).startswith("http"):
            return {"parse": 0, "url": str(u3), "format": "audio/mpeg",
                    "header": {"User-Agent": self.UA, "Referer": "https://tingshu.kuwo.cn/"},
                    "flag": self.MNAME}
        # 兜底: antiserver 干净直链 (仅当 mobi.s 失败时)
        for fmt in ["mp3", "mp4", "aph"]:
            u = f"{self.ANTI_HOST}/anti.s?type=convert_url&rid={chapter_id}&format={fmt}&response=url"
            r = self._get(u)
            if r:
                txt = r.text.strip().replace("\n", "").replace("\r", "").replace(" ", "")
                if txt.startswith("http"):
                    return {"parse": 0, "url": txt, "format": "audio/mpeg",
                            "header": {"User-Agent": self.UA, "Referer": "https://tingshu.kuwo.cn/"},
                            "flag": self.MNAME}
        return {"parse": 0, "url": ""}

    def localProxy(self, param=""):
        return {}

    def destroy(self):
        pass