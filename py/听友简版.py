# -*- coding: utf-8 -*-
"""听友FM 精简诊断版: homeContent 返回固定分类（无网络/加密依赖）"""
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        def homeContent(self, filter=False): return {"class": [], "list": [], "filters": {}}
        def categoryContent(self, tid, pg, filter=False, extend=''): return {"list": []}
        def detailContent(self, ids): return {"list": []}
        def searchContent(self, key, quick, pg='1'): return {"list": []}
        def playerContent(self, flag, id, vipFlags=None): return {"parse": 0, "url": ""}
        def init(self, extend=''): pass
        def destroy(self): pass


class Spider(BaseSpider):
    BASE = "https://tingyou.fm"
    UA = "Mozilla/5.0"

    def init(self, extend=''):
        pass

    def homeContent(self, filter=False):
        cls_ = [
            {"type_id": "46", "type_name": "玄幻奇幻"},
            {"type_id": "11", "type_name": "武侠小说"},
            {"type_id": "19", "type_name": "言情通俗"},
        ]
        lst = [
            {"vod_id": "3879657962", "vod_name": "三体(1-3部)", "vod_pic": "https://file.tingyou8.vip/pic/5DD07C7E68BF50C.jpg", "vod_remarks": "261集"},
            {"vod_id": "9783312385", "vod_name": "剑来", "vod_pic": "https://file.tingyou8.vip/pic/I7I0081G467902.gif", "vod_remarks": "5329集"},
        ]
        return {"class": cls_, "list": lst, "filters": {}}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        return {"list": [{"vod_id": tid, "vod_name": f"分类{tid}书籍", "vod_pic": "", "vod_remarks": "10集"}]}

    def detailContent(self, ids):
        vod_id = ids[0] if ids else ""
        return {"list": [{"vod_id": vod_id, "vod_name": "听友FM测试详情", "vod_pic": "",
                          "vod_play_from": "听友FM", "vod_play_url": "第1集$1#第2集$2"}]}

    def searchContent(self, key, quick, pg="1"):
        return {"list": [{"vod_id": "s1", "vod_name": f"搜索:{key}", "vod_pic": "", "vod_remarks": "3集"}]}

    def playerContent(self, flag, id, vipFlags=None):
        return {"parse": 0, "url": "https://tingyou.fm/api/payload"}

    def destroy(self):
        pass
