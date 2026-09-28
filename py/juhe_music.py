# -*- coding: utf-8 -*-
# 聚合音乐 [歌词适配版] - TVBox py 音乐源
# 聚合 QQ/网易/酷狗/酷我/咪咕 搜索 + 播放直链
# 参考: 海阔"歌词适配"规则提取的接口
import requests
import json
import re
import sys
import base64
import hashlib
import time
from urllib.parse import quote

try:
    sys.path.append('..')
    from base.spider import Spider
except Exception:
    class Spider:
        def __init__(self):
            pass

class Spider(Spider):
    def getName(self):
        return "聚合音乐"

    def init(self, extend=""):
        self.header = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36'
        }

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        pass

    def homeContent(self, filter):
        # 分类 = 平台
        return {
            "class": [
                {"type_id": "wy", "type_name": "网易云"},
                {"type_id": "kw", "type_name": "酷我"}
            ],
            "filters": {}
        }

    def homeVideoContent(self):
        # 首页 = 酷狗热门搜索
        return self.searchContent("热门歌曲", False)

    def categoryContent(self, tid, pg, filter, extend):
        # 分类 = 平台热门
        hot_words = {"wy": "网易热歌", "kw": "酷我热歌"}
        return self.searchContent(hot_words.get(tid, "热门歌曲"), False)

    def searchContent(self, key, quick, pg='1'):
        """多平台聚合搜索"""
        vods = []
        # 网易云搜索
        try:
            vods += self._search_wy(key)
        except Exception:
            pass
        # 酷我搜索
        try:
            vods += self._search_kw(key)
        except Exception:
            pass
        return {"list": vods}

    # ========== QQ音乐 ==========
    def _search_qq(self, key):
        url = f'https://c.y.qq.com/soso/fcgi-bin/client_search_cp?p=1&n=20&w={quote(key)}&format=json'
        r = requests.get(url, headers={**self.header, 'Referer': 'https://y.qq.com/'}, timeout=10)
        data = json.loads(r.text)
        songs = data.get('data', {}).get('song', {}).get('list', [])
        vods = []
        for s in songs:
            mid = s.get('mid', '')
            if not mid:
                continue
            name = s.get('name', '')
            singer = '&'.join(a.get('name', '') for a in s.get('singer', []))
            pic = f"https://y.gtimg.cn/music/photo_new/T002R300x300M000{s.get('album', {}).get('mid', '')}.jpg"
            vods.append({
                "vod_id": f"qq_{mid}",
                "vod_name": f"[QQ] {name}",
                "vod_pic": pic,
                "vod_remarks": singer,
                "vod_actor": singer
            })
        return vods

    # ========== 网易云 ==========
    def _search_wy(self, key):
        url = f'http://music.163.com/api/search/get/web?csrf_token=&hlpretag=&hlposttag=&s={quote(key)}&type=1&offset=0&total=true&limit=20'
        r = requests.get(url, headers={**self.header, 'Referer': 'https://music.163.com/'}, timeout=10)
        data = json.loads(r.text)
        songs = data.get('result', {}).get('songs', [])
        vods = []
        for s in songs:
            sid = s.get('id', '')
            if not sid:
                continue
            name = s.get('name', '')
            singer = '&'.join(a.get('name', '') for a in s.get('artists', []))
            pic = s.get('album', {}).get('picUrl', '') or ''
            vods.append({
                "vod_id": f"wy_{sid}",
                "vod_name": f"[网易] {name}",
                "vod_pic": pic,
                "vod_remarks": singer,
                "vod_actor": singer
            })
        return vods

    # ========== 酷狗 ==========
    def _search_kg(self, key):
        url = f'http://mobilecdn.kugou.com/api/v3/search/song?format=json&keyword={quote(key)}&page=1&pagesize=20'
        r = requests.get(url, headers={**self.header, 'Referer': 'http://m.kugou.com/'}, timeout=10)
        data = json.loads(r.text)
        songs = data.get('data', {}).get('info', [])
        vods = []
        for s in songs:
            hashv = s.get('hash', '')
            if not hashv:
                continue
            name = s.get('songname', '')
            singer = s.get('singername', '')
            pic = s.get('album_id', '')
            pic_url = f"https://img.sakula.com/member_album/{pic}/240x240.jpg" if pic else ''
            vods.append({
                "vod_id": f"kg_{hashv}",
                "vod_name": f"[酷狗] {name}",
                "vod_pic": pic_url,
                "vod_remarks": singer,
                "vod_actor": singer,
                "vod_content": json.dumps({"hash": hashv}, ensure_ascii=False)
            })
        return vods

    # ========== 酷我 ==========
    def _search_kw(self, key):
        url = f'https://search.kuwo.cn/r.s?client=kt&all={quote(key)}&pn=0&rn=20&ver=kwplayer_ar_12.2.0.0&ft=music&vipver=1&encoding=utf8&rformat=json&mobi=1'
        r = requests.get(url, headers={**self.header, 'Referer': 'https://www.kuwo.cn/'}, timeout=10)
        data = json.loads(r.text)
        songs = data.get('abslist', [])
        vods = []
        for s in songs:
            rid = s.get('MUSICRID', '').replace('MUSIC_', '')
            if not rid:
                continue
            name = s.get('SONGNAME', '')
            singer = s.get('ARTIST', '')
            pic = f"https://img1.kuwo.cn/star/albumcover/300/{s.get('ALBUMID', '')}.jpg"
            vods.append({
                "vod_id": f"kw_{rid}",
                "vod_name": f"[酷我] {name}",
                "vod_pic": pic,
                "vod_remarks": singer,
                "vod_actor": singer
            })
        return vods

    # ========== 咪咕 ==========
    def _search_mg(self, key):
        url = f'https://jadeite.migu.cn/music_search/v3/search/searchAll?text={quote(key)}&pageNo=1&pageSize=20'
        r = requests.get(url, headers={**self.header, 'Referer': 'https://m.music.migu.cn/'}, timeout=10)
        data = json.loads(r.text)
        songs = data.get('songResultData', {}).get('result', [])
        vods = []
        for s in songs:
            cid = s.get('copyrightId', '') or s.get('contentId', '')
            if not cid:
                continue
            name = s.get('songName', '')
            singer = s.get('singer', '') or ''
            pic = s.get('albumImgs', [{}])[0].get('img', '') if s.get('albumImgs') else ''
            vods.append({
                "vod_id": f"mg_{cid}",
                "vod_name": f"[咪咕] {name}",
                "vod_pic": pic,
                "vod_remarks": singer,
                "vod_actor": singer
            })
        return vods

    def detailContent(self, ids):
        # 直接返回播放（音乐源详情=播放）
        vid = str(ids[0]) if isinstance(ids, (list, tuple)) else str(ids)
        return {"list": [{"vod_id": vid, "vod_name": vid, "vod_play_from": "直链", "vod_play_url": f"播放${vid}"}]}

    def playerContent(self, flag, id, vipFlags=None):
        """多平台播放解析"""
        try:
            vid = id
            if vid.startswith('wy_'):
                return self._play_wy(vid[3:])
            elif vid.startswith('kw_'):
                return self._play_kw(vid[3:])
        except Exception:
            pass
        return {"parse": 0, "url": id, "header": {}}

    # QQ播放
    def _play_qq(self, mid):
        # QQ音乐播放: 用 vkey 接口
        url = f'https://u6.y.qq.com/cgi-bin/musicu.fcg?format=json&data={quote(json.dumps({"req_0": {"module": "vkey.GetVkeyServer", "method": "CgiGetVkey", "param": {"guid": "10000", "songmid": [mid], "songtype": [0], "uin": "0", "loginflag": 1, "platform": "20"}}}, separators=(",", ":")))}'
        r = requests.get(url, headers={**self.header, 'Referer': 'https://y.qq.com/'}, timeout=10)
        data = json.loads(r.text)
        purl = data.get('req_0', {}).get('data', {}).get('midurlinfo', [{}])[0].get('purl', '')
        if purl:
            return {"parse": 0, "url": f"https://dl.stream.qqmusic.qq.com/{purl}", "header": {}}
        # 兜底: 试听地址
        return {"parse": 0, "url": f"https://y.qq.com/n/ryqq/songDetail/{mid}", "header": {}}

    # 网易播放
    def _play_wy(self, sid):
        # 网易云播放: 官方外链接口
        url = f'http://music.163.com/song/media/outer/url?id={sid}.mp3'
        return {"parse": 0, "url": url, "header": {}}

    # 酷狗播放
    def _play_kg(self, hashv):
        # 酷狗播放: get_res_privilege 接口
        url = f'http://media.store.kugou.com/v1/get_res_privilege'
        body = json.dumps({"appid": 1005, "clientver": 8000, "mid": "0", "dfid": "-", "key": hashv, "platid": 4, "type": 2, "behavior": "play", "param": {"hash": hashv, "pid": 1, "cmd": 25, "version": 8000}})
        r = requests.post(url, data=body, headers={**self.header, 'Content-Type': 'application/json', 'Referer': 'http://m.kugou.com/'}, timeout=10)
        data = json.loads(r.text)
        play_url = data.get('data', {}).get('play_url', '')
        if play_url:
            return {"parse": 0, "url": play_url, "header": {}}
        return {"parse": 0, "url": hashv, "header": {}}

    # 酷我播放
    def _play_kw(self, rid):
        url = f'https://antiserver.kuwo.cn/anti.s?type=convert_url&rid={rid}&format=mp3&response=url'
        r = requests.get(url, headers={**self.header, 'Referer': 'https://www.kuwo.cn/'}, timeout=10)
        play_url = r.text.strip()
        if play_url.startswith('http'):
            return {"parse": 0, "url": play_url, "header": {}}
        return {"parse": 0, "url": rid, "header": {}}

    # 咪咕播放
    def _play_mg(self, cid):
        url = f'https://app.c.nf.migu.cn/MIGUM3.0/v1.0/content/sub/listenSong.do?toneFlag=HQ&netType=00&userId=155MM1290D3201708IM650002311131575&ua=Android_migu&version=5.1&copyrightId=0&contentId={cid}&resourceType=2&channel=0'
        r = requests.get(url, headers={**self.header, 'Referer': 'https://m.music.migu.cn/'}, timeout=10)
        data = json.loads(r.text)
        play_url = data.get('playUrl', '') or ''
        if play_url:
            return {"parse": 0, "url": play_url, "header": {}}
        return {"parse": 0, "url": cid, "header": {}}

    def localProxy(self, param):
        return None
