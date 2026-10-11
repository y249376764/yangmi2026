# -*- coding: utf-8 -*-
"""
花子动漫 - huazidm.com
MacCMS + mxtheme 模板，服务端渲染；播放地址为「双层加密」，需调用独立解析器还原。

关键结论（已实测验证）：
1. 首页 / ：卡片 a.module-poster-item[href=/voddetail/{id}.html]
   （img[data-original=封面] + title=片名 + .module-item-note=备注）。
2. 分类 /vodtype/{tid}.html（分类：TV动画1 / 剧场2 / 特摄3 / 美漫4 / 连载动画20）。
   ⚠ 站点对 vodshow/vodsearch（分类库与搜索页）启用「系统安全验证」验证码拦截，
   且 verify_check 接口返回 500，不可用；vodtype 可正常访问，但**无有效分页**
   （?page=N 标题变化但内容相同），故分类只在第 1 页返回该分类全部卡片。
3. 搜索：走 MacCMS 原生建议接口
   GET /index.php/ajax/suggest?mid=1&wd={关键词} → {"list":[{"id","name","pic"}]}。
   （/vodsearch/ 被验证码拦截；/index.php/ajax/data 忽略 tid 且为全量，不适合分类。）
4. 详情 /voddetail/{id}.html ：h1 标题；封面 img[data-original]；简介
   .module-info-introduction-content；线路 chip .play-source-chip[data-dropdown-value=线路名]
   与集数容器 .module-play-list 一一对应（按文档顺序），集数
   a.module-play-list-link[href=/vodplay/{id}-{sid}-{nid}.html]。
5. 播放（核心，双层加密）：
   a) 播放页 /vodplay/{id}-{sid}-{nid}.html 内 player_aaaa，encrypt=2；
      url 经 base64decode 再 unescape 得到 96 位 hex 串。
   b) GET https://play.huazidm.xyz/?url={hex} → 页面内 var config={url,time,key,...}。
   c) POST https://play.huazidm.xyz/api.php  (url,time,key)
      → JSON {"code":200,"type":"mp4","url":"<AES密文base64>"}。
   d) AES-128-CBC/Pkcs7 解密（key=Js9S3utx6kd59sjV, iv=uRX7RP5JMcDPTMFE）
      → 真实播放直链（实测 206 video/mp4 可直连）。
   注：本站内嵌于 settings.js 的 AES 密钥经 jsjiami.v7 混淆，已还原为上述常量。
   为兼容不装第三方库的 TVBox 环境，本插件自带纯 Python AES-128-CBC 实现。
"""
import re
import json
import time
import base64
import requests
from urllib.parse import quote

try:
    from base.spider import Spider
except ImportError:
    class Spider:
        def __init__(self):
            pass


# ==================== 纯 Python AES-128-CBC 解密 ====================
_SBOX = [
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
    0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
    0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
    0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
    0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
    0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
    0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
    0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
    0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
    0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
    0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16,
]
_INV_SBOX = [0] * 256
for _i, _v in enumerate(_SBOX):
    _INV_SBOX[_v] = _i
_RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36]


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
        a = _xtime(a)
        b >>= 1
    return r & 0xff


def _key_expansion(key):
    nk = len(key) // 4
    nr = nk + 6
    w = [list(key[4 * i:4 * i + 4]) for i in range(nk)]
    for i in range(nk, 4 * (nr + 1)):
        temp = list(w[i - 1])
        if i % nk == 0:
            temp = temp[1:] + temp[:1]
            temp = [_SBOX[b] for b in temp]
            temp[0] ^= _RCON[i // nk - 1]
        elif nk > 6 and i % nk == 4:
            temp = [_SBOX[b] for b in temp]
        w.append([w[i - nk][j] ^ temp[j] for j in range(4)])
    return w, nr


def _add_round_key(state, w, rnd):
    for c in range(4):
        for r in range(4):
            state[r][c] ^= w[rnd * 4 + c][r]


def _inv_sub_bytes(state):
    for r in range(4):
        for c in range(4):
            state[r][c] = _INV_SBOX[state[r][c]]


def _inv_shift_rows(state):
    for r in range(1, 4):
        state[r] = state[r][-r:] + state[r][:-r]


def _inv_mix_columns(state):
    for c in range(4):
        a = [state[r][c] for r in range(4)]
        state[0][c] = _mul(a[0], 14) ^ _mul(a[1], 11) ^ _mul(a[2], 13) ^ _mul(a[3], 9)
        state[1][c] = _mul(a[0], 9) ^ _mul(a[1], 14) ^ _mul(a[2], 11) ^ _mul(a[3], 13)
        state[2][c] = _mul(a[0], 13) ^ _mul(a[1], 9) ^ _mul(a[2], 14) ^ _mul(a[3], 11)
        state[3][c] = _mul(a[0], 11) ^ _mul(a[1], 13) ^ _mul(a[2], 9) ^ _mul(a[3], 14)


def _decrypt_block(block, w, nr):
    state = [[block[r + 4 * c] for c in range(4)] for r in range(4)]
    _add_round_key(state, w, nr)
    for rnd in range(nr - 1, 0, -1):
        _inv_shift_rows(state)
        _inv_sub_bytes(state)
        _add_round_key(state, w, rnd)
        _inv_mix_columns(state)
    _inv_shift_rows(state)
    _inv_sub_bytes(state)
    _add_round_key(state, w, 0)
    return bytes(state[r][c] for c in range(4) for r in range(4))


def _aes_cbc_decrypt(cipher_bytes, key, iv):
    w, nr = _key_expansion(key)
    prev = iv
    out = bytearray()
    for off in range(0, len(cipher_bytes), 16):
        block = cipher_bytes[off:off + 16]
        dec = _decrypt_block(block, w, nr)
        out.extend(bytes(a ^ b for a, b in zip(dec, prev)))
        prev = block
    # PKCS7 unpad
    if out:
        pad = out[-1]
        if 0 < pad <= 16 and len(out) >= pad:
            out = out[:-pad]
    return bytes(out)


class Spider(Spider):
    # ==================== 基础配置 ====================
    name = "花子动漫"
    base_url = "https://www.huazidm.com"
    site_url = "https://www.huazidm.com"
    parser_url = "https://play.huazidm.xyz"

    searchable = 1
    quickSearch = 1
    filterable = 0
    changeable = 1

    class_name = ["TV动画", "连载动画", "剧场", "特摄", "美漫"]
    class_url = ["1", "20", "2", "3", "4"]
    CATEGORY_NAMES = {
        "1": "TV动画",
        "20": "连载动画",
        "2": "剧场",
        "3": "特摄",
        "4": "美漫",
    }

    # AES 常量（由 settings.js 混淆代码还原）
    AES_KEY = b"Js9S3utx6kd59sjV"
    AES_IV = b"uRX7RP5JMcDPTMFE"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://www.huazidm.com/",
        "Connection": "keep-alive",
    }

    play_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.huazidm.com/",
        "Accept": "*/*",
    }

    def __init__(self):
        super().__init__()
        self._session = requests.Session()
        self._session.headers.update(self.headers)
        self._play_cache = {}
        self._cache_ttl = 1200
        self._last_req_time = 0
        self._min_req_interval = 0.7

    # ==================== 工具方法 ====================
    def _log(self, msg):
        print("[%s] %s" % (self.name, msg))

    def _clean_html(self, text):
        if not text:
            return ""
        text = re.sub(r'<br\s*/?>', ' ', text)
        text = re.sub(r'<[^>]+>', '', text)
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&quot;', '"')
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _fix_pic(self, pic):
        if not pic:
            return ""
        pic = pic.strip()
        if pic.startswith("//"):
            return "https:" + pic
        if pic.startswith("/"):
            return self.base_url + pic
        return pic

    # ==================== 请求基础 ====================
    def _apply_req_delay(self):
        now = time.time()
        elapsed = now - self._last_req_time
        if 0 < elapsed < self._min_req_interval:
            time.sleep(self._min_req_interval - elapsed)
        self._last_req_time = time.time()

    def fetch(self, url, headers=None, timeout=30, method="get", data=None):
        self._apply_req_delay()
        if method == "post":
            return self._session.post(url, headers=headers or {}, data=data, timeout=timeout)
        return self._session.get(url, headers=headers or {}, timeout=timeout)

    def _is_bad_page(self, html):
        if not html:
            return True
        if '系统安全验证' in html or 'System Error' in html or '404' == html.strip()[:3] and len(html) < 200:
            return True
        return False

    def _get(self, url, max_retry=3, timeout=20, headers=None):
        try:
            for attempt in range(max_retry):
                resp = self.fetch(url, headers=headers or self.headers, timeout=timeout)
                html = resp.text
                if self._is_bad_page(html):
                    self._log("页面异常(%s)，重试 %s" % (resp.status_code, url))
                    if attempt < max_retry - 1:
                        time.sleep(1 + attempt)
                        continue
                    return ""
                return html
            return ""
        except Exception as e:
            self._log("请求失败: %s, %s" % (url, e))
            return ""

    # ==================== 列表解析 ====================
    def _parse_video_list(self, html):
        """解析 a.module-poster-item 卡片（首页/分类通用）"""
        videos = []
        if not html:
            return videos
        for m in re.finditer(r'<a[^>]*href="(/voddetail/(\d+)\.html)"[^>]*class="[^"]*module-poster-item[^"]*"(.*?)(?=<a[^>]*class="[^"]*module-poster-item|<div class="module-footer|$)', html, re.DOTALL):
            vod_id = m.group(2)
            block = m.group(1) + m.group(3)
            title = ""
            tm = re.search(r'title="([^"]*)"', m.group(0))
            if tm:
                title = tm.group(1).strip()
            pm = re.search(r'<img[^>]*(?:data-original|data-src|src)="([^"]+)"', block)
            pic = pm.group(1) if pm else ""
            nm = re.search(r'class="module-item-note"[^>]*>([^<]*)<', block)
            note = self._clean_html(nm.group(1)) if nm else ""
            if not title:
                am = re.search(r'alt="([^"]*)"', block)
                if am:
                    title = am.group(1).strip()
            if not title:
                continue
            videos.append({
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": self._fix_pic(pic),
                "vod_remarks": note,
            })
        # 去重
        seen = set()
        dedup = []
        for v in videos:
            if v["vod_id"] in seen:
                continue
            seen.add(v["vod_id"])
            dedup.append(v)
        return dedup

    # ==================== 播放源解析（详情页） ====================
    def _parse_play_sources(self, html, vod_id):
        """线路 chip 与 .module-play-list 容器按文档顺序一一对应"""
        sources = []
        if not html:
            return sources
        chips = re.findall(r'data-dropdown-value="([^"]*)"', html)
        blocks = re.findall(
            r'<div class="module-play-list">.*?module-play-list-base">(.*?)</div>\s*</div>',
            html, re.DOTALL)
        if not blocks:
            # 退化：所有播放链接归为一条线路
            blocks = [html]
        for k, body in enumerate(blocks):
            eps = re.findall(
                r'href="/vodplay/%s-(\d+)-(\d+)\.html"[^>]*(?:title="([^"]*)")?[^>]*>\s*(?:<span>)?([^<]*)'
                % re.escape(str(vod_id)), body)
            if not eps:
                continue
            eps2 = []
            for sid, nid, t1, t2 in eps:
                name = self._clean_html(t1) or self._clean_html(t2) or ("第%s集" % nid)
                eps2.append((sid, nid, name))
            if not eps2:
                continue
            name = chips[k] if k < len(chips) and chips[k].strip() else ("线路%s" % (k + 1))
            ep_list = []
            for sid, nid, ep_name in sorted(eps2, key=lambda x: int(x[1])):
                ep_list.append({"name": ep_name, "link": "%s-%s-%s" % (vod_id, sid, nid)})
            if ep_list:
                sources.append({"source_name": self._clean_html(name), "episodes": ep_list})
        return sources

    # ==================== 播放地址解析（双层解密） ====================
    def _extract_player_url(self, vod_id, sid, nid):
        """播放页 player_aaaa(encrypt=2) → base64decode → unescape → hex"""
        url = "%s/vodplay/%s-%s-%s.html" % (self.base_url, vod_id, sid, nid)
        html = self._get(url, headers=dict(self.headers, Referer="%s/voddetail/%s.html" % (self.base_url, vod_id)))
        if not html:
            return ""
        m = re.search(r'player_aaaa=(\{.*?\})\s*</script>', html, re.DOTALL)
        if not m:
            m = re.search(r'player_aaaa=(\{.*?\})\s*;', html, re.DOTALL)
        if not m:
            return ""
        try:
            data = json.loads(m.group(1).strip())
        except Exception as e:
            self._log("player_aaaa 解析失败: %s" % e)
            return ""
        raw = data.get("url", "") or ""
        enc = str(data.get("encrypt", "0"))
        try:
            if enc == "2":
                pad = (4 - len(raw) % 4) % 4
                dec = base64.b64decode(raw + "=" * pad).decode("utf-8", "ignore")
                from urllib.parse import unquote
                return unquote(dec)
            if enc == "1":
                from urllib.parse import unquote
                return unquote(raw)
            return raw
        except Exception as e:
            self._log("播放地址解码失败: %s" % e)
            return ""

    def _resolve_play_url(self, vod_id, sid, nid):
        cache_key = "%s-%s-%s" % (vod_id, sid, nid)
        now = time.time()
        if cache_key in self._play_cache:
            url, ts = self._play_cache[cache_key]
            if now - ts < self._cache_ttl:
                return url
        hexs = self._extract_player_url(vod_id, sid, nid)
        if not hexs:
            self._log("未取到 hex（%s）" % cache_key)
            return ""
        # 解析器页面 → config
        phtml = self._get("%s/?url=%s" % (self.parser_url, hexs),
                          headers={"User-Agent": self.headers["User-Agent"],
                                   "Referer": self.parser_url + "/"})
        if not phtml:
            self._log("解析器页面请求失败")
            return ""
        cm = re.search(r'var config = (\{.*?\});', phtml, re.DOTALL)
        if not cm:
            self._log("未找到解析器 config")
            return ""
        try:
            cfg = json.loads(cm.group(1))
        except Exception as e:
            self._log("config 解析失败: %s" % e)
            return ""
        # api.php
        try:
            resp = self.fetch("%s/api.php" % self.parser_url,
                              headers={"User-Agent": self.headers["User-Agent"],
                                       "Referer": self.parser_url + "/",
                                       "Content-Type": "application/x-www-form-urlencoded",
                                       "X-Requested-With": "XMLHttpRequest"},
                              method="post",
                              data={"url": cfg.get("url", ""), "time": cfg.get("time", ""),
                                    "key": cfg.get("key", "")},
                              timeout=25)
            j = resp.json()
        except Exception as e:
            self._log("解析接口异常: %s" % e)
            return ""
        if str(j.get("code")) != "200":
            self._log("解析失败: %s" % str(j)[:120])
            return ""
        ct = (j.get("url") or "").strip()
        if not ct:
            return ""
        try:
            raw = base64.b64decode(ct)
            pt = _aes_cbc_decrypt(raw, self.AES_KEY, self.AES_IV).decode("utf-8", "ignore").strip()
        except Exception as e:
            self._log("AES 解密失败: %s" % e)
            return ""
        if pt.startswith("http"):
            self._log("播放直链: %s" % pt[:90])
            self._play_cache[cache_key] = (pt, now)
            return pt
        return ""

    # ==================== TVBox 核心方法 ====================
    def init(self, extend=''):
        self._log("初始化完成")

    def homeContent(self, filter=False):
        return {
            "class": [
                {"type_id": tid, "type_name": name}
                for tid, name in self.CATEGORY_NAMES.items()
            ]
        }

    def homeVideoContent(self):
        try:
            html = self._get(self.base_url)
            if not html:
                return {"list": []}
            videos = self._parse_video_list(html)
            return {"list": videos[:30]}
        except Exception as e:
            self._log("homeVideoContent异常: %s" % e)
            return {"list": []}

    def categoryContent(self, tid, pg, filter=False, content=None):
        try:
            pg = max(1, int(pg or 1))
            if str(tid) not in self.CATEGORY_NAMES:
                return {"list": [], "page": pg, "pagecount": 1, "limit": 60, "total": 0}
            # vodtype 无有效分页，仅在首页返回
            if pg > 1:
                return {"list": [], "page": pg, "pagecount": 1, "limit": 60, "total": 0}
            url = "%s/vodtype/%s.html" % (self.base_url, tid)
            self._log("分类请求: " + url)
            html = self._get(url)
            if not html:
                return {"list": [], "page": pg, "pagecount": 1, "limit": 60, "total": 0}
            videos = self._parse_video_list(html)
            return {
                "list": videos,
                "page": pg,
                "pagecount": 1,
                "limit": 60,
                "total": len(videos),
            }
        except Exception as e:
            self._log("categoryContent异常: %s" % e)
            return {"list": [], "page": pg, "pagecount": 1, "limit": 60, "total": 0}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            try:
                pg = max(1, int(pg or 1))
            except (TypeError, ValueError):
                pg = 1
            keyword = str(key or "").strip()
            if not keyword:
                return {"page": pg, "pagecount": 1, "limit": 0, "total": 0, "list": []}
            url = "%s/index.php/ajax/suggest?mid=1&wd=%s" % (self.base_url, quote(keyword))
            self._log("搜索请求: %s" % url)
            html = self._get(url)
            videos = []
            if html:
                try:
                    j = json.loads(html)
                    for it in (j.get("list") or []):
                        videos.append({
                            "vod_id": str(it.get("id")),
                            "vod_name": it.get("name", "") or "",
                            "vod_pic": self._fix_pic(it.get("pic", "") or ""),
                            "vod_remarks": "",
                        })
                except Exception as e:
                    self._log("搜索解析失败: %s" % e)
            return {
                "list": videos,
                "page": pg,
                "pagecount": 9999,
                "limit": 20,
                "total": 999999,
            }
        except Exception as e:
            self._log("searchContent异常: %s" % e)
            return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        try:
            vod_id = ids[0] if isinstance(ids, list) else str(ids)
            url = "%s/voddetail/%s.html" % (self.base_url, vod_id)
            self._log("详情请求: " + url)
            html = self._get(url)
            if not html:
                return {"list": []}

            vod_name = ""
            tm = re.search(r'<h1[^>]*>([^<]*)</h1>', html)
            if tm:
                vod_name = self._clean_html(tm.group(1))
            if not vod_name:
                tm = re.search(r'<title>([^<]*)</title>', html)
                if tm:
                    vod_name = self._clean_html(tm.group(1).split("-")[0])
            vod_pic = ""
            pm = re.search(r'<img[^>]*(?:data-original|data-src|src)="([^"]+)"[^>]*alt="[^"]*"', html)
            if pm:
                vod_pic = self._fix_pic(pm.group(1))
            vod_content = ""
            dm = re.search(r'<div class="module-info-introduction-content">(.*?)</div>', html, re.DOTALL)
            if dm:
                vod_content = self._clean_html(dm.group(1))
            vod_remarks = ""
            rm = re.search(r'class="module-info-tag[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
            if rm:
                vod_remarks = self._clean_html(rm.group(1))

            sources = self._parse_play_sources(html, vod_id)
            if not sources:
                self._log("未能解析到播放源")
                return {"list": []}

            from_list = []
            url_list = []
            for src in sources:
                from_list.append(src["source_name"])
                url_list.append("#".join(
                    "%s$%s" % (ep["name"], ep["link"]) for ep in src["episodes"]))

            video = {
                "vod_id": vod_id,
                "vod_name": vod_name or "未知",
                "vod_pic": vod_pic,
                "vod_content": vod_content,
                "vod_remarks": vod_remarks,
                "vod_play_from": "$$$".join(from_list),
                "vod_play_url": "$$$".join(url_list),
            }
            self._log("详情解析成功: %s 线路: %s" % (video["vod_name"], "$$$".join(from_list)))
            return {"list": [video]}
        except Exception as e:
            self._log("detailContent异常: %s" % e)
            return {"list": []}

    def playerContent(self, flag, id, vipFlags=None):
        try:
            parts = str(id).split("-")
            if len(parts) < 3:
                return {"parse": 0, "url": "", "header": ""}
            vod_id, sid, nid = parts[0], parts[1], parts[2]
            play_url = self._resolve_play_url(vod_id, sid, nid)
            if not play_url:
                return {"parse": 0, "url": "", "header": ""}
            return {"parse": 0, "url": play_url, "header": self.play_headers.copy()}
        except Exception as e:
            self._log("playerContent异常: %s" % e)
            return {"parse": 0, "url": "", "header": ""}

    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    def localProxy(self, param):
        pass
