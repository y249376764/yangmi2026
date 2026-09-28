# -*- coding: utf-8 -*-
# 洛雪插件转换器 - TVBox py 音乐源
# 功能：导入洛雪(LX Music)插件，自动扫描API端点，转成可用的搜索+播放源
# 原理：洛雪插件是JS文件(export default {platform, search, getMediaSource...})，
#       本源不运行JS，而是正则解析源码提取 HTTP 端点，用 Python 自己发请求
# 导入方式：把插件JS源码放到仓库 plugins/lx/ 目录，本源自动扫描全部插件
import requests
import json
import re
import sys
import os
from urllib.parse import quote

try:
    sys.path.append('..')
    from base.spider import Spider
except Exception:
    class Spider:
        def __init__(self):
            pass

# ========== 内置洛雪插件（直接内嵌，盒子可立即使用） ==========
BUILTIN_PLUGINS = [
    {"name": "网易云", "src": "// 网易云音乐 - 洛雪插件格式（歌词适配接口）\nexport default {\n    platform: \"网易云\",\n    version: \"1.0.0\",\n    description: \"网易云音乐，歌词适配接口\",\n    supportedSearchType: [\"songs\"],\n    defaultSearchType: \"songs\",\n    search: {\n        songs: async (page, { keyword }) => {\n            const url = `http://music.163.com/api/search/get/web?csrf_token=&hlpretag=&hlposttag=&s=${keyword}&type=1&offset=${(page - 1) * 20}&total=true&limit=20`;\n            const res = await fetch(url);\n            const data = await res.json();\n            return (data.result && data.result.songs || []).map(item => ({\n                id: item.id,\n                title: item.name,\n                artist: (item.artists || []).map(a => a.name).join('&'),\n                album: item.album && item.album.name || '',\n                artwork: item.album && item.album.picUrl || ''\n            }));\n        }\n    },\n    getMediaSource: async (song, quality) => {\n        const url = `http://music.163.com/song/media/outer/url?id=${song.id}.mp3`;\n        return { url: url, headers: {} };\n    }\n};\n"},
    {"name": "酷我音乐", "src": "// 标准洛雪插件样例 - 用于测试转换器\nexport default {\n    platform: \"酷我音乐\",\n    version: \"1.0.0\",\n    srcUrl: \"https://example.com/kuwo.js\",\n    description: \"测试用酷我插件\",\n    cacheControl: \"no-cache\",\n    primaryKey: \"$guid\",\n    supportedSearchType: [\"songs\", \"albums\", \"playLists\", \"mvs\"],\n    defaultSearchType: \"songs\",\n    request: {\n      headers: {\n        \"User-Agent\": \"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36\",\n        \"Referer\": \"https://www.kuwo.cn/\",\n        \"csrf\": \"abc123\"\n      }\n    },\n    search: {\n      songs: async (page, { keyword }) => {\n        const url = `https://search.kuwo.cn/r.s?client=kt&all=${keyword}&pn=${page - 1}&rn=30&ver=kwplayer_ar_12.2.0.0&ft=music&vipver=1&encoding=utf8&rformat=json&mobi=1`;\n        const res = await fetch(url);\n        const data = await res.json();\n        return data.abslist.map(item => ({\n          id: item.MUSICRID.replace('MUSIC_', ''),\n          title: item.SONGNAME,\n          artist: item.ARTIST,\n          album: item.ALBUM,\n          artwork: `https://img1.kuwo.cn/star/albumcover/300/${item.ALBUMID}.jpg`\n        }));\n      }\n    },\n    getMediaSource: async (song, quality) => {\n      const url = `https://antiserver.kuwo.cn/anti.s?type=convert_url&rid=${song.id}&format=mp3&response=url`;\n      const res = await fetch(url);\n      const text = await res.text();\n      return {\n        url: text.trim(),\n        headers: { \"User-Agent\": \"Mozilla/5.0\" }\n      };\n    }\n};\n"}
]

# URL 提取字符类（排除 双引号 单引号 反引号 空白）
SQ = chr(39)  # 单引号


def _URL_RE():
    return r'https?://[^"' + SQ + r'`;' + chr(10) + chr(13) + r']+'


class Spider(Spider):
    def getName(self):
        return "洛雪转换器"

    def init(self, extend=""):
        self.header = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36'
        }
        self.plugins = self._load_plugins()

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        pass

    def _load_plugins(self):
        plugins = []
        for p in BUILTIN_PLUGINS:
            plugins.append(p)
        try:
            base = os.path.dirname(os.path.abspath(__file__))
            lx_dir = os.path.join(base, 'plugins', 'lx')
            if os.path.isdir(lx_dir):
                for f in os.listdir(lx_dir):
                    if f.endswith('.js'):
                        with open(os.path.join(lx_dir, f), 'r', encoding='utf-8', errors='ignore') as fp:
                            plugins.append({"name": f[:-3], "src": fp.read()})
        except Exception:
            pass
        return plugins

    def _extract_url(self, text):
        m = re.search(_URL_RE(), text)
        return m.group(0) if m else ''

    def _parse_plugin(self, src):
        info = {'platform': '', 'search_url': '', 'play_url': '', 'has_search': False, 'has_play': False}

        m = re.search(r'platform\s*[:=]\s*["' + SQ + r']([^"' + SQ + r']+)["' + SQ + r']', src)
        if m:
            info['platform'] = m.group(1)
        if not info['platform']:
            m = re.search(r'@name\s+([^\n]+)', src)
            if m:
                info['platform'] = m.group(1).strip()

        # 搜索接口：search 关键词后第一个URL
        m = re.search(r'search.{0,500}?https?://[^"' + SQ + r'`;' + chr(10) + chr(13) + r']+', src, re.S)
        if m:
            info['search_url'] = self._clean_url(m.group(0)[m.group(0).find('http'):])
            info['has_search'] = True
        if not info['search_url']:
            m = re.search(r'https?://[^"' + SQ + r'`;' + chr(10) + chr(13) + r']*(?:search|Search|s\?|all=)[^"' + SQ + r'`;' + chr(10) + chr(13) + r']*', src)
            if m:
                info['search_url'] = self._clean_url(m.group(0))
                info['has_search'] = True

        # 播放接口：getMediaSource/getMusicUrl/convert_url 后第一个URL
        m = re.search(r'(?:getMediaSource|getMusicUrl|convert_url|anti\.s)[^"' + SQ + r';]{0,300}?https?://[^"' + SQ + r'`;' + chr(10) + chr(13) + r']+', src, re.S)
        if m:
            u = m.group(0)
            info['play_url'] = self._clean_url(u[u.find('http'):])
            info['has_play'] = True
        if not info['play_url']:
            m = re.search(r'https?://[^"' + SQ + r'`;' + chr(10) + chr(13) + r']*?(?:rid|songmid|hash|musicid)[^"' + SQ + r'`;' + chr(10) + chr(13) + r']*', src)
            if m:
                info['play_url'] = self._clean_url(m.group(0))
                info['has_play'] = True

        return info

    def _clean_url(self, u):
        """截取合法URL：去掉JS语法残留"""
        # 截到 反引号/引号/分号/换行 前
        for sep in ['`', chr(34), chr(39), ';', chr(10), chr(13)]:
            if sep in u:
                u = u.split(sep)[0]
        u = u.rstrip()
        # 模板变量里的空格（${page - 1}）→ 0
        u = re.sub(r'\$\{[^}]*\s[^}]*\}', '0', u)
        return u

    def _fill_params(self, url, key):
        url = re.sub(r'\$?\{(?:keyword|key|wd|text|word|query|name)\}', quote(key), url)
        # 先填 id 类模板（song.id/rid/musicid/hash 等）
        url = re.sub(r'\$?\{(?:song\.id|rid|id|hash|musicid|songmid)\}', quote(key), url)
        url = re.sub(r'\$?\{(?:page|pg|p|offset|start|index|pn)[^}]*\}?', '0', url)
        url = re.sub(r'\$\{[^}]*\}?', '', url)
        url = url.replace('${', '').replace('`', '')
        return url

    def homeContent(self, filter):
        cls = []
        for i, p in enumerate(self.plugins):
            info = self._parse_plugin(p['src'])
            name = info['platform'] or p['name'] or ('插件%d' % (i + 1))
            cls.append({"type_id": str(i), "type_name": name})
        if not cls:
            cls = [{"type_id": "0", "type_name": "无插件"}]
        return {"class": cls, "filters": {}}

    def homeVideoContent(self):
        return self.searchContent("热门", False)

    def categoryContent(self, tid, pg, filter, extend):
        return self.searchContent("热门", False, pg, tid)

    def searchContent(self, key, quick, pg='1', plugin_idx=None):
        vods = []
        if plugin_idx is not None:
            idx = int(plugin_idx)
            if idx < len(self.plugins):
                vods += self._search_with_plugin(self.plugins[idx], key)
        else:
            for p in self.plugins:
                try:
                    vods += self._search_with_plugin(p, key)
                except Exception:
                    continue
        return {"list": vods}

    def _search_with_plugin(self, plugin, key):
        info = self._parse_plugin(plugin['src'])
        vods = []
        if not info['has_search']:
            return vods
        url = self._fill_params(info['search_url'], key)
        try:
            r = requests.get(url, headers=self.header, timeout=10)
            data = r.json()
            items = data.get('data') or data.get('result') or data.get('songs') or data.get('list') or data.get('albums') or data.get('albumlist') or data.get('abslist') or []
            if isinstance(items, dict):
                items = items.get('list') or items.get('songs') or items.get('items') or []
            if not isinstance(items, list):
                items = []
            for it in items:
                if isinstance(it, str):
                    continue
                sid = it.get('id') or it.get('songmid') or it.get('rid') or it.get('musicrid') or it.get('MUSICRID') or it.get('hash') or it.get('albumid') or ''
                name = it.get('name') or it.get('songname') or it.get('SONGNAME') or it.get('title') or it.get('album_name') or ''
                artist = it.get('artist') or it.get('singer') or it.get('singername') or it.get('ARTIST') or ''
                if not artist and isinstance(it.get('artists'), list):
                    artist = '&'.join(a.get('name', '') for a in it['artists'] if isinstance(a, dict))
                pic = it.get('pic') or it.get('album_pic') or it.get('cover') or it.get('artwork') or it.get('album_img') or ''
                if not pic and isinstance(it.get('album'), dict):
                    pic = it['album'].get('picUrl', '') or ''
                if sid and name:
                    pf = info['platform'] or plugin['name']
                    # id前缀路由平台（wy_=网易 kw_=酷我）
                    pf_key = ''
                    pf_l = pf.lower()
                    if '网易' in pf_l or 'wy' in pf_l:
                        pf_key = 'wy_'
                    elif '酷我' in pf_l or 'kw' in pf_l:
                        pf_key = 'kw_'
                    vods.append({
                        "vod_id": pf_key + str(sid),
                        "vod_name": "[%s] %s" % (pf, name),
                        "vod_pic": pic,
                        "vod_remarks": artist,
                        "vod_actor": artist,
                        "vod_content": json.dumps({"p": plugin['name'], "u": info['play_url']}, ensure_ascii=False)
                    })
        except Exception:
            pass
        return vods

    def detailContent(self, ids):
        vid = str(ids[0]) if isinstance(ids, (list, tuple)) else str(ids)
        return {"list": [{"vod_id": vid, "vod_name": vid, "vod_play_from": "洛雪", "vod_play_url": "播放$" + vid}]}

    def playerContent(self, flag, id, vipFlags=None):
        try:
            song_id = str(id)
            pf_key = ''
            if song_id.startswith('wy_'):
                pf_key = 'wy_'
                song_id = song_id[3:]
            elif song_id.startswith('kw_'):
                pf_key = 'kw_'
                song_id = song_id[3:]
            for p in self.plugins:
                info = self._parse_plugin(p['src'])
                # 平台前缀匹配：跳过不匹配的插件
                pf_l = (info['platform'] or '').lower()
                if pf_key == 'wy_' and not ('网易' in pf_l or 'wy' in pf_l):
                    continue
                if pf_key == 'kw_' and not ('酷我' in pf_l or 'kw' in pf_l):
                    continue
                info = self._parse_plugin(p['src'])
                if info['has_play']:
                    url = self._fill_params(info['play_url'], song_id)
                    url = url.replace('{rid}', song_id).replace('{id}', song_id).replace('{hash}', song_id).replace('{musicid}', song_id)
                    # 网易云 outer/url 是302重定向地址，直接返回给播放器跟随
                    if 'outer/url' in url or 'music.163.com' in url:
                        return {"parse": 0, "url": url, "header": {}}
                    try:
                        r = requests.get(url, headers=self.header, timeout=10)
                        play = r.text.strip()
                        if play.startswith('{'):
                            dd = json.loads(play)
                            play = dd.get('url') or dd.get('playUrl') or dd.get('src') or dd.get('data') or dd.get('play_url') or ''
                            if isinstance(play, dict):
                                play = play.get('url', '')
                        if play.startswith('http'):
                            return {"parse": 0, "url": play, "header": {}}
                    except Exception:
                        continue
        except Exception:
            pass
        return {"parse": 0, "url": id, "header": {}}

    def localProxy(self, param):
        return None
