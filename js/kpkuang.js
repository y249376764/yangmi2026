/**
 * 看片狂人 新式 JS0 接口源
 * 适配 FongMi TVBox / 默影视 规范
 * 播放: 优先直链, 非标准地址走 tvbox-xg 嗅探
 * 更多资源请到网站 https://navpage-2026.surge.sh/
 */
let hosts = ['https://www.kpkuang.us', 'https://www.kpkuang.cfd', 'https://www.kpkuang.fyi'];
let host = hosts[0];
let UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';

async function init(cfg) { }

async function home(filter) {
    return JSON.stringify({
        class: [
            { type_id: '1', type_name: '电影' },
            { type_id: '2', type_name: '连续剧' },
            { type_id: '3', type_name: '综艺' },
            { type_id: '4', type_name: '动漫' },
            { type_id: '37', type_name: '短剧' }
        ],
        filters: {}
    });
}

async function homeVod() {
    let html = await req(`${host}/vodtype/1.html`, { headers: { 'User-Agent': UA } });
    let videos = parseList(html.content);
    return JSON.stringify({ list: videos });
}

function parseList(html) {
    let videos = [];
    let seen = {};
    // 卡片: a[href=/voddetail/xxx] 标题是 a 文本 (fed 模板)
    let re = /<a[^>]*href="(\/voddetail\/[^"]+)"[^>]*>(.*?)<\/a>/g;
    let m;
    while ((m = re.exec(html)) !== null) {
        let href = m[1], blk = m[2];
        if (href in seen) continue;
        seen[href] = 1;
        let title = blk.replace(/<[^>]+>/g, '').replace(/\s+/g, '').trim();
        if (!title || title.length < 2) continue;
        // 图片: 卡片附近的 data-original (CSS 背景图可能拿不到, 尽力)
        let pic = '';
        let ctx = html.substring(Math.max(0, m.index - 400), m.index + 400);
        let pm = ctx.match(/(?:data-original|data-src|src)="(https?:\/\/[^"]+)"/);
        if (pm) pic = pm[1];
        videos.push({
            vod_id: href,
            vod_name: title,
            vod_pic: pic,
            vod_remarks: ''
        });
    }
    return videos;
}

async function category(tid, pg, filter, extend) {
    let url = `${host}/vodtype/${tid}.html`;
    if (pg > 1) url = `${host}/vodtype/${tid}-${pg}.html`;
    let html = await req(url, { headers: { 'User-Agent': UA } });
    let videos = parseList(html.content);
    return JSON.stringify({ page: pg, pagecount: 999, list: videos });
}

async function detail(id) {
    let url = id.startsWith('http') ? id : host + id;
    let html = await req(url, { headers: { 'User-Agent': UA, 'Referer': host } });
    let h = html.content;
    let vod = {
        vod_id: id,
        vod_name: '未知影片',
        vod_pic: '',
        vod_year: '',
        vod_area: '',
        vod_actor: '',
        vod_director: '',
        vod_content: '',
        vod_play_from: '',
        vod_play_url: ''
    };
    let om = h.match(/<h1[^>]*>([^<]+)<\/h1>/);
    if (om) vod.vod_name = om[1].trim();
    let pm = h.match(/<meta[^>]*property="og:image"[^>]*content="([^"]+)"/);
    if (pm) vod.vod_pic = pm[1];
    let dm = h.match(/<meta[^>]*name="description"[^>]*content="([^"]*)"/);
    if (dm) vod.vod_content = dm[1].trim();
    // 线路 + 选集: "XX的播放列表" + ul.fed-part-rows
    let lineRe = /<span[^>]*>([^<]+)<\/span>\s*的播放列表.*?<ul class="fed-part-rows"[^>]*>(.*?)<\/ul>/g;
    let lines = [], lineMap = {};
    let lm;
    while ((lm = lineRe.exec(h)) !== null) {
        let name = lm[1].replace(/\s+/g, '');
        if (!name || lineMap[name]) continue;
        lineMap[name] = [];
        let epsRe = /<a[^>]*class="[^"]*fed-btns-info[^"]*"[^>]*href="(\/vodplay\/[^"]+)"[^>]*>(.*?)<\/a>/g;
        let em;
        while ((em = epsRe.exec(lm[2])) !== null) {
            let href = em[1];
            let label = em[2].replace(/<[^>]+>/g, '').replace(/\s+/g, '');
            if (!label) continue;
            lineMap[name].push(`${label}$${host + href}`);
        }
        lines.push(name);
    }
    if (lines.length) {
        vod.vod_play_from = lines.join('$$$');
        vod.vod_play_url = lines.map(l => lineMap[l].join('#')).join('$$$');
    }
    return JSON.stringify({ list: [vod] });
}

async function search(wd, quick) {
    let url = `${host}/vodsearch/${encodeURIComponent(wd)}.html`;
    let html = await req(url, { headers: { 'User-Agent': UA } });
    let videos = parseList(html.content);
    return JSON.stringify({ list: videos });
}

async function play(flag, id, flags) {
    // 播放页地址 -> 交给 XG 嗅探 (tvbox-xg:)
    return JSON.stringify({ parse: 0, url: `tvbox-xg:${id}` });
}

export default { init, home, homeVod, category, detail, search, play };
