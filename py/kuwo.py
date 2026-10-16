# -*- coding: utf-8 -*-
"""🎵 酷我畅听 (kuwo.py) —— 默影视听书蜘蛛
酷我公开接口：专辑搜索/章节/128k mp3 直链
更多资源请到网站：https://navpage-2026.surge.sh/
"""
import re, time
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

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
KW_S = "https://search.kuwo.cn/r.s"
KW_M = "https://mobi.kuwo.cn"
HDR = {"User-Agent": UA, "Referer": "https://www.kuwo.cn/", "Accept": "application/json, text/plain, */*"}

WORDS = [["玄幻奇幻", "玄幻奇幻 有声小说"], ["都市言情", "都市言情 有声小说"], ["悬疑推理", "悬疑推理 有声小说"],
         ["武侠仙侠", "武侠仙侠 有声小说"], ["评书相声", "相声评书"], ["儿童故事", "儿童故事 有声小说"]]

def kcover(u):
    u = str(u or "")
    if not u: return ""
    if re.match(r"^https?:", u): return u
    return "http://img2.sycdn.kuwo.cn/star/albumcover/" + u

def mkb(aid, name, artist, img, cnt, cat):
    return {"vod_id": "ss:kuwo:" + str(aid), "vod_name": name, "vod_pic": kcover(img),
            "vod_remarks": "共 %s 章" % cnt if cnt else "", "vod_actor": artist,
            "vod_content": cat + " · " + (a.get("info") or a.get("title") or "")[:160] if isinstance(a, dict) else cat,
            "style": {"type": "rect", "ratio": 1.0}}

def kw_list(text):
    s = str(text or "").replace("&nbsp;", " ")
    try:
        j = __import__("json").loads(s)
        if j.get("musiclist"):
            return [(str(x.get("name") or ""), str(x.get("musicrid") or x.get("rid") or "").replace("MUSIC_", "")) for x in j["musiclist"]]
    except Exception:
        pass
    out = []
    re1 = re.compile(r'"name"\s*:\s*"((?:[^"\\]|\\.)*)"[\s\S]{0,400}?"musicrid"\s*:\s*"([^"]+)"')
    for m in re1.finditer(s):
        out.append((m.group(1), m.group(2).replace("MUSIC_", "")))
    if not out:
        re2 = re.compile(r'"musicrid"\s*:\s*"([^"]+)"[\s\S]{0,200}?"name"\s*:\s*"((?:[^"\\]|\\.)*)"')
        for m in re2.finditer(s):
            out.append((m.group(2), m.group(1).replace("MUSIC_", "")))
    return out

def search(kw, page):
    u = KW_S + "?client=kt&all=%s&pn=%d&rn=20&type=album&ver=kwplayer_ar_9.2.2.1&vipver=1&show_copyright_off=1&encoding=utf8&rformat=json&mobi=1&ft=album" % (requests.utils.quote(kw), page - 1)
    try:
        r = requests.get(u, headers=HDR, timeout=15)
        j = r.json() if r.status_code == 200 else None
    except Exception:
        return []
    out = []
    for a in (j or {}).get("albumlist") or []:
        if not a.get("albumid"): continue
        cnt = a.get("musiccnt") or a.get("songnum") or a.get("songcount") or ""
        out.append({"vod_id": "ss:kuwo:" + str(a["albumid"]), "vod_name": a.get("name") or "",
                    "vod_pic": kcover(a.get("img") or a.get("hts_img") or ""),
                    "vod_remarks": "共 %s 章" % cnt if cnt else "", "vod_actor": a.get("artist") or "",
                    "vod_content": (a.get("info") or a.get("title") or "")[:160],
                    "style": {"type": "rect", "ratio": 1.0}})
    return out

class Spider(BaseSpider):
    def getName(self): return "🎵酷我畅听"
    def init(self, extend=""): pass

    def homeContent(self, filter=False):
        cls = [{"type_id": "kw:" + w[1], "type_name": w[0], "land": 1, "ratio": 1.0} for w in WORDS]
        lst = search("玄幻奇幻 有声小说", 1)[:20]
        return {"class": cls, "list": lst, "filters": {}}

    def homeVideoContent(self): return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        p = max(int(pg or 1), 1)
        kw = tid[3:] if tid.startswith("kw:") else tid
        lst = search(kw, p)
        return {"list": lst, "page": p, "pagecount": p + 1 if lst else p, "limit": 20, "total": len(lst)}

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        aid = vid.split(":")[-1]
        eps = []
        qs = "stype=albuminfo&loginUid=0&loginSid=null&prod=kwplayer_ar_9.1.7.0&bkprod=kwbook_ar_9.1.7.0&corp=kuwo&show_copyright_off=1&vipver=MUSIC_8.2.0.0_BCS17&mobi=1&sortby=3&iskwbook=1"
        for p in range(0, 40):
            u = KW_S + "?%s&albumid=%s&pn=%d&rn=200" % (qs, aid, p)
            try:
                r = requests.get(u, headers=HDR, timeout=25)
                text = r.text if r.status_code == 200 else ""
            except Exception:
                break
            lst = kw_list(text)
            if not lst: break
            for nm, rid in lst:
                if rid:
                    eps.append("%s$%s" % (nm.replace("$", " ").replace("#", " "), "kwm:" + rid))
            if len(lst) < 200: break
            time.sleep(0.15)
        vod = {"vod_id": vid, "vod_name": "", "vod_pic": "", "type_name": "听书",
               "vod_play_from": "酷我畅听", "vod_play_url": "#".join(eps),
               "vod_remarks": "%d 集" % len(eps) if eps else "暂无章节"}
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        p = max(int(pg or 1), 1)
        lst = search(str(key or ""), p)
        return {"list": lst, "page": p, "pagecount": p + 1 if lst else p, "limit": 20, "total": len(lst)}

    def searchContentPage(self, key, quick, pg="1"):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, id, vipFlags=None):
        cid = str(id or "")
        if not cid.startswith("kwm:"): return {"parse": 0, "url": ""}
        rid = cid[4:].replace("MUSIC_", "")
        u = KW_M + "/mobi.s?f=web&user=0&source=kwplayercar_ar_6.0.0.9_B_jiakong_vh.apk&from=PC&type=convert_url_with_sign&br=128kmp3&rid=%s" % requests.utils.quote(rid)
        try:
            r = requests.get(u, headers={"User-Agent": UA}, timeout=16)
            j = r.json() if r.status_code == 200 else None
        except Exception:
            j = None
        url = ((j or {}).get("data") or {}).get("url") or ""
        if not url or url == "None": return {"parse": 0, "url": ""}
        return {"parse": 0, "url": url.replace("http://", "https://"),
                "header": '{"User-Agent": "%s", "Referer": "http://www.kuwo.cn/", "Range": "bytes=0-"}' % UA}

    def isVideoFormat(self, url): return False
    def manualVideoCheck(self): return False
    def localProxy(self, param=""): return {}
    def destroy(self): pass
