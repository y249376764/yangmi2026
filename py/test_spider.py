# -*- coding: utf-8 -*-
"""测试蜘蛛: 返回固定数据, 不依赖任何站点/加密"""
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
    def init(self, extend=''):
        pass

    def homeContent(self, filter=False):
        return {
            "class": [
                {"type_id": "1", "type_name": "测试分类1"},
                {"type_id": "2", "type_name": "测试分类2"},
            ],
            "list": [
                {"vod_id": "1", "vod_name": "测试书籍A", "vod_pic": "", "vod_remarks": "10集"},
                {"vod_id": "2", "vod_name": "测试书籍B", "vod_pic": "", "vod_remarks": "20集"},
            ],
            "filters": {},
        }

    def categoryContent(self, tid, pg, filter=False, extend=""):
        return {"list": [{"vod_id": tid + "-1", "vod_name": f"分类{tid}第{pg}页书", "vod_pic": "", "vod_remarks": "5集"}]}

    def detailContent(self, ids):
        vod_id = ids[0] if ids else ""
        return {"list": [{"vod_id": vod_id, "vod_name": "测试详情", "vod_pic": "",
                          "vod_play_from": "测试", "vod_play_url": "第1集$1#第2集$2"}]}

    def searchContent(self, key, quick, pg="1"):
        return {"list": [{"vod_id": "s1", "vod_name": f"搜索结果:{key}", "vod_pic": "", "vod_remarks": "3集"}]}

    def playerContent(self, flag, id, vipFlags=None):
        return {"parse": 0, "url": "https://www.tingyou.fm/api/payload"}
