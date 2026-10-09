// 66大片网 (66dpw.vip) 海阔视界规则函数库 v1
// 苹果CMS mxpro 模板: 分类vodtype/详情voddetail/播放vodplay
// 原始逻辑来自用户提供的 py 蜘蛛(66dpw), 选择器全部沿用, 不自创
// 播放加密 enc2: URL解码 -> Base64解码 -> URL解码 (对应 py 的 decrypt_enc2)
//
// 布局遵循用户海阔标准: 分类一排scroll_button + 绿色高亮#3CB371 + ●纯文本
//   卡片@rule内联详情 / lazyRule回调自包含 / 播放#isVideo=true##noHistory#
//   翻页头部隐藏只显内容 / version整数 / 按钮纯文本禁HTML
// 本规则不含任何推广站点、外部群链接或第三方入口

var PC_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';

// 域名: 只放 py 蜘蛛里实际出现的域名, 不臆造备用域名
var DOMAINS = ['https://www.66dpw.vip'];
var HOST = getMyVar('dpw66Host', DOMAINS[0]);

// 分类: 与 py 蜘蛛 homeContent 完全一致
var CATS = [
    { name: '电影', id: '1' },
    { name: '动漫', id: '2' },
    { name: '剧集', id: '3' },
    { name: '短剧', id: '4' },
    { name: '综艺', id: '5' }
];

// ---------- 通用: 图片 / 链接 ----------
function getImg(u) {
    if (u == null || u == '') { return ''; }
    if (u == '/') { return ''; }
    if (u.indexOf('http://') == 0) { u = 'https://' + u.substr(7); }
    if (u.indexOf('hiker://') == 0 || u.indexOf('video://') == 0) { return u; }
    if (u.indexOf('http') == -1) { u = HOST + (u.indexOf('/') == 0 ? u : '/' + u); }
    return u;
}

function getUrl(u) {
    if (u == null || u == '') { return ''; }
    if (u.indexOf('hiker://') == 0 || u.indexOf('video://') == 0) { return u; }
    if (u.indexOf('http') == -1) { u = HOST + (u.indexOf('/') == 0 ? u : '/' + u); }
    return u;
}

// ---------- 通用: 请求 ----------
function getHtml(url) {
    var html = '';
    var tryUrls = [url];
    for (var di = 0; di < DOMAINS.length; di++) {
        var u2 = url.replace(HOST, DOMAINS[di]);
        var dup = false;
        for (var ti = 0; ti < tryUrls.length; ti++) {
            if (tryUrls[ti] == u2) { dup = true; break; }
        }
        if (!dup) { tryUrls.push(u2); }
    }
    for (var i = 0; i < tryUrls.length; i++) {
        try {
            html = fetch(tryUrls[i], { headers: { 'User-Agent': PC_UA, 'Referer': HOST + '/' }, timeout: 8000 }) || '';
        } catch (e) { html = ''; }
        if (html != '' && html != null) {
            if (html.indexOf('Just a moment') == -1 && html.indexOf('<html') != -1) {
                break;
            }
            html = '';
        }
    }
    return html;
}

// ---------- 列表页解析: 与 py 蜘蛛同源(a[href*="/voddetail/"] + data-original) ----------
function parseList(html) {
    var out = [];
    if (html == null || html == '') { return out; }
    var seen = {};
    var re = /<a\b([^>]*)>([\s\S]*?)<\/a>/gi;
    var m;
    while ((m = re.exec(html)) != null) {
        var attrs = m[1] || '';
        var inner = m[2] || '';
        var hm = attrs.match(/href="([^"]*)"/i);
        if (hm == null) { continue; }
        var href = hm[1];
        if (href.indexOf('/voddetail/') == -1) { continue; }
        var vm = href.match(/voddetail\/(\d+)/);
        if (vm == null) { continue; }
        var vid = vm[1];
        if (seen[vid]) { continue; }
        var tm = attrs.match(/title="([^"]*)"/i);
        var title = '';
        if (tm != null) {
            title = tm[1];
        } else {
            title = inner.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
        }
        title = title.replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim();
        if (title == '') { continue; }
        var im = inner.match(/data-original="([^"]*)"/i);
        if (im == null) { im = inner.match(/\ssrc="([^"]*)"/i); }
        var img = im != null ? getImg(im[1]) : '';
        var nm = inner.match(/module-item-note">([\s\S]*?)<\//i);
        var note = '';
        if (nm != null) { note = nm[1].replace(/<[^>]+>/g, '').trim(); }
        seen[vid] = 1;
        out.push({ vid: vid, title: title, img: img, note: note, url: getUrl(href) });
    }
    return out;
}

// ---------- 加密播放地址解密 ----------
// 只处理 %XX, 不把 + 变空格(否则破坏 base64)
function urlDec(s) {
    if (s == null) { return ''; }
    s = String(s);
    try {
        return decodeURIComponent(s);
    } catch (e) {
        return s.replace(/%([0-9A-Fa-f]{2})/g, function (mm, hh) {
            return String.fromCharCode(parseInt(hh, 16));
        });
    }
}

// enc2(本站): URL解码 -> Base64解码 -> URL解码
// enc1: 纯 Base64 解码
function decryptUrl(raw, enc) {
    if (raw == null || raw == '') { return ''; }
    var s = String(raw);
    if (s.indexOf('http') == 0) { return s; }
    var v = '';
    if (enc == 1) {
        try { v = base64Decode(s); } catch (e1) { v = ''; }
        if (v != '' && v.indexOf('http') != 0) { v = urlDec(v); }
    } else {
        try { v = base64Decode(urlDec(s)); } catch (e2) { v = ''; }
        if (v != '') { try { v = urlDec(v); } catch (e3) { } }
    }
    if (v != '' && v.indexOf('http') == 0) { return v; }
    try {
        var v2 = base64Decode(s);
        if (v2 != '' && v2.indexOf('http') == 0) { return v2; }
    } catch (e4) { }
    return v;
}

// 从播放页提取真实地址(mxpro: player_aaaa 里的 url + encrypt)
function extractPlayUrl(html) {
    if (html == null || html == '') { return ''; }
    var src = html;
    var pm = html.match(/player_aaaa[\s\S]{0,2500}?<\/script>/i);
    if (pm != null) { src = pm[0]; }
    else {
        pm = html.match(/player_aaaa[\s\S]{0,2500}/i);
        if (pm != null) { src = pm[0]; }
    }
    var um = src.match(/"url"\s*:\s*"([^"]+)"/i);
    if (um == null) { um = src.match(/\burl\s*=\s*"([^"]+)"/i); }
    if (um == null) { um = src.match(/'url'\s*:\s*'([^']+)'/i); }
    if (um == null) { return ''; }
    var em = src.match(/"encrypt"\s*:\s*(\d+)/i);
    var enc = em != null ? parseInt(em[1]) : 2;
    return decryptUrl(um[1], enc);
}

// ---------- 详情页: 线路名 ----------
function parseLines(html) {
    var lines = [];
    if (html == null || html == '') { return lines; }
    var re = /data-dropdown-value="([^"]*)"/gi;
    var m;
    while ((m = re.exec(html)) != null) {
        var ln = (m[1] || '').replace(/<[^>]+>/g, '').replace(/\s+/g, '');
        if (ln != '') { lines.push(ln); }
    }
    if (lines.length == 0) {
        var re2 = /<span[^>]*class="[^"]*module-tab-name[^"]*"[^>]*>([^<]+)<\/span>/gi;
        while ((m = re2.exec(html)) != null) {
            var ln2 = (m[1] || '').replace(/<[^>]+>/g, '').replace(/\s+/g, '');
            if (ln2 != '') { lines.push(ln2); }
        }
    }
    return lines;
}

// ---------- 详情页: 选集块切分(起始标记 -> 下一个标记) ----------
function splitPlayBlocks(html) {
    var out = [];
    if (html == null || html == '') { return out; }
    var starts = [];
    var re = /<div[^>]*class="[^"]*module-play-list[^"]*"[^>]*>/gi;
    var m;
    while ((m = re.exec(html)) != null) { starts.push(m.index); }
    if (starts.length == 0) { return out; }
    var marks = [];
    var re2 = /data-dropdown-value="/gi;
    while ((m = re2.exec(html)) != null) { marks.push(m.index); }
    var re3 = /<span[^>]*class="[^"]*module-tab-name[^"]*"[^>]*>/gi;
    while ((m = re3.exec(html)) != null) { marks.push(m.index); }
    for (var i = 0; i < starts.length; i++) {
        var s = starts[i];
        var e = html.length;
        if (i + 1 < starts.length) { e = starts[i + 1]; }
        for (var k = 0; k < marks.length; k++) {
            if (marks[k] > s && marks[k] < e) { e = marks[k]; break; }
        }
        out.push(html.substring(s, e));
    }
    return out;
}

// ---------- 详情页: 解析单个选集块 ----------
function parseEpBlock(block) {
    var eps = [];
    var seen = {};
    if (block == null || block == '') { return eps; }
    var re = /<a\b([^>]*)>([\s\S]*?)<\/a>/gi;
    var m;
    while ((m = re.exec(block)) != null) {
        var attrs = m[1] || '';
        var inner = m[2] || '';
        var hm = attrs.match(/href="([^"]*)"/i);
        if (hm == null) { continue; }
        var href = hm[1];
        if (href.indexOf('/vodplay/') == -1) { continue; }
        var nm = inner.replace(/<[^>]+>/g, '').replace(/\s+/g, '').trim();
        if (nm == '') { continue; }
        var epNum = '';
        var mm = nm.match(/EP(\d+)/i);
        if (mm != null) { epNum = mm[1]; }
        if (epNum == '') { mm = nm.match(/第?(\d+)集/); if (mm != null) { epNum = mm[1]; } }
        if (epNum == '') { mm = href.match(/-(\d+)\.html$/); if (mm != null) { epNum = mm[1]; } }
        if (epNum == '') { epNum = nm; }
        if (seen[epNum]) { continue; }
        seen[epNum] = 1;
        eps.push({ name: '第' + epNum + '集', num: epNum, url: getUrl(href) });
    }
    return eps;
}

// ---------- 二级分类: 从分类页动态抓取, 不硬编码 id ----------
function parseSubs(html) {
    var out = [];
    if (html == null || html == '') { return out; }
    var seen = {};
    // 一级 id 不算二级
    var tops = {};
    for (var t = 0; t < CATS.length; t++) { tops[CATS[t].id] = 1; }
    var re = /<a\b([^>]*)>([\s\S]*?)<\/a>/gi;
    var m;
    while ((m = re.exec(html)) != null) {
        var attrs = m[1] || '';
        var inner = m[2] || '';
        var hm = attrs.match(/href="([^"]*)"/i);
        if (hm == null) { continue; }
        var href = hm[1];
        var sm = href.match(/\/vodtype\/(\d+)\.html/i);
        if (sm == null) { sm = href.match(/\/vodtype\/(\d+)\//i); }
        if (sm == null) { continue; }
        var sid = sm[1];
        if (tops[sid]) { continue; }
        if (seen[sid]) { continue; }
        var txt = inner.replace(/<[^>]+>/g, '').replace(/\s+/g, '').trim();
        if (txt == '') { continue; }
        if (txt.length > 8) { continue; }
        seen[sid] = 1;
        out.push({ name: txt, code: sid });
    }
    return out;
}

// ================= 主页 =================
function 主页() {
    var d = [];
    var page = parseInt(MY_PAGE) || 1;
    var tid = getMyVar('dpw66Cat', CATS[0].id);
    var subKey = 'dpw66Subs_' + tid;
    var subCache = getMyVar(subKey, '');
    var true_url = HOST + '/vodtype/' + tid + '.html';
    var subNow = getMyVar('dpw66Sub', '');
    if (subNow != '') { true_url = HOST + '/vodtype/' + subNow + '.html'; }
    if (page > 1) { true_url = true_url.replace('.html', '-' + page + '.html'); }
    var html = getHtml(true_url);
    // 二级列表缓存到 MyVar, 避免选中二级后还要再请求一次一级页
    if (subCache == '' && html != '') {
        var tmp = parseSubs(html);
        if (tmp.length > 0) {
            try { putMyVar(subKey, JSON.stringify(tmp)); } catch (eJ) { }
            subCache = JSON.stringify(tmp);
        }
    }
    if (!MY_PAGE || page <= 1) {
        for (var ci = 0; ci < CATS.length; ci++) {
            (function (it) {
                var nowCat = getMyVar('dpw66Cat', CATS[0].id);
                var on = it.id == nowCat;
                d.push({
                    title: on ? ('● ' + it.name) : it.name,
                    col_type: 'scroll_button',
                    url: $('#noLoading#').lazyRule(function (itData) {
                        putMyVar('dpw66Cat', itData.id);
                        putMyVar('dpw66Sub', '');
                        putMyVar('MY_PAGE', 1);
                        refreshPage();
                        return 'hiker://empty';
                    }, it),
                    extra: { backgroundColor: on ? '#3CB371' : '' }
                });
            })(CATS[ci]);
        }
        d.push({ col_type: 'blank_block' });
        // ---- 二级分类(优先用缓存, 缓存没有才用当前 html) ----
        var subs = [];
        if (subCache != '') {
            try { subs = JSON.parse(subCache); } catch (eS) { subs = []; }
        }
        if (subs.length == 0 && html != '') { subs = parseSubs(html); }
        if (subs.length > 0) {
            var nowSub = getMyVar('dpw66Sub', '');
            for (var si = 0; si < subs.length && si < 30; si++) {
                (function (so) {
                    var onS = so.code == nowSub;
                    d.push({
                        title: onS ? ('● ' + so.name) : so.name,
                        col_type: 'scroll_button',
                        url: $('#noLoading#').lazyRule(function (s2) {
                            putMyVar('dpw66Sub', s2.code);
                            putMyVar('MY_PAGE', 1);
                            refreshPage();
                            return 'hiker://empty';
                        }, so),
                        extra: { backgroundColor: onS ? '#20FA7298' : '' }
                    });
                })(subs[si]);
            }
            d.push({ col_type: 'blank_block' });
        }
    }
    // 选中二级时用它作为 tid
    var useTid = tid;
    var sub = getMyVar('dpw66Sub', '');
    if (sub != '') { useTid = sub; }
    if (html == '') {
        d.push({ title: '加载失败，请稍后重试', col_type: 'text_1' });
    } else {
        var list = parseList(html);
        if (list.length == 0) {
            d.push({ title: '没有获取到内容', col_type: 'text_1' });
        } else {
            for (var i = 0; i < list.length; i++) {
                var v = list[i];
                d.push({
                    title: v.title,
                    desc: v.note,
                    img: v.img,
                    url: v.url + '#immersiveTheme##fullTheme#@rule=js:$.require("dpw66").详情()',
                    col_type: 'movie_3'
                });
            }
        }
    }
    setResult(d);
}

// ================= 搜索 =================
function 搜索() {
    var d = [];
    var kw = '';
    var parts = String(MY_URL || '').split('##');
    if (parts.length > 1) {
        try { kw = decodeURIComponent(parts[1]); } catch (e) { kw = parts[1]; }
    }
    if (kw == '') {
        var km = String(MY_URL || '').match(/[?&]wd=([^&]+)/);
        if (km != null) { try { kw = decodeURIComponent(km[1]); } catch (e2) { kw = km[1]; } }
    }
    if (kw == '') {
        d.push({ title: '请输入搜索关键词', col_type: 'text_1' });
        setResult(d);
        return;
    }
    var ek = encodeURIComponent(kw);
    var html = getResCode();
    if (html == null || html == '' || html.indexOf('<html') == -1) {
        html = getHtml(HOST + '/vodsearch/-------------.html?wd=' + ek);
    }
    var list = parseList(html);
    // 兜底1: 换搜索路径
    if (list.length == 0) {
        var h2 = getHtml(HOST + '/index.php/vod/search.html?wd=' + ek);
        if (h2 != '') { list = parseList(h2); }
    }
    // 兜底2: 苹果CMS XML API
    if (list.length == 0) {
        var xml = getHtml(HOST + '/api.php/provide/vod/at/xml/?wd=' + ek);
        if (xml != '' && xml.indexOf('<list>') != -1) {
            var re = /<vod>[\s\S]*?<id>(\d+)<\/id>[\s\S]*?<name>([\s\S]*?)<\/name>[\s\S]*?<pic>([\s\S]*?)<\/pic>/gi;
            var m;
            while ((m = re.exec(xml)) != null) {
                list.push({
                    vid: m[1],
                    title: m[2].replace(/<[^>]+>/g, '').trim(),
                    img: getImg(m[3]),
                    note: '',
                    url: getUrl('/voddetail/' + m[1] + '.html')
                });
            }
        }
    }
    // 兜底3: 放宽解析(抓所有 voddetail 链接, 不要求 title 属性)
    if (list.length == 0 && html != '' && html.indexOf('<html') != -1) {
        var seen2 = {};
        var re2 = /<a\b[^>]*href="([^"]*\/voddetail\/\d+[^"]*)"[^>]*>([\s\S]*?)<\/a>/gi;
        var m2;
        while ((m2 = re2.exec(html)) != null) {
            var vm2 = m2[1].match(/voddetail\/(\d+)/);
            if (vm2 == null) { continue; }
            if (seen2[vm2[1]]) { continue; }
            var t2 = m2[2].replace(/<[^>]+>/g, '').trim();
            if (t2 == '') { t2 = '影片' + vm2[1]; }
            seen2[vm2[1]] = 1;
            list.push({ vid: vm2[1], title: t2, img: '', note: '', url: getUrl(m2[1]) });
        }
    }
    if (list.length == 0) {
        d.push({ title: '未找到相关影片', col_type: 'text_1' });
    } else {
        for (var i = 0; i < list.length; i++) {
            var v = list[i];
            d.push({
                title: v.title,
                desc: v.note,
                img: v.img,
                url: v.url + '#immersiveTheme##fullTheme#@rule=js:$.require("dpw66").详情()',
                col_type: 'movie_3'
            });
        }
    }
    setResult(d);
}

// ================= 详情 =================
function 详情() {
    var d = [];
    var html = getResCode();
    if (html == null || html == '' || html.indexOf('<h1') == -1) {
        html = getHtml(MY_URL);
    }
    if (html == '') {
        d.push({ title: '加载失败，请稍后重试', col_type: 'text_1' });
        setResult(d);
        return;
    }
    var title = '';
    var tm = html.match(/<h1[^>]*>([\s\S]*?)<\/h1>/i);
    if (tm != null) { title = tm[1].replace(/<[^>]+>/g, '').trim(); }
    var img = '';
    var pm = html.match(/<img[^>]*class="[^"]*lazyload[^"]*"[^>]*data-original="([^"]*)"/i);
    if (pm == null) { pm = html.match(/class="[^"]*video-cover[^"]*"[^>]*data-original="([^"]*)"/i); }
    if (pm != null) { img = getImg(pm[1]); }
    if (title != '') {
        d.push({ title: title, img: img, desc: '', col_type: 'movie_1_vertical_pic_blur' });
    }
    var desc = '';
    var dm = html.match(/module-info-introduction">([\s\S]*?)<\/div>/i);
    if (dm != null) {
        desc = dm[1].replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
    }
    if (desc == '') {
        var raw = pdfh(html, 'body&&Text') || '';
        var di = raw.indexOf('简介：');
        if (di >= 0) { desc = raw.substring(di + 3, di + 300); }
    }
    desc = desc.replace(/\s+/g, ' ').trim();
    if (desc.length > 200) { desc = desc.substring(0, 200) + '...'; }
    if (desc != '') { d.push({ title: desc, col_type: 'long_text' }); }
    d.push({ col_type: 'blank_block' });

    // ---- 线路名 ----
    var lines = parseLines(html);
    if (lines.length == 0) { lines = ['默认']; }

    // ---- 选集块 ----
    var blocksHtml = splitPlayBlocks(html);
    var rawBlocks = [];
    for (var bi = 0; bi < blocksHtml.length; bi++) {
        rawBlocks.push(parseEpBlock(blocksHtml[bi]));
    }
    // 块数>线路数: 多余块合并进最后一个线路(按集号去重) —— 与看片狂人 v2 同源修复
    var items = [];
    for (var i2 = 0; i2 < lines.length; i2++) {
        var eps = [];
        if (i2 < rawBlocks.length) { eps = rawBlocks[i2].slice(0); }
        if (i2 == lines.length - 1) {
            for (var ex = lines.length; ex < rawBlocks.length; ex++) {
                var seenN = {};
                for (var q = 0; q < eps.length; q++) { seenN[eps[q].num] = 1; }
                for (var w = 0; w < rawBlocks[ex].length; w++) {
                    if (!seenN[rawBlocks[ex][w].num]) { eps.push(rawBlocks[ex][w]); }
                }
            }
        }
        if (eps.length == 0) { continue; }
        items.push({ name: lines[i2], eps: eps });
    }
    if (items.length == 0) {
        // 兜底: 整页抓所有 /vodplay/ 链接当一个线路
        var allEps = parseEpBlock(html);
        if (allEps.length > 0) {
            items.push({ name: lines[0], eps: allEps });
        }
    }
    if (items.length == 0) {
        d.push({ title: '暂无线路', col_type: 'text_1' });
        setResult(d);
        return;
    }
    items.sort(function (a, b) { return b.eps.length - a.eps.length; });

    var lineKey = MY_URL + '_line';
    var nowLine = -1;
    var saved = getMyVar(lineKey, '');
    if (saved != '' && saved != null) {
        var nv = parseInt(saved);
        if (!isNaN(nv)) { nowLine = nv; }
    }
    if (nowLine < 0 || nowLine >= items.length) { nowLine = 0; }

    for (var li3 = 0; li3 < items.length; li3++) {
        (function (idx) {
            var on = idx == nowLine;
            d.push({
                title: on ? ('● ' + items[idx].name + '(' + items[idx].eps.length + ')') : (items[idx].name + '(' + items[idx].eps.length + ')'),
                url: $('#noLoading#').lazyRule(function (ld) {
                    putMyVar(ld.key, String(ld.idx));
                    refreshPage(false);
                    return 'hiker://empty';
                }, { key: lineKey, idx: idx }),
                col_type: 'scroll_button',
                extra: { backgroundColor: on ? '#3CB371' : '' }
            });
        })(li3);
    }
    d.push({ col_type: 'blank_block' });

    var sortKey = MY_URL + '_sort';
    var sortOrder = getMyVar(sortKey, '正序');
    var newSort = sortOrder == '正序' ? '倒序' : '正序';
    d.push({
        title: (sortOrder == '正序' ? '● 正序' : '● 倒序'),
        col_type: 'scroll_button',
        url: $('#noLoading#').lazyRule(function (key, val) {
            putMyVar(key, val);
            refreshPage(false);
            return 'hiker://empty';
        }, sortKey, newSort),
        extra: { backgroundColor: '#3CB371' }
    });
    d.push({ col_type: 'blank_block' });

    var cur = items[nowLine];
    var outEp = cur.eps.slice(0);
    outEp.sort(function (a, b) {
        var na = parseInt(a.num) || 0;
        var nb = parseInt(b.num) || 0;
        return sortOrder == '倒序' ? nb - na : na - nb;
    });

    for (var c = 0; c < outEp.length; c++) {
        (function (ep) {
            // lazyRule 回调是独立JS上下文, 看不到函数库里的任何方法
            // —— 解密三段全部内联, UA硬编码, 不依赖外部函数(海阔铁律: 回调自包含)
            var lazy = $('').lazyRule(function (pu) {
                var UA3 = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';
                // 只处理 %XX, 不把 + 变空格(否则破坏 base64)
                function ud(s) {
                    if (s == null) { return ''; }
                    s = String(s);
                    try { return decodeURIComponent(s); } catch (e) {
                        return s.replace(/%([0-9A-Fa-f]{2})/g, function (mm, hh) {
                            return String.fromCharCode(parseInt(hh, 16));
                        });
                    }
                }
                function dec(raw, enc) {
                    if (raw == null || raw == '') { return ''; }
                    var s = String(raw);
                    if (s.indexOf('http') == 0) { return s; }
                    var v = '';
                    if (enc == 1) {
                        try { v = base64Decode(s); } catch (e1) { v = ''; }
                        if (v != '' && v.indexOf('http') != 0) { v = ud(v); }
                    } else {
                        try { v = base64Decode(ud(s)); } catch (e2) { v = ''; }
                        if (v != '') { try { v = ud(v); } catch (e3) { } }
                    }
                    if (v != '' && v.indexOf('http') == 0) { return v; }
                    try {
                        var v2 = base64Decode(s);
                        if (v2 != '' && v2.indexOf('http') == 0) { return v2; }
                    } catch (e4) { }
                    return v;
                }
                function ext(html) {
                    if (html == null || html == '') { return ''; }
                    var src = html;
                    var pm = html.match(/player_aaaa[\s\S]{0,2500}?<\/script>/i);
                    if (pm != null) { src = pm[0]; }
                    else {
                        pm = html.match(/player_aaaa[\s\S]{0,2500}/i);
                        if (pm != null) { src = pm[0]; }
                    }
                    var um = src.match(/"url"\s*:\s*"([^"]+)"/i);
                    if (um == null) { um = src.match(/\burl\s*=\s*"([^"]+)"/i); }
                    if (um == null) { um = src.match(/'url'\s*:\s*'([^']+)'/i); }
                    if (um == null) { return ''; }
                    var em = src.match(/"encrypt"\s*:\s*(\d+)/i);
                    var enc = em != null ? parseInt(em[1]) : 2;
                    return dec(um[1], enc);
                }
                var ph = '';
                try { ph = request(pu) || ''; } catch (e1) { ph = ''; }
                if (ph == '') {
                    try {
                        ph = fetch(pu, { headers: { 'User-Agent': UA3, 'Referer': pu }, timeout: 8000 }) || '';
                    } catch (e2) { ph = ''; }
                }
                var real = '';
                if (ph != '') { real = ext(ph); }
                if (real != '' && real.indexOf('http') == 0) {
                    return real + '#isVideo=true##noHistory#';
                }
                // 解密失败: 交嗅探兜底
                return 'video://' + pu + '#isVideo=true##noHistory#';
            }, ep.url);
            d.push({
                title: ep.name,
                url: ep.url + '@' + lazy,
                col_type: outEp.length > 6 ? 'text_4' : 'text_2',
                extra: { cls: 'playlist', id: ep.url }
            });
        })(outEp[c]);
    }
    setResult(d);
}

$.exports = { 主页: 主页, 搜索: 搜索, 详情: 详情 };
