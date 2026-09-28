/**
 * 奈飞工厂 netflixgc.com 影视源
 * 新式 JS0 接口源（适配 FongMi TVBox / 影视仓）
 * 列表：POST /index.php/ds_api/vod {type,class,area,year,lang,version,state,letter,by,page} → JSON
 * 详情：/voddetail/{id}.html 解析简介/演员/资源列表（多源多集）
 * 播放：/vodplay/{id}-{sid}-{nid}.html，player_aaaa encrypt:2 → unescape(base64decode(url)) → m3u8
 * 搜索：/vodsearch/-------------.html?wd= 解析内嵌结果
 */

let host = 'https://www.netflixgc.com';
let UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15';

// 5个分类（MacCMS type id）
const CATS = [
    ['电影', 1], ['连续剧', 2], ['纪录片', 24], ['漫剧', 3], ['综艺', 23]
];

function clean(s) {
    return (s || '').replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#39;/g, "'").trim();
}

async function getHtml(url, postData) {
    try {
        let opts = { headers: { 'User-Agent': UA, 'Referer': host, 'X-Requested-With': 'XMLHttpRequest' } };
        let res;
        if (postData) {
            opts.headers['Content-Type'] = 'application/x-www-form-urlencoded';
            opts.method = 'POST';
            opts.body = postData;
            res = await req(url, opts);
        } else {
            res = await req(url, opts);
        }
        return res ? res.content || '' : '';
    } catch (e) {
        return '';
    }
}

// ============ 列表解析（ds_api/vod JSON） ============
function parseListJson(jsonStr) {
    let list = [];
    try {
        let d = JSON.parse(jsonStr);
        if (d && d.code == 1 && d.list) {
            d.list.forEach(v => {
                list.push({
                    vod_id: v.vod_id,
                    vod_name: v.vod_name || '',
                    vod_pic: v.vod_pic || '',
                    vod_remarks: v.vod_remarks || (v.vod_score ? v.vod_score : ''),
                    vod_actor: v.vod_actor || ''
                });
            });
        }
    } catch (e) {}
    return list;
}

async function fetchList(type, pg, by) {
    pg = pg || 1;
    let data = 'type=' + (type || '') + '&class=&area=&year=&lang=&version=&state=&letter=&by=' + (by || 'time') + '&level=0&weekday=&page=' + pg;
    let json = await getHtml(host + '/index.php/ds_api/vod', data);
    let list = parseListJson(json);
    let pagecount = 1;
    try {
        let d = JSON.parse(json);
        pagecount = d.pagecount || 1;
    } catch (e) {}
    return { list: list, page: pg, pagecount: pagecount };
}

/**
 * 初始化配置
 */
async function init(cfg) {}

/**
 * 首页分类
 */
async function home(filter) {
    let classes = CATS.map(c => ({ type_id: String(c[1]), type_name: c[0] }));
    return JSON.stringify({ class: classes, filters: {} });
}

/**
 * 首页推荐（最新）
 */
async function homeVod() {
    let r = await fetchList('', 1);
    return JSON.stringify({ list: r.list });
}

/**
 * 分类列表
 */
async function category(tid, pg, filter, extend) {
    let r = await fetchList(tid, pg);
    return JSON.stringify({ page: r.page, pagecount: r.pagecount, list: r.list });
}

/**
 * 详情页
 */
async function detail(id) {
    let html = await getHtml(host + '/voddetail/' + id + '.html');
    let vod = { vod_id: id, vod_name: '', vod_pic: '', vod_content: '', vod_actor: '', vod_director: '', vod_remarks: '', vod_play_url: '', vod_play_from: '' };
    // 书名/片名：<title> 或 h1
    let m = html.match(/<h1[^>]*>([^<]{2,50})<\/h1>/);
    if (!m) m = html.match(/<title>([^<]{2,50})/);
    if (m) vod.vod_name = clean(m[1]).replace(/_电影.*|_连续剧.*|_纪录片.*|_综艺.*|_漫剧.*/, '');
    // 封面
    m = html.match(/<img[^>]+class="lazy[^"]*"[^>]+src="data:image[^"]*"[^>]*data-src="([^"]+)"/);
    if (!m) m = html.match(/detail-pic[\s\S]*?<img[^>]+data-src="([^"]+)"/);
    if (!m) m = html.match(/<img[^>]+data-src="([^"]+\.(?:jpg|jpeg|png|webp))"/);
    if (m) vod.vod_pic = m[1];
    // 简介
    m = html.match(/id="height_limit"[^>]*>([\s\S]*?)<\/div>/);
    if (m) vod.vod_content = clean(m[1]);
    // 导演
    m = html.match(/导演\s*:\s*<\/strong>([\s\S]*?)<\/div>/);
    if (m) vod.vod_director = clean(m[1]);
    // 演员
    m = html.match(/演员\s*:\s*<\/strong>([\s\S]*?)<\/div>/);
    if (m) vod.vod_actor = clean(m[1]);
    // 备注（更新/评分）
    m = html.match(/更新：<\/em>([^<]+)</);
    if (m) vod.vod_remarks = clean(m[1]);

    // ===== 资源列表（多源多集） =====
    // 源 tab：anthology-tab 里 <a class="swiper-slide"><i></i>&nbsp;蓝光-1<span class="badge">10</span></a>
    // 集数：anthology-list-box 里 <a class="hide this-link" href="/vodplay/{id}-{sid}-{nid}.html">标题</a>
    let srcNames = [];
    let srcRe = /anthology-tab[\s\S]*?<a class="swiper-slide">[\s\S]*?<\/i>&nbsp;([^<]+?)(?:<span class="badge">\d+<\/span>)?<\/a>/g;
    while ((m = srcRe.exec(html)) !== null) {
        srcNames.push(clean(m[1]));
    }
    // 集数按源分组：每个 anthology-list-box 一组
    let boxRe = /<div class="anthology-list-box[^"]*">[\s\S]*?<ul class="anthology-list-play[^"]*">([\s\S]*?)<\/ul>/g;
    let boxes = [];
    while ((m = boxRe.exec(html)) !== null) boxes.push(m[1]);
    let playFrom = [], playUrl = [];
    srcNames.forEach(function (name, idx) {
        let box = boxes[idx] || '';
        let epRe = /<a[^>]+href="\/vodplay\/\d+-(\d+)-(\d+)\.html"[^>]*>([^<]*)<\/a>/g;
        let eps = [], em;
        while ((em = epRe.exec(box)) !== null) {
            let title = clean(em[3]);
            if (!title) title = em[2];
            eps.push(title + '$' + host + '/vodplay/' + id + '-' + em[1] + '-' + em[2] + '.html');
        }
        if (eps.length > 0) {
            playFrom.push(name);
            playUrl.push(eps.join('#'));
        }
    });
    // 兜底：直接抓所有 vodplay 链接按 sid 分组
    if (playFrom.length === 0) {
        let allEpRe = /<a[^>]+href="\/vodplay\/(\d+)-(\d+)-(\d+)\.html"[^>]*>([^<]*)<\/a>/g;
        let groups = {};
        while ((m = allEpRe.exec(html)) !== null) {
            let sid = m[2], nid = m[3], title = clean(m[4]) || nid;
            if (!groups[sid]) groups[sid] = [];
            groups[sid].push(title + '$' + host + '/vodplay/' + id + '-' + sid + '-' + nid + '.html');
        }
        let sids = Object.keys(groups);
        sids.forEach(function (sid, idx) {
            playFrom.push('线路' + (idx + 1));
            playUrl.push(groups[sid].join('#'));
        });
    }
    vod.vod_play_from = playFrom.join('$$$');
    vod.vod_play_url = playUrl.join('$$$');
    return JSON.stringify({ list: [vod] });
}

/**
 * 搜索
 */
async function search(wd, quick) {
    let html = await getHtml(host + '/vodsearch/-------------.html?wd=' + encodeURIComponent(wd));
    let list = [];
    // 搜索卡片：detail-pic img（alt+data-src 顺序不固定）+ detail-info a[href=/voddetail/] > h3 标题
    let re = /<div class="detail-pic">[\s\S]*?data-src="([^"]+)"[\s\S]*?alt="([^"]*)"[\s\S]*?<a[^>]+href="\/voddetail\/(\d+)\.html"[^>]*>[\s\S]*?<h3[^>]*>([^<]*)<\/h3>/g;
    let m;
    while ((m = re.exec(html)) !== null) {
        list.push({
            vod_id: m[3],
            vod_name: clean(m[4]) || clean(m[2]),
            vod_pic: m[1],
            vod_remarks: ''
        });
    }
    // 兜底：任意 voddetail 链接
    if (list.length === 0) {
        let re2 = /<a[^>]+href="\/voddetail\/(\d+)\.html"[^>]*>([^<]{2,40})<\/a>/g;
        let seen = {};
        while ((m = re2.exec(html)) !== null) {
            if (!seen[m[1]]) {
                seen[m[1]] = 1;
                list.push({ vod_id: m[1], vod_name: clean(m[2]), vod_pic: '', vod_remarks: '' });
            }
        }
    }
    return JSON.stringify({ list: list });
}

/**
 * 播放解析：player_aaaa encrypt:2 → unescape(base64decode(url))
 */
function base64decode(str) {
    try {
        let bin = atob(str);
        let bytes = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
        return new TextDecoder().decode(bytes);
    } catch (e) {
        return '';
    }
}

async function play(flag, id, flags) {
    // id 形如 https://www.netflixgc.com/vodplay/152700-1-1.html
    let html = await getHtml(id);
    let m = html.match(/player_aaaa=({[\s\S]*?})<\/script>/);
    let url = '';
    if (m) {
        try {
            let p = JSON.parse(m[1]);
            if (p.url) {
                if (p.encrypt == '2') {
                    url = decodeURIComponent(base64decode(p.url));
                } else if (p.encrypt == '1') {
                    url = decodeURIComponent(p.url);
                } else {
                    url = p.url;
                }
            }
        } catch (e) {}
    }
    if (!url) {
        let m2 = html.match(/https?:\/\/[^"'\s<>]+?\.m3u8[^"'\s<>]*/);
        if (m2) url = m2[0];
    }
    return JSON.stringify({ parse: 0, url: url, header: 'User-Agent=' + UA });
}

// 导出标准接口对象
export default {
    init,
    home,
    homeVod,
    category,
    detail,
    search,
    play
};
