# -*- coding: utf-8 -*-
"""
河马剧场 - kuaikaw.cn  (TVBox Spider)

站点性质：Next.js（SSG/SSR）短剧站。所有页面数据都内联在
<script id="__NEXT_DATA__"> 里（服务端已渲染好 JSON），无需签名。
搜索走客户端接口 POST /seo/video/6007（返回 JSON）。

已实测验证的关键结论：
1. 路由：
   首页        /
   分类        /browse/{typeThreeId}            分页 /browse/{typeThreeId}/{page}
   （typeThreeId=0 表示「全部」；每页 10 条，站点约 450 页）
   详情页      /drama/{bookId}                   数据在 __NEXT_DATA__.props.pageProps
   播放页      /episode/{bookId}/{chapterId}     数据在同一位置，含 chapterVideoVo
   搜索        POST /seo/video/6007  body={"sourceType":1,"keyword":kw,"index":page}
2. 页面数据位置：
   __NEXT_DATA__.props.pageProps
     - 详情：bookInfoVo(bookName/coverWap/introduction/statusDesc...)
             + chapterList([{chapterId,chapterName,isCharge,chapterVideoVo}])
     - 分类：bookList([{bookId,bookName,coverWap,introduction}]) + page + pages
3. 播放地址：
   chapterList[i].chapterVideoVo 内含 mp4 / m3u8 直链（同一地址），
   encrypt 无关，直接可播（实测 https 返回视频文件）。
4. **重要局限**：该站是付费短剧站，每部剧仅【前 5 集】免费且 SSR 数据里带
   chapterVideoVo；第 6 集起 isCharge=1 且没有 chapterVideoVo（需登录/付费）。
   因此 playerContent 对未解锁集数只能返回空地址，这是站点侧限制，非插件问题。
5. 请求头带 pname: www.kuaikaw.cn 即可访问搜索接口。
"""
import re
import json
import time
import requests
from urllib.parse import quote

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        def __init__(self):
            pass


class Spider(BaseSpider):
    # ==================== 基础配置 ====================
    name = "河马剧场"
    base_url = "https://www.kuaikaw.cn"
    site_url = "https://www.kuaikaw.cn"

    searchable = 1
    quickSearch = 1
    filterable = 0
    changeable = 1

    # 限速：避免请求过密被封
    _min_req_interval = 0.5
    _last_req_ts = 0.0
    _cache = {}
    _cache_ttl = 1800

    _headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"),
        "pname": "www.kuaikaw.cn",
        "Accept": "text/html,application/json,*/*",
    }

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self._session = requests.Session()
        self._session.headers.update(self._headers)
        self._next_re = re.compile(
            r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)

    # ==================== 通用工具 ====================
    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        if not url:
            return False
        u = url.lower()
        return (".m3u8" in u or ".mp4" in u or ".flv" in u or ".ts" in u)

    def manualVideoCheck(self):
        return False

    def _log(self, msg):
        try:
            print("[%s] %s" % (self.name, msg))
        except Exception:
            pass

    def _throttle(self):
        wait = self._min_req_interval - (time.time() - self._last_req_ts)
        if wait > 0:
            time.sleep(wait)
        self._last_req_ts = time.time()

    def _get_html(self, url):
        self._throttle()
        try:
            r = self._session.get(url, timeout=20)
            r.encoding = "utf-8"
            return r.text or ""
        except Exception as e:
            self._log("请求失败 %s: %s" % (url, e))
            return ""

    def _get_next_data(self, url):
        """抓取页面并解析 __NEXT_DATA__ JSON"""
        html = self._get_html(url)
        if not html:
            return None
        m = self._next_re.search(html)
        if not m:
            return None
        try:
            return json.loads(m.group(1))
        except Exception:
            return None

    def _abs_pic(self, pic):
        if not pic:
            return ""
        if pic.startswith("//"):
            return "https:" + pic
        return pic

    def _card(self, b):
        return {
            "vod_id": str(b.get("bookId") or ""),
            "vod_name": b.get("bookName") or "",
            "vod_pic": self._abs_pic(b.get("coverWap")),
            "vod_remarks": b.get("statusDesc") or b.get("introduction", "")[:20],
        }

    # ==================== 首页 ====================
    def _home_props(self):
        d = self._get_next_data(self.base_url + "/")
        if not d:
            return {}
        return d.get("props", {}).get("pageProps", {}) or {}

    def homeContent(self, filter=None):
        props = self._home_props()
        tags = props.get("typeThreeList") or []
        classes = [{"type_id": "0", "type_name": "全部"}]
        for t in tags:
            ids = t.get("typeThreeIds") or []
            if not ids:
                continue
            classes.append({"type_id": str(ids[0]), "type_name": t.get("name") or ""})
        # 去重、限制数量（TVBox 分类过多体验差）
        seen = set()
        out = []
        for c in classes:
            if c["type_id"] in seen:
                continue
            seen.add(c["type_id"])
            out.append(c)
            if len(out) >= 24:
                break
        return {"class": out, "filters": {}}

    def homeVideoContent(self):
        props = self._home_props()
        vids = []
        seen = set()
        for col in props.get("seoColumnVos") or []:
            for b in col.get("bookInfos") or []:
                bid = str(b.get("bookId") or "")
                if not bid or bid in seen:
                    continue
                seen.add(bid)
                vids.append(self._card(b))
        if not vids:
            # 退回分类第一页
            cc = self.categoryContent("0", 1, False, None)
            vids = cc.get("list", [])
        return {"list": vids}

    # ==================== 分类 ====================
    def categoryContent(self, tid, pg, filter, extend):
        pg = max(1, int(pg or 1))
        tid = str(tid or "0")
        url = "%s/browse/%s" % (self.base_url, tid)
        if pg > 1:
            url = "%s/browse/%s/%d" % (self.base_url, tid, pg)
        self._log("分类请求: " + url)
        d = self._get_next_data(url)
        if not d:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 10, "total": 0}
        pp = d.get("props", {}).get("pageProps", {}) or {}
        items = [self._card(b) for b in (pp.get("bookList") or [])]
        pages = int(pp.get("pages") or 1)
        return {
            "list": items,
            "page": pg,
            "pagecount": pages,
            "limit": 10,
            "total": len(items) * pages,
        }

    # ==================== 搜索 ====================
    def searchContent(self, key, quick=False, pg="1"):
        pg = max(1, int(pg or 1))
        url = self.base_url + "/seo/video/6007"
        body = {"sourceType": 1, "keyword": key, "index": pg}
        self._log("搜索请求: %s -> %s" % (key, url))
        self._throttle()
        try:
            r = self._session.post(
                url, data=json.dumps(body),
                headers={"Content-Type": "application/json"},
                timeout=20)
            data = (r.json() or {}).get("data", {}) or {}
        except Exception as e:
            self._log("搜索失败: %s" % e)
            return {"list": []}
        items = [self._card(b) for b in (data.get("bookList") or [])]
        return {"list": items}

    # ==================== 详情 ====================
    def detailContent(self, array):
        ids = array
        if isinstance(array, (list, tuple)):
            ids = array[0] if array else ""
        ids = str(ids)
        url = "%s/drama/%s" % (self.base_url, ids)
        self._log("详情请求: " + url)
        d = self._get_next_data(url)
        if not d:
            return {"list": []}
        pp = d.get("props", {}).get("pageProps", {}) or {}
        info = pp.get("bookInfoVo") or {}
        chapters = pp.get("chapterList") or []

        parts = []
        for c in chapters:
            cid = str(c.get("chapterId") or "")
            cname = c.get("chapterName") or ("第%s集" % c.get("chapterIndex"))
            # 播放标识：bookId_chapterId
            parts.append("%s$%s_%s" % (cname, ids, cid))
        play_url = "#".join(parts) if parts else ""

        type_three = info.get("bookTypeThree") or []
        vod_class = ",".join([t.get("name", "") for t in type_three if t.get("name")])

        item = {
            "vod_id": ids,
            "vod_name": info.get("bookName") or "",
            "vod_pic": self._abs_pic(info.get("coverWap")),
            "vod_remarks": info.get("statusDesc") or "",
            "vod_content": info.get("introduction") or "",
            "vod_actor": ",".join([x for x in [info.get("actor"), info.get("actress")] if x]),
            "type_name": vod_class,
            "vod_play_from": "河马剧场",
            "vod_play_url": play_url,
        }
        self._log("详情解析成功: %s 集数=%d" % (item["vod_name"], len(chapters)))
        return {"list": [item]}

    # ==================== 播放 ====================
    def playerContent(self, flag, id, vipFlags):
        # id 形如 "bookId_chapterId"
        book_id, chapter_id = "", ""
        if isinstance(id, str) and "_" in id:
            book_id, chapter_id = id.split("_", 1)
        else:
            chapter_id = str(id)

        url = "%s/episode/%s/%s" % (self.base_url, book_id, chapter_id)
        self._log("播放请求: " + url)
        d = self._get_next_data(url)
        result = {"parse": 0, "url": "", "header": {"User-Agent": self._headers["User-Agent"]}}
        if not d:
            return result
        pp = d.get("props", {}).get("pageProps", {}) or {}
        chapters = pp.get("chapterList") or []
        cur = str(pp.get("chapterId") or chapter_id)

        target = None
        for c in chapters:
            if str(c.get("chapterId")) == cur:
                target = c
                break
        if target is None and chapters:
            target = chapters[0]

        if target:
            cv = target.get("chapterVideoVo") or {}
            m3u8 = cv.get("m3u8") or cv.get("mp4") or ""
            if m3u8:
                result["url"] = m3u8
                self._log("播放URL: " + m3u8[:100])
            else:
                self._log("该集未解锁/无视频源（付费短剧限制）")
        return result

    # ==================== 其他 ====================
    def localProxy(self, param):
        return None

    def destroy(self):
        try:
            self._session.close()
        except Exception:
            pass


if __name__ == "__main__":
    s = Spider()
    print("classes:", [(c["type_id"], c["type_name"]) for c in s.homeContent()["class"][:8]])
    hv = s.homeVideoContent()
    print("home videos:", len(hv["list"]), hv["list"][0] if hv["list"] else None)
    cc = s.categoryContent("0", 1, False, None)
    print("category 全部:", len(cc["list"]), "pagecount:", cc["pagecount"])
    sc = s.searchContent("总裁", False, "1")
    print("search 总裁:", len(sc["list"]))
    det = s.detailContent(["41000100525"])
    v = det["list"][0]
    print("detail:", v["vod_name"], "eps:", len(v["vod_play_url"].split("#")))
    ep = v["vod_play_url"].split("#")[0].split("$", 1)[1]
    pc = s.playerContent("河马剧场", ep, None)
    print("play:", pc["url"][:100] if pc["url"] else "NO URL")