# -*- coding: utf-8 -*-
# 歌词适配 · TVBox Python 蜘蛛版
# 由海阔视界「歌词适配」规则移植（保留 wy/kg/kw/qq 四平台搜索 + 合音聚合线路池播放）
# 接口均来自原版规则内已内置的合音聚合 v4.0 线路（2026-09 实测直链）

import re
import json
import time
import random
import hashlib
import base64
import urllib.parse
from urllib.request import Request, urlopen

try:
    import requests
    HAS_REQ = True
except Exception:
    HAS_REQ = False

try:
    from base.spider import Spider
except Exception:
    class Spider:
        def __init__(self):
            pass

UA_PC = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
UA_MOBILE = "Mozilla/5.0 (Linux; Android 13; Mi 10 Pro Build/TKQ1.221114.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/97.0.4692.98 Mobile Safari/537.36"


def http_get_bytes(url, headers=None, timeout=8):
    """通用 GET 请求, 返回原始字节"""
    h = {"User-Agent": UA_PC}
    if headers:
        h.update(headers)
    try:
        if HAS_REQ:
            r = requests.get(url, headers=h, timeout=timeout)
            return r.content
    except Exception:
        pass
    try:
        req = Request(url, headers=h)
        with urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception:
        return b""


def http_get(url, headers=None, timeout=8):
    """通用 GET 请求, 返回文本"""
    h = {"User-Agent": UA_PC}
    if headers:
        h.update(headers)
    try:
        if HAS_REQ:
            r = requests.get(url, headers=h, timeout=timeout)
            return r.text
    except Exception:
        pass
    try:
        req = Request(url, headers=h)
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", "replace")
    except Exception:
        return ""


def http_post(url, data=None, json_body=None, headers=None, timeout=8):
    """通用 POST 请求. data 为表单/原始串, json_body 自动 JSON"""
    h = {"User-Agent": UA_PC, "Content-Type": "application/json"}
    if headers:
        h.update(headers)
    try:
        if HAS_REQ:
            if json_body is not None:
                r = requests.post(url, json=json_body, headers=h, timeout=timeout)
            else:
                r = requests.post(url, data=data, headers=h, timeout=timeout)
            return r.text
    except Exception:
        pass
    try:
        body = json.dumps(json_body).encode() if json_body is not None else (data.encode() if isinstance(data, str) else data)
        req = Request(url, data=body, headers=h)
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", "replace")
    except Exception:
        return ""


def md5(s):
    if isinstance(s, str):
        s = s.encode("utf-8")
    return hashlib.md5(s).hexdigest()


def hms(ms):
    """毫秒 -> mm:ss"""
    try:
        s = int(ms) // 1000
        m = s // 60
        ss = s % 60
        return "%02d:%02d" % (m, ss)
    except Exception:
        return ""


def fmt_size(size):
    try:
        size = float(size)
    except Exception:
        return "未知"
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return ("%.2f" % size if unit != "B" else str(int(size))) + " " + unit
        size /= 1024
    return "%.2f TB" % size


# ==================== 合音聚合线路池 (原版 jiexi 页 heyinPlay 移植) ====================

def ht_resolve(source, rid, quality="128k"):
    """长青海棠 resolve-url 黄金接口 (通吃五平台)"""
    level = {"128k": "standard", "320k": "exhigh", "flac": "lossless", "flac24bit": "lossless"}.get(quality, "standard")
    try:
        body = json.dumps({"source": source, "rid": str(rid), "level": level})
        resp = http_post("https://musicserver.haitangw.cc/v1/music/resolve-url", data=body,
                         headers={"Content-Type": "application/json", "User-Agent": UA_PC}, timeout=6)
        d = json.loads(resp)
        u = d.get("data", {}).get("url") if isinstance(d, dict) else ""
        if u and u.startswith("http"):
            return u
    except Exception:
        pass
    return ""


def xinghai_get(source, params):
    """星海后端 (通吃五平台)"""
    qs = urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
    try:
        resp = http_get("https://yy.zddyr.top/lx/api/?source=%s&%s" % (source, qs), timeout=6)
        d = json.loads(resp)
        u = d.get("url") if isinstance(d, dict) else ""
        if u and u.startswith("http"):
            return u
    except Exception:
        pass
    return ""


def kw_car(rid, quality="128k"):
    """酷我车机 nmobi (免登录)"""
    br = "flac" if quality in ("flac", "flac24bit") else "128kmp3"
    try:
        url = ("http://nmobi.kuwo.cn/mobi.s?f=web&source=kwplayercar_ar_6.0.0.9_B_jiakong_vh.apk"
               "&type=convert_url_with_sign&rid=%s&br=%s&user=4277905399&loginUid=2135286277" % (rid, br))
        resp = http_get(url, timeout=6)
        m = re.search(r"https?://[^\s\"'<>]+", resp or "")
        if m:
            return m.group(0)
    except Exception:
        pass
    return ""


def kw_anti(rid, quality="128k"):
    """酷我 anti.s 官方"""
    fmt = "flac" if quality in ("flac", "flac24bit") else "mp3"
    try:
        url = "http://antiserver.kuwo.cn/anti.s?type=convert_url3&rid=%s&format=%s&response=url" % (rid, fmt)
        resp = http_get(url, headers={"Referer": "http://www.kuwo.cn/"}, timeout=6)
        u = (resp or "").strip()
        if u.startswith("http"):
            return u
    except Exception:
        pass
    return ""


def kg_getdata(hash_, album_id=""):
    """酷狗官方 getdata"""
    try:
        url = ("https://wwwapi.kugou.com/yy/index.php?r=play/getdata&hash=%s&platid=4&album_id=%s"
               "&mid=00000000000000000000000000000000" % (hash_, album_id or ""))
        resp = http_get(url, headers={"Referer": "https://www.kugou.com/"}, timeout=6)
        d = json.loads(resp)
        u = (d.get("data") or {}).get("play_backup_url") or (d.get("data") or {}).get("play_url")
        if u:
            return u
    except Exception:
        pass
    return ""


def mg_getplay(copyright_id):
    """咪咕官方"""
    try:
        url = "https://music.migu.cn/v3/api/music/audioPlayer/getPlayInfo?copyrightId=%s" % copyright_id
        resp = http_get(url, headers={"Referer": "https://music.migu.cn/"}, timeout=6)
        d = json.loads(resp)
        u = (d.get("data") or {}).get("url") or (d.get("data") or {}).get("playUrl")
        if u:
            return u
    except Exception:
        pass
    return ""


def qq_vkey(songmid, str_media_mid="", quality="128k"):
    """QQ 官方 vkey"""
    cfg = {"128k": ["M500", ".mp3"], "320k": ["M800", ".mp3"], "flac": ["F000", ".flac"], "flac24bit": ["F000", ".flac"]}
    pre, ext = cfg.get(quality, ["M500", ".mp3"])
    smm = str_media_mid or songmid
    file_ = pre + smm + ext
    req_data = {
        "req_0": {
            "module": "vkey.GetVkeyServer",
            "method": "CgiGetVkey",
            "param": {"filename": [file_], "guid": "10000", "songmid": [songmid], "songtype": [0],
                      "uin": "0", "loginflag": 1, "platform": "20"}
        },
        "loginUin": "0",
        "comm": {"uin": "0", "format": "json", "ct": 24, "cv": 0}
    }
    try:
        url = "https://u.y.qq.com/cgi-bin/musicu.fcg?format=json&data=" + urllib.parse.quote(json.dumps(req_data))
        resp = http_get(url, headers={"Referer": "https://y.qq.com"}, timeout=6)
        d = json.loads(resp)
        info = (d.get("req_0") or {}).get("data") or {}
        purl = ((info.get("midurlinfo") or [{}])[0] or {}).get("purl")
        sip = (info.get("sip") or [None])[0]
        if purl:
            return (sip or "https://isure.stream.qqmusic.qq.com/") + purl
    except Exception:
        pass
    return ""


def tx_vkeys(mid):
    """vkeys 第三方 QQ 最稳"""
    try:
        url = "https://api.vkeys.cn/v2/music/tencent/geturl?mid=" + mid
        resp = http_get(url, headers={"User-Agent": "LX-Music-Mobile"}, timeout=6)
        d = json.loads(resp)
        u = (d.get("data") or {}).get("url") or (d.get("data") or {}).get("link")
        if u and u.startswith("http"):
            return u
    except Exception:
        pass
    return ""


def wy_eapi_url(song_id, quality="128k"):
    """网易云 eapi 播放 (纯 Python 实现 AES-ECB)"""
    level = {"128k": "standard", "320k": "exhigh", "flac": "lossless", "flac24bit": "lossless"}.get(quality, "exhigh")
    path = "/api/song/enhance/player/url/v1"
    params = {"ids": [int(song_id)], "level": level, "encodeType": "mp3"}

    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    text = json.dumps(params, separators=(",", ":"))
    digest = md5("nobody" + path + "use" + text + "md5forencrypt")
    data = path + "-36cd479b6b5-" + text + "-36cd479b6b5-" + digest

    def aes_ecb_hex(key, plain):
        pad = 16 - (len(plain) % 16)
        plain += chr(pad) * pad
        cipher = Cipher(algorithms.AES(key.encode()), modes.ECB())
        enc = cipher.encryptor()
        out = enc.update(plain.encode()) + enc.finalize()
        return out.hex().upper()

    enc = aes_ecb_hex("e82ckenh8dichen8", data)
    url = "https://interface3.music.163.com/eapi" + path
    resp = http_post(url, data="params=" + urllib.parse.quote(enc),
                     headers={"User-Agent": UA_PC, "Referer": "https://music.163.com",
                              "Cookie": "os=pc; appver=8.9.70",
                              "Content-Type": "application/x-www-form-urlencoded"}, timeout=6)
    d = json.loads(resp)
    u = (d.get("data") or [{}])[0].get("url")
    if u:
        return u.replace("\\u0026", "&")
    return ""


def heyin_play(platform, song_id, quality="128k", extra=None):
    """合音聚合播放: 按平台依次尝试, 返回直链或 ''"""
    extra = extra or {}
    lines = []
    if platform == "wy":
        lines = [
            lambda: wy_eapi_url(song_id, quality),
            lambda: ht_resolve("wy", song_id, quality),
            lambda: xinghai_get("wy", {"songmid": song_id, "quality": quality}),
        ]
    elif platform == "qq":
        mid = extra.get("mid") or song_id
        mmid = extra.get("mediaMid") or mid
        lines = [
            lambda: qq_vkey(mid, mmid, quality),
            lambda: tx_vkeys(mid),
            lambda: ht_resolve("tx", mid, quality),
            lambda: xinghai_get("tx", {"songmid": mid, "quality": quality}),
        ]
    elif platform == "kg":
        h = extra.get("hash") or song_id
        aid = extra.get("albumId") or ""
        lines = [
            lambda: kg_getdata(h, aid),
            lambda: ht_resolve("kg", h, quality),
            lambda: xinghai_get("kg", {"mainHash": h, "hash": h, "quality": quality}),
        ]
    elif platform == "kw":
        rid = extra.get("rid") or song_id
        lines = [
            lambda: kw_car(rid, quality),
            lambda: kw_anti(rid, quality),
            lambda: ht_resolve("kw", rid, quality),
            lambda: xinghai_get("kw", {"songmid": rid, "quality": quality}),
        ]
    elif platform == "mg":
        lines = [
            lambda: mg_getplay(song_id),
            lambda: ht_resolve("mg", song_id, quality),
            lambda: xinghai_get("mg", {"songmid": song_id, "name": extra.get("name", ""), "quality": quality}),
        ]
    else:
        return ""
    limit = min(3, len(lines))
    for i in range(limit):
        try:
            u = lines[i]()
            if u and u.startswith("http"):
                return u
        except Exception:
            continue
    return ""


# ==================== 平台搜索 ====================

def search_wy(keyword, page=1):
    """网易云搜索 (公开 web 接口, 无需加密)"""
    results = []
    try:
        url = ("https://music.163.com/api/search/get/web?s=" + urllib.parse.quote(keyword) +
               "&type=1&limit=60&offset=" + str((page - 1) * 60))
        resp = http_get(url, headers={"User-Agent": UA_PC, "Referer": "https://music.163.com"}, timeout=8)
        d = json.loads(resp)
        songs = ((d.get("result") or {}).get("songs")) or []
        for s in songs:
            name = s.get("name") or ""
            singer = "&".join([a.get("name", "") for a in (s.get("artists") or [])]) or ""
            al = s.get("album") or {}
            pic = (t.get("artists") or [{}])[0].get("img1v1Url") or ""
            results.append({
                "name": name,
                "singer": singer,
                "duration": hms(s.get("duration")),
                "songId": str(s.get("id")),
                "album": al.get("name") or "",
                "pic": pic or (al.get("artist") or {}).get("img1v1Url") or "",
                "platform": "wy",
                "qualitys": [],
            })
    except Exception:
        pass
    return results


def search_kg(keyword, page=1):
    """酷狗搜索 (webSign 签名接口)"""
    results = []
    try:
        mid = str(int(time.time() * 1000))
        params = [
            "dfid=-", "mid=" + mid, "uuid=" + mid, "appid=1058", "srcappid=2919",
            "clientver=1000", "clienttime=" + mid, "pagesize=60", "page=" + str(page),
            "userid=440908392", "token=f7524337c1ae877929a1497cf3d5d37e5c4cb8073fc298e492a67babc376a9d4",
            "keyword=" + urllib.parse.quote(keyword),
            "platid=4", "version=8000", "iscorrection=1", "privilege_filter=0",
        ]
        sign_key = "NVPh5oo715z5DIWAeQlhMDsWXXQV4hwt"
        sorted_p = sorted(params)
        sig = md5(sign_key + "".join(sorted_p) + sign_key)
        qs = "&".join(sorted_p) + "&signature=" + sig
        url = "http://mobilecdnbj.kugou.com/api/v3/search/song?&" + qs
        resp = http_get(url, headers={
            "User-Agent": "Android712-AndroidPhone-10518-18-0-NetMusic-wifi",
            "dfid": "-", "mid": mid, "clienttime": mid,
            "KG-FAKE": "440908392", "KG-THash": "3e5ec6b", "KG-Tid": "1",
            "KG-Rec": "1", "KG-RC": "1", "KG-RF": "00869891",
        }, timeout=8)
        d = json.loads(resp)
        songs = ((d.get("data") or {}).get("info")) or []
        for s in songs:
            name = s.get("songname") or s.get("name") or ""
            singer = s.get("singername") or ""
            h = (s.get("hash") or "").upper()
            results.append({
                "name": name,
                "singer": singer,
                "duration": hms((s.get("duration") or 0) * 1000),
                "songId": h,
                "album": s.get("album_name") or "",
                "pic": s.get("album_sizable_cover") or s.get("imgUrl") or "",
                "platform": "kg",
                "qualitys": [],
            })
    except Exception:
        pass
    return results


def search_kw(keyword, page=1):
    """酷我搜索 (r.s 老接口, 免签名)"""
    results = []
    try:
        p = {
            "rformat": "json", "encoding": "utf8", "ft": "music", "rn": 60,
            "pn": str(page - 1), "all": keyword, "vipver": "MUSIC_8.0.3.0_BCS75",
            "mobi": 1, "newsearch": 1, "searchapi": 7, "issubtitle": 1,
            "vermerge": 1, "strategy": 2012, "show_copyright_off": 1,
            "correct": 1, "cluster": 0, "client": "kt", "spPrivilege": 0, "newver": 3,
        }
        url = "http://search.kuwo.cn/r.s?" + urllib.parse.urlencode(p)
        resp = http_get(url, timeout=8)
        d = json.loads(resp)
        for s in (d.get("abslist") or []):
            rid_raw = s.get("MUSICRID") or ""
            rid = rid_raw.split("_")[1].split("&")[0] if "_" in rid_raw else (s.get("musicrid") or "")
            # 过滤片段
            name = s.get("SONGNAME") or s.get("name") or ""
            if "片段" in name:
                continue
            results.append({
                "name": name,
                "singer": s.get("ARTIST") or "",
                "duration": hms(int(s.get("DURATION") or 0) * 1000),
                "songId": rid,
                "album": s.get("ALBUM") or "",
                "pic": s.get("web_albumpic_short") and ("https://img2.kuwo.cn/star/albumcover/" + s["web_albumpic_short"].replace("120", "500")) or "",
                "platform": "kw",
                "qualitys": [],
            })
    except Exception:
        pass
    return results


def _qq_zzb_sign(post_body):
    """QQ webSign zzb 签名 (原版 qq.js 移植)"""
    h = md5(post_body).upper()

    def pick_id(hh, idxs):
        return "".join(hh[i] for i in idxs)

    t = pick_id(h, [21, 4, 9, 26, 16, 20, 27, 30])
    e = pick_id(h, [18, 11, 3, 2, 1, 7, 6, 25])
    ol = [212, 45, 80, 68, 195, 163, 163, 203, 157, 220, 254, 91, 204, 79, 104, 6]
    pairs = re.findall(r"..", h)
    c = []
    for i, v in enumerate(pairs):
        zd = int(v, 16)
        c.append(zd ^ ol[i])
    b64 = base64.b64encode(bytes(c)).decode()
    sign = ("zzb" + t + b64 + e).lower().replace("\\", "").replace("/", "").replace("+", "").replace("=", "")
    return sign


def _qq_get_comm():
    """QQ comm 完整字段 (原版 getComm 移植)"""
    cv = 948168827
    return {
        "cv": cv, "ct": 11, "format": "json", "inCharset": "utf-8", "outCharset": "utf-8",
        "notice": 0, "platform": "yqq.json", "needNewCode": 1, "uin": cv,
        "g_tk_new_20200303": cv, "g_tk": cv, "tmeAppID": "qqmusiclight",
        "nettype": "NETWORK_WIFI", "tmeLoginType": "2", "devicelevel": "31",
        "os_ver": 11, "v": cv, "qq": cv, "authst": "", "tmeLoginMethod": "1",
        "fPersonality": "0", "phonetype": "0",
    }


def search_qq(keyword, page=1):
    """QQ音乐搜索 (原版完整逻辑: musicu.fcg + zzb签名 + data包裹 + 完整comm)"""
    results = []
    try:
        data = {
            "module": "music.search.SearchCgiService",
            "method": "DoSearchForQQMusicLite",
            "param": {
                "query": keyword, "search_type": 0, "num_per_page": 60,
                "page_num": page, "nqc_flag": 0, "grp": 1,
            }
        }
        # 原版 body: {data: 请求, comm: getComm()}
        body = json.dumps({"data": data, "comm": _qq_get_comm()}, separators=(",", ":"))
        sign = _qq_zzb_sign(body)
        url = ("https://u6.y.qq.com/cgi-bin/musics.fcg?_=" + str(int(time.time() * 1000)) +
               "&sign=" + sign)
        resp = http_post(url, data=body,
                         headers={"Referer": "https://y.qq.com/",
                                  "User-Agent": "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; WOW64; Trident/5.0)",
                                  "Cookie": "qm_keyst=Q_H_L_5FBMRs-uicpIQo8Ymt3v0w1f0DAyJwQMdLJPVKmmOQZRQZkuz8AfB1Q; uin=948168827;",
                                  "Content-Type": "application/json"}, timeout=8)
        d = json.loads(resp)
        # 新版响应路径: data.data.body.item_song (数组)
        body_resp = ((d.get("data") or {}).get("data") or {}).get("body") or {}
        songs = body_resp.get("item_song") or []
        for s in songs:
            mid = s.get("mid") or s.get("songmid") or ""
            name = s.get("name") or s.get("title") or s.get("songname") or ""
            singer = "&".join([x.get("name", "") for x in (s.get("singer") or [])]) or s.get("singername") or ""
            album = s.get("album") or {}
            f = s.get("file") or {}
            pic = "https://y.gtimg.cn/music/photo_new/T002R500x500M000" + (album.get("mid") or "") + ".jpg"
            results.append({
                "name": name,
                "singer": singer,
                "duration": hms((s.get("interval") or 0) * 1000),
                "songId": mid,
                "album": album.get("name") or s.get("albumname") or "",
                "pic": pic,
                "strMediaMid": f.get("media_mid") or "",
                "platform": "qq",
                "qualitys": [],
            })
    except Exception:
        pass
    return results


# ==================== 歌词 ====================

def lyric_wy(song_id):
    """网易云歌词 (公开接口, 无需加密)"""
    try:
        url = "https://music.163.com/api/song/lyric?id=%s&lv=-1&kv=-1&tv=-1" % song_id
        resp = http_get(url, headers={"User-Agent": UA_PC, "Referer": "https://music.163.com"}, timeout=8)
        d = json.loads(resp)
        return ((d.get("lrc") or {}).get("lyric")) or ""
    except Exception:
        return ""


def lyric_kg(hash_):
    try:
        url = "http://m.kugou.com/app/i/krc.php?cmd=100&timelength=999999&hash=" + hash_
        raw = http_get_bytes(url, timeout=8)
        if raw:
            for enc in ("utf-8", "gbk", "gb18030"):
                try:
                    return raw.decode(enc, "replace")
                except Exception:
                    continue
            return raw.decode("utf-8", "replace")
        return ""
    except Exception:
        return ""


def lyric_kw(rid):
    """酷我歌词 (newlyric 老接口: xor参数 + deflate解压)"""
    try:
        import zlib
        key = b"yeelion"
        params = "user=12345,web,web,web&requester=localhost&req=1&rid=MUSIC_" + rid
        buf = params.encode()
        xor = bytes([buf[i] ^ key[i % len(key)] for i in range(len(buf))])
        b64 = base64.b64encode(xor).decode()
        url = "http://newlyric.kuwo.cn/newlyric.lrc?" + b64
        raw = http_get_bytes(url, timeout=8)
        idx = raw.find(b"\r\n\r\n")
        if idx == -1:
            return ""
        payload = raw[idx + 4:]
        try:
            lrc = zlib.decompress(payload, 15)
        except Exception:
            lrc = zlib.decompress(payload, -15)
        return lrc.decode("gb18030", "replace")
    except Exception:
        return ""


def lyric_qq(songmid):
    """QQ歌词 (musicu.fcg PlayLyricInfo, lyric 字段 base64)"""
    try:
        import urllib.parse as up
        req = {"req_0": {"module": "music.musichallSong.PlayLyricInfo", "method": "GetPlayLyricInfo",
                         "param": {"songMID": songmid, "songType": 0}},
               "comm": {"uin": 948168827, "format": "json", "ct": 11, "cv": 948168827}}
        url = "https://u.y.qq.com/cgi-bin/musicu.fcg?format=json&data=" + up.quote(json.dumps(req))
        resp = http_get(url, headers={"Referer": "https://y.qq.com/", "User-Agent": UA_PC,
                                      "Cookie": "qm_keyst=Q_H_L_5FBMRs-uicpIQo8Ymt3v0w1f0DAyJwQMdLJPVKmmOQZRQZkuz8AfB1Q; uin=948168827;"}, timeout=8)
        d = json.loads(resp)
        lyric_b64 = ((d.get("req_0") or {}).get("data") or {}).get("lyric") or ""
        if lyric_b64:
            return base64.b64decode(lyric_b64).decode("utf-8", "replace")
        return ""
    except Exception:
        return ""


# ==================== 平台热门/榜单 ====================

def rank_wy(page=1):
    """网易云热歌榜"""
    results = []
    try:
        url = "https://music.163.com/api/playlist/detail?id=3778678"
        resp = http_get(url, headers={"User-Agent": UA_PC, "Referer": "https://music.163.com"}, timeout=8)
        d = json.loads(resp)
        tracks = ((d.get("result") or {}).get("tracks")) or []
        # 分页 (每页30)
        start = (page - 1) * 30
        for t in tracks[start:start + 30]:
            name = t.get("name") or ""
            singer = "&".join([a.get("name", "") for a in (t.get("artists") or [])]) or ""
            al = t.get("album") or {}
            pic = (t.get("artists") or [{}])[0].get("img1v1Url") or ""
            results.append({
                "name": name, "singer": singer, "duration": hms(t.get("duration")),
                "songId": str(t.get("id")), "album": al.get("name") or "",
                "pic": pic or (al.get("artist") or {}).get("img1v1Url") or "",
                "platform": "wy", "qualitys": [],
            })
    except Exception:
        pass
    return results


def rank_kg(page=1):
    """酷狗 TOP500"""
    results = []
    try:
        url = "http://mobilecdnbj.kugou.com/api/v3/rank/song?rankid=8888&page=%s&pagesize=30&platid=4" % page
        resp = http_get(url, headers={"User-Agent": "Android712-AndroidPhone-10518-18-0-NetMusic-wifi"}, timeout=8)
        d = json.loads(resp)
        for s in ((d.get("data") or {}).get("info") or []):
            results.append({
                "name": s.get("songname") or "", "singer": s.get("singername") or "",
                "duration": hms((s.get("duration") or 0) * 1000),
                "songId": (s.get("hash") or "").upper(),
                "album": s.get("album_name") or "",
                "pic": s.get("album_sizable_cover") or "",
                "platform": "kg", "qualitys": [],
            })
    except Exception:
        pass
    return results


def rank_kw(page=1):
    """酷我热歌榜 (kbangserver 老接口免签名)"""
    results = []
    try:
        pn = page - 1
        url = ("http://kbangserver.kuwo.cn/ksong.s?from=pc&fmt=json&pn=%s&rn=30&type=bang"
               "&data=content&id=16&show_copyright_off=0&pcmp4=1&isbang=1" % pn)
        resp = http_get(url, headers={"User-Agent": UA_PC, "Referer": "http://www.kuwo.cn/"}, timeout=8)
        d = json.loads(resp)
        for s in (d.get("musiclist") or []):
            rid = str(s.get("id") or "")
            results.append({
                "name": s.get("name") or "",
                "singer": s.get("artist") or "",
                "duration": "",
                "songId": rid,
                "album": s.get("album") or "",
                "pic": "",
                "platform": "kw", "qualitys": [],
            })
    except Exception:
        pass
    return results


# ==================== TVBox 蜘蛛接口 ====================

def _play_url(platform, song_id, quality="128k", extra=None, name=""):
    """返回可直接播放的直链 (带 # 后缀标记音频)"""
    u = heyin_play(platform, song_id, quality, extra)
    if u:
        return u + "#isMusic=true"
    return ""


# ==================== 网易云歌单 (二级分类) ====================

# 网易云歌单分类 (语种/风格/场景/情感/主题)
WY_PL_CATS = [
    ("语种", ["华语", "欧美", "日语", "韩语", "粤语", "小语种"]),
    ("风格", ["流行", "摇滚", "民谣", "电子", "舞曲", "说唱", "轻音乐", "爵士", "乡村", "古典"]),
    ("场景", ["清晨", "夜晚", "学习", "工作", "下午茶", "地铁", "驾车", "运动"]),
    ("情感", ["怀旧", "清新", "浪漫", "伤感", "治愈", "放松", "孤独", "感动"]),
    ("主题", ["综艺", "影视原声", "游戏", "旅行", "咖啡", "动画"]),
]


def wy_playlists(cat, pg=1):
    """按分类取网易云热门歌单"""
    results = []
    try:
        url = ("https://music.163.com/api/playlist/list?cat=" + urllib.parse.quote(cat) +
               "&order=hot&limit=30&offset=" + str((pg - 1) * 30) + "&total=true")
        resp = http_get(url, headers={"User-Agent": UA_PC, "Referer": "https://music.163.com"}, timeout=10)
        d = json.loads(resp)
        # 注意: playlists 在顶层 (不是 result.playlists)
        pls = d.get("playlists") or ((d.get("result") or {}).get("playlists")) or []
        for p in pls:
            pic = (p.get("coverImgUrl") or p.get("picUrl") or "").replace("http://", "https://")
            results.append({
                "pid": str(p.get("id") or ""),
                "name": p.get("name") or "",
                "pic": pic,
                "count": p.get("trackCount") or 0,
                "creator": ((p.get("creator") or {}).get("nickname")) or "",
            })
    except Exception:
        pass
    return results


def wy_playlist_songs(pid, pg=1):
    """取歌单内歌曲 (一次拉全部, 不截断)"""
    results = []
    try:
        url = "https://music.163.com/api/playlist/detail?id=" + pid
        resp = http_get(url, headers={"User-Agent": UA_PC, "Referer": "https://music.163.com"}, timeout=10)
        d = json.loads(resp)
        tracks = ((d.get("result") or {}).get("tracks")) or []
        for t in tracks:
            name = t.get("name") or ""
            singer = "&".join([a.get("name", "") for a in (t.get("artists") or [])]) or ""
            al = t.get("album") or {}
            pic = (t.get("artists") or [{}])[0].get("img1v1Url") or ""
            results.append({
                "name": name, "singer": singer, "duration": hms(t.get("duration")),
                "songId": str(t.get("id")), "album": al.get("name") or "",
                "pic": pic or (al.get("artist") or {}).get("img1v1Url") or "",
                "platform": "wy", "qualitys": [],
            })
    except Exception:
        pass
    return results


# ==================== TVBox 蜘蛛接口 (老式 CSP 标准, 参照 juhe_music.py) ====================

def _entry(vod_id, name, pic, remark="", desc=""):
    """构造 TVBox vod 条目 (全文字, 无图片位)"""
    return {
        "vod_id": vod_id,
        "vod_name": name,
        "vod_pic": "",
        "vod_remarks": remark,
        "vod_content": desc,
        "type_name": "音乐",
    }


def _make_vod_id(plat, song_id, extra, name):
    """生成携带平台+ID+extra的 vod_id"""
    return "%s|%s|128k|%s|%s" % (plat, song_id,
                                 urllib.parse.quote(json.dumps(extra, ensure_ascii=False)),
                                 urllib.parse.quote(name or ""))


def _build_extra(it):
    return {"pic": it.get("pic") or "", "album": it.get("album") or "",
            "singer": it.get("singer") or "", "mid": it.get("songId"),
            "hash": it.get("songId"), "albumId": "", "rid": it.get("songId"),
            "mediaMid": it.get("strMediaMid") or ""}


# 平台默认图标 (原版 image.js)
PLATFORM_ICONS = {
    "wy": "https://android-artworks.25pp.com/fs08/2024/01/09/0/110_9d8058e8404df856e99876c7c975a0e5_con_130x130.png",
    "kg": "https://android-artworks.25pp.com/fs08/2024/01/02/3/110_4f951d42ac0dd576a53db81621be2f53_con_130x130.png",
    "kw": "https://android-artworks.25pp.com/fs08/2023/12/28/2/110_9ff45ea0adf6502febdcc384df355269_con_130x130.png",
    "qq": "https://android-artworks.25pp.com/fs08/2023/12/21/0/2_b7596a6777b7c62d06094bfb8d5bcfdd_con_130x130.png",
}


def _items_to_vods(items, plat, plat_tag):
    vods = []
    for it in items:
        extra = _build_extra(it)
        vid = _make_vod_id(plat, it["songId"], extra, it.get("name") or "")
        name = "%s - %s" % (it.get("name") or "", it.get("singer") or "")
        pic = ""
        vods.append(_entry(vid, name, pic,
                           remark="[%s] %s" % (plat_tag, it.get("duration") or ""),
                           desc="%s《%s》 %s" % (plat_tag, it.get("album") or "", it.get("duration") or "")))
    return vods


class Spider(Spider):
    """歌词适配 · TVBox py 音乐源 (老式 CSP 接口)"""

    def getName(self):
        return "歌词适配"

    def init(self, extend=""):
        self.header = {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36"}

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        pass

    def homeContent(self, filter):
        """首页: 一级分类 = 平台 (网易云/酷狗/酷我/QQ音乐), 二级 = 歌单分类组"""
        classes = [
            {"type_id": "wy", "type_name": "网易云"},
            {"type_id": "kg", "type_name": "酷狗"},
            {"type_id": "kw", "type_name": "酷我"},
            {"type_id": "qq", "type_name": "QQ音乐"},
        ]
        # 二级分类 (每个平台下都有): 歌单分类组 (语种/风格/场景/情感/主题)
        # 每个组里放具体分类值
        filters = {}
        for plat in ["wy", "kg", "kw", "qq"]:
            groups = []
            for grp, cats in WY_PL_CATS:
                vals = [{"n": "全部", "v": ""}]
                vals += [{"n": c, "v": c} for c in cats]
                groups.append({"key": "pl_" + grp, "name": grp, "value": vals})
            filters[plat] = groups
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        """首页推荐: 热门歌单 (用户要求首页用歌单)"""
        try:
            pls = wy_playlists("全部", 1)
            vods = []
            for p in pls[:30]:
                vods.append(_entry("pl|" + p["pid"], p["name"], p["pic"],
                                   remark="[歌单] %s首" % p["count"],
                                   desc="热门歌单\n创建者: %s" % p["creator"]))
            return {"list": vods}
        except Exception:
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        """分类页: tid=平台(wy/kg/kw/qq), filter.pl_cat=歌单分类值
        1) 选了歌单分类 → 返回该分类歌单
        2) 没选 → 返回平台热歌榜"""
        try:
            pg = int(pg) or 1
            # 二级: filter 里任一 pl_xxx key 的值 = 歌单分类值
            pl_cat = ""
            if isinstance(filter, dict):
                for k, v in filter.items():
                    if k.startswith("pl_") and v:
                        pl_cat = v
                        break
            if pl_cat:
                # 返回该分类的歌单 (纯文字)
                pls = wy_playlists(pl_cat, pg)
                vods = []
                for p in pls:
                    vods.append(_entry("pl|" + p["pid"], p["name"], p["pic"],
                                       remark="[歌单] %s首" % p["count"],
                                       desc="歌单分类: %s\n创建者: %s" % (pl_cat, p["creator"])))
                return {"list": vods}
            # 没选二级: 平台热歌榜 (纯文字)
            if tid == "wy":
                items = rank_wy(pg)
                tag = "网易云"
            elif tid == "kg":
                items = rank_kg(pg)
                tag = "酷狗"
            elif tid == "kw":
                items = rank_kw(pg)
                tag = "酷我"
            elif tid == "qq":
                items = rank_wy(pg)  # QQ 热歌暂用网易云榜
                tag = "QQ音乐"
            else:
                items = []
                tag = tid
            return {"list": _items_to_vods(items, tid, tag)}
        except Exception:
            return {"list": []}

    def searchContent(self, key, quick, pg='1'):
        """四平台搜索"""
        vods = []
        for plat, func, tag in [("wy", search_wy, "网易云"), ("kg", search_kg, "酷狗"),
                                ("kw", search_kw, "酷我"), ("qq", search_qq, "QQ音乐")]:
            try:
                items = func(key, int(pg))
                vods += _items_to_vods(items, plat, tag)
            except Exception:
                continue
        # 去重
        seen = set()
        dedup = []
        for v in vods:
            k = v["vod_name"]
            if k not in seen:
                seen.add(k)
                dedup.append(v)
        # 排序: 歌名精确匹配优先, 其次以关键词开头, 再按名称
        def _rk(v):
            n = (v.get("vod_name") or "").lower()
            if n == key.lower():
                return (0, n)
            if n.startswith(key.lower()):
                return (1, n)
            return (2, n)
        dedup.sort(key=_rk)
        return {"list": dedup}

    def detailContent(self, ids):
        """详情:
        1) vod_id = pl|<pid> → 返回歌单歌曲列表 (每首歌一集, 点哪集播哪首)
        2) 否则 → 单曲详情, 用合音聚合解析出可播放地址
        """
        try:
            vid = str(ids[0]) if isinstance(ids, (list, tuple)) else str(ids)
            # ===== 歌单 =====
            if vid.startswith("pl|"):
                pid = vid[3:]
                songs = wy_playlist_songs(pid)
                # 每首歌当一集, 点哪集播哪首; TVBox 播完自动下一曲
                eps = []
                for i, it in enumerate(songs):
                    extra = _build_extra(it)
                    song_vid = _make_vod_id("wy", it["songId"], extra, it.get("name") or "")
                    eps.append("第%d首 %s - %s$%s" % (i + 1, it.get("name") or "", it.get("singer") or "", song_vid))
                if not eps:
                    return {"list": []}
                # 随机播放: 打乱顺序生成第二行
                import random as _rnd
                rnd_eps = eps[:]
                _rnd.shuffle(rnd_eps)
                vod = {
                    "vod_id": vid,
                    "vod_name": "歌单",
                    "vod_pic": "",
                    "vod_play_from": "顺序播放$$$随机播放",
                    "vod_play_url": "#".join(eps) + "$$$" + "#".join(rnd_eps),
                    "vod_content": "歌单内歌曲\n顺序播放: 播完自动下一曲\n随机播放: 打乱顺序播放",
                }
                return {"list": [vod]}
            # ===== 单曲 =====
            parts = vid.split("|")
            plat = parts[0]
            sid = parts[1] if len(parts) > 1 else vid
            quality = parts[2] if len(parts) > 2 else "128k"
            extra = json.loads(urllib.parse.unquote(parts[3])) if len(parts) > 3 and parts[3] else {}
            name = urllib.parse.unquote(parts[4]) if len(parts) > 4 else ""
            # 依次尝试音质
            urls = []
            play_plat = "wy" if (plat == "qq" and sid.isdigit()) else plat
            for q in ([quality, "320k", "flac"] if quality != "flac" else [quality]):
                u = _play_url(play_plat, sid, q, extra, name)
                if u:
                    urls.append(u)
            play_url = urls[0] if urls else ""
            # 附带歌词
            lrc = ""
            try:
                if plat == "wy":
                    lrc = lyric_wy(sid)
                elif plat == "kg":
                    lrc = lyric_kg(sid)
                elif plat == "kw":
                    lrc = lyric_kw(sid)
                elif plat == "qq":
                    lrc = lyric_qq(sid) or (lyric_wy(sid) if sid.isdigit() else "")
            except Exception:
                lrc = ""
            vod = {
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": extra.get("pic") or "",
                "vod_play_from": "歌词适配",
                "vod_play_url": "播放$" + play_url,
                "vod_content": (extra.get("album") or "") + " - " + (extra.get("singer") or "") + "\n\n" + lrc,
            }
            return {"list": [vod]}
        except Exception:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        """播放: 直链已在详情解析好, 剥掉'播放$'前缀和#isMusic=true标记, 带header"""
        try:
            u = id
            if u.startswith("播放$"):
                u = u[3:]
            if u.startswith("$"):
                u = u[1:]
            # 去掉海阔专用标记 #isMusic=true (TVBox 不需要, 会干扰播放)
            if "#isMusic" in u:
                u = u.split("#isMusic")[0]
            # http 升级 https (播放器安全限制/防盗链)
            if u.startswith("http://"):
                u = u.replace("http://", "https://", 1)
            # 带 UA + Referer header (防盗链源需要)
            header = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            }
            return {"parse": 0, "url": u, "header": header}
        except Exception:
            return {"parse": 0, "url": id, "header": {}}

    def localProxy(self, param):
        return []

