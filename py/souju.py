#!/usr/bin/python
# coding: utf-8
# 搜剧AI 蜘蛛版 (WebHomeTV 通用 CSP 注入)
# 31 域名自动切换: souju.ai + bpz1-10.app + bpz1-10.top + baipaizhe1-10.com
# API 签名: HMAC-SHA256(SJ_KEY, method + "\n" + path+search + "\n" + ts + "\n" + nonce)
import base64
import hashlib
import hmac
import json
import random
import re
import sys
import time
from html import unescape
from urllib.parse import quote, unquote, urlparse

import requests

requests.packages.urllib3.disable_warnings()

try:
    sys.path.append('..')
    from base.spider import Spider
except Exception:
    class Spider(object):
        pass


class Spider(Spider):

    def __init__(self):
        super().__init__()
        self.name = '搜剧AI'
        self.host = 'https://souju.ai'
        self.SJ_KEY = 'f39d73aa7a6426203cdee1ef17b31d3b7ea8c23f4c59c62a3a8aa0f39ee5e79d'
        self.SESSION_POOL = [
            'ums_OSQd6yDhgyoZ4CdQaBVqS_ulNzoeradwzH7ny-MHL0M',
            'ums_-7nG5U8bTHGI5cbaB3g6rgrKRFtebxo3tWEoyb1agR4',
            'ums_aO6E4gSdryo6HcKxdLIzFUlFoPIgwMu41-4RhSbKsQU',
        ]
        self.session_idx = 0
        self.SESSION = self.SESSION_POOL[0]
        self.SJ_DOMAINS = [
            'https://souju.ai',
            'https://bpz1.app', 'https://bpz2.app', 'https://bpz3.app',
            'https://bpz4.app', 'https://bpz5.app', 'https://bpz6.app',
            'https://bpz7.app', 'https://bpz8.app', 'https://bpz9.app',
            'https://bpz10.app',
            'https://bpz1.top', 'https://bpz2.top', 'https://bpz3.top',
            'https://bpz4.top', 'https://bpz5.top', 'https://bpz6.top',
            'https://bpz7.top', 'https://bpz8.top', 'https://bpz9.top',
            'https://bpz10.top',
        ]
        for bi in range(1, 11):
            self.SJ_DOMAINS.append('https://baipaizhe%d.com' % bi)
        self.cur_host = self.SJ_DOMAINS[0]
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Linux; Android 13; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36',
            'x-ai-movie-client-name': 'movie-search-frontend',
            'x-ai-movie-client-version': '1.0.0',
            'x-ai-movie-build-version': 'aimovie-v2026.09.22.2-4570aa027fc4-web',
            'x-ai-movie-protocol-version': '2026-07-05.library-v2.playback-v1',
            'Cookie': 'ai_movie_session=',
        })
        self.SESSION = ''
        self.classes = []

    # ============ 签名 ============
    def _sign_path(self, url, host_old):
        qi = url.find('?')
        path = url[:qi] if qi >= 0 else url
        search = url[qi:] if qi >= 0 else ''
        if path.startswith(host_old):
            path = path[len(host_old):]
        if path.startswith('http'):
            sl2 = path.find('/', 8)
            path = path[sl2:] if sl2 >= 0 else '/'
        return path, search

    def _sig_headers(self, method, url, host):
        ts = str(int(time.time() * 1000))
        nonce = ''.join(random.choice('0123456789abcdef') for _ in range(16))
        path, search = self._sign_path(url, host)
        sig_msg = '%s\n%s%s\n%s\n%s' % (method, path, search, ts, nonce)
        sig = hmac.new(self.SJ_KEY.encode(), sig_msg.encode(), hashlib.sha256).hexdigest()
        return {
            'x-ai-movie-timestamp': ts,
            'x-ai-movie-nonce': nonce,
            'x-ai-movie-signature': sig,
            'x-ai-movie-client-name': 'movie-search-frontend',
            'x-ai-movie-client-version': '1.0.0',
            'x-ai-movie-build-version': 'aimovie-v2026.09.22.2-4570aa027fc4-web',
            'x-ai-movie-protocol-version': '2026-07-05.library-v2.playback-v1',
            'x-ai-movie-site-host': host.replace('https://', ''),
            'Cookie': 'ai_movie_session=' + self.SESSION,
            'User-Agent': self.session.headers['User-Agent'],
        }

    def _rewrite(self, url, host_old, h2):
        if url.startswith(host_old):
            return h2 + url[len(host_old):]
        if url.startswith('https://'):
            slash = url.find('/', 8)
            return h2 + (url[slash:] if slash >= 0 else '/')
        return url

    # ============ 请求 (域名失效自动切换) ============
    def sj_get(self, url, host_old=None):
        if host_old is None:
            host_old = self.cur_host
        last_err = ''
        hosts = [self.cur_host] + [h for h in self.SJ_DOMAINS if h != self.cur_host]
        for h2 in hosts:
            try:
                url2 = self._rewrite(url, host_old, h2)
                headers = self._sig_headers('GET', url2, h2)
                resp = self.session.get(url2, headers=headers, timeout=15, verify=False)
                if resp.status_code != 200 or not resp.text:
                    last_err = 'empty/%s' % resp.status_code
                    continue
                self.cur_host = h2
                return resp.text
            except Exception as e3:
                last_err = str(e3)
        # 全部域名失败: 轮换 session 再试一次
        if last_err:
            self.session_idx = (self.session_idx + 1) % len(self.SESSION_POOL)
            self.SESSION = self.SESSION_POOL[self.session_idx]
            for h2 in hosts:
                try:
                    url2 = self._rewrite(url, host_old, h2)
                    headers = self._sig_headers('GET', url2, h2)
                    resp = self.session.get(url2, headers=headers, timeout=15, verify=False)
                    if resp.status_code == 200 and resp.text:
                        self.cur_host = h2
                        return resp.text
                except Exception:
                    pass
        return None

    # ============ 分类 ============
    def _load_classes(self):
        try:
            s = self.sj_get(self.cur_host + '/v1/feed/home?scope=public&mode=preview&sections=11&cards=10')
            if not s:
                return []
            sj = json.loads(s)
            secs = sj.get('sections') or []
            arr = []
            for sec in secs:
                title = sec.get('title') or ''
                if not title:
                    continue
                cid = sec.get('id') or title
                arr.append({'type_id': str(cid), 'type_name': title})
            return arr
        except Exception as e:
            print('[搜剧AI] 分类加载失败: %s' % e)
            return []

    # ============ 首页 ============
    def homeContent(self, filter=False):
        result = {'class': self.classes}
        if filter:
            result['filters'] = {}
        try:
            s = self.sj_get(self.cur_host + '/v1/feed/home?scope=public&mode=preview&sections=11&cards=10')
            if s:
                sj = json.loads(s)
                secs = sj.get('sections') or []
                arr = []
                if not self.classes:
                    self.classes = self._load_classes()
                    result['class'] = self.classes
                for sec in secs:
                    title = sec.get('title') or ''
                    cards = sec.get('cards') or []
                    for c in cards:
                        av = c.get('id') or ''
                        if not av.startswith('av_'):
                            continue
                        name = c.get('title') or '影片'
                        pic = c.get('poster_url') or c.get('cover_url') or ''
                        remark = ''
                        try:
                            remark = c.get('year') or ''
                        except Exception:
                            pass
                        arr.append(self._entry(av, name, pic, remark))
                        if len(arr) >= 60:
                            break
                result['list'] = arr
            else:
                result['list'] = []
        except Exception as e:
            print('[搜剧AI] 首页失败: %s' % e)
            result['list'] = []
        return result

    def homeVideoContent(self):
        try:
            return {'list': self.homeContent(False).get('list', [])[:40]}
        except Exception as e:
            print('[搜剧AI] 首页推荐失败: %s' % e)
            return {'list': []}

    # ============ 分类内容 ============
    def categoryContent(self, tid, pg, filter=False, extend=False):
        pg = int(pg or 1)
        try:
            url = '%s/v1/browse/catalog?q=%s&limit=20&page=%d' % (self.cur_host, quote(str(tid)), pg)
            s = self.sj_get(url)
            if not s:
                return {'list': [], 'page': pg, 'pagecount': pg}
            sj = json.loads(s)
            cards = sj.get('cards') or []
            arr = []
            seen = set()
            for cd in cards:
                av = cd.get('selected_variant_id') or cd.get('default_variant_id') or ''
                if not av.startswith('av_'):
                    continue
                if av in seen:
                    continue
                seen.add(av)
                name = cd.get('title') or '影片'
                pic = cd.get('poster_url') or cd.get('cover_url') or ''
                remark = ''
                try:
                    seasons = cd.get('seasons') or []
                    if seasons:
                        remark = '%d季' % len(seasons)
                except Exception:
                    pass
                arr.append(self._entry(av, name, pic, remark))
            return {'list': arr, 'page': pg, 'pagecount': pg + 1 if arr else pg}
        except Exception as e:
            print('[搜剧AI] 分类失败: %s' % e)
            return {'list': [], 'page': pg, 'pagecount': pg}

    # ============ 搜索 ============
    def searchContent(self, key, quick=False, pg=1):
        pg = int(pg or 1)
        try:
            pu = unquote(key)
            s = self.sj_get(self.cur_host + '/v1/suggest?q=' + quote(pu) + '&limit=20&mode=thread')
            if not s:
                return {'list': [], 'page': pg, 'pagecount': pg}
            sj = json.loads(s)
            sugs = sj.get('suggestions') or []
            arr = []
            seen = set()
            for si, su in enumerate(sugs):
                tg = su.get('target') or {}
                av = tg.get('variant_id') or ''
                if not av.startswith('av_'):
                    continue
                if av in seen:
                    continue
                seen.add(av)
                name = su.get('label') or ('影片%d' % (si + 1))
                pic = ''
                try:
                    pic = tg.get('poster_url') or ''
                except Exception:
                    pass
                arr.append(self._entry(av, name, pic, ''))
            return {'list': arr, 'page': pg, 'pagecount': pg + 1 if arr else pg}
        except Exception as e:
            print('[搜剧AI] 搜索失败: %s' % e)
            return {'list': [], 'page': pg, 'pagecount': pg}

    # ============ 详情 ============
    def detailContent(self, ids):
        try:
            av = ids[0] if isinstance(ids, list) else ids
            av = unquote(av)
            s = self.sj_get(self.cur_host + '/v1/catalog/' + quote(av))
            if not s:
                return {'list': []}
            sj = json.loads(s)
            eps = []
            try:
                es = self.sj_get(self.cur_host + '/v1/catalog/' + quote(av) + '/episodes?limit=100&offset=0')
                if es:
                    ej = json.loads(es)
                    eps = ej.get('episodes') or []
            except Exception:
                pass
            name = sj.get('title') or sj.get('name') or av
            pic = sj.get('poster_url') or sj.get('cover_url') or ''
            year = sj.get('year') or ''
            area = sj.get('region') or sj.get('area') or ''
            actor = sj.get('cast') or sj.get('actors') or ''
            content = sj.get('description') or sj.get('intro') or ''
            play_from = '搜剧AI'
            play_url = ''
            eps_list = []
            for ei, ep in enumerate(eps):
                ep_id = ep.get('token') or ep.get('id') or ep.get('variant_id') or ''
                ep_name = ep.get('title') or ep.get('name') or ('第%d集' % (ei + 1))
                if ep_id:
                    eps_list.append('%s$%s' % (ep_name, ep_id))
            if eps_list:
                play_url = '#'.join(eps_list)
            vod = {
                'vod_id': av,
                'vod_name': name,
                'vod_pic': pic,
                'vod_year': str(year),
                'vod_area': area,
                'vod_actor': actor,
                'vod_content': content,
                'vod_play_from': play_from,
                'vod_play_url': play_url,
            }
            return {'list': [vod]}
        except Exception as e:
            print('[搜剧AI] 详情失败: %s' % e)
            return {'list': []}

    # ============ 播放 ============
    def playerContent(self, flag, id, vipFlags=None):
        try:
            token = unquote(id)
            if token.startswith('http://') or token.startswith('https://'):
                return {'url': token, 'header': {'User-Agent': self.session.headers['User-Agent']}}
            s = self.sj_get(self.cur_host + '/v1/playback/resolve/' + quote(token))
            if not s:
                return {'url': 'toast://播放失败,未获取到播放地址'}
            sj = json.loads(s)
            lines = sj.get('line_options') or []
            bad_hosts = ['v.qq.com', 'qq.com', 'iqiyi.com', 'youku.com', 'mgtv.com',
                         'bilibili.com', 'sohu.com', 'pptv.com', 'le.com', '1905.com', 'acfun.cn']
            for ln in lines:
                u = str(ln.get('url') or '').strip()
                kind = str(ln.get('url_kind') or '')
                if kind == 'm3u8' and u.startswith('http'):
                    skip = False
                    for bh in bad_hosts:
                        if bh in u:
                            skip = True
                            break
                    if not skip:
                        return {'url': u, 'header': {'User-Agent': self.session.headers['User-Agent'], 'Referer': self.cur_host + '/'}}
            for ln in lines:
                u = str(ln.get('url') or '').strip()
                kind = str(ln.get('url_kind') or '')
                if kind == 'resolve_ticket' and u.startswith('resolve://'):
                    line_id = u[len('resolve://'):].strip()
                    if line_id:
                        r2 = self.sj_get(self.cur_host + '/v1/playback/resolve/' + quote(line_id))
                        if r2:
                            try:
                                rj = json.loads(r2)
                                for ln2 in rj.get('line_options') or []:
                                    u2 = str(ln2.get('url') or '').strip()
                                    if u2.startswith('http'):
                                        return {'url': u2, 'header': {'User-Agent': self.session.headers['User-Agent'], 'Referer': self.cur_host + '/'}}
                            except Exception:
                                pass
            return {'url': 'toast://未找到可播放线路'}
        except Exception as e:
            print('[搜剧AI] 播放失败: %s' % e)
            return {'url': 'toast://播放失败:%s' % e}

    # ============ 工具 ============
    def _entry(self, vod_id, name, pic, remark='', desc=''):
        return {
            'vod_id': str(vod_id),
            'vod_name': str(name),
            'vod_pic': pic or '',
            'vod_remarks': str(remark),
        }

    def init(self):
        self.classes = self._load_classes()
        return ''

    def destroy(self):
        try:
            self.session.close()
        except Exception:
            pass
        return ''
