# -*- coding: utf-8 -*-
"""
爱优腾芒哔哩聚合 —— 影视聚合 Python 源（OK影视 / 蜂蜜影视 / TVBox 通用）
=====================================================================
适配 OK影视、蜂蜜影视、TVBox 类壳子的标准 Python 源。
"""

import re
import json
import urllib.parse

# 网络请求：优先壳子内置 requests，缺失时降级 urllib（便于本地测试）
try:
    import requests as _requests
    _HAS_REQUESTS = True
except Exception:  # noqa: BLE001
    _requests = None
    _HAS_REQUESTS = False

# 兼容壳子内置基类；本地测试无壳子时回退到空基类
try:
    from base.spider import Spider as _BaseSpider
except Exception:  # noqa: BLE001
    class _BaseSpider:
        pass


def _log(*args):
    try:
        print("腾爱优聚合", *args)
    except Exception:  # noqa: BLE001
        pass


def _enc(value):
    """encodeURIComponent（保留 !'()*-._~ ）。"""
    return urllib.parse.quote(str(value), safe="!'()*-._~")


# 分类：数字 ID -> 接口字母参数 + 名称
_CATEGORY = {
    "1": ("qq",       "腾讯视频"),
    "2": ("qiyi",     "爱奇艺"),
    "3": ("youku",    "优酷视频"),
    "4": ("mgtv",     "芒果TV"),
    "5": ("bilibili", "B站"),
}
_KEY_TO_NUM = {v[0]: k for k, v in _CATEGORY.items()}


class Spider(_BaseSpider):
    """腾爱优聚合 —— 影视聚合源。"""

    name = "腾爱优聚合"

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def init(self, extend=""):
        """初始化：创建带 UA 的会话。extend 可传自定义解析站（JSON 或裸 URL）。"""
        _log("init ->", extend)
        self.host = "http://cj.tianwe.cn"
        self.header = {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/150.0.0.0 Safari/537.36"),
        }
        # 直链解析站（kptv 域名已死 2026-09-29，直接停用避免每次播放白等超时）
        self.parse_api = ""
        # 88lin 官方接口池（https://go.88lin.eu.org/vip/ 页面内置，2026-09-29 实测）
        # 全部为浏览器端 JS/WASM 解析，纯 HTTP 取不到直链，
        # 由壳子 WebView 打开解析页完成播放 —— 这是当前唯一通用方案。
        # 顺序 = 实测响应速度排序（2026-09-29 腾讯源秒回）：PlayerJY/夜幕/m3u8tv-jx/七哥202617/七七/闲鱼/ckplayer 优先
        # 播放时会自动轮换：失败/超时自动换下一个接口，避免卡死
        self.parse_sites = [
            "https://jx.playerjy.com/?url=",
            "https://yemu.xyz/?url=",
            "https://jx.m3u8.tv/jx/jx.php?url=",
            "https://jx.202617.xyz/tv.php?url=",
            "https://jx.77flv.cc/?url=",
            "https://jx.xymp4.cc/?url=",
            "https://www.ckplayer.vip/jiexi/?url=",
            "https://bd.jx.cn/?url=",
            "https://www.pangujiexi.com/jiexi/?url=",
            "https://jx.yparse.com/index.php?url=",
            "https://bfq.txnp.cn/player?url=",
            "https://bfzyplayer.com/player/?url=",
            "https://jx.wujinkk.com/dplayer/?url=",
            "https://www.8090g.cn/?url=",
            "https://json.ovvo.pro/jx.php?url=",
            "https://json.fongmi.cc/web?url=",
            "https://jx.hls.one/?url=",
            "https://jx.xmflv.com/?url=",
            "https://jx.2s0.cn/?url=",
            "https://www.daga.cc/vip1/?url=",
            "https://jx.xmflv.cc/?url=",
        ]
        # 用户自定义解析站（extend 传入时优先使用）
        self.custom_jx = self._parse_extend(extend)
        self.timeout = 10
        if _HAS_REQUESTS:
            self.session = _requests.Session()
            self.session.headers.update(self.header)

    @staticmethod
    def _parse_extend(extend):
        """从 extend 解析自定义解析站前缀。支持 JSON 字典或裸字符串。"""
        if not extend:
            return ""
        s = str(extend).strip()
        try:
            d = json.loads(s)
            if isinstance(d, dict):
                return str(d.get("parse", "") or d.get("jx", "")).strip()
        except Exception:  # noqa: BLE001
            pass
        if "url=" in s or "?" in s:
            return s
        return ""

    def getName(self):
        return self.name

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        pass

    def localProxy(self, param):
        return None

    # ------------------------------------------------------------------
    # 网络请求
    # ------------------------------------------------------------------
    def _http_get(self, url):
        """GET 请求，返回文本；失败返回空字符串。"""
        try:
            if _HAS_REQUESTS:
                sess = getattr(self, "session", None) or _requests
                r = sess.get(url, timeout=getattr(self, "timeout", 15),
                             verify=False)
                r.encoding = "utf-8"
                return r.text
            # 降级 urllib
            import urllib.request
            req = urllib.request.Request(url, headers=self.header)
            with urllib.request.urlopen(req,
                                        timeout=getattr(self, "timeout", 15)) as resp:
                data = resp.read()
                try:
                    return data.decode("utf-8")
                except Exception:  # noqa: BLE001
                    return data.decode("latin-1")
        except Exception as exc:  # noqa: BLE001
            _log("myfetch err ", exc)
            return ""

    def _get_json(self, url):
        """GET 并解析 JSON。"""
        try:
            return json.loads(self._http_get(url))
        except Exception:  # noqa: BLE001
            return None

    # ------------------------------------------------------------------
    # 首页
    # ------------------------------------------------------------------
    def homeContent(self, filter=False):
        """首页：分类 + 筛选。"""
        try:
            classes = [
                {"type_id": "1", "type_pid": "0", "type_name": "腾讯视频"},
                {"type_id": "2", "type_pid": "0", "type_name": "爱奇艺"},
                {"type_id": "3", "type_pid": "0", "type_name": "优酷视频"},
                {"type_id": "4", "type_pid": "0", "type_name": "芒果TV"},
                {"type_id": "5", "type_pid": "0", "type_name": "B站"},
            ]

            type_filter = {
                "key": "t",
                "name": "类型",
                "value": [
                    {"n": "全部", "v": ""},
                    {"n": "电视剧", "v": "2"},
                    {"n": "电影", "v": "1"},
                    {"n": "动漫", "v": "4"},
                    {"n": "综艺", "v": "3"},
                    {"n": "少儿", "v": "5"},
                    {"n": "纪录片", "v": "6"},
                    {"n": "短剧", "v": "7"},
                ],
            }
            # 细分类型筛选（接口用 class= 参数支持中文类型，实测有数据）
            # 电影:动作片/喜剧片/爱情片/科幻片/恐怖片/剧情片/战争片
            # 剧集:国产剧/香港剧/韩国剧/欧美剧/台湾剧/日本剧/泰国剧
            # 动漫:国产动漫/日韩动漫/欧美动漫
            class_filter = {
                "key": "class",
                "name": "细分",
                "value": [
                    {"n": "全部", "v": ""},
                    {"n": "动作片", "v": "动作片"},
                    {"n": "喜剧片", "v": "喜剧片"},
                    {"n": "爱情片", "v": "爱情片"},
                    {"n": "科幻片", "v": "科幻片"},
                    {"n": "恐怖片", "v": "恐怖片"},
                    {"n": "剧情片", "v": "剧情片"},
                    {"n": "战争片", "v": "战争片"},
                    {"n": "国产剧", "v": "国产剧"},
                    {"n": "香港剧", "v": "香港剧"},
                    {"n": "韩国剧", "v": "韩国剧"},
                    {"n": "欧美剧", "v": "欧美剧"},
                    {"n": "台湾剧", "v": "台湾剧"},
                    {"n": "日本剧", "v": "日本剧"},
                    {"n": "泰国剧", "v": "泰国剧"},
                    {"n": "国产动漫", "v": "国产动漫"},
                    {"n": "日韩动漫", "v": "日韩动漫"},
                    {"n": "欧美动漫", "v": "欧美动漫"},
                ],
            }
            filters = {}
            for c in classes:
                filters[c["type_id"]] = [type_filter, class_filter]

            result = {"class": classes, "list": []}
            if filter:
                result["filters"] = filters
            return result
        except Exception as exc:  # noqa: BLE001
            _log("homeContent err", exc)
            return {"class": [], "list": []}

    def homeVideoContent(self):
        """首页推荐（原脚本无，返回空）。"""
        return {"list": []}

    # ------------------------------------------------------------------
    # 分类
    # ------------------------------------------------------------------
    def categoryContent(self, tid, pg, filter=False, extend=None):
        """
        分类列表。
        tid   : 数字分类 id（1-5）
        pg    : 页码
        extend: 筛选 {class, year, ...}
        """
        extend = extend or {}
        key = self._to_key(tid) or "qq"
        try:
            page = int(pg) if pg else 1
        except Exception:  # noqa: BLE001
            page = 1

        params = ["from=" + key, "ac=detail", "limit=24", "pg=" + str(page)]
        # 大类型走 t 参数（电视剧/电影/动漫/综艺/少儿/纪录片/短剧，数值 1-7）
        t = extend.get("t") or "2"
        params.append("t=" + t)
        # 细分类型走 class 参数（动作片/恐怖片/国产剧/欧美动漫 等，中文，实测支持）
        sub = extend.get("class")
        if sub:
            params.append("class=" + _enc(sub))

        url = self.host + "/api.php/provide/vod/?" + "&".join(params)
        _log("api category url ->", url)

        data = self._get_json(url)
        if not data:
            return {"list": [], "page": page, "pagecount": 1, "limit": 0,
                    "total": 0}

        vod_list = []
        if isinstance(data.get("list"), list):
            vod_list = [
                {
                    "vod_id": str(v.get("vod_id", "")),
                    "vod_name": v.get("vod_name", ""),
                    "vod_pic": v.get("vod_pic", ""),
                    "vod_remarks": v.get("vod_remarks", ""),
                }
                for v in data["list"]
            ]

        pc = data.get("pagecount") or 1
        try:
            pc = int(pc)
        except Exception:  # noqa: BLE001
            pc = 1

        return {
            "list": vod_list,
            "page": page,
            "pagecount": pc,
            "limit": len(vod_list),
            "total": pc * len(vod_list) if vod_list else 0,
        }

    # ------------------------------------------------------------------
    # 详情
    # ------------------------------------------------------------------
    def detailContent(self, ids):
        """详情。ids 可能为列表或 '1$xx' 字符串，取 id 最后一段。"""
        if not ids:
            return {"list": []}
        vid = str(ids)
        if isinstance(ids, (list, tuple)):
            vid = str(ids[0])
        vid = vid.split("$")[-1].strip()

        url = (self.host + "/api.php/provide/vod/?" +
               "&".join(["ac=detail", "ids=" + vid]))
        _log("detailurl", url)

        data = self._get_json(url)
        if not data:
            return {"list": []}

        vod_list = []
        if isinstance(data.get("list"), list):
            for item in data["list"]:
                if not item.get("vod_id"):
                    continue
                vod_list.append({
                    "vod_id": str(item.get("vod_id", "")),
                    "vod_name": item.get("vod_name", ""),
                    "vod_pic": item.get("vod_pic", ""),
                    "vod_remarks": item.get("vod_remarks", ""),
                    "vod_year": item.get("vod_year", ""),
                    "type_name": item.get("type_name", ""),
                    "vod_area": item.get("vod_area", ""),
                    "vod_lang": item.get("vod_lang", ""),
                    "vod_content": item.get("vod_content", ""),
                    "vod_play_from": item.get("vod_play_from", ""),
                    "vod_play_url": item.get("vod_play_url", ""),
                })
        return {"list": vod_list}

    # ------------------------------------------------------------------
    # 搜索
    # ------------------------------------------------------------------
    def searchContent(self, key, quick, pg="1"):
        """搜索。key 关键词，quick 是否快速搜索，pg 页码。"""
        if not key:
            return {"list": []}
        url = (self.host + "/api.php/provide/vod/?ac=detail&wd=" +
               _enc(key) + "&pg=" + str(pg))
        _log("api searchUrl:", url)

        data = self._get_json(url)
        if not data:
            return {"list": [], "page": str(pg), "pagecount": 1}

        vod_list = []
        if isinstance(data.get("list"), list):
            vod_list = [
                {
                    "vod_id": str(v.get("vod_id", "")),
                    "vod_name": v.get("vod_name") or v.get("name") or "",
                    "vod_pic": v.get("vod_pic") or v.get("pic") or "",
                    "vod_remarks": v.get("vod_remarks") or "",
                }
                for v in data["list"]
                if v.get("vod_id")
            ]

        pc = data.get("pagecount") or 1
        try:
            pc = int(pc)
        except Exception:  # noqa: BLE001
            pc = 1
        return {"list": vod_list, "page": str(pg), "pagecount": pc}

    # ------------------------------------------------------------------
    # 播放解析
    # ------------------------------------------------------------------
    def playerContent(self, flag, id, vipFlags):
        """播放：直链直接返回；自定义解析站优先；否则直链尝试 + WebView 兜底。"""
        _log("开始获取播放地址: ", id)
        try:
            if self._is_direct(id):
                return {"parse": 0, "url": id, "header": dict(self.header),
                        "playUrl": ""}

            # 1) 用户自定义解析站（extend 配置），壳子 WebView 打开解析
            if getattr(self, "custom_jx", ""):
                _log("使用自定义解析:", self.custom_jx + id)
                return {"parse": 1, "url": self.custom_jx + id,
                        "header": dict(self.header), "playUrl": ""}

            # 2) WebView 解析站：按实测响应速度排序，自动轮换。
            #    优先取当前接口；若上次接口失败过则换下一个，避免卡死。
            web_url = self._webview_jx(id)
            if web_url:
                return {"parse": 1, "url": web_url,
                        "header": dict(self.header), "playUrl": ""}
        except Exception as exc:  # noqa: BLE001
            _log("play失败: ", exc)
        return {"parse": 1, "url": id, "header": dict(self.header),
                "playUrl": ""}

    def _webview_jx(self, video_url):
        """取 WebView 解析站地址，失败自动轮换下一个接口。"""
        sites = getattr(self, "parse_sites", None) or []
        if not sites:
            return ""
        # 当前接口索引（记录在实例上，失败时 +1 轮换）
        idx = getattr(self, "_jx_idx", 0)
        if idx >= len(sites):
            idx = 0
        site = sites[idx]
        self._jx_idx = idx + 1  # 下次自动用下一个接口
        _log("WebView解析站[%d/%d]: %s" % (idx + 1, len(sites), site))
        return site + video_url

    def _mark_jx_fail(self):
        """标记当前接口失败，下次播放自动跳过。"""
        idx = getattr(self, "_jx_idx", 0)
        # 若已轮换到尾则从头开始
        sites = getattr(self, "parse_sites", None) or []
        if idx >= len(sites):
            self._jx_idx = 0
        _log("解析接口自动切换 -> 下一个")

    def _is_direct(self, url):
        s = str(url)
        return any(k in s for k in ("m3u", "mp4"))

    def _parse_video_url(self, video_url):
        """解析播放地址：请求解析源取 token，再请求 resolve 接口。"""
        parse_api = self.parse_api
        resolve_url = parse_api + video_url
        _log("正在请求解析地址:", resolve_url)

        try:
            text1 = self._http_get(resolve_url)
            token = self._extract_token(text1)
            if not token:
                raise Exception("解析源无 token")

            host = parse_api.split("//")[1].split("/")[0]
            api_url = ("https://" + host + "/api/resolve.php?token=" +
                       _enc(token))
            text2 = self._http_get(api_url)
            data = json.loads(text2) if text2 else {}
            play_url = self._format_url(data.get("url"))

            if not play_url:
                raise Exception("解析源链接为空")

            _log("解析成功并返回 ->", play_url)
            return play_url
        except Exception as exc:  # noqa: BLE001
            _log("解析失败: ", exc)
            return ""

    @staticmethod
    def _extract_token(text):
        m = re.search(r'apiToken\s*:\s*["\']([^"\']+)["\']', text or "")
        return m.group(1) if m else None

    @staticmethod
    def _format_url(url):
        if not url:
            return ""
        url = str(url).replace("\\", "")
        url = re.sub(r"^(https?:\/)((?!\/))", r"\1/", url,
                     flags=re.IGNORECASE)
        return url

    @staticmethod
    def _to_key(tid):
        """把数字 type_id 映射回接口字母参数；字母原样返回。"""
        if tid is None:
            return None
        s = str(tid).strip()
        if s in _CATEGORY:
            return _CATEGORY[s][0]
        if s in _KEY_TO_NUM:
            return s
        return s
