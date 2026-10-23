js:
setPageTitle("TVBox 接口导入");
var Color = getItem('主题颜色', '#3399cc');
var bgTint = '#15' + String(Color).replace('#', '');
var CACHEF = 'hiker://files/_cache/Juying2/tvbox_preview.json';
var CFGF = 'hiker://files/rules/Src/Juying2/config.json';

function _pendingSrc() {
    var v = '';
    try { v = String(getMyVar('jybox_pending', '') || ''); } catch (e) { v = ''; }
    if (!v) { try { v = String(getMyVar('jybox_src', '') || ''); } catch (e2) { v = ''; } }
    return String(v).trim();
}
function _readCache() {
    var s = '';
    try { s = String(readFile(CACHEF) || ''); } catch (e) { s = ''; }
    if (!s) { return {}; }
    try { return JSON.parse(s) || {}; } catch (e2) { return {}; }
}
function _writeCache(o) {
    try { writeFile(CACHEF, JSON.stringify(o)); } catch (e) { }
}
function _clearCache() { try { deleteFile(CACHEF); } catch (e) { } }

function _bom(s) { return (s && s.charCodeAt(0) === 0xFEFF) ? s.substring(1) : s; }

function _stripComments(s) {
    var out = '', i = 0, n = s.length, inStr = false, quote = '', inLine = false, inBlock = false;
    while (i < n) {
        var c = s.charAt(i);
        if (inLine) { if (c === '\n' || c === '\r') { inLine = false; out += c; } i++; continue; }
        if (inBlock) {
            if (c === '*' && s.charAt(i + 1) === '/') { inBlock = false; i += 2; continue; }
            i++; continue;
        }
        if (inStr) {
            out += c;
            if (c === '\\') { out += s.charAt(i + 1) || ''; i += 2; continue; }
            if (c === quote) { inStr = false; }
            i++; continue;
        }
        if (c === '"' || c === "'") { inStr = true; quote = c; out += c; i++; continue; }
        if (c === '/' && s.charAt(i + 1) === '/') { inLine = true; i += 2; continue; }
        if (c === '/' && s.charAt(i + 1) === '*') { inBlock = true; i += 2; continue; }
        out += c; i++;
    }
    return out;
}

function _stripTrailingCommas(s) {
    var out = '', inStr = false, quote = '';
    for (var i = 0; i < s.length; i++) {
        var c = s.charAt(i);
        if (inStr) {
            out += c;
            if (c === '\\') { out += s.charAt(i + 1) || ''; i++; continue; }
            if (c === quote) { inStr = false; }
            continue;
        }
        if (c === '"' || c === "'") { inStr = true; quote = c; out += c; continue; }
        if (c === ',') {
            var j = i + 1;
            while (j < s.length && /\s/.test(s.charAt(j))) { j++; }
            if (s.charAt(j) === '}' || s.charAt(j) === ']') { continue; }
        }
        out += c;
    }
    return out;
}

function _singleToDouble(s) {
    var out = '', i = 0, n = s.length;
    while (i < n) {
        var c = s.charAt(i);
        if (c !== "'") { out += c; i++; continue; }
        var j = i + 1, buf = '';
        while (j < n) {
            var d = s.charAt(j);
            if (d === '\\') { buf += d + (s.charAt(j + 1) || ''); j += 2; continue; }
            if (d === "'") { break; }
            buf += d; j++;
        }
        if (j >= n) { out += c; i++; continue; }
        if (buf.indexOf('"') >= 0) { out += c; i++; continue; }
        out += '"' + buf + '"';
        i = j + 1;
    }
    return out;
}

function _quoteKeys(s) {
    // JSON5 允许 {name: 'x'} 这种无引号键；JSON.parse 不认 -> 补引号
    // 只在“{ 或 , 之后 + 标识符 + :”处动手，且全程字符串感知
    var out = '', i = 0, n = s.length, inStr = false, quote = '';
    while (i < n) {
        var c = s.charAt(i);
        if (inStr) {
            out += c;
            if (c === '\\') { out += s.charAt(i + 1) || ''; i += 2; continue; }
            if (c === quote) { inStr = false; }
            i++; continue;
        }
        if (c === '"' || c === "'") { inStr = true; quote = c; out += c; i++; continue; }
        if (c === '{' || c === ',') {
            out += c; i++;
            var sp = '';
            while (i < n && /\s/.test(s.charAt(i))) { sp += s.charAt(i); i++; }
            out += sp;
            var idf = '';
            var j = i;
            while (j < n && /[A-Za-z0-9_$]/.test(s.charAt(j))) { idf += s.charAt(j); j++; }
            if (idf && /[A-Za-z_$]/.test(idf.charAt(0))) {
                var k = j;
                while (k < n && /\s/.test(s.charAt(k))) { k++; }
                if (s.charAt(k) === ':') {
                    out += '"' + idf + '"';
                    i = j;
                    continue;
                }
            }
            continue;
        }
        out += c; i++;
    }
    return out;
}

function _cutBalanced(s) {
    var st = s.indexOf('{');
    if (st < 0) { return ''; }
    var depth = 0, inStr = false, quote = '';
    for (var i = st; i < s.length; i++) {
        var c = s.charAt(i);
        if (inStr) {
            if (c === '\\') { i++; continue; }
            if (c === quote) { inStr = false; }
            continue;
        }
        if (c === '"' || c === "'") { inStr = true; quote = c; continue; }
        if (c === '{') { depth++; }
        else if (c === '}') { depth--; if (depth === 0) { return s.substring(st, i + 1); } }
    }
    return '';
}

function _parseLoose(raw) {
    var s0 = _bom(String(raw || ''));
    var s1 = _stripComments(s0);
    var s2 = _stripTrailingCommas(s1);
    var s3 = _cutBalanced(s2);
    var s4 = _stripTrailingCommas(_quoteKeys(_singleToDouble(s2)));
    var tries = [
        ['原文', s0],
        ['去注释', s1],
        ['去尾逗号', s2],
        ['补键引号', s4],
        ['组合清洗', _stripTrailingCommas(_stripComments(s3 || s2))],
        ['单引号转双引号', _stripTrailingCommas(_singleToDouble(s2))]
    ];
    if (s3) { tries.push(['截取首个完整对象', s3]); }
    if (s3) { tries.push(['截取+补键引号', _stripTrailingCommas(_quoteKeys(_singleToDouble(s3)))]); }
    for (var i = 0; i < tries.length; i++) {
        try {
            var o = JSON.parse(tries[i][1]);
            if (o && typeof o === 'object') { return { ok: true, obj: o, via: tries[i][0] }; }
        } catch (e) { }
    }
    var msg = '无法解析', pos = -1, sample = s4 || s3 || s2 || s0;
    try { JSON.parse(sample); } catch (e2) {
        msg = String((e2 && e2.message) || e2);
        var m = msg.match(/position\s+(\d+)/);
        if (m) { pos = parseInt(m[1], 10); }
    }
    return { ok: false, msg: msg, pos: pos, sample: sample };
}

function _expandUrl(s) {
    var out = [];
    var gh = s.match(/^https?:\/\/github\.com\/([^\/]+)\/([^\/]+)\/(?:blob|raw)\/([^\/]+)\/(.+)$/i);
    if (gh) {
        var p = gh[4].split('?')[0];
        out.push('https://cdn.jsdelivr.net/gh/' + gh[1] + '/' + gh[2] + '@' + gh[3] + '/' + p);
        out.push('https://fastly.jsdelivr.net/gh/' + gh[1] + '/' + gh[2] + '@' + gh[3] + '/' + p);
        out.push('https://raw.githubusercontent.com/' + gh[1] + '/' + gh[2] + '/' + gh[3] + '/' + p);
        out.push(s);
        return out;
    }
    var gt = s.match(/^https?:\/\/gitee\.com\/([^\/]+)\/([^\/]+)\/(?:blob|raw)\/([^\/]+)\/(.+)$/i);
    if (gt) {
        out.push('https://gitee.com/' + gt[1] + '/' + gt[2] + '/raw/' + gt[3] + '/' + gt[4].split('?')[0]);
        out.push(s);
        return out;
    }
    out.push(s);
    return out;
}

function _fetchText(src) {
    var s = String(src || '').trim();
    if (!s) { return { ok: false, log: ['输入为空'] }; }
    var h0 = s.charAt(0);
    if (h0 === '{' || h0 === '[') { return { ok: true, text: s, log: ['粘贴内容'] }; }
    if (!/^https?:\/\//i.test(s)) {
        var p = (s.indexOf('file://') === 0) ? s : ('file://' + s);
        try {
            var t = readFile(p) || '';
            if (t) { return { ok: true, text: t, log: ['本地文件'] }; }
        } catch (e) { }
        return { ok: false, log: ['本地文件读取失败'] };
    }
    var urls = [], base = _expandUrl(s), bi;
    for (bi = 0; bi < base.length; bi++) {
        urls.push(base[bi]);
        if (/^http:\/\//i.test(base[bi])) { urls.push(base[bi].replace(/^http:/i, 'https:')); }
    }
    var uas = ['Mozilla/5.0', 'okhttp/4.12.0'];
    var log = [];
    for (var i = 0; i < urls.length; i++) {
        for (var j = 0; j < uas.length; j++) {
            var r = '', err = '';
            try {
                r = String(fetch(urls[i], { timeout: 12000, headers: { 'User-Agent': uas[j], 'Accept': '*/*' } }) || '');
            } catch (e1) {
                err = String((e1 && e1.message) || e1);
                try { r = String(getContnet(urls[i]) || ''); } catch (e2) { r = ''; }
            }
            var tag = urls[i].replace(/^https?:\/\//i, '').substring(0, 46);
            if (r && r.trim()) {
                var hd = r.trim().charAt(0);
                if (hd === '{' || hd === '[') {
                    log.push('✔ ' + tag);
                    return { ok: true, text: r, log: log };
                }
                log.push('✘ ' + tag + ' 非JSON');
            } else {
                log.push('✘ ' + tag + ' ' + (err || '空响应').substring(0, 40));
            }
        }
    }
    return { ok: false, log: log };
}

function _strOf(v) {
    if (v === null || v === undefined) { return ''; }
    if (typeof v === 'string') { return v; }
    try { return JSON.stringify(v); } catch (e) { return String(v); }
}
function _hasExt(s, ext) {
    var t = _strOf(s);
    if (!t) { return false; }
    var i = t.indexOf(ext);
    while (i >= 0) {
        var nx = t.charAt(i + ext.length);
        if (nx === '' || !/[a-zA-Z0-9]/.test(nx)) { return true; }
        i = t.indexOf(ext, i + 1);
    }
    return false;
}

function _normalize(obj) {
    var arr = [];
    if (!obj) { return arr; }
    function push(s, k) {
        if (!s || typeof s !== 'object') { return; }
        var nm = String(s.name || s.key || k || '');
        var ext = _strOf(s.ext);
        arr.push({
            key: String(s.key || s.id || k || nm),
            name: nm,
            api: _strOf(s.api),
            code: _strOf(s.code),
            detail: _strOf(s.detail || s.playUrl),
            ext: ext,
            type: (s.type === undefined || s.type === null || s.type === '') ? 0 : Number(s.type),
            jar: _strOf(s.jar),
            hide: (s.hide === 1 || s.hide === true),
            searchable: s.searchable,
            adult: nm.indexOf('\uD83D\uDD1E') >= 0
        });
    }
    if (Object.prototype.toString.call(obj) === '[object Array]') {
        for (var i = 0; i < obj.length; i++) { push(obj[i], 'k' + i); }
        return arr;
    }
    for (var k in obj) {
        if (!Object.prototype.hasOwnProperty.call(obj, k)) { continue; }
        push(obj[k], k);
    }
    return arr;
}

function _isCfgSpider(api) {
    return /^csp_XBPQ/i.test(api) || /^csp_XYQHiker/i.test(api) || /^csp_XPath/i.test(api) || /^csp_XBiubiu/i.test(api);
}

function _classify(site, spider) {
    var api = String(site.api || ''), ext = String(site.ext || ''), type = Number(site.type);
    if (api.indexOf('py_') === 0) { return 'py'; }
    if (_hasExt(ext, '.py') || _hasExt(api, '.py')) { return 'py'; }
    // 聚影自身支持 XBPQ / XYQHiker / XPath / biubiu 这类"配置型蜘蛛"(ext 指向 JSON)
    if (_isCfgSpider(api)) { return 'drpy'; }
    if (api.indexOf('csp_') === 0) { return 'jar'; }
    if (type === 3 && String(site.jar || spider || '').length > 0) { return 'jar'; }
    if (_hasExt(ext, '.js') || _hasExt(api, '.js') || api.indexOf('drpy') >= 0 || ext.indexOf('drpy') >= 0) { return 'drpy'; }
    if (/^https?:\/\//i.test(api)) { return 'bocai'; }
    return 'unknown';
}

function _detect(obj) {
    var spider = (typeof obj.spider === 'string') ? obj.spider : '';
    var lives = obj.lives || [];
    var parses = obj.parses || obj.parse || [];
    var sites = [], fmt = 'unknown';
    if (Object.prototype.toString.call(obj.sites) === '[object Array]') {
        fmt = 'tvbox'; sites = _normalize(obj.sites);
    } else if (obj.api_site && typeof obj.api_site === 'object') {
        fmt = 'lunatv'; sites = _normalize(obj.api_site);
    } else if (obj.sites && typeof obj.sites === 'object') {
        fmt = 'lunatv'; sites = _normalize(obj.sites);
    } else if (Object.prototype.toString.call(obj) === '[object Array]') {
        fmt = 'array'; sites = _normalize(obj);
    } else {
        var probe = _normalize(obj), has = 0;
        for (var i = 0; i < probe.length; i++) { if (probe[i].api) { has++; } }
        if (has > 0) { fmt = 'lunatv'; sites = probe; }
    }
    return { fmt: fmt, spider: spider, sites: sites, lives: lives, parses: parses };
}

function _bucket(info) {
    var b = { bocai: [], jar: [], drpy: [], py: [], unknown: [] };
    var adultN = 0, list = [], i;
    for (i = 0; i < info.sites.length; i++) {
        var s = info.sites[i];
        if (!s || s.hide || !s.api) { continue; }
        if (s.adult) { adultN++; }
        b[_classify(s, info.spider)].push(s);
        list.push(s);
    }
    return { buckets: b, adultN: adultN, sites: list };
}

function _jyBase() {
    var base = '';
    try { base = String((typeof config !== 'undefined' && config.聚影) ? config.聚影 : ''); } catch (e) { base = ''; }
    if (!base) { try { base = String(getPublicItem('聚影', '') || ''); } catch (e2) { base = ''; } }
    if (!base) { base = 'hiker://files/rules/Src/Juying2/SrcJuying.js'; }
    require(base.replace(/[^/]*$/, '') + 'SrcJySet.js');
    return base;
}

function _jdUrl(u) {
    var s = String(u || '').trim();
    if (!s) { return []; }
    var gh = s.match(/^https?:\/\/github\.com\/([^\/]+)\/([^\/]+)\/(?:blob|raw)\/([^\/]+)\/(.+)$/i);
    if (gh) {
        var p0 = gh[4].split('?')[0];
        return [
            'https://cdn.jsdelivr.net/gh/' + gh[1] + '/' + gh[2] + '@' + gh[3] + '/' + p0,
            'https://fastly.jsdelivr.net/gh/' + gh[1] + '/' + gh[2] + '@' + gh[3] + '/' + p0,
            'https://raw.githubusercontent.com/' + gh[1] + '/' + gh[2] + '/' + gh[3] + '/' + p0,
            s
        ];
    }
    return [s];
}

function _grabCode(u) {
    if (!u) { return ''; }
    if (u.charAt(0) === 'j' || u.charAt(0) === 'v' || /^\/\//.test(u) || /^func/.test(u)) { return u; }
    var urls = _jdUrl(u);
    for (var i = 0; i < urls.length; i++) {
        try {
            var r = String(fetch(urls[i], { timeout: 12000, headers: { 'User-Agent': 'Mozilla/5.0' } }) || '');
            if (r && r.length > 20) { return r; }
        } catch (e) { }
        try {
            var r2 = String(getContnet(urls[i]) || '');
            if (r2 && r2.length > 20) { return r2; }
        } catch (e2) { }
    }
    return '';
}

function _cleanName(n, i) {
    var s = String(n || ('源' + (i + 1)));
    s = s.replace(/[\uD800-\uDFFF]/g, '').replace(/\s+/g, ' ').trim();
    return s || ('源' + (i + 1));
}

function _saveLives(list, srcUrl) {
    var cfgF = 'hiker://files/rules/Src/Juying2/liveconfig.json';
    var cfg = {};
    try { cfg = JSON.parse(String(readFile(cfgF) || '{}')) || {}; } catch (e) { cfg = {}; }
    var data = cfg['data'] || [];
    var urls = [], i, j;
    var baseUrl = '';
    var mo0 = String(srcUrl || '').match(/^https?:\/\/[^\/]+\//);
    if (mo0) { baseUrl = mo0[0]; }
    for (i = 0; i < list.length; i++) {
        var lv = list[i];
        if (!lv) { continue; }
        if (lv.channels && lv.channels.length) {
            for (j = 0; j < lv.channels.length; j++) {
                var ch = lv.channels[j] || {};
                var arr = ch.urls || [];
                for (var q = 0; q < arr.length; q++) {
                    var u0 = String(arr[q] || '').replace('proxy://do=live&type=txt&ext=', '');
                    if (!/^http/.test(u0)) {
                        try { u0 = base64Decode(u0); } catch (eD) { continue; }
                    }
                    urls.push({ name: ch.name || ('直播' + (urls.length + 1)), url: u0 });
                }
            }
            continue;
        }
        var lu = String(lv.url || lv.api || '');
        if (!lu) { continue; }
        if (/^\./.test(lu) && baseUrl) { lu = baseUrl + lu.replace(/^\.\//, ''); }
        urls.push({ name: lv.name || ('直播' + (urls.length + 1)), url: lu });
    }
    var ok = 0;
    for (i = 0; i < urls.length; i++) {
        var dup = false;
        for (j = 0; j < data.length; j++) { if (data[j].url === urls[i].url) { dup = true; break; } }
        if (dup) { continue; }
        var txt = '';
        try { txt = String(fetch(urls[i].url, { timeout: 6000 }) || ''); } catch (eF) { txt = ''; }
        if (!txt) { continue; }
        if (txt.indexOf('#genre#') === -1 && txt.indexOf('#EXTINF') === -1) { continue; }
        data.push({ name: urls[i].name, url: urls[i].url });
        ok++;
    }
    if (ok > 0) {
        cfg['data'] = data;
        try { writeFile(cfgF, JSON.stringify(cfg)); } catch (eW) { ok = 0; }
    }
    return ok;
}

function _mapSite(s, i) {
    // 把星集分类结果翻译成聚影 getBoxSource 认得的样子
    // 聚影认得:  http 采集口(cms) / .py 尾(py) / .js 尾(hipy_t3) / csp_XXX + ext / type=4 + /api/
    var api = String(s.api || '').trim();
    var ext = String(s.ext || '').trim();
    var t = Number(s.type);
    if (!api) { return { bad: 1 }; }

    if (api.indexOf('csp_') === 0) {
        var one = { name: _cleanName(s.name, i), api: api, type: (t || 3) };
        if (ext) { one.ext = ext; }
        if (s.jar) { one.jar = s.jar; }
        return { site: one, kind: 'csp' };
    }
    if (t === 4 && /\/api\/|\/drpys\//.test(api)) {
        var one4 = { name: _cleanName(s.name, i), api: api, type: 4 };
        if (ext) { one4.ext = ext; }
        return { site: one4, kind: 'hipy_t4' };
    }
    var pyUrl = '';
    if (_hasExt(api, '.py') && /^https?:/i.test(api)) { pyUrl = api; }
    else if (_hasExt(ext, '.py') && /^https?:/i.test(ext)) { pyUrl = ext; }
    // ★ 关键: 聚影 getBoxSource 里 type 0/1 会被当成 cms 采集口,
    //   .py/.js 蜘蛛必须避开这两个值, 否则 py 源会变成一句 cms 地址(播放必挂)
    if (pyUrl) { return { site: { name: _cleanName(s.name, i), api: pyUrl, type: 9 }, kind: 'py' }; }

    var jsUrl = '';
    if (_hasExt(api, '.js') && /^https?:/i.test(api)) { jsUrl = api; }
    else if (_hasExt(ext, '.js') && /^https?:/i.test(ext)) { jsUrl = ext; }
    if (jsUrl) { return { site: { name: _cleanName(s.name, i), api: jsUrl, type: 9 }, kind: 'drpy' }; }

    if (/^https?:\/\//i.test(api)) {
        var one2 = { name: _cleanName(s.name, i), api: api, type: (t === 4 ? 4 : 1) };
        if (ext && !/^https?:/i.test(ext)) { one2.ext = ext; }
        return { site: one2, kind: 'cms' };
    }
    return { bad: 1 };
}

function _doImport(kind) {
    var c = _readCache();
    if (!c || !(c.sites || []).length) { return '缓存已失效，请重新解析'; }
    var b = c.buckets || {};
    var all = c.sites || [];
    var pick = [], i;
    if (kind === 'bocai') { pick = (b.bocai || []).slice(); }
    else if (kind === 'jar') { pick = (b.jar || []).slice(); }
    else if (kind === 'drpy') { pick = (b.drpy || []).slice(); }
    else if (kind === 'py') { pick = (b.py || []).slice(); }
    else if (kind === 'normal') { pick = all.filter(function (x) { return !x.adult; }); }
    else if (kind === 'adult') { pick = all.filter(function (x) { return !!x.adult; }); }
    else { pick = all.slice(); }
    var lives = [], parses = [];
    if (kind === 'all' || kind === 'lives') { lives = c.lives || []; }
    if (kind === 'all' || kind === 'parses') { parses = c.parses || []; }
    if (!pick.length && !lives.length && !parses.length) { return '没有可导入的内容'; }

    var srcUrl = String(c.src || '');
    var srcFor = /^https?:\/\//i.test(srcUrl) ? srcUrl : 'http://local.placeholder/x.json';

    var sites = [], bad = 0, jarN = 0;
    for (i = 0; i < pick.length; i++) {
        if (_classify(pick[i], c.spider) === 'jar') { jarN++; continue; }
        var mp = _mapSite(pick[i], i);
        if (mp.bad) { bad++; continue; }
        sites.push(mp.site);
    }

    var mode = 0;
    try {
        var jc = JSON.parse(String(readFile(CFGF) || '{}'));
        if (jc && jc['importmode']) { mode = 2; }
    } catch (eM) { mode = 0; }

    var box = {}, jk = -1;
    try {
        _jyBase();
        showLoading('正在转换并保存（' + sites.length + ' 站）');
        box = (sites.length || parses.length) ? (getBoxSource(srcFor, 1, { jk: 1, jx: 1 }, JSON.stringify({ sites: sites, parses: parses })) || {}) : {};
        if (typeof DBGBOX !== 'undefined') { DBGBOX.box = box; DBGBOX.sites = sites; }
    } catch (eB) {
        hideLoading();
        var em = String((eB && eB.message) || eB);
        if (em.indexOf('getBoxSource') > -1 || em.indexOf('jiekousave') > -1) {
            return '聚影源码未就绪：请先打开一次聚影首页让源码安装完成，再重试';
        }
        return '转换失败：' + em;
    }
    hideLoading();
    if (box.message) { return box.message; }
    if (box.jklist && box.jklist.length) {
        try { jk = jiekousave(box.jklist, mode); } catch (e1) { jk = -1; }
    } else { jk = 0; }
    var jx = 0;
    if (box.jxlist && box.jxlist.length) {
        try { jx = jiexisave(box.jxlist, mode); } catch (e3) { jx = -1; }
    }
    var lv = 0;
    if (lives.length) {
        try { lv = _saveLives(lives, srcUrl); } catch (e2) { lv = 0; }
    }

    var restN = Math.max(0, sites.length - (jk > 0 ? jk : 0));
    var parts = [];
    if (jk > 0) { parts.push('接口 +' + jk); }
    if (jx > 0) { parts.push('解析 +' + jx); }
    if (lv > 0) { parts.push('直播 +' + lv); }
    if (jarN > 0) { parts.push('跳过蜘蛛站 ' + jarN + '（TVBox 内核，聚影不支持）'); }
    if (bad > 0) { parts.push('跳过无地址 ' + bad); }
    if (restN > 0) { parts.push('未保存 ' + restN + '（重复或地址无效）'); }
    if (!parts.length) { parts.push('没有新增'); }
    return '导入完成：' + parts.join('，');
}

var act = String(getParam('act') || '');
var d = [];

if (act === 'do') {
    var kind = String(getParam('k') || 'all');
    var msg = '';
    try {
        showLoading('正在导入...');
        msg = _doImport(kind);
    } catch (eI) {
        msg = '导入异常：' + ((eI && eI.message) || eI);
    }
    hideLoading();
    d.push({ title: '<b>📥 ' + msg + '</b>', col_type: 'rich_text', extra: { lineVisible: false, backgroundColor: bgTint } });
    d.push({ col_type: 'line_blank' });
    d.push({
        title: '↩ 返回预览（继续导入其他分类）',
        col_type: 'text_center_1',
        url: 'hiker://page/jyTvbox#noHistory##noRecordHistory#',
        extra: { backgroundColor: bgTint }
    });
    d.push({
        title: '🔄 重新输入新配置',
        col_type: 'text_center_1',
        url: 'hiker://page/jyTvbox#noHistory##noRecordHistory#?act=reset'
    });
    d.push({
        title: '返回上一页',
        col_type: 'text_center_1',
        url: 'hiker://empty'
    });
    setResult(d);
} else if (act === 'go') {
    var src = _pendingSrc();
    try { clearMyVar('jybox_pending'); } catch (eC) { }
    if (!src) {
        d.push({ title: '请先填写接口地址或粘贴配置内容', col_type: 'rich_text', extra: { lineVisible: false } });
        d.push({ col_type: 'line_blank' });
        d.push({ title: '🔙 返回输入', col_type: 'text_center_1', url: 'hiker://page/jyTvbox#noHistory##noRecordHistory#?act=reset' });
        setResult(d);
    } else {
        showLoading('正在获取配置（多节点重试）');
        var res = _fetchText(src);
        hideLoading();
        if (!res.ok) {
            d.push({ title: '❌ 获取失败', col_type: 'text_center_1', extra: { backgroundColor: '#15FF0000' } });
            d.push({
                title: '<small><font color=#868E96>地址：' + String(src).substring(0, 200).replace(/</g, '&lt;') + '<br><br>' + (res.log || []).join('<br>') + '<br><br>可改用「从文件选择」，或直接粘贴整段 JSON</font></small>',
                col_type: 'rich_text', extra: { lineVisible: false }
            });
            d.push({ col_type: 'line_blank' });
            d.push({ title: '🔄 返回重试', col_type: 'text_center_1', url: 'hiker://page/jyTvbox#noHistory##noRecordHistory#?act=reset' });
            setResult(d);
        } else {
            var pr = _parseLoose(res.text);
            if (!pr.ok) {
                d.push({ title: '❌ 解析失败：不是合法 JSON', col_type: 'text_center_1', extra: { backgroundColor: '#15FF0000' } });
                var ctx = '';
                if (pr.pos >= 0 && pr.sample) {
                    var a0 = Math.max(0, pr.pos - 60), b0 = Math.min(pr.sample.length, pr.pos + 60);
                    ctx = '<br>出错位置附近：<br>' + String(pr.sample).substring(a0, b0).replace(/</g, '&lt;');
                }
                d.push({
                    title: '<small><font color=#868E96>' + pr.msg + ctx + '<br><br>开头 200 字：<br>' + String(res.text).substring(0, 200).replace(/</g, '&lt;') + '</font></small>',
                    col_type: 'rich_text', extra: { lineVisible: false }
                });
                d.push({ col_type: 'line_blank' });
                d.push({ title: '🔄 返回重试', col_type: 'text_center_1', url: 'hiker://page/jyTvbox#noHistory##noRecordHistory#?act=reset' });
                setResult(d);
            } else {
                var info = _detect(pr.obj);
                var bk = _bucket(info);
                if (!bk.sites.length && !(info.lives || []).length) {
                    d.push({ title: '⚠️ 没有识别到站点', col_type: 'text_center_1' });
                    var ks = [];
                    for (var kk in pr.obj) { if (Object.prototype.hasOwnProperty.call(pr.obj, kk)) { ks.push(kk); } }
                    d.push({
                        title: '<small><font color=#868E96>顶层键：' + ks.join('、') + '<br>支持 TVBox(sites) / LunaTV(api_site) / 站点数组</font></small>',
                        col_type: 'rich_text', extra: { lineVisible: false }
                    });
                    d.push({ col_type: 'line_blank' });
                    d.push({ title: '🔄 返回重试', col_type: 'text_center_1', url: 'hiker://page/jyTvbox#noHistory##noRecordHistory#?act=reset' });
                    setResult(d);
                } else {
                    _writeCache({
                        fmt: info.fmt, spider: info.spider, sites: bk.sites, lives: info.lives,
                        parses: info.parses, buckets: bk.buckets, adultN: bk.adultN, src: src
                    });
                    d.push({ title: '✅ 解析完成，正在生成预览', col_type: 'text_center_1' });
                    setResult(d);
                    refreshPage(false);
                }
            }
        }
    }
} else {
    if (act === 'reset') { _clearCache(); try { clearMyVar('jybox_src'); } catch (eR) { } }
    var cache = _readCache();
    if (cache && cache.sites && cache.sites.length) {
        var b2 = cache.buckets || { bocai: [], jar: [], drpy: [], py: [], unknown: [] };
        var sitesN = cache.sites.length;
        var adultN2 = Number(cache.adultN) || 0;
        var normalN = Math.max(0, sitesN - adultN2);
        var livesL = cache.lives || [];
        var parsesL = cache.parses || [];
        var fmtName = (cache.fmt === 'lunatv') ? 'LunaTV 配置' : (cache.fmt === 'array' ? '站点数组' : 'TVBox 接口');
        var base2 = 'hiker://page/jyTvbox#noHistory##noRecordHistory#?act=do&k=';

        d.push({
            title: '<b>✅ 解析成功</b><br><small>' + fmtName + ' · 共 ' + sitesN + ' 站（普通 ' + normalN + ' / 🔞 ' + adultN2 + '）· 直播 ' + livesL.length + ' · 解析 ' + parsesL.length + '</small>',
            col_type: 'rich_text', extra: { lineVisible: false, backgroundColor: bgTint }
        });
        if (cache.spider) {
            d.push({ title: '<small>🕷 全局 spider：' + String(cache.spider).substring(0, 90) + '</small>', col_type: 'rich_text', extra: { lineVisible: false } });
        }
        d.push({ col_type: 'line' });
        d.push({ title: '🍎 苹果CMS ' + b2.bocai.length + ' 个', col_type: 'text_1', url: 'hiker://empty', extra: { lineVisible: false } });
        d.push({ title: '🕷 蜘蛛站 ' + b2.jar.length + ' 个' + (b2.jar.length ? '（TVBox 内核，聚影不支持·自动跳过）' : ''), col_type: 'text_1', url: 'hiker://empty', extra: { lineVisible: false } });
        d.push({ title: '🐉 配置蜘蛛(Drpy/XYQ/XBPQ) ' + b2.drpy.length + ' 个', col_type: 'text_1', url: 'hiker://empty', extra: { lineVisible: false } });
        d.push({ title: '🐍 Python站 ' + b2.py.length + ' 个', col_type: 'text_1', url: 'hiker://empty', extra: { lineVisible: false } });
        if (b2.unknown.length) {
            d.push({ title: '❓ 未识别 ' + b2.unknown.length + ' 个（跳过）', col_type: 'text_1', url: 'hiker://empty', extra: { lineVisible: false } });
        }
        d.push({ col_type: 'line' });

        if (adultN2 > 0 && normalN > 0) {
            d.push({ title: '⬇ 导入普通站（' + normalN + '）', col_type: 'text_center_1', url: base2 + 'normal', extra: { backgroundColor: bgTint } });
            d.push({ title: '⬇ 导入全部（' + sitesN + '）', col_type: 'text_center_1', url: base2 + 'all', extra: { backgroundColor: bgTint } });
            d.push({ title: '🔞 仅导入成人站（' + adultN2 + '）', col_type: 'text_center_1', url: base2 + 'adult', extra: { backgroundColor: '#10E8A33D' } });
        } else {
            d.push({ title: '⬇ 一键全部导入（' + sitesN + '）', col_type: 'text_center_1', url: base2 + 'all', extra: { backgroundColor: bgTint } });
        }
        d.push({ col_type: 'line_blank' });
        if (b2.bocai.length) { d.push({ title: '只导入苹果CMS（' + b2.bocai.length + '）', col_type: 'text_center_1', url: base2 + 'bocai' }); }
        if (b2.jar.length) { d.push({ title: '只导入蜘蛛站（' + b2.jar.length + '）⚠️ 聚影不支持，会全部跳过', col_type: 'text_center_1', url: base2 + 'jar' }); }
        if (b2.drpy.length) { d.push({ title: '只导入配置蜘蛛（' + b2.drpy.length + '）', col_type: 'text_center_1', url: base2 + 'drpy' }); }
        if (b2.py.length) { d.push({ title: '只导入Python（' + b2.py.length + '）', col_type: 'text_center_1', url: base2 + 'py' }); }
        if (livesL.length) { d.push({ title: '导入直播源（' + livesL.length + '）', col_type: 'text_center_1', url: base2 + 'lives' }); }
        if (parsesL.length) { d.push({ title: '导入解析规则（' + parsesL.length + '）', col_type: 'text_center_1', url: base2 + 'parses' }); }
        d.push({ col_type: 'line_blank' });
        d.push({ title: '🔄 重新输入', col_type: 'text_center_1', url: 'hiker://page/jyTvbox#noHistory##noRecordHistory#?act=reset' });
        d.push({ col_type: 'line_blank' });
        d.push({ title: '<small><font color=#888E96>来源：' + String(cache.src || '').substring(0, 80) + '</font></small>', col_type: 'rich_text', extra: { lineVisible: false } });
    } else {
        d.push({
            title: '<b>📥 TVBox 接口导入</b><br><small>支持接口地址、GitHub 链接、本地文件、直接粘贴 JSON</small>',
            col_type: 'rich_text', extra: { lineVisible: false, backgroundColor: bgTint }
        });
        d.push({ col_type: 'line_blank' });
        d.push({
            title: '', desc: '粘贴接口地址，或整段 JSON',
            col_type: 'input',
            extra: {
                defaultValue: '', type: 'textarea', height: 4,
                onChange: 'putMyVar("jybox_src",input);'
            }
        });
        d.push({
            title: '📁 从文件选择', col_type: 'text_center_1',
            url: 'fileSelect://' + $.toString(function () {
                var code = String(readFile(input) || '');
                if (!code || !code.trim()) { toast('文件为空'); return 'hiker://empty'; }
                var h = code.trim().charAt(0);
                if (h !== '{' && h !== '[') { toast('不是 JSON 文件'); return 'hiker://empty'; }
                putMyVar('jybox_pending', code);
                return 'hiker://page/jyTvbox#noHistory##noRecordHistory#?act=go';
            })
        });
        d.push({
            title: '🔍 开始解析', col_type: 'text_center_1',
            url: $().lazyRule(function () {
                var v = '';
                try { v = String(getMyVar('jybox_src', '') || '').trim(); } catch (e) { v = ''; }
                if (!v) { return 'toast://请先填写地址或粘贴内容'; }
                putMyVar('jybox_pending', v);
                return 'hiker://page/jyTvbox#noHistory##noRecordHistory#?act=go';
            }),
            extra: { backgroundColor: bgTint }
        });
        d.push({ col_type: 'line' });
        d.push({
            title: '<small><font color=#868E96>解析成功后可预览分流：苹果CMS / 蜘蛛 / Drpy / Python / 直播 / 解析，可按类别分别导入，也可只导普通站跳过成人站。<br><br>获取失败时：用浏览器打开接口地址，全选复制整段粘贴；GitHub 页面链接会自动换 jsdelivr 重试。</font></small>',
            col_type: 'rich_text', extra: { lineVisible: false }
        });
        d.push({ col_type: 'line_blank' });
        d.push({ title: '<small><font color=#888E96>更多资源请到 navpage-2026.surge.sh</font></small>', col_type: 'rich_text', extra: { lineVisible: false } });
    }
}
setResult(d);