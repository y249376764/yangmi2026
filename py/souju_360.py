#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 360影搜 py 蜘蛛 (盒子注入版) - 搜剧AI/看剧AI 多域名官方源
# 搜剧AI: kanju.ai + souju.ai 双域名 HMAC-SHA256 签名, 失败自动切换
# 播放: resolve 返回 m3u8 直链 (红牛/极速/魔都/新浪/1080zyk等资源站官方源), 过滤爱优腾芒B
import json
import re
import time
import random
import hmac
import hashlib
import urllib.parse
from base.spider import Spider

# 模块级全局缓存 (WebHomeTV 每次 new 实例, 但模块常驻 → 登录/session/线路表跨实例复用)
_SJ_G = {'session': '', 'line_cache': {}}

class S(Spider):
    UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)'
    # 360kan 界面接口 (只负责首页推荐 + 分类列表)
    KAN_API = 'https://api.web.360kan.com/v1'
    KAN_SEARCH = 'https://api.so.360kan.com'
    # 搜剧AI 域名 + 签名 key
    SJ_HOSTS = [
        'https://kanju.ai', 'https://souju.ai',
        'https://bpz1.app', 'https://bpz2.app', 'https://bpz3.app',
        'https://bpz4.app', 'https://bpz5.app', 'https://bpz6.app',
        'https://bpz7.app', 'https://bpz8.app', 'https://bpz9.app',
        'https://bpz10.app',
        'https://bpz1.top', 'https://bpz2.top', 'https://bpz3.top',
        'https://bpz4.top', 'https://bpz5.top', 'https://bpz6.top',
        'https://bpz7.top', 'https://bpz8.top', 'https://bpz9.top',
        'https://bpz10.top',
    ]
    SJ_KEY = 'f39d73aa7a6426203cdee1ef17b31d3b7ea8c23f4c59c62a3a8aa0f39ee5e79d'
    KJ_KEY = '557d0e4ae929f438da6bd84412374e6086b8af09b3fed54bf22601d5bf8c54a0'
    # 搜剧AI 登录账号 (v4 完整链路: 登录拿 session 才能解析官方线路)
    SJ_ACCOUNT = '249376764'
    SJ_PASSWORD = '19811012'
    # 过滤的爱优腾芒B等不可播域名
    BAD_HOSTS = ['v.qq.com', 'qq.com', 'iqiyi.com', 'youku.com', 'mgtv.com', 'bilibili.com',
                 'sohu.com', 'pptv.com', 'le.com', '1905.com', 'acfun.cn']
    # 搜剧AI 分类: 电影/电视剧/综艺/动漫
    CLASS = [
        {"type_id": "1", "type_name": "电影"},
        {"type_id": "2", "type_name": "电视剧"},
        {"type_id": "3", "type_name": "综艺"},
        {"type_id": "4", "type_name": "动漫"},
    ]

    # 二级分类筛选 (WebHomeTV 格式: dict 按 type_id 分组)
    # 类型 cat 仅电影(catid=1)生效; 地区 area / 年份 year 全频道生效
    _F_CAT = [{"n": "全部", "v": ""}, {"n": "剧情", "v": "剧情"}, {"n": "喜剧", "v": "喜剧"}, {"n": "动作", "v": "动作"}, {"n": "爱情", "v": "爱情"}, {"n": "科幻", "v": "科幻"}, {"n": "悬疑", "v": "悬疑"}, {"n": "惊悚", "v": "惊悚"}, {"n": "恐怖", "v": "恐怖"}, {"n": "犯罪", "v": "犯罪"}, {"n": "战争", "v": "战争"}, {"n": "历史", "v": "历史"}, {"n": "动画", "v": "动画"}, {"n": "奇幻", "v": "奇幻"}, {"n": "冒险", "v": "冒险"}, {"n": "武侠", "v": "武侠"}, {"n": "古装", "v": "古装"}, {"n": "家庭", "v": "家庭"}, {"n": "传记", "v": "传记"}, {"n": "纪录片", "v": "纪录片"}, {"n": "音乐", "v": "音乐"}, {"n": "歌舞", "v": "歌舞"}, {"n": "儿童", "v": "儿童"}, {"n": "青春", "v": "青春"}, {"n": "运动", "v": "运动"}]
    _F_AREA = [{"n": "全部", "v": ""}, {"n": "大陆", "v": "大陆"}, {"n": "香港", "v": "香港"}, {"n": "台湾", "v": "台湾"}, {"n": "美国", "v": "美国"}, {"n": "日本", "v": "日本"}, {"n": "韩国", "v": "韩国"}, {"n": "英国", "v": "英国"}, {"n": "法国", "v": "法国"}, {"n": "德国", "v": "德国"}, {"n": "印度", "v": "印度"}, {"n": "泰国", "v": "泰国"}, {"n": "其它", "v": "其它"}]
    _F_YEAR = [{"n": "全部", "v": ""}, {"n": "2025", "v": "2025"}, {"n": "2024", "v": "2024"}, {"n": "2023", "v": "2023"}, {"n": "2022", "v": "2022"}, {"n": "2021", "v": "2021"}, {"n": "2020", "v": "2020"}, {"n": "2019", "v": "2019"}, {"n": "2018", "v": "2018"}, {"n": "2017", "v": "2017"}, {"n": "2016", "v": "2016"}, {"n": "2015", "v": "2015"}, {"n": "更早", "v": "更早"}]
    FILTERS = {
        '1': [{"key": "cat", "name": "类型", "value": _F_CAT}, {"key": "area", "name": "地区", "value": _F_AREA}, {"key": "year", "name": "年份", "value": _F_YEAR}],
        '2': [{"key": "area", "name": "地区", "value": _F_AREA}, {"key": "year", "name": "年份", "value": _F_YEAR}],
        '3': [{"key": "area", "name": "地区", "value": _F_AREA}, {"key": "year", "name": "年份", "value": _F_YEAR}],
        '4': [{"key": "area", "name": "地区", "value": _F_AREA}, {"key": "year", "name": "年份", "value": _F_YEAR}],
    }

    def init(self, extend=""):
        # 从模块缓存恢复 session (WebHomeTV 每次 new 实例, 模块级缓存跨实例复用)
        self.SJ_SESSION = _SJ_G.get('session', '')
        pass

    # 搜剧AI 登录: POST /v1/users/password/login → ai_movie_session (v4 完整链路)
    def _sj_login(self):
        if self.SJ_SESSION:
            return True
        # 模块缓存已有 session 直接用
        if _SJ_G.get('session'):
            self.SJ_SESSION = _SJ_G['session']
            return True
        try:
            # 登录只用前2个稳定域名 (session 全域名通用)
            login_hosts = self.SJ_HOSTS[:2]
            for host in login_hosts:
                try:
                    ts = str(int(time.time() * 1000))
                    nonce = ''.join(random.choices('0123456789abcdef', k=16))
                    key = self._sj_key(host)
                    path = '/v1/users/password/login'
                    sig_msg = 'POST\n' + path + '\n' + ts + '\n' + nonce
                    sig = hmac.new(key.encode(), sig_msg.encode('utf-8'), hashlib.sha256).hexdigest()
                    headers = {
                        'x-ai-movie-timestamp': ts,
                        'x-ai-movie-nonce': nonce,
                        'x-ai-movie-signature': sig,
                        'Referer': host + '/',
                        'User-Agent': self.UA,
                        'Accept': 'application/json',
                        'Content-Type': 'application/json',
                        'Origin': host,
                    }
                    body = {"authProtocol": "aimovie.native-auth.v3", "account": self.SJ_ACCOUNT, "password": self.SJ_PASSWORD}
                    r = self.post(host + path, json=body, headers=headers, timeout=20)
                    if not r:
                        continue
                    # 从 cookie/Set-Cookie 拿 ai_movie_session (XaHVDvJi 方式: cookies.get 优先)
                    sess = ''
                    try:
                        c = r.cookies.get('ai_movie_session')
                        if c and c.startswith('ums_'):
                            sess = c
                    except Exception:
                        pass
                    if not sess:
                        try:
                            raw = r.headers.get('Set-Cookie') or ''
                            m = re.search(r'ai_movie_session=(ums_[^;]+)', raw)
                            if m:
                                sess = m.group(1)
                        except Exception:
                            pass
                    if not sess:
                        try:
                            all_sc = []
                            try:
                                all_sc = r.raw.headers.get_all('Set-Cookie') or []
                            except Exception:
                                pass
                            for sc in all_sc:
                                if 'ai_movie_session=ums_' in sc:
                                    sess = sc.split('ai_movie_session=')[1].split(';')[0]
                                    break
                        except Exception:
                            pass
                    if sess:
                        self.SJ_SESSION = sess
                        _SJ_G['session'] = sess  # 写模块缓存
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        return False

    # ============ 搜剧AI 签名请求 (多域名) ============

    def _sj_key(self, host):
        return self.KJ_KEY if 'kanju' in host else self.SJ_KEY

    def _sj_cands(self):
        """候选域名: 缓存好域名优先 + 全列表去重"""
        good = _SJ_G.get('good_host', '')
        out = []
        if good and good in self.SJ_HOSTS:
            out.append(good)
        for h in self.SJ_HOSTS:
            if h not in out:
                out.append(h)
        return out

    def _sj_req(self, method, path, body=None, timeout=20):
        # 多域名: 优先用缓存的好域名, 再试 kanju/souju, 最后试其他
        last_err = ''
        # 只试前 5 个, 避免 21 个全遍历太慢
        for host in self._sj_cands()[:5]:
            try:
                r = self._sj_req_host(host, method, path, body, timeout)
                _SJ_G['good_host'] = host  # 记好用的
                return r
            except Exception as e:
                last_err = str(e)
                continue
        raise Exception('搜剧AI 域名均失败: ' + last_err)

    def _sj_req_host(self, host, method, path, body, timeout):
        import json as _sj_json
        ts = str(int(time.time() * 1000))
        nonce = ''.join(random.choices('0123456789abcdef', k=16))
        key = self._sj_key(host)
        # 签名消息: METHOD\npath+search\nts\nnonce
        qi = path.find('?')
        p = path[:qi] if qi >= 0 else path
        s = path[qi:] if qi >= 0 else ''
        sig_msg = method + '\n' + p + s + '\n' + ts + '\n' + nonce
        sig = hmac.new(key.encode(), sig_msg.encode('utf-8'), hashlib.sha256).hexdigest()
        headers = {
            'x-ai-movie-timestamp': ts,
            'x-ai-movie-nonce': nonce,
            'x-ai-movie-signature': sig,
            'Accept': 'application/json',
            'Referer': host + '/',
            'User-Agent': self.UA,
        }
        # 登录态: 带 ai_movie_session cookie (v4 关键, 官方线路需要登录)
        if self.SJ_SESSION:
            headers['Cookie'] = 'ai_movie_session=' + self.SJ_SESSION
        url = host + path
        if method == 'POST':
            # 用 self.post json=body (v4 方式, WebHomeTV post 支持 json 参数)
            r = self.post(url, json=body, headers=headers, timeout=timeout)
            txt = r.text if hasattr(r, 'text') else str(r)
            return _sj_json.loads(txt)
        else:
            r = self.fetch(url, headers=headers, timeout=timeout)
            txt = r.text if hasattr(r, 'text') else str(r)
            return _sj_json.loads(txt)

    # 搜索: GET /v1/browse/catalog?intent=search&q= (当前接口, 返回 cards)
    def _sj_search_cards(self, keyword, pages=2):
        cards = []
        seen = set()
        # 只试前3个域名 (good_host优先 + kanju + souju)
        hosts = self._sj_cands()[:3]
        for host in hosts:
            try:
                q = urllib.parse.quote(keyword)
                cat = self._sj_req_host(host, 'GET', f'/v1/browse/catalog?intent=search&q={q}&page_num=1&page_size=20', None, 20)
                items = (cat or {}).get('cards') or []
                if not items:
                    continue
                for cd in items:
                    av = cd.get('id') or ''
                    if not av or av in seen:
                        continue
                    seen.add(av)
                    cards.append({
                        'id': av,
                        'host': host,
                        'title': cd.get('title') or '',
                        'pic': cd.get('poster_url') or cd.get('backdrop_url') or cd.get('carousel_url') or '',
                    })
            except Exception:
                continue
        return cards

    # 剧集列表: 按 av_id (指定域名)
    def _sj_episodes(self, av, host=None):
        if not host:
            host = self.SJ_HOSTS[0]
        ep = self._sj_req_host(host, 'GET', f'/v1/catalog/{av}/episodes?limit=200&offset=0', None, 20)
        eps = (ep or {}).get('episodes') or []
        arr = []
        for i, ei in enumerate(eps):
            tk = ei.get('token') or ''
            if not tk:
                continue
            name = ei.get('title') or ei.get('display_name') or ('第' + str(i + 1) + '集')
            arr.append({'name': name, 'token': tk, 'host': host})
        return arr

    # 播放解析: resolve token → 线路列表 [(线路名, m3u8直链), ...]
    # 官方线路 (resolve_ticket) 用 resolve-line 二次解析成 m3u8, 优先;
    # 第三方 m3u8 直链保留; 过滤爱优腾芒B
    def _sj_resolve_lines(self, token, host=None):
        if not host:
            host = self.SJ_HOSTS[0]
        rs = self._sj_req_host(host, 'GET', '/v1/playback/resolve/' + urllib.parse.quote(token) + '?view=compact', None, 20)
        lines = (rs or {}).get('line_options') or []
        out = []
        seen = set()
        # 1. 官方线路 (resolve_ticket → resolve-line 二次解析)
        for ln in lines:
            u = str(ln.get('url') or '').strip()
            if not u.startswith('resolve://'):
                continue
            label = str(ln.get('label') or ln.get('display_label') or '官方')
            tid = u.replace('resolve://', '')
            try:
                rl = self._sj_req_host(host, 'POST', '/v1/playback/resolve-line', {'ticket': tid}, 15)
                lu = ((rl or {}).get('line') or {}).get('url') or ''
            except Exception:
                lu = ''
            if not lu or not str(lu).startswith('http'):
                continue
            if any(b in lu for b in self.BAD_HOSTS):
                continue
            if lu in seen:
                continue
            seen.add(lu)
            out.append((label, str(lu)))
        # 2. 第三方 m3u8 直链
        for ln in lines:
            u = str(ln.get('url') or '').strip()
            kind = str(ln.get('url_kind') or '')
            if kind != 'm3u8' or not u.startswith('http'):
                continue
            if any(b in u for b in self.BAD_HOSTS):
                continue
            if u in seen:
                continue
            seen.add(u)
            label = str(ln.get('label') or ln.get('display_label') or '')
            if not label or label in ('?', 'None', 'null'):
                label = '线路' + str(len(out) + 1)
            out.append((label, u))
        # 3. 兜底: 全失败时取第一个 m3u8
        if not out:
            for ln in lines:
                u = str(ln.get('url') or '').strip()
                if u.startswith('http') and '.m3u8' in u:
                    out.append(('线路1', u))
                    break
        return out

    # 构建播放串: 照抄 XaHVDvJi (每线路分段, id=线路名||kind||token)
    # vod_play_from = 线路名$$$线路名...; vod_play_url = 每线路一段 (集名$线路名||kind||token 用#分隔)
    # playerContent 解析 id 三段 (线路名/类型/token), 不依赖 flag
    def _sj_vod_play(self, eps):
        if not eps:
            return '', ''
        lines = self._sj_line_table(eps[0]['token'])
        if not lines:
            lines = [{'name': '官方', 'kind': 'official'}, {'name': '第三方', 'kind': 'm3u8'}]
        froms = []
        urls = []
        for li in lines:
            froms.append(li['name'])
            parts = []
            for i, ep in enumerate(eps):
                tt = ep.get('name') or '第{}集'.format(i + 1)
                tok = ep.get('token', '')
                u = '{}||{}||{}'.format(li['name'], li['kind'], tok)
                parts.append('{}${}'.format(tt, u))
            urls.append('#'.join(parts))
        return '$$$'.join(froms), '$$$'.join(urls)

    # 线路表: 照抄 XaHVDvJi (name 字段, resolve?line=yjm3u8)
    # 返回 [{"name": 线路名, "kind": "official"/"m3u8"}]
    def _sj_line_table(self, tk0):
        # 线路表缓存: 同一影片详情/播放复用 (token 相同 → 线路相同, 秒回)
        if tk0 in _SJ_G['line_cache']:
            return _SJ_G['line_cache'][tk0]
        opts = []
        for host in self._sj_cands()[:3]:
            try:
                j = self._sj_req_host(host, 'GET', '/v1/playback/resolve/' + urllib.parse.quote(tk0) + '?line=yjm3u8', None, 12)
                opts = (j or {}).get('line_options') or []
                if len(opts) >= 3:
                    break
            except Exception:
                continue
        lines = []
        seen = set()
        for o in opts:
            nm = o.get('name') or o.get('label') or ''
            u = o.get('url', '')
            k = o.get('url_kind', '')
            if not nm or not u:
                continue
            if k == 'resolve_ticket':
                # 官方线路: 保留
                if nm in seen:
                    continue
                seen.add(nm)
                lines.append({'name': nm, 'kind': 'official'})
            elif k == 'm3u8' and u.startswith('http'):
                # 第三方: 过滤 BAD_HOSTS (爱优腾芒B不可播) + 按线路名去重
                if any(b in u for b in self.BAD_HOSTS):
                    continue
                if nm in seen:
                    continue
                seen.add(nm)
                lines.append({'name': nm, 'kind': 'm3u8'})
        if lines:
            _SJ_G['line_cache'][tk0] = lines  # 写模块缓存
        return lines

    # 只拿线路 label 列表 (不解析 URL, 快) — 搜剧AI XaHVDvJi 流畅模式
    def _sj_line_labels(self, token, host=None):
        if not host:
            host = self.SJ_HOSTS[0]
        try:
            rs = self._sj_req_host(host, 'GET', '/v1/playback/resolve/' + urllib.parse.quote(token) + '?view=compact', None, 12)
            lines = (rs or {}).get('line_options') or []
        except Exception:
            return []
        labels = []
        seen = set()
        # 1. 第三方 m3u8 线路名 (优先, 流畅; 官方常卡放后面)
        for ln in lines:
            u = str(ln.get('url') or '').strip()
            kind = str(ln.get('url_kind') or '')
            if kind != 'm3u8' or not u.startswith('http'):
                continue
            if any(b in u for b in self.BAD_HOSTS):
                continue
            label = str(ln.get('label') or ln.get('display_label') or '')
            if not label or label in ('?', 'None', 'null'):
                label = '线路' + str(len(labels) + 1)
            if label in seen:
                continue
            seen.add(label)
            labels.append(label)
        # 2. 官方线路名 (resolve_ticket, 放后面)
        for ln in lines:
            u = str(ln.get('url') or '').strip()
            if not u.startswith('resolve://'):
                continue
            label = str(ln.get('label') or ln.get('display_label') or '官方')
            if label in seen:
                continue
            seen.add(label)
            labels.append(label)
        # 3. 兜底
        if not labels:
            for ln in lines:
                u = str(ln.get('url') or '').strip()
                if u.startswith('http') and '.m3u8' in u:
                    labels.append('线路1')
                    break
        return labels

    # ============ 360kan 界面接口 ============

    def _kan_get(self, url, timeout=15):
        r = self.fetch(url, headers={'X-Requested-With': 'XMLHttpRequest', 'User-Agent': self.UA}, timeout=timeout)
        return json.loads(r.text if hasattr(r, 'text') else str(r))

    # ============ Spider 接口 ============

    def homeContent(self, filter):
        # 首页: 4 大分类 + 360kan 热门推荐(电影)
        try:
            hot = self.categoryContent('1', '1', False, {})
            return {"class": self.CLASS, "filters": self.FILTERS, "list": hot.get('list', [])}
        except Exception:
            return {"class": self.CLASS, "filters": self.FILTERS, "list": []}

    def homeVideoContent(self):
        return self.categoryContent('1', '1', False, {})

    # 搜剧AI 卡片: id → av_xxx
    def _sj_card(self, it):
        if not it:
            return None
        av = str(it.get('id') or '')
        if not av:
            return None
        return {
            "vod_id": 'sj:' + av,
            "vod_name": str(it.get('title') or ''),
            "vod_pic": it.get('poster_url') or it.get('cover_url') or '',
            "vod_remarks": str(it.get('remarks') or ''),
        }

    def categoryContent(self, tid, pg, filter, extend):
        try:
            tid = str(tid or '1')
            pg = str(pg or '1')
            # 二级分类筛选 (extend 带 cat/area/year)
            cat = str((extend or {}).get('cat') or '')
            area = str((extend or {}).get('area') or '')
            year = str((extend or {}).get('year') or '')
            # cat 类型仅电影(catid=1)生效, 其他频道传空
            if tid != '1':
                cat = ''
            url = self.KAN_API + f'/filter/list?catid={tid}&rank=rankhot&cat={urllib.parse.quote(cat)}&year={year}&area={urllib.parse.quote(area)}&act=&size=35&pageno={pg}'
            j = self._kan_get(url)
            movies = ((j.get('data') or {}).get('movies')) or []
            videos = []
            for m in movies:
                mid = m.get('id') or m.get('ent_id') or ''
                if not mid:
                    continue
                title = str(m.get('title') or '')
                score = m.get('doubanscore') or ''
                pic = m.get('cover') or m.get('cdncover') or ''
                if pic.startswith('//'):
                    pic = 'https:' + pic
                desc = str(m.get('comment') or m.get('description') or '')[:30]
                videos.append({
                    "vod_id": '360:' + str(mid) + '|' + urllib.parse.quote(title),
                    "vod_name": title + (' ' + str(score) if score else ''),
                    "vod_pic": pic,
                    "vod_remarks": desc,
                })
            return {"list": videos, "page": int(pg), "pagecount": 999, "limit": 0, "total": 0}
        except Exception:
            return {"list": [], "page": int(pg or 1), "pagecount": 1, "limit": 0, "total": 0}

    def searchContent(self, key, quick, pg="1"):
        try:
            kw = urllib.parse.quote(str(key))
            videos = []
            seen = set()
            # 1. 搜剧AI 搜索 (intent=search, cards 字段; /v1/search 已 404)
            try:
                cards = self._sj_search_cards(str(key), pages=2)
                for cd in cards:
                    av = cd['id']
                    if av in seen:
                        continue
                    seen.add(av)
                    videos.append({
                        "vod_id": 'sj:' + av,
                        "vod_name": cd.get('title', ''),
                        "vod_pic": cd.get('pic', ''),
                        "vod_remarks": '搜剧AI',
                    })
            except Exception:
                pass
            # 2. 360kan 搜索兜底
            try:
                url = self.KAN_SEARCH + f'/index?force_v=1&kw={kw}&pageno=1&v_ap=1&tab=all'
                j = self._kan_get(url)
                rows = (((j.get('data') or {}).get('longData') or {}).get('rows')) or []
                for r in rows:
                    rid = r.get('id') or r.get('ent_id') or ''
                    if not rid or rid in seen:
                        continue
                    seen.add(rid)
                    title = str(r.get('titleTxt') or '')
                    cat = str(r.get('cat_name') or '')
                    cover = r.get('cover') or ''
                    desc = str(r.get('description') or '')[:40]
                    videos.append({
                        "vod_id": '360:' + rid,
                        "vod_name": title,
                        "vod_pic": cover,
                        "vod_remarks": (cat + ' ' if cat else '') + desc,
                    })
            except Exception:
                pass
            return {"list": videos, "page": 1, "pagecount": 1, "limit": 0, "total": 0}
        except Exception:
            return {"list": [], "page": 1, "pagecount": 1, "limit": 0, "total": 0}

    def detailContent(self, ids):
        try:
            # 先登录 (v4 链路: 官方解析需要 session)
            if not self.SJ_SESSION:
                self._sj_login()
            vid = str(ids[0])
            vod = {"vod_id": vid, "vod_name": '影片', "vod_pic": '', "vod_remarks": '', "vod_content": ''}
            # 搜剧AI 卡片: sj:av_id → 直接搜剧AI 详情
            if vid.startswith('sj:'):
                av = vid[3:]
                eps = []
                try:
                    eps = self._sj_episodes(av, self.SJ_HOSTS[0])
                except Exception:
                    eps = []
                if not eps:
                    return {"list": []}
                # 搜剧AI 详情字段 (XaHVDvJi 同款)
                try:
                    dj = self._sj_req_host(self.SJ_HOSTS[0], 'GET', '/v1/catalog/' + urllib.parse.quote(av) + '/detail', None, 12)
                    if dj:
                        vod['vod_name'] = str(dj.get('title') or '搜剧AI影片')
                        vod['vod_pic'] = dj.get('poster_url') or dj.get('cover_url') or ''
                        vod['vod_content'] = str(dj.get('description') or '')[:300]
                except Exception:
                    pass
                play_from, play_url = self._sj_vod_play(eps)
                vod['vod_play_from'] = play_from or '搜剧AI'
                vod['vod_play_url'] = play_url
                vod['vod_remarks'] = str(len(eps)) + '集'
                return {"list": [vod]}
            # 360kan 卡片: 360:id|标题 (标题已编码在 vod_id) → 搜剧AI 搜片名 → 播放
            rid = vid[4:]
            title = ''
            if '|' in rid:
                rid, title = rid.split('|', 1)
                title = urllib.parse.unquote(title)
            # 标题去评分后缀: "醒来 8.5" → "醒来"
            import re as _re
            title = _re.sub(r'\s+\d+(\.\d+)?$', '', title)
            if not title:
                try:
                    j = self._kan_get(self.KAN_API + f'/detail?cat=1&id={rid}')
                    d = (j.get('data') or {})
                    title = str(d.get('title') or '')
                    pic = d.get('cdncover') or ''
                    if pic.startswith('//'):
                        pic = 'https:' + pic
                    vod['vod_pic'] = pic
                    vod['vod_content'] = str(d.get('description') or '')[:300]
                except Exception:
                    pass
            # 用搜剧AI 搜标题 → 详情 + 播放
            if title:
                try:
                    cards = self._sj_search_cards(title, pages=1)
                    if cards:
                        cd0 = cards[0]
                        eps = self._sj_episodes(cd0['id'], self.SJ_HOSTS[0])
                        play_from, play_url = self._sj_vod_play(eps)
                        vod['vod_play_from'] = play_from or '搜剧AI'
                        vod['vod_play_url'] = play_url
                        vod['vod_remarks'] = str(len(eps)) + '集'
                        vod['vod_name'] = title
                except Exception:
                    pass
            if not vod.get('vod_play_url'):
                return {"list": []}
            return {"list": [vod]}
        except Exception:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        r = {"flag": flag, "id": id, "url": "", "header": {"User-Agent": self.UA, "Referer": self.SJ_HOSTS[0] + "/"}}
        try:
            # id 三段: 线路名||kind||token (XaHVDvJi 格式)
            sid = str(id)
            seg = sid.split('||')
            if len(seg) < 3:
                return r
            lname = seg[0]
            kind = seg[1]
            tk = seg[2]
            # 官方线路才需要登录 session; 第三方直接 resolve 即可 (省一次登录)
            if kind == 'official':
                if not self.SJ_SESSION:
                    self._sj_login()
                if not self.SJ_SESSION:
                    return r
            # resolve 拿线路 (照抄 XaHVDvJi: ?line=yjm3u8)
            opts = []
            for host in self._sj_cands()[:3]:
                try:
                    j = self._sj_req_host(host, 'GET', '/v1/playback/resolve/' + urllib.parse.quote(tk) + '?line=yjm3u8', None, 15)
                    opts = (j or {}).get('line_options') or []
                    if opts:
                        break
                except Exception:
                    continue
            if not opts:
                return r
            if kind == 'official':
                ticket = ''
                for o in opts:
                    nm = o.get('name') or o.get('label') or ''
                    if nm == lname and o.get('url_kind') == 'resolve_ticket':
                        ticket = o.get('url', '')[len('resolve://'):]
                        break
                if not ticket:
                    for o in opts:
                        if o.get('url_kind') == 'resolve_ticket':
                            ticket = o.get('url', '')[len('resolve://'):]
                            break
                if ticket:
                    # resolve-line 结果缓存 (同一 ticket 解析一次, 切回秒回)
                    rl_key = 'rl:' + ticket
                    if rl_key in _SJ_G['line_cache']:
                        bu = _SJ_G['line_cache'][rl_key]
                        if bu.startswith('http'):
                            r['url'] = bu
                            return r
                    bj = self._sj_req_host(self.SJ_HOSTS[0], 'POST', '/v1/playback/resolve-line', {'ticket': ticket}, 12)
                    if bj:
                        bu = (bj.get('line') or {}).get('url', '')
                        if bu.startswith('http'):
                            _SJ_G['line_cache'][rl_key] = bu  # 写缓存
                            r['url'] = bu
                            return r
                # 官方失败: 回退第一个可播 m3u8
                for o in opts:
                    if o.get('url_kind') == 'm3u8' and o.get('url', '').startswith('http'):
                        if any(b in o['url'] for b in self.BAD_HOSTS):
                            continue
                        r['url'] = o['url']
                        return r
            else:
                # 第三方: 按线路名匹配 m3u8, 失败取第一个
                for o in opts:
                    nm = o.get('name') or o.get('label') or ''
                    if nm == lname and o.get('url_kind') == 'm3u8' and o.get('url', '').startswith('http'):
                        if any(b in o['url'] for b in self.BAD_HOSTS):
                            break
                        r['url'] = o['url']
                        return r
                for o in opts:
                    if o.get('url_kind') == 'm3u8' and o.get('url', '').startswith('http'):
                        if any(b in o['url'] for b in self.BAD_HOSTS):
                            continue
                        r['url'] = o['url']
                        return r
        except Exception:
            pass
        return r

    # 解析全部线路 [(label, kind, url_or_ticket)] 双域名重试, 第三方优先
    def _sj_resolve_all(self, token):
        for host in self._sj_cands()[:3]:
            try:
                rs = self._sj_req_host(host, 'GET', '/v1/playback/resolve/' + urllib.parse.quote(token) + '?view=compact', None, 15)
                lines = (rs or {}).get('line_options') or []
                cands = []
                seen_lab = set()
                for ln in lines:
                    u = str(ln.get('url') or '').strip()
                    kind = str(ln.get('url_kind') or '')
                    label = str(ln.get('label') or ln.get('display_label') or '')
                    if kind == 'm3u8' and u.startswith('http'):
                        if any(b in u for b in self.BAD_HOSTS):
                            continue
                        lab = label if label and label not in ('?', 'None', 'null') else '线路' + str(len(cands) + 1)
                        if lab in seen_lab:
                            continue
                        seen_lab.add(lab)
                        cands.append((lab, 'm3u8', u))
                for ln in lines:
                    u = str(ln.get('url') or '').strip()
                    label = str(ln.get('label') or ln.get('display_label') or '')
                    if u.startswith('resolve://'):
                        lab = label or '官方'
                        if lab in seen_lab:
                            continue
                        seen_lab.add(lab)
                        cands.append((lab, 'official', u.replace('resolve://', '')))
                if cands:
                    return cands
            except Exception:
                continue
        return []


class Spider(S):
    pass
