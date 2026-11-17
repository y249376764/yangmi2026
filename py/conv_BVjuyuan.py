# -*- coding: utf-8 -*-
# BV剧院 · 蜘蛛🕷️ py 源
# 由「BV剧院」小程序 v8 完整转换：私有签名接口 -> PythonHiker Spider
# 原小程序：HOST/PFX/SKEY/DEV + MD5(payload) -> SHA1 签名头 t/sign/deviceId

import json
import time
import hashlib
import re

HOST = 'https://m.y2s52n7.com'
PFX = '/mw-movie'
SKEY = 'cb808529bae6b6be45ecfab29a4889bc'
DEV = '9f2c1a7b4d8e6c0a5b3d1e9f7a2c4b6d'
UA = 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
MAIN = [('电影', '1'), ('电视剧', '2'), ('综艺', '3'), ('动漫', '4'), ('短剧', '88')]


def _enc(s):
    """与 JS encodeURIComponent 等价"""
    try:
        from urllib.parse import quote as _q
        return _q(str(s), safe="!'()*-._~")
    except Exception:
        return str(s)


def _http(url, headers):
    """三级取网页：requests -> urllib -> 宿主注入 fetch"""
    try:
        import requests
        r = requests.get(url, headers=headers, timeout=15)
        if r is not None:
            return r.text if hasattr(r, 'text') else str(r)
    except Exception:
        pass
    try:
        from urllib.request import Request, urlopen
        req = Request(url, headers=headers)
        with urlopen(req, timeout=15) as f:
            return f.read().decode('utf-8', 'ignore')
    except Exception:
        pass
    try:
        r = fetch(url, {'headers': headers})  # noqa: F821
        if isinstance(r, dict):
            r = r.get('body') or r.get('text') or ''
        return str(r or '')
    except Exception:
        pass
    return ''


def _qstr(p):
    ks = sorted([k for k in p if p[k] is not None and p[k] != ''])
    raw = '&'.join('%s=%s' % (k, p[k]) for k in ks)
    enc = '&'.join('%s=%s' % (k, _enc(p[k])) for k in ks)
    return raw, enc


def _api(path, p=None):
    """与小程序 api() 逐字对齐：payload=排序裸参 + key + t；sign=SHA1(MD5(payload).hex)"""
    p = p or {}
    raw, enc = _qstr(p)
    t = str(int(time.time() * 1000))
    payload = (raw + '&' if raw else '') + 'key=' + SKEY + '&t=' + t
    md5hex = hashlib.md5(payload.encode('utf-8')).hexdigest()
    sign = hashlib.sha1(md5hex.encode('ascii')).hexdigest()
    url = HOST + PFX + path + ('?' + enc if enc else '')
    hd = {'User-Agent': UA, 't': t, 'sign': sign, 'deviceId': DEV, 'authorization': ''}
    body = ''
    for _i in range(3):
        body = _http(url, hd)
        if body:
            break
    if not body:
        return None
    try:
        o = json.loads(body)
        if o and o.get('code') and o['code'] != 200:
            return None
        return o.get('data') if o else None
    except Exception:
        return None


def _pic(u):
    return (str(u) + '@Referer=' + HOST + '/') if u else ''


def _dsc(it):
    a = []
    for k in ('vodClass', 'vodArea'):
        if it.get(k):
            a.append(str(it[k]))
    if it.get('vodScore'):
        a.append('评分' + str(it['vodScore']))
    if it.get('vodRemarks'):
        a.append(str(it['vodRemarks']))
    elif it.get('vodSerial'):
        a.append('更新至' + str(it['vodSerial']))
    return ' · '.join(a)


def _vod(it):
    return {
        'vod_id': str(it.get('vodId') or ''),
        'vod_name': str(it.get('vodName') or ''),
        'vod_pic': _pic(it.get('vodPic')),
        'vod_remarks': _dsc(it),
    }


def _list(data):
    return [_vod(x) for x in (data.get('list') or []) if x and x.get('vodId')]


class Spider(object):
    def __init__(self):
        self._cls = None

    def init(self, extend=""):
        return ""

    def getName(self):
        return "BV剧院"

    def _classes(self):
        # 只保留 5 个一级分类，不做二级展开（弹窗里一排就够，清爽）。
        # type_id = 主类|0 → categoryContent 解析成「该大类全部」，翻页正常。
        if self._cls is not None:
            return self._cls
        out = []
        for nm, v in MAIN:
            out.append({'type_id': v + '|0', 'type_name': nm})
        self._cls = out
        return out

    def homeContent(self, filter):
        cl = self._classes()
        data = _api('/anonymous/video/list', {'type1': '1', 'type': '', 'pageNum': '1', 'pageSize': '24'}) or {}
        return {'class': cl, 'list': _list(data)}

    def categoryContent(self, tid, pg, filter, extend):
        parts = str(tid or '1|0').split('|')
        t1 = parts[0] or '1'
        t2 = parts[1] if len(parts) > 1 else ''
        if t2 == '0':
            t2 = ''
        data = _api('/anonymous/video/list', {'type1': t1, 'type': t2, 'pageNum': str(pg), 'pageSize': '24'}) or {}
        lst = _list(data)
        try:
            total = int(data.get('total') or 0)
        except Exception:
            total = 0
        try:
            pages = int(data.get('pages') or data.get('pageCount') or 0)
        except Exception:
            pages = 0
        return {'list': lst, 'page': int(pg), 'pagecount': pages or (999 if lst else 1),
                'limit': 24, 'total': total or len(lst)}

    def searchContent(self, key, quick, pg):
        data = _api('/anonymous/video/searchByWordPageable',
                    {'keyword': str(key or ''), 'pageNum': str(pg), 'pageSize': '20'}) or {}
        return {'list': _list(data), 'page': int(pg)}

    def detailContent(self, array):
        if isinstance(array, (str, bytes)):
            ids = [str(array)]
        else:
            try:
                ids = [str(x) for x in array]
            except Exception:
                ids = [str(array)]
        vid = ids[0] if ids else ''
        info = _api('/anonymous/video/detail', {'id': vid}) or {}
        eps = info.get('episodeList') or []
        urls = []
        for j, ep in enumerate(eps):
            try:
                name = str(ep.get('name') or '')
                nid = str(ep.get('nid') or '')
            except Exception:
                continue
            num = re.sub(r'[^0-9]', '', name) or str(j + 1)
            urls.append('%s$%s|%s' % (num, vid, nid))
        return {'list': [{
            'vod_id': vid,
            'vod_name': str(info.get('vodName') or ''),
            'vod_pic': _pic(info.get('vodPic')),
            'type_name': str(info.get('vodClass') or ''),
            'vod_year': str(info.get('vodYear') or ''),
            'vod_area': str(info.get('vodArea') or ''),
            'vod_remarks': str(info.get('vodRemarks') or ''),
            'vod_score': str(info.get('vodScore') or ''),
            'vod_content': str(info.get('vodContent') or info.get('vodBlurb') or ''),
            'vod_play_from': 'BV剧院',
            'vod_play_url': '#'.join(urls),
        }]}

    def playerContent(self, flag, ep, vipFlags):
        s = str(ep or '')
        if '|' in s:
            vid, nid = s.split('|', 1)
        else:
            vid, nid = '', s
        data = _api('/anonymous/v2/video/episode/url',
                    {'id': vid, 'nid': nid, 'clientType': '1'}) or {}
        lst = data.get('list') or []
        best, br = None, -1
        for it in lst:
            if not isinstance(it, dict) or not it.get('url'):
                continue
            try:
                r = int(it.get('resolution') or 0)
            except Exception:
                r = 0
            if r > br:
                br, best = r, it
        if best is None:
            return {'parse': 0, 'url': '', 'header': {}}
        return {'parse': 0, 'url': str(best['url']),
                'header': {'User-Agent': UA, 'Referer': HOST + '/'}}
