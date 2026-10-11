// TVBox 配置导入专用模板：MacCMS / 苹果CMS 采集（TVBox 的 type=1 / type=0）
// 由「聚阅独立自主版」导入页生成接口时自动使用，勿手动编辑。
// host 来自接口对象 jkdata.host（导入时写入）
let parse = {
    作者: '聚阅独立版',
    版本: '1',
    host: '',
    页码: {
        主页: true,
        分类: true,
        排行: true,
        更新: true
    },
    _host: function () {
        try {
            if (jkdata && jkdata.host) { return String(jkdata.host); }
        } catch (e) { }
        try {
            if (jkdata && jkdata.tmpl && jkdata.tmpl.配置 && jkdata.tmpl.配置.host) {
                return String(jkdata.tmpl.配置.host);
            }
        } catch (e2) { }
        return '';
    },
    // 拼接 MacCMS 接口地址
    _api: function (params) {
        let h = this._host();
        if (!h) { return ''; }
        if (h.indexOf('?') > -1) {
            return h + '&' + params;
        }
        return h + (h.endsWith('/') ? '' : '/') + 'api.php/provide/vod/?' + params;
    },
    _get: function (url) {
        try {
            let r = fetch(url, { timeout: 15000 });
            if (!r) { return null; }
            let s = String(r).trim();
            if (s.startsWith('{') || s.startsWith('[')) {
                return JSON.parse(s);
            }
            // 可能被包了一层
            let i = s.indexOf('{');
            if (i > -1) { return JSON.parse(s.substring(i)); }
        } catch (e) { }
        return null;
    },
    // 列表项 -> 海阔卡片
    _card: function (v) {
        let pic = v.vod_pic || '';
        if (pic && pic.startsWith('//')) { pic = 'https:' + pic; }
        return {
            title: v.vod_name || '',
            img: pic,
            desc: v.vod_remarks || (v.type_name || ''),
            url: 'https://' + '##' + String(v.vod_id) + '##' + (v.vod_name || '') + '##' + pic,
            col_type: 'movie_2'
        };
    },
    主页: function () {
        let d = [];
        let pg = parseInt(MY_PAGE || '1');
        let cls = '';
        try { cls = fyclass || ''; } catch (e) { }
        let url = this._api('ac=videolist&pg=' + pg + (cls ? '&t=' + encodeURI(cls) : ''));
        let j = this._get(url);
        if (!j || !j.list) { return d; }
        j.list.forEach((v) => {
            let c = this._card(v);
            if (c.title) { d.push(c); }
        });
        return d;
    },
    二级: function (url) {
        let id = '';
        try {
            let ss = String(url).split('##');
            id = ss[2] || ss[1] || '';
        } catch (e) { }
        let out = { list: [], desc: '', img: '' };
        if (!id) { return out; }
        let j = this._get(this._api('ac=videolist&ids=' + id));
        if (!j || !j.list || !j.list[0]) { return out; }
        let v = j.list[0];
        out.desc = String(v.vod_content || '').replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ');
        let pic = v.vod_pic || '';
        if (pic && pic.startsWith('//')) { pic = 'https:' + pic; }
        out.img = pic;
        // 线路 + 集数
        let froms = String(v.vod_play_from || '').split('$$$');
        let urls = String(v.vod_play_url || '').split('$$$');
        let list = [];
        for (let i = 0; i < urls.length; i++) {
            let eps = urls[i].split('#');
            for (let k = 0; k < eps.length; k++) {
                let one = eps[k].split('$');
                let nm = one[0] || ('第' + (k + 1) + '集');
                let u = one[1] || one[0] || '';
                if (/^https?:/.test(u)) {
                    // 直链，可直接播
                } else if (u.endsWith('.m3u8') || u.indexOf('m3u8') > -1) {
                    // m3u8
                }
                list.push({
                    title: (froms.length > 1 ? ('[' + (froms[i] || ('线' + (i + 1))) + ']') : '') + nm,
                    url: u
                });
            }
            // 默认只展开第一条线路，其余按需
            if (list.length > 0 && i === 0) { break; }
        }
        out.list = list;
        return out;
    },
    搜索: function (name) {
        let d = [];
        let pg = parseInt(MY_PAGE || '1');
        let j = this._get(this._api('ac=videolist&wd=' + encodeURI(name) + '&pg=' + pg));
        if (!j || !j.list) { return d; }
        j.list.forEach((v) => {
            let c = this._card(v);
            if (c.title) { d.push(c); }
        });
        return d;
    },
    解析: function (url) {
        return url;
    },
    最新: function (url) {
        return '';
    }
}
