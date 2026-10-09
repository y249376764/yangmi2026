/**
 * 奈飞工厂 netflixgc.com 影视源
 * 新式 JS0 接口源（适配 FongMi TVBox / 影视仓）
 * 列表：POST /index.php/ds_api/vod {type,class,area,year,lang,version,state,letter,by,page} → JSON
 * 详情：/voddetail/{id}.html 解析简介/演员/资源列表（多源多集）
 * 播放：/vodplay/{id}-{sid}-{nid}.html，player_aaaa encrypt:2 → unescape(base64decode(url)) → m3u8
 * 搜索：/vodsearch/-------------.html?wd= 解析内嵌结果
 */

let host = 'https://www.netflixgc.com';
// 备用域名池（主域名失败自动切换）
const HOSTS = ['https://www.netflixgc.com', 'https://www.netflixgc.net'];
let hostIdx = 0;
let UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15';

// 5个分类（MacCMS type id）
const CATS = [
    ['电影', 1], ['连续剧', 2], ['纪录片', 24], ['漫剧', 3], ['综艺', 23]
];

function clean(s) {
    return (s || '').replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#39;/g, "'").trim();
}

async function getHtml(url, postData) {
    // 域名失败自动切换重试（最多尝试全部域名）
    for (let attempt = 0; attempt < HOSTS.length; attempt++) {
        if (attempt > 0) {
            hostIdx = (hostIdx + 1) % HOSTS.length;
            host = HOSTS[hostIdx];
        }
        let thisUrl = url.replace(HOSTS[(hostIdx + HOSTS.length - 1) % HOSTS.length], host);
        try {
            let opts = { headers: { 'User-Agent': UA, 'Referer': host, 'X-Requested-With': 'XMLHttpRequest' } };
            let res;
            if (postData) {
                opts.headers['Content-Type'] = 'application/x-www-form-urlencoded';
                opts.method = 'POST';
                opts.body = postData;
                res = await req(thisUrl, opts);
            } else {
                res = await req(thisUrl, opts);
            }
            let content = res ? res.content || '' : '';
            if (content && content.length > 1) {
                return content;
            }
        } catch (e) {}
    }
    return '';
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

async function fetchList(type, pg, by, filter) {
    pg = pg || 1;
    filter = filter || {};
    // 二级筛选: 类型/地区/年份/语言 (filter 是 {key: value})
    let cls = filter['class'] || '';
    let area = filter['area'] || '';
    let year = filter['year'] || '';
    let lang = filter['lang'] || '';
    let data = 'type=' + (type || '') + '&class=' + encodeURIComponent(cls) + '&area=' + encodeURIComponent(area) + '&year=' + encodeURIComponent(year) + '&lang=' + encodeURIComponent(lang) + '&version=&state=&letter=&by=' + (by || 'time') + '&level=0&weekday=&page=' + pg;
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
 * 首页分类 (带二级筛选: 类型/地区/年份/语言/版本/状态)
 */
async function home(filter) {
    let classes = CATS.map(c => ({ type_id: String(c[1]), type_name: c[0] }));
    let filters = {
        'class': { key: 'class', name: '类型', value: [
            {n: '全部', v: ''}, {n: '剧情', v: '剧情'}, {n: '动作', v: '动作'}, {n: '爱情', v: '爱情'}, {n: '科幻', v: '科幻'},
            {n: '喜剧', v: '喜剧'}, {n: '悬疑', v: '悬疑'}, {n: '惊悚', v: '惊悚'}, {n: '战争', v: '战争'}, {n: '犯罪', v: '犯罪'},
            {n: '恐怖', v: '恐怖'}, {n: '冒险', v: '冒险'}, {n: '动画', v: '动画'}, {n: '纪录', v: '纪录'}, {n: '奇幻', v: '奇幻'}
        ]},
        'area': { key: 'area', name: '地区', value: [
            {n: '全部', v: ''}, {n: '大陆', v: '大陆'}, {n: '香港', v: '香港'}, {n: '台湾', v: '台湾'}, {n: '美国', v: '美国'},
            {n: '韩国', v: '韩国'}, {n: '日本', v: '日本'}, {n: '英国', v: '英国'}, {n: '法国', v: '法国'}, {n: '泰国', v: '泰国'},
            {n: '印度', v: '印度'}, {n: '其他', v: '其他'}
        ]},
        'year': { key: 'year', name: '年份', value: [
            {n: '全部', v: ''}, {n: '2026', v: '2026'}, {n: '2025', v: '2025'}, {n: '2024', v: '2024'}, {n: '2023', v: '2023'},
            {n: '2022', v: '2022'}, {n: '2021', v: '2021'}, {n: '2020', v: '2020'}, {n: '2019', v: '2019'}, {n: '2018', v: '2018'},
            {n: '2017', v: '2017'}, {n: '更早', v: '2016'}
        ]},
        'lang': { key: 'lang', name: '语言', value: [
            {n: '全部', v: ''}, {n: '国语', v: '国语'}, {n: '粤语', v: '粤语'}, {n: '英语', v: '英语'}, {n: '日语', v: '日语'},
            {n: '韩语', v: '韩语'}, {n: '法语', v: '法语'}, {n: '其他', v: '其他'}
        ]}
    };
    return JSON.stringify({ class: classes, filters: filters });
}

/**
 * 首页推荐（最新）
 */
async function homeVod() {
    let r = await fetchList('', 1);
    return JSON.stringify({ list: r.list });
}

/**
 * 分类列表 (支持二级筛选: filter 为 {class/area/year/lang: value})
 */
async function category(tid, pg, filter, extend) {
    let r = await fetchList(tid, pg, 'time', filter || {});
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
    // 源 tab：anthology-tab 里多个 <a class="swiper-slide"><i></i>&nbsp;线路名<span class="badge">N</span></a>
    // 一次抓取 tab 容器内所有线路名（不再锚定 anthology-tab 导致只匹配第一个）
    let srcNames = [];
    let tabRe = /<div class="anthology-tab[\s\S]*?<div class="swiper-wrapper">([\s\S]*?)<\/div><\/div>/;
    let tabHtml = (html.match(tabRe) || [])[1] || '';
    if (tabHtml) {
        let slideRe = /<a class="swiper-slide">[\s\S]*?<\/i>&nbsp;([^<]+?)(?:<span class="badge">\d+<\/span>)?<\/a>/g;
        let sm;
        while ((sm = slideRe.exec(tabHtml)) !== null) {
            let n = clean(sm[1]);
            if (n && srcNames.indexOf(n) === -1) srcNames.push(n);
        }
    }
    // 集数按源分组：每个 anthology-list-box 一组
    let boxRe = /<div class="anthology-list-box[^"]*">[\s\S]*?<ul class="anthology-list-play[^"]*">([\s\S]*?)<\/ul>/g;
    let boxes = [];
    while ((m = boxRe.exec(html)) !== null) boxes.push(m[1]);
    let playFrom = [], playUrl = [];
    let lineCount = Math.max(srcNames.length, boxes.length);
    for (let li = 0; li < lineCount; li++) {
        let name = srcNames[li] || ('线路' + (li + 1));
        let box = boxes[li] || '';
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
    }
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
    let m = html.match(/player_aaaa=(\{[\s\S]*?\})<\/script>/);
    let url = '';
    let urlNext = '';
    if (m) {
        try {
            let p = JSON.parse(m[1]);
            let raw = p.url || '';
            if (raw) {
                if (p.encrypt == '2') {
                    url = decodeURIComponent(base64decode(raw));
                } else if (p.encrypt == '1') {
                    url = decodeURIComponent(raw);
                } else {
                    url = raw;
                }
            }
            // url_next 备用 (连播下一集)
            if (p.url_next) {
                let rn = p.url_next;
                if (p.encrypt == '2') {
                    urlNext = decodeURIComponent(base64decode(rn));
                } else if (p.encrypt == '1') {
                    urlNext = decodeURIComponent(rn);
                } else {
                    urlNext = rn;
                }
            }
        } catch (e) {}
    }
    if (!url) {
        let m2 = html.match(/https?:\/\/[^"'\s<>]+?\.m3u8[^"'\s<>]*/);
        if (m2) url = m2[0];
    }
    if (!url && urlNext) url = urlNext;
    // ===== 快速探测: 当前线路 m3u8 不可达时, 自动换同剧其他线路 =====
    if (url) {
        let ok = await probeUrl(url);
        if (!ok) {
            // 从当前播放页找同剧其他 sid 的 vodplay 链接 (选集列表)
            let sidRe = /\/vodplay\/(\d+)-(\d+)-(\d+)\.html/g;
            let sids = {}, sm;
            while ((sm = sidRe.exec(html)) !== null) {
                if (!sids[sm[2]]) sids[sm[2]] = 1;
            }
            let curSid = (id.match(/-(\d+)-\d+\.html/) || [])[1] || '';
            for (let sid in sids) {
                if (sid === curSid) continue;
                let altHtml = await getHtml(host + '/vodplay/' + id.replace(/-\d+-\d+\.html/, '-' + sid + '-1.html'));
                let am = altHtml.match(/player_aaaa=(\{[\s\S]*?\})<\/script>/);
                if (am) {
                    try {
                        let ap = JSON.parse(am[1]);
                        let aurl = ap.url || '';
                        if (aurl) {
                            if (ap.encrypt == '2') aurl = decodeURIComponent(base64decode(aurl));
                            else if (ap.encrypt == '1') aurl = decodeURIComponent(aurl);
                        }
                        if (aurl && await probeUrl(aurl)) {
                            url = aurl;
                            break;
                        }
                    } catch (e) {}
                }
            }
        }
    }
    // 带完整 header (UA + Referer), 防分片防盗链导致卡顿
    let header = 'User-Agent=' + UA + '&Referer=' + host + '/';
    return JSON.stringify({ parse: 0, url: url, header: header });
}

// 快速探测 m3u8 可访问性 (3秒超时, 只读前几字节)
async function probeUrl(u) {
    try {
        let res = await req(u, {
            headers: { 'User-Agent': UA, 'Referer': host + '/' },
            timeout: 3
        });
        return !!(res && res.content && res.content.length > 0);
    } catch (e) {
        return false;
    }
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
