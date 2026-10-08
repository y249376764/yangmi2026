// 看片狂人 (kpkuang) 海阔视界规则函数库 v2
// MacCMS 在线播放站: 分类vodtype/详情voddetail/播放vodplay
// 多域名: DOMAINS + getMyVar记忆 + 主页切换按钮
// 详情页: 线路(fed-drop-btns) + 选集(fed-play-item) + 排序按钮(正序/倒序)
// 播放: 选集链接 + lazyRule 提取 data-play -> slice(3) base64解码 -> 解析接口
//
// ============ v2 修复 (2026-10-08, 对照 py 蜘蛛 v2 同步) ============
// ① 集数块与线路错位 -> 集数不全:
//    某线路被拆成多个 fed-play-item 块(分卷/分组)时, 按"线路索引=块索引"硬配会串位,
//    后面线路的集数被吃掉。改为: 块数>线路数时, 多余块合并进最后一个线路(按集号去重)。
// ② 线路按集数降序, 集数最全的排第一并默认选中:
//    实测推翻 v1 注释——超清DR/AB/BY/MD 才是真源(能播+集数全);
//    IK影视/电影天堂 等"官方线"是残缺废源(分片能下=跑流量, 但不出画面最后失败)。
// ③ 播放同集跨线路回退 + m3u8 校验(#EXTM3U):
//    每集带最多2条同集备用线路地址, 首选校验不过自动切备用线路的同集。
// ==================================================================
var DOMAINS = ['https://www.kpkuang.us', 'https://www.kpkuang.cfd', 'https://kpkuang.fyi', 'https://kpkuang.org'];
var HOST = getMyVar('kpkuangHost', DOMAINS[0]);

// 分类数据: id -> 名称
var CATS = [
    { name: '电影', id: '1', sub: [{ name: '全部', code: '1' }, { name: '动作片', code: '6' }, { name: '喜剧片', code: '7' }, { name: '爱情片', code: '8' }, { name: '科幻片', code: '9' }, { name: '恐怖片', code: '10' }, { name: '剧情片', code: '11' }, { name: '战争片', code: '12' }, { name: '纪录片', code: '29' }] },
    { name: '连续剧', id: '2', sub: [{ name: '全部', code: '2' }, { name: '国产剧', code: '13' }, { name: '港剧', code: '14' }, { name: '日剧', code: '15' }, { name: '欧美剧', code: '16' }, { name: '韩剧', code: '23' }, { name: '越南剧', code: '22' }, { name: '泰剧', code: '21' }, { name: '台剧', code: '20' }] },
    { name: '综艺', id: '3', sub: [{ name: '全部', code: '3' }] },
    { name: '动漫', id: '4', sub: [{ name: '全部', code: '4' }] },
    { name: '短剧', id: '37', sub: [{ name: '全部', code: '37' }, { name: '爽文短剧', code: '36' }, { name: '现代都市', code: '39' }, { name: '脑洞悬疑', code: '40' }, { name: '年代穿越', code: '41' }, { name: '古装仙侠', code: '42' }, { name: '反转爽剧', code: '43' }, { name: '女频恋爱', code: '44' }, { name: '成长逆袭', code: '45' }] }
];

// 图片处理: 相对路径拼域名, 空/'/'过滤, http转https
function getImg(u) {
    if (u == null || u == '') { return ''; }
    if (u == '/') { return ''; }
    if (u.indexOf('http://') == 0) { u = 'https://' + u.substr(7); }
    if (u.indexOf('hiker://') == 0 || u.indexOf('video://') == 0 || u.indexOf('webRule://') == 0) { return u; }
    if (u.indexOf('http') == -1) { u = HOST + u; }
    return u;
}

// 链接处理
function getUrl(u) {
    if (u == null || u == '') { return ''; }
    // hiker:// 协议不拼 HOST (防 www.kpkuang.ushiker 错)
    if (u.indexOf('hiker://') == 0 || u.indexOf('video://') == 0 || u.indexOf('webRule://') == 0) { return u; }
    if (u.indexOf('http') == -1) { u = HOST + u; }
    return u;
}

// 公共请求: fetch + PC UA + 失败换域名重试
function getHtml(url) {
    var html = '';
    var tryUrls = [url];
    var fastHost = getMyVar('kpkuangFast', '');
    if (fastHost != '') {
        var uf = url.replace(HOST, fastHost);
        if (uf != url && tryUrls.indexOf(uf) == -1) { tryUrls.unshift(uf); }
    }
    for (var ui = 0; ui < DOMAINS.length; ui++) {
        var u2 = url.replace(HOST, DOMAINS[ui]);
        var dup = false;
        for (var di = 0; di < tryUrls.length; di++) {
            if (tryUrls[di] == u2) { dup = true; break; }
        }
        if (!dup) { tryUrls.push(u2); }
    }
    for (var ti = 0; ti < tryUrls.length; ti++) {
        try {
            html = fetch(tryUrls[ti], { headers: { 'User-Agent': PC_UA }, timeout: 8000 }) || '';
        } catch (e) { html = ''; }
        if (html != '' && html != null) {
            if (html.indexOf('Just a moment') == -1 && html.indexOf('<html') != -1) {
                try { putMyVar('kpkuangFast', tryUrls[ti].replace(/^(https?:\/\/)/, '')); } catch (e3) {}
                break;
            }
            html = '';
        }
    }
    return html;
}

// 带Referer的请求 (kpdata API 需要 Referer 才返回结果)
function getHtmlWithHeaders(url) {
    var html = '';
    try {
        html = fetch(url, { headers: { 'User-Agent': PC_UA, 'Referer': HOST + '/' }, timeout: 8000 }) || '';
    } catch (e) { html = ''; }
    if (html == '' || html == null) {
        try {
            html = fetch(url, { headers: { 'User-Agent': PC_UA, 'Referer': HOST + '/' }, timeout: 8000 }) || '';
        } catch (e) { html = ''; }
    }
    return html;
}
var PC_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';

// ============ v2 新增: 选集块切分 ============
// 不用 pdfa 取块(li 内有嵌套 ul/li, 可能被 </li> 截断), 改用"起始标记 -> 下一个标记"切
function splitPlayBlocks(html) {
    var out = [];
    if (html == null || html == '') { return out; }
    var starts = [];
    var re = /<li[^>]*class="[^"]*fed-play-item[^"]*"[^>]*>/gi;
    var m;
    while ((m = re.exec(html)) != null) { starts.push(m.index); }
    if (starts.length == 0) { return out; }
    // 终止标记: 下一个 fed-play-item 或下一个 fed-drop-btns
    var marks = [];
    var re2 = /class="[^"]*fed-drop-btns[^"]*"/gi;
    while ((m = re2.exec(html)) != null) { marks.push(m.index); }
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

// ============ v2 新增: 解析单个选集块 ============
// 直接正则抓 a.fed-btns-info (href 与 class 顺序不定), 只保留 /vodplay/ 链接, 同集去重
function parseEpBlock(block) {
    var eps = [];
    var seen = {};
    if (block == null || block == '') { return eps; }
    var re = /<a\b([^>]*)>([\s\S]*?)<\/a>/gi;
    var m;
    while ((m = re.exec(block)) != null) {
        var attrs = m[1] || '';
        var inner = m[2] || '';
        if (attrs.indexOf('fed-btns-info') == -1) { continue; }
        var hm = attrs.match(/href="([^"]*)"/i);
        if (hm == null) { continue; }
        var href = hm[1];
        if (href.indexOf('/vodplay/') == -1) { continue; }
        var nm = inner.replace(/<[^>]+>/g, '').replace(/\s+/g, '');
        if (nm == '') { continue; }
        // 集数: EP数字 > 第N集 > URL尾号 > 原名
        var epNum = '';
        var mm = nm.match(/EP(\d+)/i);
        if (mm != null) { epNum = mm[1]; }
        if (epNum == '') { mm = nm.match(/第?(\d+)集/); if (mm != null) { epNum = mm[1]; } }
        if (epNum == '') { mm = href.match(/-(\d+)\.html$/); if (mm != null) { epNum = mm[1]; } }
        if (epNum == '') { epNum = nm; }
        if (seen[epNum]) { continue; }   // 同集不同片源(S1_EP1(2)(3))只留第一个
        seen[epNum] = 1;
        eps.push({ name: '第' + epNum + '集', num: epNum, url: getUrl(href) });
    }
    return eps;
}

// ============ 主页 ============
function 主页() {
    var d = [];
    var page = MY_PAGE;
    page = parseInt(page) || 1;
    if (page == 1) {
        var domOptions = '';
        for (var di = 0; di < DOMAINS.length; di++) {
            if (di > 0) { domOptions = domOptions + ','; }
            domOptions = domOptions + '"' + DOMAINS[di].replace('https://', '') + '"';
        }
        d.push({
            title: '切换域名',
            desc: '当前: ' + HOST.replace('https://', ''),
            col_type: 'flex_button',
            url: 'select://' + JSON.stringify({
                title: '选择域名',
                options: JSON.parse('[' + domOptions + ']'),
                col: 1,
                js: 'var doms=["https://www.kpkuang.us","https://www.kpkuang.cfd","https://kpkuang.fyi","https://kpkuang.org"];for(var ii=0;ii<doms.length;ii++){if(doms[ii].replace("https://","")==input){putMyVar("kpkuangHost",doms[ii]);putMyVar("kpkuangFast",doms[ii].replace("https://",""));putMyVar("MY_PAGE",1);refreshPage();break;}}"hiker://empty";'
            })
        });
        for (var k = 0; k < CATS.length; k++) {
            var it = CATS[k];
            d.push({ title: it.name == getMyVar('nowCatName', '电影') ? ('““' + it.name + '””') : it.name, col_type: 'scroll_button', url: $('#noLoading#').lazyRule(function (itData) { putMyVar("nowCat", itData.id); putMyVar("nowCatName", itData.name); putMyVar("nowSub", itData.sub[0].code); putMyVar("MY_PAGE", 1); refreshPage(); return 'hiker://empty'; }, it) });
        }
        d.push({ "col_type": "blank_block" });
        var nowCat = getMyVar('nowCat', '1');
        var nowCatName = getMyVar('nowCatName', '电影');
        var nowSub = getMyVar('nowSub', '1');
        var curCat = null;
        for (var ci = 0; ci < CATS.length; ci++) {
            if (CATS[ci].id == nowCat) { curCat = CATS[ci]; break; }
        }
        if (curCat == null) { curCat = CATS[0]; }
        var subList = curCat.sub;
        for (var si = 0; si < subList.length; si++) {
            var sobj = subList[si];
            d.push({ title: sobj.code == nowSub ? ('““' + sobj.name + '””') : sobj.name, col_type: "scroll_button", url: $('#noLoading#').lazyRule(function (e) { putMyVar('nowSub', e.code); putMyVar("MY_PAGE", 1); refreshPage(); return 'hiker://empty'; }, sobj) });
        }
        d.push({ "col_type": "blank_block" });
    }
    var nowCat2 = getMyVar('nowCat', '1');
    var nowSub2 = getMyVar('nowSub', '1');
    var true_url = HOST + "/vodtype/" + nowSub2 + "/page/" + page + ".html";
    var html = getHtml(true_url);
    if (html == '') {
        d.push({ title: '加载失败，请稍后重试', col_type: 'text_1' });
    } else {
        var list = pdfa(html, 'body&&li.fed-list-item');
        for (var i = 0; i < list.length; i++) {
            var video = list[i];
            var t = pdfh(video, 'a.fed-list-pics&&title') || '';
            if (t == '') { t = pdfh(video, 'span.cinema_title&&Text') || ''; }
            if (t == '') { t = pdfh(video, 'a.fed-list-title&&Text') || ''; }
            var u = getUrl(pd(video, 'a.fed-list-pics&&href'));
            var img = getImg(pd(video, 'a.fed-list-pics&&data-original'));
            var desc = pdfh(video, 'span.fed-list-name&&Text') || '';
            if (desc == '') { desc = pdfh(video, 'span.fed-list-remarks&&Text') || ''; }
            if (u == '' || t == '') { continue; }
            d.push({ title: t, desc: desc, img: img, url: u + '#immersiveTheme##autoCache#@rule=js:$.require("kpkuang").详情()', col_type: 'movie_3_marquee' });
        }
    }
    setResult(d);
}

// ============ 搜索 ============
function 搜索() {
    var d = [];
    var kw = getParam('kw', '') || '';
    if (kw == '') {
        var km = MY_URL.match(/[?&]kw=([^&]+)/);
        if (km != null) { kw = decodeURIComponent(km[1]); }
    }
    var html = getResCode();
    if (html == null || html == '' || html.indexOf('"code":1') == -1) {
        var ts = new Date().getTime();
        html = getHtmlWithHeaders('https://kpdata.flixfiend.top/esearch/index?kw=' + encodeURIComponent(kw) + '&ts=' + ts + '&callback=cb');
    }
    var data = [];
    if (html != '') {
        var m = html.match(/"js":"([^"]+)"/);
        if (m != null && m[1] != '') {
            try {
                var jsonStr = base64Decode(m[1]);
                data = JSON.parse(jsonStr);
            } catch (e) { data = []; }
        }
    }
    if (data == null || data.length == 0) {
        d.push({ title: '未找到相关影片', col_type: 'text_1' });
    } else {
        for (var i = 0; i < data.length; i++) {
            var item = data[i];
            if (item == null) { continue; }
            var itData = item.data || {};
            var itHigh = item.high || {};
            var title = itHigh.vod_name || itData.vod_name || '';
            if (typeof title == 'object') { title = title.join(' '); }
            title = title.replace(/<[^>]+>/g, '').trim();
            var href = HOST + '/voddetail/' + item.id + '/';
            var img = itData.vod_imdb_poster || itData.vod_douban_cover || itData.vod_pic || '';
            if (img == '') { img = ''; }
            if (img.indexOf('http') == -1) { img = getImg(img); }
            if (title == '') { continue; }
            d.push({ title: title, desc: '', img: img, url: href + '#immersiveTheme##autoCache#@rule=js:$.require("kpkuang").详情()', col_type: 'movie_3_marquee' });
        }
    }
    setResult(d);
}

// ============ 详情 (v2) ============
function 详情() {
    var d = [];
    var html = getResCode();
    if (html == null || html == '' || (html.indexOf('fed-drop-btns') == -1 && html.indexOf('fed-play-item') == -1 && html.indexOf('<h1') == -1)) {
        html = getHtml(MY_URL);
    }
    if (html == '') {
        d.push({ title: '加载失败，请稍后重试', col_type: 'text_1' });
    } else {
        var title = pdfh(html, 'h1&&Text') || '';
        var img = pd(html, 'img[data-original]&&data-original') || '';
        img = getImg(img);
        var desc = '';
        var raw = pdfh(html, 'body&&Text') || '';
        var di = raw.indexOf('以下是剧情简介：');
        if (di >= 0) {
            desc = raw.substring(di + 8, di + 300);
        } else {
            di = raw.indexOf('简介：');
            if (di >= 0) { desc = raw.substring(di + 3, di + 300); }
        }
        desc = desc.replace(/\s+/g, ' ').trim();
        if (desc.length > 200) { desc = desc.substring(0, 200) + '...'; }
        if (title != '') {
            d.push({ title: title, img: img, desc: '', col_type: 'movie_1_vertical_pic_blur' });
        }
        if (desc != '') {
            d.push({ title: desc, col_type: 'long_text' });
        }
        d.push({ col_type: 'blank_block' });

        // ---- 线路名 ----
        var lines = [];
        var reLine = /<li[^>]*class="[^"]*fed-drop-btns[^"]*"[^>]*>([\s\S]*?)<a\b[^>]*>([\s\S]*?)<\/a>/gi;
        var ml;
        while ((ml = reLine.exec(html)) != null) {
            var ln = (ml[2] || '').replace(/<[^>]+>/g, '').replace(/\s+/g, '');
            if (ln != '') { lines.push(ln); }
        }
        if (lines.length == 0) {
            // 兜底: 用 pdfa
            var lineEls = pdfa(html, 'body&&li.fed-drop-btns');
            if (lineEls != null) {
                for (var li2 = 0; li2 < lineEls.length; li2++) {
                    var ln2 = pdfh(lineEls[li2], 'a&&Text') || '';
                    ln2 = ln2.replace(/\s+/g, '');
                    if (ln2 != '') { lines.push(ln2); }
                }
            }
        }

        // ---- 选集块 ----
        var rawBlocks = [];
        var blocksHtml = splitPlayBlocks(html);
        for (var bi = 0; bi < blocksHtml.length; bi++) {
            rawBlocks.push(parseEpBlock(blocksHtml[bi]));
        }
        if (rawBlocks.length == 0) {
            // 兜底: 用 pdfa
            var playItems = pdfa(html, 'body&&li.fed-play-item');
            if (playItems != null) {
                for (var pi = 0; pi < playItems.length; pi++) {
                    rawBlocks.push(parseEpBlock(playItems[pi]));
                }
            }
        }

        // ---- 对齐: 块数>线路数时, 多余块合并进最后一个线路(按集号去重) ----
        var nLine = lines.length;
        if (nLine == 0) { lines.push('线路1'); nLine = 1; }
        if (rawBlocks.length > nLine) {
            var head = rawBlocks.slice(0, nLine - 1);
            var rest = [];
            var seen2 = {};
            for (var b = nLine - 1; b < rawBlocks.length; b++) {
                for (var e2 = 0; e2 < rawBlocks[b].length; e2++) {
                    var ep2 = rawBlocks[b][e2];
                    if (seen2[ep2.num]) { continue; }
                    seen2[ep2.num] = 1;
                    rest.push(ep2);
                }
            }
            rawBlocks = head.concat([rest]);
        }

        // ---- 只保留有集数的线路, 并按集数降序(集数最全的排第一) ----
        var items = [];
        for (var i2 = 0; i2 < lines.length && i2 < rawBlocks.length; i2++) {
            if (rawBlocks[i2].length == 0) { continue; }
            items.push({ name: lines[i2], eps: rawBlocks[i2] });
        }
        if (items.length == 0) {
            d.push({ title: '暂无线路', col_type: 'text_1' });
            setResult(d);
            return;
        }
        items.sort(function (a, b) { return b.eps.length - a.eps.length; });

        // ---- 当前线路: 未设置过则默认选第0个(集数最全) ----
        var lineKey = MY_URL + '_line';
        var nowLine = -1;
        var saved = getMyVar(lineKey, '');
        if (saved != '' && saved != null) {
            var nv = parseInt(saved);
            if (!isNaN(nv)) { nowLine = nv; }
        }
        if (nowLine < 0 || nowLine >= items.length) { nowLine = 0; }

        // ---- 线路按钮 ----
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

        // ---- 选集 ----
        var sortKey = MY_URL + '_sort';
        var sortOrder = getMyVar(sortKey, '正序');
        var newSort = sortOrder == '正序' ? '倒序' : '正序';
        d.push({ title: (sortOrder == '正序' ? '● 正序' : '● 倒序'), col_type: 'scroll_button', url: $('#noLoading#').lazyRule(function (key, val) { putMyVar(key, val); refreshPage(false); return 'hiker://empty'; }, sortKey, newSort), extra: { backgroundColor: '#3CB371' } });
        d.push({ col_type: 'blank_block' });

        var cur = items[nowLine];
        var outEp = cur.eps.slice(0);
        outEp.sort(function (a, b) {
            var na = parseInt(a.num) || 0;
            var nb = parseInt(b.num) || 0;
            return sortOrder == '倒序' ? nb - na : na - nb;
        });

        // 同集跨线路映射: num -> 其它线路的 url (备用, 最多2条)
        var altMap = {};
        for (var ai = 0; ai < items.length; ai++) {
            if (ai == nowLine) { continue; }
            for (var ae = 0; ae < items[ai].eps.length; ae++) {
                var aep = items[ai].eps[ae];
                if (!altMap[aep.num]) { altMap[aep.num] = []; }
                if (altMap[aep.num].length < 2) { altMap[aep.num].push(aep.url); }
            }
        }

        for (var c = 0; c < outEp.length; c++) {
            var ep = outEp[c];
            var cands = [ep.url];
            var alts = altMap[ep.num] || [];
            for (var al = 0; al < alts.length; al++) {
                if (alts[al] != ep.url) { cands.push(alts[al]); }
            }
            var candsStr = cands.join('||');
            // 播放: 依次尝试候选(首选 + 同集备用线路), 校验通过才返回
            var lazy = $('').lazyRule(function (candsStr2) {
                var UA2 = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';
                var list2 = String(candsStr2).split('||');
                var firstDirect = '';
                var multi = list2.length > 1;
                try {
                    for (var ci2 = 0; ci2 < list2.length; ci2++) {
                        var pu = list2[ci2];
                        var ph = request(pu) || '';
                        var dm = ph.match(/data-play="([^"]+)"/);
                        if (dm == null || dm[1] == '') { continue; }
                        var realUrl = '';
                        try { realUrl = base64Decode(dm[1].substring(3)); } catch (e1) {
                            try { realUrl = base64Decode(dm[1]); } catch (e2) { realUrl = ''; }
                        }
                        if (realUrl.indexOf('http') != 0) { continue; }
                        if (realUrl.indexOf('.m3u8') != -1) {
                            if (firstDirect == '') { firstDirect = realUrl; }
                            if (multi) {
                                // 校验: 必须真能拿到 m3u8 内容(废源分片能下但流无效 -> 跑流量不出画面)
                                var ok = true;
                                try {
                                    var mc = fetch(realUrl, { headers: { 'User-Agent': UA2 }, timeout: 6000 }) || '';
                                    if (mc.indexOf('#EXTM3U') == -1) { ok = false; }
                                } catch (e3) { ok = true; }
                                if (!ok) { continue; }
                            }
                            return realUrl;
                        }
                        if (realUrl.indexOf('.mp4') != -1 || realUrl.indexOf('.flv') != -1) {
                            return realUrl;
                        }
                        // 非直链: 嗅探播放器页
                        return 'video://' + realUrl;
                    }
                } catch (e9) { }
                if (firstDirect != '') { return firstDirect; }
                // 全部失败: 兜底嗅探首选播放页
                return 'video://' + list2[0];
            }, candsStr);
            d.push({ title: ep.name, url: ep.url + '@' + lazy, col_type: outEp.length > 6 ? 'text_4' : 'text_2', extra: { cls: 'playlist', id: ep.url } });
        }
    }
    setResult(d);
}

$.exports = { 主页: 主页, 搜索: 搜索, 详情: 详情 };
