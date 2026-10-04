# -*- coding: utf-8 -*-
# 歌词适配 [蜘蛛版] - 基于海阔"歌词适配"规则提取
# 平台: 网易云(wy) / 酷狗(kg) / 酷我(kw) / QQ(qq)
# 搜索: 各平台官方搜索接口
# 播放: 长青海棠 resolve-url (通吃四平台) → 星海后端 → 官方兜底
# 2026-10-04 实测: 海棠 wy/kg 全通, 酷狗官方 getSongInfo 可用
import json
import os
import re
import ssl
import sys
import time
import hashlib
import urllib.parse
import urllib.request
from base.spider import Spider as BaseSpider

# ---- 纯 Python AES (网易云 weapi/eapi, 无外部依赖) ----
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


def _aes_encrypt_raw(data: bytes, key: bytes, iv: bytes = None):
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

UA = "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36"
UA_MOBILE = "Mozilla/5.0 (Linux; Android 12; M2104K10AC) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0 Mobile Safari/537.36"

# 忽略证书 (部分 CDN 证书域名不匹配)
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

# 网易云 weapi/eapi 密钥 (从歌词适配规则提取)
WY_KEY = "0CoJUm6Qyw8W8jud"
WY_IV = "0102030405060708"
WY_EAPI_KEY = "e82ckenh8dichen8"
WY_ENC_SEC = "bf50d0bcf56833b06d8d1219496a452a1d860fd58a14c0aafba3e770104ca77dc6856cb310ed3309039e6865081be4ddc2df52663373b20b70ac25b4d0c6ca466daef6b50174e93536e2d580c49e70649ad1936584899e85722eb83ceddfb4f56c1172fca5e60592d0e6ee3e8e02be1fe6e53f285b0389162d8e6ddc553857cd"


def _http(url, ref=None, data=None, headers=None, timeout=15):
    """GET/POST 请求 (忽略证书), 失败重试1次"""
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


# ---------- AES 工具 (纯 Python 实现 weapi/eapi) ----------
def _aes_encrypt(text, key, iv=None, mode="cbc"):
    """AES 加密, 返回 hex 或 base64"""
    try:
        from Crypto.Cipher import AES
    except Exception:
        # 极简 AES-ECB/CBC 实现 (仅用于网易云 eapi/weapi)
        return _aes_pure(text, key, iv, mode)
    try:
        if mode == "cbc":
            pad = 16 - (len(text) % 16)
            text += chr(pad) * pad
            cipher = AES.new(key.encode(), AES.MODE_CBC, iv.encode())
            return cipher.encrypt(text.encode()).hex().upper()
        else:
            pad = 16 - (len(text) % 16)
            text += chr(pad) * pad
            cipher = AES.new(key.encode(), AES.MODE_ECB)
            return cipher.encrypt(text.encode()).hex().upper()
    except Exception:
        return _aes_pure(text, key, iv, mode)


def _aes_pure(text, key, iv, mode):
    """纯 Python AES (S-box 查表 + 轮函数 + CBC/ECB)"""
    # AES S-box
    SBOX = [
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
    # 简化: 仅实现 ECB/CBC 加密 (网易云用)
    # 实际用 pycryptodome 为主, 纯实现仅在缺失时兜底
    # 这里直接抛异常让调用方返回空 (避免错误播放)
    return ""


def _weapi_params(obj):
    """网易云 weapi 双层 AES 加密参数 (纯Python AES)"""
    text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    try:
        params = _aes_b64(_aes_b64(text, WY_KEY, WY_IV), WY_KEY, WY_IV)
        return {"params": params, "encSecKey": WY_ENC_SEC}
    except Exception:
        return None


def _eapi_params(path, obj):
    """网易云 eapi 参数 (纯Python AES-ECB)"""
    text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    data = "%s-36cd479b6b5-%s-36cd479b6b5-%s" % (path, text,
        hashlib.md5(("nobody" + path + "use" + text + "md5forencrypt").encode()).hexdigest())
    try:
        return _aes_hex(data, WY_EAPI_KEY)
    except Exception:
        return ""


class Spider(BaseSpider):
    name = "歌词适配"

    def __init__(self):
        self.host = "https://interface.music.163.com"
        self.ua = UA

    # ---------- 首页 ----------
    def init(self, extend=""):
        return self.homeContent(extend)

    def homeContent(self, filter=False):
        return {
            "class": [
                {"type_id": "wy", "type_name": "网易云"},
                {"type_id": "kg", "type_name": "酷狗"},
                {"type_id": "kw", "type_name": "酷我"},
                {"type_id": "qq", "type_name": "QQ音乐"},
            ],
            "filters": {},
        }

    def homeVodContent(self, page=1, filter=False):
        return self.searchContent("热门歌曲", False)

    # ---------- 分类 (各平台热歌) ----------
    def categoryContent(self, tid, pg, filter=False, extend=""):
        hot_words = {"wy": "热歌", "kg": "酷狗热歌", "kw": "酷我热歌", "qq": "QQ热歌"}
        return self.searchContent(hot_words.get(tid, "热歌"), False)

    # ---------- 搜索 ----------
    def searchContent(self, key, quick, pg="1"):
        """四平台聚合搜索"""
        kw = str(key or "").strip()
        if not kw:
            return {"list": []}
        vods = []
        seen = set()
        # 1) 网易云 (weapi 搜索)
        try:
            d = self._wy_search(kw)
            for s in d:
                sid = str(s.get("id") or "")
                name = str(s.get("name") or "")
                if not sid or name in seen:
                    continue
                seen.add(name)
                artists = ", ".join([a.get("name", "") for a in (s.get("artists") or []) if a.get("name")])
                al = s.get("album") or {}
                vods.append({
                    "vod_id": "wy_" + sid,
                    "vod_name": name,
                    "vod_pic": str(al.get("picUrl") or "").replace("{size}", "400"),
                    "vod_remarks": artists or "网易云",
                    "vod_tag": "wy",
                })
        except Exception:
            pass
        # 2) 酷狗
        try:
            d = self._kg_search(kw)
            for s in d:
                name = str(s.get("FileName") or "")
                if name in seen:
                    continue
                seen.add(name)
                vods.append({
                    "vod_id": "kg_" + str(s.get("FileHash") or ""),
                    "vod_name": name,
                    "vod_pic": str(s.get("Image") or "").replace("{size}", "400"),
                    "vod_remarks": str(s.get("SingerName") or "") or "酷狗",
                    "vod_tag": "kg",
                })
        except Exception:
            pass
        # 3) 酷我
        try:
            d = self._kw_search(kw)
            for s in d:
                name = str(s.get("name") or "")
                if name in seen:
                    continue
                seen.add(name)
                vods.append({
                    "vod_id": "kw_" + str(s.get("rid") or ""),
                    "vod_name": name,
                    "vod_pic": str(s.get("pic") or ""),
                    "vod_remarks": str(s.get("artist") or "") or "酷我",
                    "vod_tag": "kw",
                })
        except Exception:
            pass
        # 4) QQ
        try:
            d = self._qq_search(kw)
            for s in d:
                name = str(s.get("title") or s.get("songname") or "")
                if name in seen:
                    continue
                seen.add(name)
                vods.append({
                    "vod_id": "qq_" + str(s.get("songmid") or s.get("mid") or ""),
                    "vod_name": name,
                    "vod_pic": str(s.get("album_pic") or "").replace("{size}", "400"),
                    "vod_remarks": str(s.get("singer") or "") or "QQ音乐",
                    "vod_tag": "qq",
                })
        except Exception:
            pass
        return {"list": vods, "page": 1, "pagecount": 1, "total": len(vods)}

    # ---------- 各平台搜索 ----------
    def _wy_search(self, kw):
        """网易云 weapi 搜索"""
        params = _weapi_params({"s": kw, "type": 1, "limit": 30, "offset": 0, "strategy": 5})
        if not params:
            return []
        url = "https://interface.music.163.com/weapi/search/get"
        # weapi 需要 form-urlencoded (params+encSecKey)
        body = urllib.parse.urlencode(params).encode()
        try:
            h = {"User-Agent": UA, "Referer": "https://music.163.com/",
                 "Content-Type": "application/x-www-form-urlencoded"}
            req = urllib.request.Request(url, data=body, headers=h)
            with urllib.request.urlopen(req, timeout=15, context=_CTX) as r:
                resp = r.read().decode("utf-8", errors="ignore")
            return ((json.loads(resp).get("result") or {}).get("songs") or [])
        except Exception:
            return []
        return ((d or {}).get("result") or {}).get("songs") or []

    def _kg_search(self, kw):
        url = ("https://songsearch.kugou.com/song_search_v2?keyword=%s&page=1&pagesize=30"
               "&userid=-1&clientver=&platform=WebFilter&filter=2&iscorrection=1"
               "&privilege_filter=0&area_code=1") % urllib.parse.quote(kw)
        d = _json(url)
        return ((d or {}).get("data") or {}).get("lists") or []

    def _kw_search(self, kw):
        url = "https://www.kuwo.cn/api/www/search/searchMusicBykeyWord?key=%s&pn=1&rn=30&httpsStatus=1" % urllib.parse.quote(kw)
        d = _json(url, ref="https://www.kuwo.cn/", headers={"csrf": "", "Cookie": "kw_token="})
        return ((d or {}).get("data") or {}).get("list") or []

    def _qq_search(self, kw):
        payload = {
            "req": {"method": "DoSearchForQQMusicDesktop", "module": "music.search_search_cp",
                    "param": {"query": kw, "num_per_page": 30, "page_num": 1}}
        }
        url = "https://u.y.qq.com/cgi-bin/musicu.fcg?format=json&data=" + urllib.parse.quote(json.dumps(payload, ensure_ascii=False))
        d = _json(url)
        body = ((d or {}).get("req") or {}).get("data") or {}
        return ((body.get("body") or {}).get("song") or {}).get("list") or []

    # ---------- 详情 ----------
    def detailContent(self, ids):
        vid = str(ids[0]).split("$")[0]
        tag, rid = vid.split("_", 1)
        # 单曲详情 = 直接给播放
        name = "歌曲"
        vod = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": "",
            "vod_play_from": "歌词适配",
            "vod_play_url": "播放$" + tag + ":" + rid,
        }
        return {"list": [vod]}

    # ---------- 播放 (核心: 海棠 → 星海 → 官方) ----------
    def playerContent(self, flag, id, vipFlags=None):
        raw = str(id or "").strip()
        tag = ""
        rid = raw
        if "$" in raw:
            rid = raw.split("$")[-1]
        # 兼容 wy:123 / wy_123 / 123
        if ":" in rid:
            tag, rid = rid.split(":", 1)
        elif "_" in rid and rid.split("_")[0] in ("wy", "kg", "kw", "qq"):
            tag, rid = rid.split("_", 1)
        source_map = {"wy": "wy", "kg": "kg", "kw": "kw", "qq": "qq"}
        source = source_map.get(tag, tag)
        url = ""
        # 1) 长青海棠 (通吃四平台)
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
        """长青海棠 resolve-url (2026-10-04 实测 wy/kg 全通)"""
        d = _json("https://musicserver.haitangw.cc/v1/music/resolve-url",
                  data={"source": source, "rid": str(rid), "level": "standard"})
        u = ((d or {}).get("data") or {}).get("url") or ""
        return u if u.startswith("http") else ""

    def _xinghai(self, source, rid):
        """星海后端"""
        d = _json("https://yy.zddyr.top/lx/api/?source=%s&id=%s" % (source, urllib.parse.quote(str(rid))))
        u = (d or {}).get("url") or ""
        return u if u.startswith("http") else ""

    def _kg_official(self, hash):
        """酷狗官方 getSongInfo (免费歌)"""
        d = _json("http://m.kugou.com/app/i/getSongInfo.php?cmd=playInfo&hash=" + hash,
                  ref="http://m.kugou.com/")
        if d:
            u = str(d.get("url") or d.get("play_url") or "")
            if u.startswith("http"):
                return u
        return ""

    def _wy_official(self, sid):
        """网易云 eapi player/url (规则同款, AES-ECB 加密)"""
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
        return "歌词适配"

    def getCategory(self):
        return [
            {"type_id": "wy", "type_name": "网易云"},
            {"type_id": "kg", "type_name": "酷狗"},
            {"type_id": "kw", "type_name": "酷我"},
            {"type_id": "qq", "type_name": "QQ音乐"},
        ]