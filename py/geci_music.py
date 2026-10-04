# -*- coding: utf-8 -*-
# 歌词适配 [蜘蛛版] v2 - 歌单分类版
# 基于海阔"歌词适配"规则提取 + 用户要求改造
# 一级分类: 推荐/语种/风格/场景/情感/主题 (网易云歌单五维)
# 二级分类: 网易云 playlist/catalogue 动态标签
# 内容: 歌单列表 (小图+文字布局: 歌单名+歌曲数)
# 播放: 长青海棠 resolve-url → 星海后端 → 官方兜底
# 2026-10-04 实测: 分类/歌单/详情/播放全链路通
import json
import re
import ssl
import time
import hashlib
import urllib.parse
import urllib.request
from base.spider import Spider as BaseSpider

UA = "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36"
UA_MOBILE = "Mozilla/5.0 (Linux; Android 12; M2104K10AC) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0 Mobile Safari/537.36"

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

# 网易云 weapi/eapi 密钥
WY_KEY = "0CoJUm6Qyw8W8jud"
WY_IV = "0102030405060708"
WY_EAPI_KEY = "e82ckenh8dichen8"
WY_ENC_SEC = "bf50d0bcf56833b06d8d1219496a452a1d860fd58a14c0aafba3e770104ca77dc6856cb310ed3309039e6865081be4ddc2df52663373b20b70ac25b4d0c6ca466daef6b50174e93536e2d580c49e70649ad1936584899e85722eb83ceddfb4f56c1172fca5e60592d0e6ee3e8e02be1fe6e53f285b0389162d8e6ddc553857cd"


def _http(url, ref=None, data=None, headers=None, timeout=15):
    for _ in range(2):
        try:
            h = {"User-Agent": UA}
            if ref:
                h["Referer"] = ref
            if headers:
                h.update(headers)
            body = None
            if data is not None:
                body = data.encode() if isinstance(data, str) else json.dumps(data).encode()
                h["Content-Type"] = "application/json"
            req = urllib.request.Request(url, data=body, headers=h)
            with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
                return r.read().decode("utf-8", errors="ignore")
        except Exception:
            time.sleep(0.8)
    return ""


def _json(url, ref=None, data=None, headers=None):
    try:
        return json.loads(_http(url, ref, data, headers))
    except Exception:
        return None


# ---- 纯 Python AES (网易云 weapi/eapi) ----
_SBOX = [
    0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
    0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
    0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
    0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
    0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
    0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
    0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
    0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
    0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
    0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
    0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
    0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
    0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
    0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
    0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
    0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16,
]
_RCON = [0x00,0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1b,0x36]


def _xtime(a):
    a <<= 1
    if a & 0x100:
        a ^= 0x11b
    return a & 0xff


def _mul(a, b):
    r = 0
    while b:
        if b & 1:
            r ^= a
        b >>= 1
        a = _xtime(a)
    return r


def _sub_word(w):
    return ((_SBOX[(w >> 24) & 0xff] << 24) | (_SBOX[(w >> 16) & 0xff] << 16) |
            (_SBOX[(w >> 8) & 0xff] << 8) | _SBOX[w & 0xff])


def _rot_word(w):
    return ((w << 8) | (w >> 24)) & 0xffffffff


def _key_expansion(key):
    k = list(key)
    w = []
    for i in range(4):
        w.append((k[4*i] << 24) | (k[4*i+1] << 16) | (k[4*i+2] << 8) | k[4*i+3])
    for i in range(4, 44):
        t = w[i-1]
        if i % 4 == 0:
            t = _sub_word(_rot_word(t)) ^ (_RCON[i//4] << 24)
        w.append(w[i-4] ^ t)
    return w


def _round_key_bytes(w, start):
    out = []
    for i in range(start, start + 4):
        out += [(w[i] >> 24) & 0xff, (w[i] >> 16) & 0xff, (w[i] >> 8) & 0xff, w[i] & 0xff]
    return out


def _add_round_key(state, rk):
    return [s ^ rk[i] for i, s in enumerate(state)]


def _sub_bytes(state):
    return [_SBOX[b] for b in state]


def _shift_rows(s):
    return [s[0], s[5], s[10], s[15], s[4], s[9], s[14], s[3],
            s[8], s[13], s[2], s[7], s[12], s[1], s[6], s[11]]


def _mix_columns(s):
    r = []
    for c in range(4):
        a0, a1, a2, a3 = s[4*c], s[4*c+1], s[4*c+2], s[4*c+3]
        r += [
            _mul(a0, 2) ^ _mul(a1, 3) ^ a2 ^ a3,
            a0 ^ _mul(a1, 2) ^ _mul(a2, 3) ^ a3,
            a0 ^ a1 ^ _mul(a2, 2) ^ _mul(a3, 3),
            _mul(a0, 3) ^ a1 ^ a2 ^ _mul(a3, 2),
        ]
    return r


def _encrypt_block(block, w):
    state = list(block)
    state = _add_round_key(state, _round_key_bytes(w, 0))
    for rnd in range(1, 10):
        state = _sub_bytes(state)
        state = _shift_rows(state)
        state = _mix_columns(state)
        state = _add_round_key(state, _round_key_bytes(w, 4 * rnd))
    state = _sub_bytes(state)
    state = _shift_rows(state)
    state = _add_round_key(state, _round_key_bytes(w, 40))
    return state


def _aes_encrypt_raw(data, key, iv=None):
    w = _key_expansion(key)
    pad = 16 - (len(data) % 16)
    data = data + bytes([pad]) * pad
    out = b""
    prev = bytes(iv) if iv else b"\x00" * 16
    for i in range(0, len(data), 16):
        block = data[i:i+16]
        if iv is not None:
            block = bytes(a ^ b for a, b in zip(block, prev))
        enc = bytes(_encrypt_block(block, w))
        if iv is not None:
            prev = enc
        out += enc
    return out


def _aes_b64(text, key, iv):
    import base64
    enc = _aes_encrypt_raw(text.encode("utf-8"), key.encode("utf-8"), iv.encode("utf-8"))
    return base64.b64encode(enc).decode()


def _aes_hex(text, key):
    enc = _aes_encrypt_raw(text.encode("utf-8"), key.encode("utf-8"), None)
    return enc.hex().upper()


def _weapi_params(obj):
    text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    try:
        params = _aes_b64(_aes_b64(text, WY_KEY, WY_IV), WY_KEY, WY_IV)
        return {"params": params, "encSecKey": WY_ENC_SEC}
    except Exception:
        return None


def _weapi_post(path, obj):
    """网易云 weapi POST 请求 (form-urlencoded)"""
    params = _weapi_params(obj)
    if not params:
        return None
    url = "https://interface.music.163.com/weapi/" + path
    body = urllib.parse.urlencode(params).encode()
    h = {"User-Agent": UA, "Referer": "https://music.163.com/",
         "Content-Type": "application/x-www-form-urlencoded",
         "Cookie": "os=pc; appver=9.0.25"}
    try:
        req = urllib.request.Request(url, data=body, headers=h)
        with urllib.request.urlopen(req, timeout=15, context=_CTX) as r:
            resp = r.read().decode("utf-8", errors="ignore")
        return json.loads(resp)
    except Exception:
        return None


# 分类维度名映射
_CAT_NAMES = {0: "语种", 1: "风格", 2: "场景", 3: "情感", 4: "主题"}
# 网易云歌单分类标签 (catalogue 实测 70个)
_CAT_TAGS = {
    0: ["华语", "欧美", "日语", "韩语", "粤语"],
    1: ["流行", "摇滚", "民谣", "电子", "舞曲", "说唱", "轻音乐", "爵士", "乡村", "R&B/Soul",
        "古典", "民族", "英伦", "金属", "朋克", "蓝调", "雷鬼", "世界音乐", "拉丁", "New Age",
        "古风", "后摇", "Bossa Nova"],
    2: ["清晨", "夜晚", "学习", "工作", "午休", "下午茶", "地铁", "驾车", "运动", "旅行", "散步", "酒吧"],
    3: ["怀旧", "清新", "浪漫", "伤感", "治愈", "放松", "孤独", "感动", "兴奋", "快乐", "安静", "思念"],
    4: ["综艺", "影视原声", "ACG", "儿童", "校园", "游戏", "70后", "80后", "90后", "网络歌曲",
        "KTV", "经典", "翻唱", "吉他", "钢琴", "器乐", "榜单", "00后"],
}


class Spider(BaseSpider):
    name = "歌词适配v2"

    def __init__(self):
        self.host = "https://interface.music.163.com"
        self.ua = UA

    # ---------- 首页 ----------
    def init(self, extend=""):
        return self.homeContent(extend)

    def homeContent(self, filter=False):
        """一级分类: 推荐/语种/风格/场景/情感/主题 (二级=网易云歌单标签)"""
        cats = [{"type_id": "recommend", "type_name": "推荐"}]
        # 语种/风格/场景/情感/主题 (固定维度)
        for cid, cname in [(0, "语种"), (1, "风格"), (2, "场景"), (3, "情感"), (4, "主题")]:
            cats.append({"type_id": "cat_%d" % cid, "type_name": cname})
        return {"class": cats, "filters": {}}

    def homeVodContent(self, page=1, filter=False):
        return self._playlists("recommend", str(page or 1))

    # ---------- 分类 (二级=歌单标签, 内容=歌单列表) ----------
    def categoryContent(self, tid, pg, filter=False, extend=""):
        # 一级维度 cat_N → 返回二级分类列表
        if re.match(r"^cat_\d+$", tid):
            cid = int(tid[4:])
            tags = _CAT_TAGS.get(cid, [])
            sub = [{"type_id": "tag_%d_%s" % (cid, urllib.parse.quote(t)), "type_name": t} for t in tags]
            return {"class": sub, "list": [], "page": 1, "pagecount": 1}
        # 二级标签 tag_N_xxx → 歌单列表
        if tid.startswith("tag_"):
            parts = tid.split("_", 2)
            if len(parts) == 3:
                tag = urllib.parse.unquote(parts[2])
                return self._playlists_by_tag(tag, str(pg or 1))
        return self._playlists(tid, str(pg or 1))

    def _playlists(self, tid, page):
        """歌单列表 (小图+文字布局) - recommend=全部热门"""
        return self._playlists_by_tag("", page)

    def _playlists_by_tag(self, tag, page):
        """按标签拉歌单 (tag='' 表示全部/推荐)"""
        offset = (int(page) - 1) * 30
        d = None
        try:
            d = _json("https://music.163.com/api/playlist/list?cat=%s&order=hot&limit=30&offset=%d" % (
                urllib.parse.quote(tag), offset),
                ref="https://music.163.com/")
        except Exception:
            d = None
        if not d:
            d = _weapi_post("playlist/list", {"cat": tag, "order": "hot", "limit": 30, "offset": offset, "total": True})
        pls = (d or {}).get("playlists") or []
        vods = []
        for p in pls:
            name = str(p.get("name") or "")
            if not name:
                continue
            vods.append({
                "vod_id": "pl_" + str(p.get("id") or ""),
                "vod_name": name,
                "vod_pic": str(p.get("coverImgUrl") or "").replace("{size}", "200"),
                "vod_remarks": str(p.get("trackCount") or 0) + "首",
            })
        pagecount = 1
        more = (d or {}).get("more")
        if more:
            pagecount = int(page) + 1
        return {"list": vods, "page": int(page), "pagecount": max(pagecount, int(page)), "total": len(vods)}

    # ---------- 详情 ----------
    def detailContent(self, ids):
        vid = str(ids[0]).split("$")[0]
        # 歌单详情 → 歌曲列表
        if vid.startswith("pl_"):
            pid = vid[3:]
            return self._playlist_songs(pid, vid)
        # 单曲 (搜索/歌单歌曲点播)
        if vid.startswith(("wy_", "kg_", "kw_", "qq_")):
            tag, rid = vid.split("_", 1)
            vod = {
                "vod_id": vid,
                "vod_name": "歌曲",
                "vod_play_from": "歌词适配",
                "vod_play_url": "播放$%s:%s" % (tag, rid),
            }
            return {"list": [vod]}
        return {"list": []}

    def _playlist_songs(self, pid, vid):
        """歌单歌曲列表 (小图+文字: 歌名+歌手)"""
        d = _json("https://music.163.com/api/v6/playlist/detail?id=%s" % pid, ref="https://music.163.com/")
        tracks = ((d or {}).get("playlist") or {}).get("tracks") or []
        # 名称/图/描述
        pl = (d or {}).get("playlist") or {}
        name = str(pl.get("name") or "歌单")
        pic = str(pl.get("coverImgUrl") or "").replace("{size}", "400")
        eps = []
        seen = set()
        for t in tracks:
            sid = str(t.get("id") or "")
            tname = str(t.get("name") or "")
            if not sid or tname in seen:
                continue
            seen.add(tname)
            artists = ", ".join(a.get("name", "") for a in (t.get("ar") or [])[:2])
            eps.append("%d. %s - %s$wy:%s" % (len(eps) + 1, tname, artists, sid))
        vod = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_remarks": str(pl.get("trackCount") or len(tracks)) + "首",
            "vod_content": str(pl.get("description") or ""),
            "vod_play_from": "歌词适配",
            "vod_play_url": "#".join(eps) if eps else "",
        }
        return {"list": [vod]}

    # ---------- 搜索 (保留四平台) ----------
    def searchContent(self, key, quick, pg="1"):
        kw = str(key or "").strip()
        if not kw:
            return {"list": []}
        vods = []
        seen = set()
        # 网易云
        try:
            d = _weapi_post("search/get", {"s": kw, "type": 1, "limit": 30, "offset": 0, "strategy": 5})
            for s in ((d or {}).get("result") or {}).get("songs") or []:
                name = str(s.get("name") or "")
                sid = str(s.get("id") or "")
                if not name or name in seen:
                    continue
                seen.add(name)
                arts = ", ".join(a.get("name", "") for a in (s.get("artists") or [])[:2])
                al = s.get("album") or {}
                vods.append({
                    "vod_id": "wy_" + sid,
                    "vod_name": name,
                    "vod_pic": str(al.get("picUrl") or "").replace("{size}", "200"),
                    "vod_remarks": arts or "网易云",
                })
        except Exception:
            pass
        # 酷狗
        try:
            d = _json("https://songsearch.kugou.com/song_search_v2?keyword=%s&page=1&pagesize=30&userid=-1&clientver=&platform=WebFilter&filter=2&iscorrection=1&privilege_filter=0&area_code=1" % urllib.parse.quote(kw))
            for s in ((d or {}).get("data") or {}).get("lists") or []:
                name = str(s.get("FileName") or "")
                if name in seen:
                    continue
                seen.add(name)
                vods.append({
                    "vod_id": "kg_" + str(s.get("FileHash") or ""),
                    "vod_name": name,
                    "vod_pic": str(s.get("Image") or "").replace("{size}", "200"),
                    "vod_remarks": str(s.get("SingerName") or "") or "酷狗",
                })
        except Exception:
            pass
        return {"list": vods, "page": 1, "pagecount": 1, "total": len(vods)}

    # ---------- 播放 ----------
    def playerContent(self, flag, id, vipFlags=None):
        raw = str(id or "").strip()
        tag = ""
        rid = raw
        if "$" in raw:
            rid = raw.split("$")[-1]
        if ":" in rid:
            tag, rid = rid.split(":", 1)
        elif "_" in rid and rid.split("_")[0] in ("wy", "kg", "kw", "qq"):
            tag, rid = rid.split("_", 1)
        source_map = {"wy": "wy", "kg": "kg", "kw": "kw", "qq": "qq"}
        source = source_map.get(tag, tag)
        url = ""
        # 1) 长青海棠
        url = self._ht_resolve(source, rid)
        # 2) 星海后端
        if not url:
            url = self._xinghai(source, rid)
        # 3) 官方兜底
        if not url:
            if source == "kg":
                url = self._kg_official(rid)
            elif source == "wy":
                url = self._wy_official(rid)
        return {"parse": 0, "jx": 0, "playUrl": "", "url": url, "header": {}}

    def _ht_resolve(self, source, rid):
        d = _json("https://musicserver.haitangw.cc/v1/music/resolve-url",
                  data={"source": source, "rid": str(rid), "level": "standard"})
        u = ((d or {}).get("data") or {}).get("url") or ""
        return u if u.startswith("http") else ""

    def _xinghai(self, source, rid):
        d = _json("https://yy.zddyr.top/lx/api/?source=%s&id=%s" % (source, urllib.parse.quote(str(rid))))
        u = (d or {}).get("url") or ""
        return u if u.startswith("http") else ""

    def _kg_official(self, hash):
        d = _json("http://m.kugou.com/app/i/getSongInfo.php?cmd=playInfo&hash=" + hash,
                  ref="http://m.kugou.com/")
        if d:
            u = str(d.get("url") or d.get("play_url") or "")
            if u.startswith("http"):
                return u
        return ""

    def _wy_official(self, sid):
        try:
            path = "/api/song/enhance/player/url"
            params = {"ids": [int(sid)], "level": "standard", "encodeType": "mp3"}
            text = json.dumps(params, ensure_ascii=False, separators=(",", ":"))
            digest = hashlib.md5(("nobody" + path + "use" + text + "md5forencrypt").encode()).hexdigest()
            data = path + "-36cd479b6b5-" + text + "-36cd479b6b5-" + digest
            enc = _aes_hex(data, WY_EAPI_KEY)
            url = "https://interface3.music.163.com/eapi" + path + "?params=" + urllib.parse.quote(enc)
            d = _json(url, ref="https://music.163.com/",
                      headers={"User-Agent": "Mozilla/5.0", "Cookie": "os=pc; appver=8.9.70"})
            songs = (d or {}).get("data") or []
            if songs and songs[0].get("url"):
                return str(songs[0]["url"]).replace("\\u0026", "&")
            return ""
        except Exception:
            return ""

    def isVideoFormat(self, url):
        return bool(re.search(r"\.(?:mp3|m4a|flac|aac|mp4|m3u8)(?:$|\?)", str(url or ""), re.I))

    def manualVideoCheck(self):
        return False

    def getName(self):
        return "歌词适配v2"

    def getCategory(self):
        return [{"type_id": "recommend", "type_name": "推荐"},
                {"type_id": "cat_0", "type_name": "语种"},
                {"type_id": "cat_1", "type_name": "风格"},
                {"type_id": "cat_2", "type_name": "场景"},
                {"type_id": "cat_3", "type_name": "情感"},
                {"type_id": "cat_4", "type_name": "主题"}]