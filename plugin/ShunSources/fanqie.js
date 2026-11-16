// ---------- 番茄听书：fq.neeao.dpdns.org 公开聚合接口（JSON 直出、免签名、免登录） ----------
// 站点是「番茄小说」的第三方接口服务，听书频道给的是真人演播音频直链（fqnovelvod.com）。
//
// 用到的接口（全部实测 2026-11-16）：
//   /api/search?key=&tab_type=2&offset=&search_id=&passback=&next_offset=   搜索（听书 tab_type=2，每页 10 本）
//   /api/discover/style?tab=听书&source_type=0                              分类导航（返回带 url 的按钮 + 无 url 的分组标题）
//   /api/discover?tab=听书&type=&gender=&genre_type=1&page=1                分类列表（100 本）
//   /api/detail?book_id=                                                    书名/作者/主播/封面/简介/状态
//   /api/book?book_id=                                                      卷 + 章节（item_id，一次给全）
//   /api/content?item_id=&book_id=&tab=听书                                 音频直链（漏了 tab 直接 400）
//
// 踩过的坑：
// FIX1 discover 不认 page / offset，翻页拿到的还是同一批 100 本 → 分类只做单页，nextUrl 一律 null，别让界面无限下拉。
// FIX2 搜索翻页必须把上一页的 search_id 和 offset 带回去；只改 offset 会被当成新搜索，第 2 页又回到第 1 页的内容。
// FIX3 /api/content 少 tab=听书 直接 400；返回的 content_type 不是 audio 时说明这本书只有文字版。
// FIX4 作者的字段里混着「（主播：XXX）」，要拆成 author + artist，不然书架上一堆书作者都带主播名。
// FIX5 封面是 fqnovelpic 带签名的地址，& 不要转义；个别书只有 audio_thumb_uri，要按顺序兜底。
(function () {
  var SITE = 'https://fq.neeao.dpdns.org';
  var UA = 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36';
  var TAB = '听书';
  var PAGE_SIZE = 10;               // 搜索接口每页固定 10 条
  var searchState = {};             // 关键词 -> { id, offset }：搜索翻页要串联 search_id

  function val(o, k) { var x = o === null || o === undefined ? '' : o[k]; return x === null || x === undefined ? '' : x; }
  function arr(o, k) { var x = o === null || o === undefined ? null : o[k]; return Object.prototype.toString.call(x) === '[object Array]' ? x : []; }
  function http(u) {
    u = String(u || '').trim();
    if (u.indexOf('//') === 0) u = 'https:' + u;
    return /^https?:\/\//i.test(u) ? u : '';
  }
  function trim(v) { return String(v === null || v === undefined ? '' : v).replace(/^\s+|\s+$/g, ''); }

  // 所有请求都带上站点 Referer 和手机 UA：这个接口服务对裸请求偶尔返回 403
  // 另外它和七猫一样偶发 TLS 断连，一次失败就重试一次，别让源直接报错
  function api(host, path) {
    var url = path.indexOf('http') === 0 ? path : SITE + path;
    var options = { desktop: false, headers: { 'User-Agent': UA, 'Referer': SITE + '/' } };
    var last = null;
    for (var i = 0; i < 2; i++) {
      try { return host.getJson(url, options); }
      catch (e) {
        if (e && e.cancelled) throw e;   // 用户主动取消，不要再试
        last = e;
        try { host.sleep(150); } catch (e2) { /* 旧版宿主没有 sleep，忽略 */ }
      }
    }
    throw last || new Error('番茄接口连不上，请稍后重试');
  }

  // 「当时明月犹在（主播：索尔配音）」→ 作者 + 主播
  function artistOf(author) { var m = /（主播[:：]\s*([^）]*)）/.exec(String(author || '')); return m ? trim(m[1]) : ''; }
  function authorOf(author) { return trim(String(author || '').replace(/（主播[:：][^）]*）/g, '')); }

  // 搜索和分类两套接口的字段名不一样（name/cover/intro 与 book_name/thumb_url/abstract），这里统一
  function toBook(o) {
    var id = String(val(o, 'book_id'));
    var status = trim(val(o, 'status'));
    var sub = trim(val(o, 'sub_info'));
    var score = trim(val(o, 'score'));
    var bits = [status, sub ? sub : (score ? '评分 ' + score : '')];
    return {
      bookUrl: 'fq:' + id,
      title: trim(val(o, 'name') || val(o, 'book_name')),
      author: authorOf(val(o, 'author')),
      artist: artistOf(val(o, 'author')) || trim(val(o, 'source')),
      coverUrl: http(val(o, 'cover') || val(o, 'thumb_url') || val(o, 'audio_thumb_uri')),
      intro: trim(val(o, 'intro') || val(o, 'abstract')),
      status: bits.filter(function (s) { return s; }).join(' · ')
    };
  }

  // 分组标题里常带装饰符号（「°・*.☆ 小说 ☆.*・°」），只留中文和字母数字
  function cleanTitle(t) {
    t = trim(t).replace(/[^\u4e00-\u9fa5A-Za-z0-9]/g, '');
    return t || '分类';
  }

  registerSource({
    id: '5a1c8e73b9d24f60a0117c3e9d5b2f84',
    name: '番茄听书',
    url: SITE + '/search',
    group: '听书',
    description: '推荐指数:4星 ⭐⭐⭐⭐\n番茄小说的听书频道，真人演播音频直链（fqnovelvod），免登录。\n只有文字版的书点开会提示没有音频；分类固定 100 本不翻页，找书建议直接用搜索。',
    multipleEpisodePages: false,

    search: function (keywords, page) {
      var host = this.host, p = Number(page) || 1;
      var offset = (p - 1) * PAGE_SIZE;
      var state = searchState[keywords];
      // FIX2：第 2 页起必须回传上一页的 search_id，否则服务端会把这次当新搜索
      if (p <= 1 || !state) state = { id: '', offset: 0 };
      var data = api(host, '/api/search?key=' + encodeURIComponent(keywords) +
        '&tab_type=2&offset=' + offset +
        '&search_id=' + encodeURIComponent(state.id) +
        '&passback=' + offset + '&next_offset=' + (offset + PAGE_SIZE)).data || {};
      var books = arr(data, 'list').map(toBook).filter(function (b) { return b.bookUrl !== 'fq:'; });
      var next = Number(val(data, 'next_offset'));
      searchState[keywords] = { id: String(val(data, 'search_id')), offset: next > offset ? next : offset + books.length };
      var more = data.has_more === true && books.length > 0;
      return { books: books, totalPage: more ? p + 1 : p };
    },

    categoryMenus: function () {
      var styles = arr(api(this.host, '/api/discover/style?tab=' + encodeURIComponent(TAB) + '&source_type=0'), 'data');
      var all = { title: '全部', tabs: [{ title: '全部听书', url: 'fq-cat:/api/discover?tab=' + encodeURIComponent(TAB) + '&type=899&gender=2&genre_type=1&page=1' }] };
      if (!styles.length) return [all];
      var groups = [], cur = null;
      styles.forEach(function (s) {
        var url = trim(val(s, 'url'));
        // 没有 url 的是分组标题（小说 / 男频 / 女频）
        if (url === '') {
          var title = cleanTitle(val(s, 'title'));
          if (val(s, 'title') === '') { cur = null; return; }
          cur = { title: title, tabs: [] };
          groups.push(cur);
          return;
        }
        if (!cur) { cur = { title: '分类', tabs: [] }; groups.push(cur); }
        cur.tabs.push({ title: trim(val(s, 'title')) || '未命名', url: 'fq-cat:' + url.replace('{{page}}', '1') });
      });
      var out = groups.filter(function (g) { return g.tabs.length > 0; });
      return out.length ? out : [all];
    },

    categoryPage: function (url) {
      var path = String(url || '').replace(/^fq-cat:/, '');
      if (path.charAt(0) !== '/') path = '/' + path;
      var data = api(this.host, path).data || {};
      var books = arr(data, 'books').map(toBook).filter(function (b) { return b.bookUrl !== 'fq:'; });
      // FIX1：服务端不认翻页参数，永远这一页；直接告诉宿主没有下一页
      return { books: books, currentPage: 1, totalPage: 1, nextUrl: null };
    },

    bookDetail: function (url, loadEpisodes) {
      var host = this.host, id = String(url || '').replace(/^fq:/, '');
      if (!/^\d+$/.test(id)) throw new Error('书籍地址无效，请重新搜索');
      var d = api(host, '/api/detail?book_id=' + encodeURIComponent(id)).data || {};
      var result = toBook(d);
      result.bookUrl = 'fq:' + id;
      result.title = trim(val(d, 'name')) || result.title;
      result.artist = result.artist || trim(val(d, 'source'));
      result.coverUrl = result.coverUrl || http(val(d, 'cover'));
      var bits = [trim(val(d, 'status')), trim(val(d, 'sub_info'))];
      result.status = bits.filter(function (s) { return s; }).join(' · ');
      result.episodes = [];
      if (!loadEpisodes) return result;

      // 目录一次给全（卷 → 章），不用翻页
      var book = api(host, '/api/book?book_id=' + encodeURIComponent(id)).data || {};
      var seen = {};
      arr(book, 'volumes').forEach(function (v) {
        arr(v, 'chapters').forEach(function (c) {
          var itemId = String(val(c, 'item_id'));
          if (!/^\d+$/.test(itemId) || seen[itemId]) return;
          seen[itemId] = true;
          result.episodes.push({
            title: trim(val(c, 'title')) || ('第 ' + (result.episodes.length + 1) + ' 集'),
            url: 'fq-e:' + itemId + ':' + id,
            isFree: c.is_free !== false
          });
        });
      });
      if (!result.episodes.length) throw new Error('这本书没有音频章节（可能只有文字版）');
      return result;
    },

    // 章节地址里只放稳定 ID，播放时才去换真实音频；直链带时效，缓存下来很快就失效
    audio: function (url) {
      var s = String(url || '');
      if (/^https?:\/\//i.test(s)) return s;
      var m = /^fq-e:(\d+):(\d+)$/.exec(s);
      if (!m) throw new Error('章节地址无效，请刷新目录');
      var d = api(this.host, '/api/content?item_id=' + m[1] + '&book_id=' + m[2] + '&tab=' + encodeURIComponent(TAB)).data || {};
      var audio = http(val(d, 'content'));
      var type = trim(val(d, 'content_type'));
      if (!audio) throw new Error('没有取到音频地址，可能这本书没有真人演播');
      if (type !== '' && type !== 'audio') throw new Error('这一章返回的是文字内容，不是音频');
      // FIX6 这里千万不能带 Referer：音频在 fqnovelvod.com 的 CDN 上，它的防盗链规则是
      // 「带 Referer 就 403 deny by referer access rule」，而裸请求/只带 UA 是 206 正常。
      // 之前一律回 {url, headers:{UA, Referer}} 导致播放器拿到 403，表现就是“点了没声音”。
      return { url: audio, headers: { 'User-Agent': UA } };
    },

    coverHeaders: function (url) {
      return String(url || '').indexOf('fqnovelpic.com') >= 0 ? { 'Referer': SITE + '/' } : null;
    }
  });
})();
