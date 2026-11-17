# -*- coding: utf-8 -*-
# 多多影视 · 蜘蛛🕷️ py 源
# 由「多多影视」小程序 v20261101 转换：接口/签名/解码常量逐字对齐，
# 播放链路改为 Python 原生 protobuf + SHA-256，不依赖 WebView 解码页。

import json
import re
import time
import hashlib

try:
    from urllib.parse import quote as _quote
except ImportError:
    from urllib import quote as _quote

HOSTS = [
    'https://dduotv01.top',
    'https://323433ssdfd.top',
    'https://duoduosdf12223234334.top',
    'https://xds2435u23422342342u.top',
]
HOST = HOSTS[0]
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
XCLIENT = '8f3d2a1c7b6e5d4c9a0b1f2e3d4c5b6a'
WEBSIGN = 'ddtvf65f3a83d6d9ad6f'

FINGER = 'WF-2c064bc5b3400788f31b848849bc3a60f835423ba2dfe69d7ea93974c216e4f2'
SK = 'WEB-50a8e9c84a1dc05669a692ded99a2dac46527229e607a7be15db88dbc59059d1'
NONCE = '00000000000000000000000000000000'
PLAYER_ID = 'com.web.player'

TYPES = [('1', '电影'), ('2', '剧集'), ('3', '综艺'), ('4', '动漫')]
SORTS = ('hot', 'time', 'score')


def _enc(s):
    try:
        return _quote(str(s), safe="!'()*-._~")
    except Exception:
        return str(s)


def _hd(route, post=False):
    h = {
        'User-Agent': UA,
        'Referer': HOST + (route or '/'),
        'Accept': 'application/json',
        'X-Client': XCLIENT,
        'web-sign': WEBSIGN,
    }
    if post:
        h['Content-Type'] = 'text/plain'
    return h


def _raw(url, headers, data=None, timeout=12):
    """三级取数据：requests -> urllib -> 宿主注入 fetch；返回 bytes。"""
    try:
        import requests
        if data is None:
            r = requests.get(url, headers=headers, timeout=timeout)
        else:
            r = requests.post(url, data=data, headers=headers, timeout=timeout)
        if r is not None:
            b = r.content if hasattr(r, 'content') else str(r).encode('utf-8', 'ignore')
            if b:
                return b
    except Exception:
        pass
    try:
        try:
            from urllib.request import Request, urlopen
        except ImportError:
            from urllib2 import Request, urlopen
        req = Request(url, data=data, headers=headers)
        resp = urlopen(req, timeout=timeout)
        b = resp.read()
        try:
            resp.close()
        except Exception:
            pass
        if b:
            return b
    except Exception:
        pass
    if data is None:
        try:
            r = fetch(url, {'headers': headers, 'timeout': timeout * 1000})  # noqa: F821
            if isinstance(r, dict):
                r = r.get('body') or r.get('text') or ''
            if r:
                return str(r).encode('utf-8', 'ignore')
        except Exception:
            pass
    return b''


def _api(path, route):
    """与原 hs.js apiGet 同口径：网络层失败换镜像，业务错误直接返回。"""
    for h in HOSTS:
        try:
            b = _raw(h + path, _hd(route))
            if not b:
                continue
            j = json.loads(b.decode('utf-8', 'ignore'))
            if not isinstance(j, dict):
                continue
            if j.get('code') != 200:
                return None
            return j
        except Exception:
            continue
    return None


# ---------- 卡片 ----------

def _pic(u):
    s = str(u or '').strip().replace('\\/', '/')
    if not s:
        return ''
    if s.startswith('//'):
        return 'https:' + s
    if not re.match(r'^https?://', s, re.I):
        return HOST + ('' if s.startswith('/') else '/') + s
    return s


def _remark(v):
    m = []
    if v.get('vod_remarks'):
        m.append(str(v['vod_remarks']))
    if v.get('vod_douban_score') and str(v['vod_douban_score']) != '0.0':
        m.append('★' + str(v['vod_douban_score']))
    if not m and v.get('vod_year'):
        m.append(str(v['vod_year']))
    return ' '.join(m)


def _card(v):
    return {
        'vod_id': str(v.get('vod_id') or ''),
        'vod_name': str(v.get('vod_name') or ''),
        'vod_pic': _pic(v.get('vod_pic')),
        'vod_remarks': _remark(v),
        'vod_year': str(v.get('vod_year') or ''),
        'vod_area': str(v.get('vod_area') or ''),
        'type_name': str(v.get('vod_class') or ''),
    }


def _cards(arr):
    out = []
    for v in (arr or []):
        if isinstance(v, dict) and v.get('vod_id') and v.get('vod_name'):
            out.append(_card(v))
    return out


def _list_of(j):
    if not isinstance(j, dict):
        return []
    d = j.get('data') or []
    return _cards(d if isinstance(d, list) else [])


def _lines(j):
    """拆 $$$线路 / #集 / $名与地址；与原 dduoLines 一致。"""
    data = (j.get('data') or []) if isinstance(j, dict) else []
    v = data[0] if data and isinstance(data[0], dict) else {}
    froms = str(v.get('vod_play_from') or '').split('$$$')
    urls = str(v.get('vod_play_url') or '').split('$$$')
    out = []
    for i, fk in enumerate(froms):
        fk = str(fk).strip()
        if not fk:
            continue
        raw = str(urls[i]) if i < len(urls) else ''
        eps = []
        for seg in raw.split('#'):
            p = seg.split('$')
            if len(p) >= 2 and p[1]:
                eps.append((str(p[0] or ('第%d集' % (len(eps) + 1))), str(p[1])))
        if eps:
            out.append({'key': fk, 'eps': eps})
    return v, out


def _ext_lines(nm):
    """站外聚合线路（免解码直连），与原 detail.js 一致，最多 6 条。"""
    out = []
    try:
        aj = _api('/api.php/web/internal/search_aggregate?name=' + _enc(nm), '/')
        axs = (aj.get('data') or []) if isinstance(aj, dict) else []
        for ex in axs:
            if not isinstance(ex, dict) or len(out) >= 6:
                break
            sn = str(ex.get('site_name') or '')
            if not sn.startswith('站外'):
                continue
            eps = []
            for g in str(ex.get('vod_play_url') or '').split('$$$'):
                for seg in g.split('#'):
                    p = seg.split('$')
                    u = str(p[1] if len(p) >= 2 else (p[0] if p else '')).strip()
                    if u:
                        eps.append((str(p[0] or '第%d集' % (len(eps) + 1)), u))
            if eps:
                out.append((sn, eps))
    except Exception:
        pass
    return out


# ---------- protobuf / 解码（对齐 DD_PAGE_JS） ----------

def _pb_varint(n):
    out = bytearray()
    n = int(n)
    while n >= 128:
        out.append((n & 127) | 128)
        n = n // 128
    out.append(n)
    return out


def _pb_bytes(field, b):
    head = bytearray([(field << 3) | 2])
    l = len(b)
    while l >= 128:
        head.append((l & 127) | 128)
        l = l // 128
    head.append(l)
    return head + bytearray(b)


def _pb_str(field, s):
    return _pb_bytes(field, str(s).encode('utf-8', 'ignore'))


def _pb_num(field, n):
    return bytearray([(field << 3) | 0]) + _pb_varint(n)


def _build_req(token, frm):
    t = int(time.time() * 1000)
    sign_src = 'finger=%s&id=%s&nonce=%s&sk=%s&time=%s&v=1' % (
        FINGER, PLAYER_ID, NONCE, SK, str(t))
    sign = hashlib.sha256(sign_src.encode('ascii')).hexdigest().upper()
    b = bytearray()
    b += _pb_str(1, token)
    b += _pb_str(2, frm)
    b += _pb_num(3, t)
    b += _pb_str(4, NONCE)
    b += _pb_str(5, sign)
    b += _pb_str(6, PLAYER_ID)
    b += _pb_num(7, 1)
    return bytes(b)


def _bi(b, p):
    c = b[p]
    return c if isinstance(c, int) else ord(c)


def _parse_resp(b):
    out = {'code': 0, 'msg': '', 'url': ''}
    if not b:
        return out
    n = len(b)
    p = 0
    while p < n:
        tag = _bi(b, p)
        p += 1
        f, w = tag >> 3, tag & 7
        val = 0
        if w == 2:
            l, sh = 0, 0
            while p < n:
                c = _bi(b, p)
                p += 1
                l |= (c & 127) << sh
                if not (c & 128):
                    break
                sh += 7
            raw = b[p:p + l]
            p += l
            try:
                val = bytes(raw).decode('utf-8')
            except Exception:
                val = bytes(raw).decode('latin-1', 'ignore')
        elif w == 0:
            v, sh = 0, 0
            while p < n:
                c = _bi(b, p)
                p += 1
                v |= (c & 127) << sh
                if not (c & 128):
                    break
                sh += 7
            val = v
        else:
            break
        if f == 1:
            try:
                out['code'] = int(val)
            except Exception:
                pass
        elif f == 2:
            out['msg'] = str(val)
        elif f == 3:
            out['url'] = str(val)
    return out


def _decode(cands, max_mirror=4):
    """cands: [(from, token)]；优先当前线路，失败自动切其它线路。"""
    got = {}
    for f, t in cands:
        for h in HOSTS[:max_mirror]:
            try:
                body = _build_req(t, f)
                b = _raw(h + '/api.php/web/decode/url', _hd('/', post=True),
                         data=body, timeout=8)
                o = _parse_resp(b)
                if o['code'] == 1 and o['url'].startswith('http'):
                    got[f] = o['url']
                    if f == cands[0][0]:
                        return o['url']
                    break
            except Exception:
                continue
    for f, t in cands:
        if got.get(f):
            return got[f]
    return ''


class Spider(object):
    def __init__(self):
        self._cls = None

    def init(self, extend=""):
        return ""

    def getName(self):
        return "多多影视"

    def _classes(self):
        if self._cls is None:
            self._cls = [{'type_id': k, 'type_name': n} for k, n in TYPES]
        return self._cls

    def homeContent(self, filter):
        # 首页推荐取「电影·最热」第一页，分类树只给 4 个一级（不展开二级）
        lst = self.categoryContent('1', 1, True, {}).get('list') or []
        return {'class': self._classes(), 'list': lst}

    def homeVideoContent(self):
        return {'list': self.categoryContent('1', 1, True, {}).get('list') or []}

    def categoryContent(self, tid, pg, filter, extend):
        t = str(tid or '1')
        name = ''
        for k, n in TYPES:
            if k == t:
                name = n
                break
        if not name and t in [n for k, n in TYPES]:
            name = t
        ext = {}
        try:
            ext = dict(extend or {})
        except Exception:
            try:
                ext = json.loads(str(extend))
            except Exception:
                ext = {}
        sort = str(ext.get('sort') or 'hot')
        if sort not in SORTS:
            sort = 'hot'
        q = '/api.php/web/filter/vod?page=%s&sort=%s' % (_enc(pg or 1), _enc(sort))
        if name:
            q += '&type_name=' + _enc(name)
        if ext.get('year'):
            q += '&year=' + _enc(ext['year'])
        if ext.get('area'):
            q += '&area=' + _enc(ext['area'])
        j = _api(q, '/type')
        lst = _list_of(j)
        return {'list': lst, 'page': int(pg or 1),
                'pagecount': 999 if lst else 1, 'limit': 21,
                'total': len(lst)}

    def searchContent(self, key, quick, pg):
        q = '/api.php/web/search/index?wd=%s&page=%s&limit=15' % (
            _enc(key or ''), _enc(pg or 1))
        j = _api(q, '/search')
        return {'list': _list_of(j), 'page': int(pg or 1)}

    def detailContent(self, array):
        if isinstance(array, (str, bytes)):
            ids = [str(array)]
        else:
            try:
                ids = [str(x) for x in array]
            except Exception:
                ids = [str(array)]
        vid = ids[0] if ids else ''
        j = _api('/api.php/web/vod/get_detail?vod_id=' + _enc(vid), '/detail')
        v, lines = _lines(j)
        froms, groups = [], []
        for ln in lines:
            froms.append(ln['key'])
            parts = []
            for idx, (nm, u) in enumerate(ln['eps'], 1):
                # 解码线路的 token 追加 |集号|影片ID 供 playerContent 跨线路兜底；
                # 站外直连 m3u8 原样保留，不加后缀。
                if u.startswith('http'):
                    parts.append('%s$%s' % (nm, u))
                else:
                    parts.append('%s$%s|%d|%s' % (nm, u, idx, vid))
            groups.append('#'.join(parts))

        # 站外聚合线路（免解码直连）
        for sn, eps in _ext_lines(str(v.get('vod_name') or '')):
            froms.append(sn)
            groups.append('#'.join('%s$%s' % e for e in eps))

        return {'list': [{
            'vod_id': vid,
            'vod_name': str(v.get('vod_name') or ''),
            'vod_pic': _pic(v.get('vod_pic')),
            'type_name': str(v.get('vod_class') or ''),
            'vod_year': str(v.get('vod_year') or ''),
            'vod_area': str(v.get('vod_area') or ''),
            'vod_remarks': _remark(v),
            'vod_actor': str(v.get('vod_actor') or ''),
            'vod_content': str(v.get('vod_use_content') or v.get('vod_content') or ''),
            'vod_play_from': '$$$'.join(froms),
            'vod_play_url': '$$$'.join(groups),
        }]}

    def playerContent(self, flag, ep, vipFlags):
        s = str(ep or '')
        token, nid, vid = s, 0, ''
        parts = s.split('|')
        if len(parts) >= 3 and parts[-2].isdigit():
            token = '|'.join(parts[:-2])
            nid = int(parts[-2])
            vid = parts[-1]
        if token.startswith('http'):
            return {'parse': 0, 'url': token}

        cur = str(flag or '')
        u = _decode([(cur, token)], 4)
        if u:
            return {'parse': 0, 'url': u}

        # 当前线路解码失败：重拉详情换新 token，按「非 4K 优先」跨线路重试
        direct = ''
        cands = []
        v2 = {}
        try:
            j = _api('/api.php/web/vod/get_detail?vod_id=' + _enc(vid), '/detail')
            v2, lines = _lines(j)
            hd, k4 = [], []
            for ln in lines:
                if not nid or nid > len(ln['eps']):
                    continue
                u2 = ln['eps'][nid - 1][1]
                if u2.startswith('http'):
                    if not direct:
                        direct = u2
                    continue
                if ln['key'] == cur:
                    continue
                (k4 if re.search(r'4K|H[. ]?265|HEVC', ln['key'], re.I) else hd).append(
                    (ln['key'], u2))
            cands = (hd + k4)[:3]
        except Exception:
            pass
        if cands:
            u = _decode(cands, 2)
            if u:
                return {'parse': 0, 'url': u}
        if direct:
            return {'parse': 0, 'url': direct}
        # 最后兜底：站外聚合的免解码直连（转换时新增的一层容错）
        try:
            for sn, eps in _ext_lines(str(v2.get('vod_name') or '')):
                if 0 < nid <= len(eps) and eps[nid - 1][1].startswith('http'):
                    return {'parse': 0, 'url': eps[nid - 1][1]}
        except Exception:
            pass
        return {'parse': 0, 'url': ''}
