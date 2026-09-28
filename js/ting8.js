/**
 * 听书吧 ting8.cc 音频源
 * 新式 JS0 接口源（适配 FongMi TVBox / 影视仓）
 * 分类24个 /books/{id}.html，分页 /books/{id}-{页码}.html 每页16本
 * 详情 /mp3/{书id}.html 含封面/简介/章节列表 /play/{书id}-0-{集}.html
 * 播放页 var now="m4a直链" 喜马拉雅CDN
 * 说明：站内搜索有图形验证码拦截，规则内无法自动通过，搜索返回空
 */

let host = 'https://www.ting8.cc';
let UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15';

// 24个分类
const CATS = [
    ['玄幻', 1], ['言情', 2], ['都市', 3], ['恐怖', 4], ['惊悚', 5],
    ['推理', 6], ['武侠', 7], ['历史', 8], ['军事', 9], ['穿越', 10],
    ['科幻', 11], ['网游', 12], ['评书', 13], ['戏曲', 14], ['笑话', 15],
    ['儿童', 16], ['财经', 17], ['广播', 18], ['诗歌', 19], ['文学', 20],
    ['粤语', 21], ['经典', 22], ['相声小品', 23], ['百家讲坛', 24]
];

function clean(s) {
    return (s || '').replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#39;/g, "'").trim();
}

async function getHtml(url) {
    try {
        let res = await req(url, { headers: { 'User-Agent': UA } });
        return res ? res.content || '' : '';
    } catch (e) {
        return '';
    }
}

// 书籍卡片解析（首页热门/分类页通用）
function parseBooks(html) {
    let list = [];
    let re = /<li class="col-[126][^"]*">[\s\S]*?<a href="(\/mp3\/(\d+)\.html)" class="img-80[^"]*">[\s\S]*?<img src="([^"]+)" alt="([^"]*)"[\s\S]*?<a href="\/mp3\/\d+\.html" class="f-bold">([^<]+)<\/a>/g;
    let m;
    while ((m = re.exec(html)) !== null) {
        list.push({
            vod_id: m[2],
            vod_name: clean(m[5]),
            vod_pic: (m[3].indexOf('http') === 0 ? m[3] : host + m[3]),
            vod_remarks: '听书吧'
        });
    }
    return list;
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
 * 首页推荐（收听热门）
 */
async function homeVod() {
    let html = await getHtml(host + '/');
    let videos = parseBooks(html);
    return JSON.stringify({ list: videos });
}

/**
 * 分类列表
 */
async function category(tid, pg, filter, extend) {
    pg = pg || 1;
    let url = host + '/books/' + tid + '.html';
    if (pg > 1) url = host + '/books/' + tid + '-' + pg + '.html';
    let html = await getHtml(url);
    let videos = parseBooks(html);
    return JSON.stringify({ page: pg, pagecount: pg + 1, list: videos });
}

/**
 * 详情页
 */
async function detail(id) {
    let html = await getHtml(host + '/mp3/' + id + '.html');
    let vod = { vod_id: id, vod_name: '', vod_pic: '', vod_content: '', vod_actor: '', vod_director: '', vod_remarks: '', vod_play_url: '', vod_play_from: '' };
    // 书名
    let m = html.match(/<h1[^>]*class="style-title[^"]*"[^>]*>([^<]+)<\/h1>/);
    if (!m) m = html.match(/<h1[^>]*>([^<]{2,40})<\/h1>/);
    if (m) vod.vod_name = clean(m[1]);
    // 封面：详情页首图
    m = html.match(/<div class="img-100[^"]*">[\s\S]*?<img src="([^"]+)"[^>]*>/);
    if (!m) m = html.match(/<img src="(\/uploads\/[^"]+)" alt="[^"]*"[^>]*>/);
    if (m) vod.vod_pic = (m[1].indexOf('http') === 0 ? m[1] : host + m[1]);
    // 简介
    m = html.match(/内容介绍：([^<]{10,})</);
    if (m) vod.vod_content = clean(m[1]);
    // 作者
    m = html.match(/作者：<a[^>]*>([^<]+)<\/a>/);
    if (m) vod.vod_director = clean(m[1]);
    // 播音
    m = html.match(/播音：<a[^>]*>([^<]+)<\/a>/);
    if (m) vod.vod_actor = clean(m[1]);
    // 章节：<li id="NN"><a title="001 标题" href="/play/{id}-0-{集}.html">
    let eps = [];
    let re = /<li id="\d+"><a[^>]*title="([^"]*)"[^>]*href="\/play\/\d+-0-(\d+)\.html"/g;
    while ((m = re.exec(html)) !== null) {
        let title = clean(m[1]);
        let num = m[2];
        let name = title.replace(/^\d+\s*/, '');
        eps.push({ name: name, url: host + '/play/' + id + '-0-' + num + '.html' });
    }
    // 兜底：任意 <a title href="/play/...">
    if (eps.length === 0) {
        let re2 = /<a[^>]*title="([^"]*)"[^>]*href="\/play\/\d+-0-(\d+)\.html"[^>]*>/g;
        while ((m = re2.exec(html)) !== null) {
            let name2 = clean(m[1]).replace(/^\d+\s*/, '');
            eps.push({ name: name2, url: host + '/play/' + id + '-0-' + m[2] + '.html' });
        }
    }
    // 拼接 vod_play_url：名称$$$地址
    let names = [], urls = [];
    eps.forEach(function (e) { names.push(e.name); urls.push(e.url); });
    vod.vod_play_url = names.join('$$$') + '$$$' + urls.join('$$$');
    vod.vod_play_from = '听书吧';
    return JSON.stringify({ list: [vod] });
}

/**
 * 搜索（站内搜索有验证码，无法自动通过）
 */
async function search(wd, quick) {
    return JSON.stringify({ list: [] });
}

/**
 * 播放解析
 */
async function play(flag, id, flags) {
    // id 形如 https://www.ting8.cc/play/20950-0-0.html
    let html = await getHtml(id);
    let m = html.match(/var now="([^"]+)"/);
    let src = m ? m[1] : '';
    if (!src) {
        let m2 = html.match(/https?:\/\/[^"'\s<>]+?\.m4a[^"'\s<>]*/);
        if (m2) src = m2[0];
    }
    return JSON.stringify({ parse: 0, url: src, header: 'User-Agent=' + UA });
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
