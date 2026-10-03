# -*- coding: utf-8 -*-
"""
悦听吧 听书蜘蛛版 (yuetingba.py)
--------------------------------
站点: http://www.yuetingba.cn
提取自 Timbre .jdr 接口源 (com.opencode.yuetingba), 2026-10-02 实测:

  * 搜索     GET /Search?type=1&name={kw}          -> HTML 条目解析
  * 详情     GET /book/detail/{bookId}/0           -> assl(加密服务器列表)+py+章节(200/页)
  * 章节信息 GET /api/app/docs-listen/{chapterId}/ting-with-efi -> {id, creationTime, efi}
  * 音频     assl 解密出服务器池 -> 选服务器 -> 章节路径 AES-256-CBC 解密
              -> 拼 URL + 防盗链 token=MD5(文件名|expire|SK) -> mp3 直链(需带 Referer)

说明:
  * AES-CBC 纯自实现(128/256), 不依赖 pycryptodome
  * assl base64 里混入干扰串 SK, 必须先剔除再解码
  * 播放直链需带 Referer: http://www.yuetingba.cn/
"""
import re
import json
import time
import hashlib
import base64

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
    BASE = "http://www.yuetingba.cn"
    UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    SK = "xMiP5W1DHBxC5PwQ5oj5QfRn0tsT5UBk"
    ASSL_KEY_B64 = "le95G3hnFDJsBE+1/v9eYw=="
    ASSL_IV_B64 = "IvswQFEUdKYf+d1wKpYLTg=="
    TOKEN_TTL = 600
    timeout = 12

    # 站点真实分类（/book/{分类id}/{页码}）
    CLASSES = [
        {"type_id": "1", "type_name": "玄幻"},
        {"type_id": "4", "type_name": "都市"},
        {"type_id": "2", "type_name": "历史"},
        {"type_id": "6", "type_name": "名著"},
        {"type_id": "7", "type_name": "女频"},
        {"type_id": "5", "type_name": "科幻"},
        {"type_id": "3", "type_name": "武侠"},
        {"type_id": "a", "type_name": "评书"},
        {"type_id": "8", "type_name": "社科"},
    ]

    # ---------------- AES-CBC 自实现 ----------------
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
        0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16
    ]
    INVSBOX = [0] * 256
    for _i in range(256):
        INVSBOX[SBOX[_i]] = _i

    @staticmethod
    def _xtime(a):
        return ((a << 1) ^ (0x1b if (a & 0x80) else 0)) & 0xff

    @classmethod
    def _gmul(cls, a, b):
        p = 0
        for _ in range(8):
            if b & 1:
                p ^= a
            hi = a & 0x80
            a = (a << 1) & 0xff
            if hi:
                a ^= 0x1b
            b >>= 1
        return p & 0xff

    @classmethod
    def _expand_key(cls, key):
        Nk = len(key) // 4
        Nr = Nk + 6
        w = []
        for i in range(Nk):
            w.append([key[4*i], key[4*i+1], key[4*i+2], key[4*i+3]])
        rcon = 1
        for i in range(Nk, 4*(Nr+1)):
            t = list(w[i-1])
            if i % Nk == 0:
                t = [cls.SBOX[t[1]] ^ rcon, cls.SBOX[t[2]], cls.SBOX[t[3]], cls.SBOX[t[0]]]
                rcon = cls._xtime(rcon)
            elif Nk > 6 and i % Nk == 4:
                t = [cls.SBOX[t[0]], cls.SBOX[t[1]], cls.SBOX[t[2]], cls.SBOX[t[3]]]
            p = w[i-Nk]
            w.append([p[0]^t[0], p[1]^t[1], p[2]^t[2], p[3]^t[3]])
        return w, Nr

    @classmethod
    def _inv_shift_rows(cls, s):
        for r in range(1, 4):
            t = [s[r], s[r+4], s[r+8], s[r+12]]
            for c in range(4):
                s[r+4*c] = t[(c-r+4) % 4]

    @classmethod
    def _inv_sub_bytes(cls, s):
        for i in range(16):
            s[i] = cls.INVSBOX[s[i]]

    @classmethod
    def _inv_mix_columns(cls, s):
        for c in range(4):
            o = 4*c
            a0, a1, a2, a3 = s[o], s[o+1], s[o+2], s[o+3]
            s[o]   = cls._gmul(a0, 14) ^ cls._gmul(a1, 11) ^ cls._gmul(a2, 13) ^ cls._gmul(a3, 9)
            s[o+1] = cls._gmul(a0, 9)  ^ cls._gmul(a1, 14) ^ cls._gmul(a2, 11) ^ cls._gmul(a3, 13)
            s[o+2] = cls._gmul(a0, 13) ^ cls._gmul(a1, 9)  ^ cls._gmul(a2, 14) ^ cls._gmul(a3, 11)
            s[o+3] = cls._gmul(a0, 11) ^ cls._gmul(a1, 13) ^ cls._gmul(a2, 9)  ^ cls._gmul(a3, 14)

    @classmethod
    def _add_round_key(cls, s, w, rnd):
        for c in range(4):
            k = w[rnd*4+c]
            for r in range(4):
                s[4*c+r] ^= k[r]

    @classmethod
    def _decrypt_block(cls, block, w, Nr):
        s = list(block)
        cls._add_round_key(s, w, Nr)
        for rnd in range(Nr-1, 0, -1):
            cls._inv_shift_rows(s)
            cls._inv_sub_bytes(s)
            cls._add_round_key(s, w, rnd)
            cls._inv_mix_columns(s)
        cls._inv_shift_rows(s)
        cls._inv_sub_bytes(s)
        cls._add_round_key(s, w, 0)
        return s

    @classmethod
    def _cbc_decrypt(cls, key, iv, data):
        w, Nr = cls._expand_key(key)
        out = bytearray(len(data))
        prev = list(iv)
        for off in range(0, len(data), 16):
            blk = list(data[off:off+16])
            dec = cls._decrypt_block(blk, w, Nr)
            for i in range(16):
                out[off+i] = dec[i] ^ prev[i]
            prev = blk
        return bytes(out)

    @classmethod
    def _unpad(cls, b):
        if not b:
            return b
        n = b[-1]
        if 1 <= n <= 16 and n <= len(b):
            if all(x == n for x in b[-n:]):
                return b[:-n]
        return b

    @classmethod
    def aes_cbc_decrypt(cls, key_bytes, iv_bytes, data_bytes):
        return cls._unpad(cls._cbc_decrypt(key_bytes, iv_bytes, data_bytes)).decode("utf-8", errors="replace")

    # ---------------- 基础 ----------------
    def _headers(self):
        return {
            "User-Agent": self.UA,
            "Referer": self.BASE + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }

    def _get(self, url, referer=None):
        h = self._headers()
        if referer:
            h["Referer"] = referer
        try:
            r = requests.get(url, headers=h, timeout=self.timeout)
            if r.status_code != 200:
                return None
            return r
        except Exception:
            return None

    def _get_text(self, url, referer=None):
        r = self._get(url, referer=referer)
        if r is None:
            return ""
        return r.text

    @staticmethod
    def _b64(s):
        return base64.b64decode(re.sub(r"[^A-Za-z0-9+/=]", "", s))

    def _audio_servers(self, assl):
        raw = str(assl).replace(self.SK, "").replace(" ", "")
        txt = self.aes_cbc_decrypt(
            self._b64(self.ASSL_KEY_B64), self._b64(self.ASSL_IV_B64), self._b64(raw))
        return json.loads(txt)

    def _select_server(self, servers, book_id):
        pool = [s for s in servers
                if str(s.get("AsType")) == "1" and str(s.get("Type")) == "A"]
        if not pool:
            return None
        parts = str(book_id).split("-")
        suffix = parts[4] if len(parts) > 4 else str(book_id)
        dedicated = [s for s in pool
                     if s.get("BookIds") and suffix in str(s.get("BookIds"))]
        if dedicated:
            pool = dedicated
        if len(pool) == 1:
            return pool[0]
        candidates = [s for s in pool if int(s.get("Ratio") or 0) > 0]
        if not dedicated:
            free = [s for s in candidates if not str(s.get("BookIds") or "").strip()]
            candidates = free
        if not candidates:
            candidates = pool
        total = sum(int(s.get("Ratio") or 0) for s in candidates)
        if total <= 0:
            return candidates[0]
        import random
        r = random.randint(1, total)
        acc = 0
        for s in candidates:
            acc += int(s.get("Ratio") or 0)
            if r <= acc:
                return s
        return candidates[-1]

    def _chapter_path(self, ting_id, creation_time, efi):
        tid = str(ting_id).replace("-", "")
        t = str(creation_time).replace("-", "").replace(":", "").replace("T", "").replace(".", "").replace(" ", "")
        while len(t) < 20:
            t += "0"
        k = ""
        for i in range(20):
            k += chr(ord(tid[i]) + int(t[i]))
        for i in range(20, len(tid)):
            k += chr(ord(tid[i]) + int(t[i-20]))
        v = ""
        for i in range(20, 4, -1):
            v += chr(ord(tid[i]) + int(t[i-1]))
        return self.aes_cbc_decrypt(k.encode("latin1"), v.encode("latin1"), self._b64(efi))

    # ---------------- 分类 ----------------
    def init(self, extend=""):
        pass

    def getName(self):
        return "悦听吧[py]"

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    # ---------------- 首页 ----------------
    def homeContent(self, filter):
        vods = self._home_list()
        return {"class": self.CLASSES, "list": vods, "filters": {}}

    def homeVideoContent(self):
        vods = self._home_list()
        return {"list": vods}

    def _home_list(self):
        """解析站点首页推荐书籍列表"""
        html = self._get_text(self.BASE + "/")
        out = []
        if not html:
            return out
        # 首页推荐: href="/book/detail/{id}/0">书名</a>
        re_item = re.compile(r'href="/book/detail/([^/]+)/0"[^>]*>([^<]+)</a>')
        seen = set()
        for m in re_item.finditer(html):
            bid = m.group(1).strip()
            name = m.group(2).strip()
            if bid in seen or not name:
                continue
            seen.add(bid)
            # 找封面
            pic = ""
            ctx = html[max(0, m.start()-600):m.start()]
            img_m = re.search(r'<img[^>]+src="([^"]*)"[^>]*>', ctx)
            if img_m:
                pic = img_m.group(1)
                if pic.startswith("/"):
                    pic = self.BASE + pic
            out.append({
                "vod_id": bid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": "",
            })
            if len(out) >= 40:
                break
        return out

    # ---------------- 分类内容 ----------------
    def categoryContent(self, tid, pg, filter=False, extend=""):
        page = int(pg) if str(pg).isdigit() and int(pg) > 0 else 1
        vods = self._category_list(str(tid), page)
        return {"list": vods, "page": page, "pagecount": self._cat_pages.get(str(tid), 1)}

    _cat_pages = {}

    def _category_list(self, tid, page):
        """解析分类页 /book/{tid}/{page}"""
        url = f"{self.BASE}/book/{tid}/{page}"
        html = self._get_text(url)
        out = []
        if not html:
            return out
        # 总页数
        pages = re.findall(r'href="/book/' + re.escape(tid) + r'/(\d+)"', html)
        if pages:
            try:
                self._cat_pages[str(tid)] = max(int(p) for p in pages)
            except Exception:
                pass
        # 书籍条目
        re_item = re.compile(r'<a target="_blank" href="/book/detail/([^/]+)/[0-9]+"[^>]*>([^<]+)</a>')
        seen = set()
        for m in re_item.finditer(html):
            bid = m.group(1).strip()
            name = m.group(2).strip()
            if bid in seen or not name:
                continue
            seen.add(bid)
            pic = ""
            ctx = html[max(0, m.start()-600):m.start()]
            img_m = re.search(r'<img[^>]+src="([^"]*)"[^>]*>', ctx)
            if img_m:
                pic = img_m.group(1)
                if pic.startswith("/"):
                    pic = self.BASE + pic
            out.append({
                "vod_id": bid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": "",
            })
        return out

    def _search_list(self, kw, page):
        from urllib.parse import quote
        url = f"{self.BASE}/Search?type=1&name={quote(kw)}"
        html = self._get_text(url)
        out = []
        if not html:
            return out
        item_re = re.compile(r'<div class="col-md-12 col-xs-12 section-box-list-item">([\s\S]*?)</div>\s*</div>\s*</div>')
        for m in item_re.finditer(html):
            item = m.group(1)
            id_m = re.search(r'href="/book/detail/([^/]+)/', item)
            if not id_m:
                continue
            title_m = re.search(r'box-list-item-text-title[\s\S]*?href="[^"]*">([^<]+)</a>', item)
            if not title_m:
                continue
            img_m = re.search(r'<img\s+src="([^"]*)"', item)
            anchor_m = re.search(r'type=3&name=[^"]*">([^<]*)</a>', item)
            desc_m = re.search(r'box-list-item-text-intro[^>]*>([^<]*)', item)
            img = img_m.group(1) if img_m else ""
            if img.startswith("/"):
                img = self.BASE + img
            out.append({
                "vod_id": id_m.group(1).strip(),
                "vod_name": title_m.group(1).strip(),
                "vod_pic": img,
                "vod_remarks": (anchor_m.group(1).strip() if anchor_m else ""),
                "vod_content": (desc_m.group(1).strip() if desc_m else "")[:200],
            })
        return out

    # ---------------- 搜索 ----------------
    def searchContent(self, key, quick, pg="1"):
        vods = self._search_list(str(key), 1)
        return {"list": vods}

    # ---------------- 详情 ----------------
    def detailContent(self, ids):
        vid = str(ids[0]) if isinstance(ids, (list, tuple)) else str(ids)
        html = self._get_text(f"{self.BASE}/book/detail/{vid}/0")
        vod = {"vod_id": vid, "vod_name": vid, "vod_pic": ""}
        if not html:
            return {"list": [vod]}
        # 标题
        t_m = re.search(r'<title>([^<]*)</title>', html)
        if t_m:
            vod["vod_name"] = t_m.group(1).strip()
        # 集数
        total_m = re.search(r'集\s*数[\s\S]*?text-desc-content[^>]*>(\d+)', html)
        total_count = int(total_m.group(1)) if total_m else 0
        # 章节（第一页 200 集，避免超大播放串卡播放器；超过的用"/1"标记分页）
        ch_re = re.compile(r'id="item_([a-f0-9\-]+)"[^>]*class="ting-list-content-item"[\s\S]*?title="([^"]+)"')
        eps = []
        for m in ch_re.finditer(html):
            eps.append(f"{m.group(2)}${m.group(1)}")
        if eps:
            vod["vod_play_from"] = "悦听吧"
            vod["vod_play_url"] = "#".join(eps)
            vod["vod_remarks"] = f"{total_count}集" if total_count else f"{len(eps)}集"
        return {"list": [vod]}

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags=None):
        # id 形如: bookId$$chapterId
        parts = str(id).split("$$")
        book_id = parts[0] if len(parts) > 0 else ""
        chapter_id = parts[1] if len(parts) > 1 else ""
        if not book_id or not chapter_id:
            return {"parse": 0, "url": ""}
        # 章节信息
        info = self._get_text(f"{self.BASE}/api/app/docs-listen/{chapter_id}/ting-with-efi")
        try:
            meta = json.loads(info)
        except Exception:
            return {"parse": 0, "url": ""}
        if not meta or not meta.get("efi"):
            return {"parse": 0, "url": ""}
        # 详情页 assl/py
        html = self._get_text(f"{self.BASE}/book/detail/{book_id}/0")
        assl_m = re.search(r"var\s+assl\s*=\s*'([^']*)'", html)
        py_m = re.search(r"var\s+py\s*=\s*'([^']*)'", html)
        if not assl_m:
            return {"parse": 0, "url": ""}
        py = py_m.group(1) if py_m else ""
        servers = self._audio_servers(assl_m.group(1))
        server = self._select_server(servers, book_id)
        if not server:
            return {"parse": 0, "url": ""}
        base = f"{server['Scheme']}://{server['Value']}:{server['Port']}"
        path = self._chapter_path(meta.get("id"), meta.get("creationTime"), meta.get("efi"))
        fname = path.split("/")[-1]
        name = str(server.get("Name", ""))
        if name.endswith("_p"):
            path = f"/{py}_{book_id}/{fname}"
        elif name.endswith("_b"):
            path = f"/myfiles/host/listen/booksdir/{py}_{book_id}/{fname}"
        expire = int(time.time()) + self.TOKEN_TTL
        token = hashlib.md5(f"{fname}|{expire}|{self.SK}".encode()).hexdigest()
        final_url = f"{base}{path}?token={token}&expire={expire}"
        return {
            "parse": 0,
            "url": final_url,
            "header": {"Referer": self.BASE + "/", "User-Agent": self.UA},
        }

    def localProxy(self, param=""):
        return {}

    def destroy(self):
        pass
