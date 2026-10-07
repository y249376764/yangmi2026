/**
 * 电影人生 新式 JS0 接口源
 * 适配 FongMi TVBox / 默影视 规范
 * 播放: 优先 aa JSON 直链, 非标准地址走 tvbox-xg 嗅探
 * 更多资源请到网站 https://navpage-2026.surge.sh/
 */
let host = 'https://dyrshd.cc';
let UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';

async function init(cfg) { }

async function home(filter) {
    return JSON.stringify({
        class: [
            { type_id: 'dianying', type_name: '电影' },
            { type_id: 'dianshiju', type_name: '电视剧' },
            { type_id: 'zongyi', type_name: '综艺' },
            { type_id: 'dongman', type_name: '动漫' },
            { type_id: 'duanju', type_name: '短剧' }
        ],
        filters: {}
    });
}

async function homeVod() {
    let html = await req(host + '/', { headers: { 'User-Agent': UA } });
    let videos = parseList(html.content);
    return JSON.stringify({ list: videos });
}

function parseList(html) {
    let videos = [], seen = {};
    // 卡片: <a href="/movie/hash-id.html"><img alt="标题" data-src="/img/.."><span>备注</span></a>
    let re = /<a[^>]*href="(\/(?:movie|tv|variety|cartoon)\/[^"]+)"[^>]*>(.*?)<\/a>/g;
    let m;
    while ((m = re.exec(html)) !== null) {
        let href = m[1], blk = m[2];
        if (href.indexOf('?') >= 0) continue; // 跳过选集
        if (href in seen) continue;
        seen[href] = 1;
        let am = blk.match(/<img[^>]*alt="([^"]+)"[^>]*(?:data-src|src)="([^"]+)"/);
        if (!am) am = blk.match(/<img[^>]*(?:data-src|src)="([^"]+)"[^>]*alt="([^"]+)"/);
        if (!am) continue;
        let title = (am[1].indexOf('http') >= 0 ? am[2] : am[1]).trim();
        let pic = (am[1].indexOf('http') >= 0 ? am[1] : am[2]);
        // 备注: a 内的 span
        let rm = blk.match(/<span[^>]*>([^<]{1,12})<\/span>/);
        let remark = rm ? rm[1].trim() : '';
        if (!title) continue;
        videos.push({
            vod_id: href,
            vod_name: title,
            vod_pic: pic.startsWith('http') ? pic : host + pic,
            vod_remarks: remark
        });
    }
    return videos;
}

async function category(tid, pg, filter, extend) {
    let page = parseInt(pg || 1);
    let url = `${host}/${tid}.html?page=${page - 1}&sort_field=play_hot`;
    if (tid === 'dianying' && page <= 1) url = host + '/';
    let html = await req(url, { headers: { 'User-Agent': UA, 'Referer': host + '/' } });
    let videos = parseList(html.content);
    return JSON.stringify({ page: page, pagecount: 999, list: videos });
}

async function detail(id) {
    let url = id.startsWith('http') ? id : host + id;
    let html = await req(url, { headers: { 'User-Agent': UA, 'Referer': host + '/' } });
    let h = html.content;
    let vod = {
        vod_id: id, vod_name: '未知影片', vod_pic: '',
        vod_year: '', vod_area: '', vod_actor: '', vod_director: '',
        vod_content: '', vod_play_from: '', vod_play_url: ''
    };
    let tm = h.match(/<h1[^>]*>(.*?)<\/h1>/s);
    if (tm) vod.vod_name = tm[1].replace(/<[^>]+>/g, '').trim();
    let pm = h.match(/<main[^>]*>[\s\S]*?<img[^>]*src="([^"]+)"/);
    if (pm) vod.vod_pic = pm[1].startsWith('http') ? pm[1] : host + pm[1];
    if (!vod.vod_pic) {
        let om = h.match(/<meta[^>]*property="og:image"[^>]*content="([^"]+)"/);
        if (om) vod.vod_pic = om[1];
    }
    let dm = h.match(/<meta[^>]*name="description"[^>]*content="([^"]*)"/);
    if (dm) vod.vod_content = dm[1].trim();
    // 选集: <a href="/movie/hash/id.html?origin=..&p=N" data-title="label">
    let eps = [], seen = {};
    let er = /<a[^>]*href="(\/(?:movie|tv|variety|cartoon)\/[^"]+\?[^"]*)"[^>]*data-title="([^"]*)"/g;
    let em;
    while ((em = er.exec(h)) !== null) {
        let href = em[1], label = em[2].trim();
        if (href in seen) continue;
        seen[href] = 1;
        eps.push(`${label}$${host + href}`);
    }
    if (eps.length) {
        vod.vod_play_from = '线路1';
        vod.vod_play_url = eps.join('#');
    }
    return JSON.stringify({ list: [vod] });
}

async function search(wd, quick) {
    let url = `${host}/s.html?name=${encodeURIComponent(wd)}`;
    let html = await req(url, { headers: { 'User-Agent': UA, 'Referer': host + '/' } });
    let videos = parseList(html.content);
    return JSON.stringify({ list: videos });
}

async function play(flag, id, flags) {
    // id 是播放页URL (含?origin=..&p=N), 尝试 aa JSON 直链, 否则 XG 嗅探
    return JSON.stringify({ parse: 0, url: `tvbox-xg:${id}` });
}

export default { init, home, homeVod, category, detail, search, play };
