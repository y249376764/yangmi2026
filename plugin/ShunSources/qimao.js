// ---------- 七猫听书：qm.neeao.dpdns.org 公开聚合接口（JSON 直出、免签到、免登录） ----------
// 七猫的听书里既有真人演播，也有官方 AI 多音色（同一章不同 voice 是不同 mp3），
// 章节音频是 cdn-audio.qimao.com 的带 expire 签名直链，所以只能播放前现取。
//
// 用到的接口（全部实测 2026-11-16）：
//   /api/audio/home                                              首页 6 个板块
//   /api/audio/categories                                        分类（2 组：热门 6 个 / 全部 20 个）
//   /api/audio/category-list?categoryId=&categoryType=2&page=     分类列表（每页 10 本，带 totalPages）
//   /api/audio/rank?rankType=rec_list|hot|new|over&categoryType=2 榜单（固定 30 本，不认 page）
//   /api/audio/search?keyword=&page=                             搜索（每页 10 本）
//   /api/audio/info?id=                                          详情（mode/aiVoices/realVoices/chapters 全量）
//   /api/audio/chapter?id=&cid=&voice=                           章节音频（voice 只对 mode=ai 的书生效）
//
// 踩过的坑：
// FIX1 这个域名偶发 SSL 断连（手机上表现为「网络错误」），所以每个请求重试一次再放弃，短 sleep 一下更稳。
// FIX2 榜单接口不认 page：翻到第 2 页还是同一批 30 本 → 榜单只做单页，nextUrl 返回 null。
// FIX3 搜索接口的 total 字段不可信（翻到第 11 页照样有数据），按「本页满 10 条就还有下一页」判断。
// FIX4 cid 是字符串（如 8554509），别转数字；章节直链带 expire，必须播放时现取，不能存进章节列表。
// FIX5 真人书（mode=real）传 voice 无效，会照样返回真人音频 → 不传 voice，用原站默认。
// FIX6 详情接口没有 status 字段，完结信息在列表的 kind 里（「杀伐果断・完结」），只在有的时候展示。
(function () {
  var SITE = 'https://qm.neeao.dpdns.org';
  var UA = 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36';
  var PAGE_SIZE = 10;            // 搜索 / 分类每页 10 本
  var RANKS = [                  // 首页那一排榜单
    ['rec_list', '🔥 推荐'],
    ['hot', '📈 热门'],
    ['new', '🆕 新书'],
    ['over', '✅ 完结']
  ];
  // AI 音色 ID 是跨书稳定的（多字符对话 10 / 明朗青年 8 / 武侠男声 4 / 古风御姐 6 / 相声阿龙 5 / 温柔淑女 7 / 儒雅青叔 9）
  // 但每本书只开一部分，所以设置里选的名字要拿这本书记录的音色列表校验
  var VOICES = [
    ['多角色对话', '10'], ['明朗青年', '8'], ['武侠男声', '4'],
    ['古风御姐', '6'], ['相声阿龙', '5'], ['温柔淑女', '7'], ['儒雅青叔', '9']
  ];
  var metaCache = {};            // 书 id -> { mode, defaultVoice, voices[] }，避免每次播放都请求详情

  function val(o, k) { var x = o === null || o === undefined ? '' : o[k]; return x === null || x === undefined ? '' : x; }
  function arr(o, k) { var x = o === null || o === undefined ? null : o[k]; return Object.prototype.toString.call(x) === '[object Array]' ? x : []; }
  function http(u) {
    u = String(u || '').trim();
    if (u.indexOf('//') === 0) u = 'https:' + u;
    return /^https?:\/\//i.test(u) ? u : '';
  }
  function trim(v) { return String(v === null || v === undefined ? '' : v).replace(/^\s+|\s+$/g, ''); }

  // FIX1：偶发 SSL 断连，重试一次
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
    throw last || new Error('七猫接口连不上，请稍后重试');
  }

  function toBook(o) {
    var id = String(val(o, 'id'));
    var kind = trim(val(o, 'kind'));
    var author = trim(val(o, 'author'));
    return {
      bookUrl: 'qm:' + id,
      title: trim(val(o, 'title')),
      author: author,
      artist: '',
      coverUrl: http(val(o, 'cover')),
      intro: trim(val(o, 'intro')),
      status: kind     // FIX6：kind 里是「杀伐果断・武侠・218.6万累计热度」这类标签
    };
  }

  registerSource({
    id: 'c4f0b7a2e61d4f938d2a5c0e7b1f3d96',
    name: '七猫听书',
    url: SITE + '/',
    group: '听书',
    description: '推荐指数:5星 ⭐⭐⭐⭐⭐\n七猫听书全量：真人演播 + 官方 AI 多音色（同一章不同音色是不同 mp3）。\n榜单固定 30 本不翻页，分类和搜索正常翻页；AI 音色可在插件设置里选，真人书不支持切音色。',
    multipleEpisodePages: false,
    config: [{
      type: 'select',
      key: 'voice',
      label: 'AI 音色（只对 AI 朗读的书生效）',
      default: '原站默认',
      options: ['原站默认'].concat(VOICES.map(function (v) { return v[0]; }))
    }],

    search: function (keywords, page) {
      var p = Number(page) || 1;
      var data = api(this.host, '/api/audio/search?keyword=' + encodeURIComponent(keywords) + '&page=' + p).data || {};
      var books = arr(data, 'items').map(toBook).filter(function (b) { return b.bookUrl !== 'qm:'; });
      // FIX3：total 不可信，本页满了就认为还有下一页；再给个 20 页上限，免得列表一直滚不到头
      var more = books.length >= PAGE_SIZE && p < 20;
      return { books: books, totalPage: more ? p + 1 : p };
    },

    categoryMenus: function () {
      var menus = [{
        title: '榜单',
        tabs: [{ title: '🏠 首页推荐', url: 'qm-home' }].concat(RANKS.map(function (r) {
          return { title: r[1], url: 'qm-rank:' + r[0] };
        }))
      }];
      var groups = arr(api(this.host, '/api/audio/categories').data, 'groups');
      groups.forEach(function (g) {
        var tabs = arr(g, 'list').map(function (c) {
          return { title: trim(val(c, 'name')), url: 'qm-cat:' + val(c, 'id') + ':' + (val(c, 'type') || '2') + ':1' };
        }).filter(function (t) { return t.title !== ''; });
        if (tabs.length) menus.push({ title: trim(val(g, 'title')) || '分类', tabs: tabs });
      });
      return menus;
    },

    categoryPage: function (url) {
      var host = this.host, s = String(url || '');
      var books = [], seen = {};

      if (s === 'qm-home') {
        // 首页 6 个板块拍平成一页，重复的书只留第一次
        arr(api(host, '/api/audio/home').data, 'sections').forEach(function (sec) {
          arr(sec, 'items').forEach(function (o) {
            var b = toBook(o);
            if (b.bookUrl === 'qm:' || seen[b.bookUrl]) return;
            seen[b.bookUrl] = true;
            books.push(b);
          });
        });
        return { books: books, currentPage: 1, totalPage: 1, nextUrl: null };
      }

      if (s.indexOf('qm-rank:') === 0) {
        // FIX2：榜单不认 page，只有 30 本
        var key = s.replace('qm-rank:', '');
        var rank = api(host, '/api/audio/rank?rankType=' + encodeURIComponent(key) + '&categoryType=2&page=1').data || {};
        return { books: arr(rank, 'items').map(toBook), currentPage: 1, totalPage: 1, nextUrl: null };
      }

      var m = /^qm-cat:(\d+):(\d+):?(\d*)$/.exec(s);
      if (!m) return { books: [], currentPage: 1, totalPage: 1 };
      var page = Number(m[3] || 1) || 1;
      var data = api(host, '/api/audio/category-list?categoryId=' + m[1] + '&categoryType=' + m[2] + '&page=' + page).data || {};
      books = arr(data, 'items').map(toBook).filter(function (b) { return b.bookUrl !== 'qm:'; });
      var totalPage = Number(val(data, 'totalPages')) || page;
      return {
        books: books, currentPage: page, totalPage: Math.max(totalPage, page),
        nextUrl: page < totalPage ? 'qm-cat:' + m[1] + ':' + m[2] + ':' + (page + 1) : null
      };
    },

    bookDetail: function (url, loadEpisodes) {
      var host = this.host, id = String(url || '').replace(/^qm:/, '');
      if (!/^\d+$/.test(id)) throw new Error('专辑地址无效，请重新搜索');
      var d = api(host, '/api/audio/info?id=' + encodeURIComponent(id)).data || {};
      var result = toBook(d);
      result.bookUrl = 'qm:' + id;
      result.title = trim(val(d, 'title')) || result.title;
      result.coverUrl = result.coverUrl || http(val(d, 'cover'));
      result.intro = trim(val(d, 'intro')) || result.intro;
      result.author = result.author || trim(val(d, 'author'));

      var chapters = arr(d, 'chapters');
      var realVoices = arr(d, 'realVoices');
      var aiVoices = arr(d, 'aiVoices');
      var mode = trim(val(d, 'mode')) || 'real';
      // 真人演播的名字就在 realVoices[0].name，可能是「延丞,水夙,兰梦梦」这种多人
      result.artist = trim(val(realVoices[0] || {}, 'name')).split(',').join('、');
      // AI 书没有播音员，就把可用音色摆出来，用户知道能切
      if (!result.artist && mode === 'ai' && aiVoices.length) {
        result.artist = 'AI 音色：' + aiVoices.slice(0, 3).map(function (v) { return trim(val(v, 'name')); }).join(' / ') +
          (aiVoices.length > 3 ? ' 等 ' + aiVoices.length + ' 种' : '');
      }
      var count = chapters.length || Number(val(d, 'episodes')) || 0;
      result.status = [
        count > 0 ? '共 ' + count + ' 集' : '',
        mode === 'ai' ? (aiVoices.length > 1 ? 'AI 多音色 · ' + aiVoices.length + ' 种' : 'AI 朗读') : '真人演播'
      ].filter(function (x) { return x; }).join(' · ');
      // 播放时要用这本书实际开了哪些音色，详情已经拿到了，先存着
      metaCache[id] = {
        mode: mode,
        defaultVoice: trim(val(d, 'defaultVoice')),
        voices: aiVoices.map(function (v) { return String(val(v, 'id')); }).filter(function (x) { return x !== ''; })
      };

      result.episodes = [];
      if (!loadEpisodes) return result;
      var seen = {};
      chapters.forEach(function (c) {
        var cid = String(val(c, 'id'));
        if (!/^\d+$/.test(cid) || seen[cid]) return;
        seen[cid] = true;
        var title = trim(val(c, 'title')) || ('第 ' + (result.episodes.length + 1) + ' 集');
        var duration = trim(val(c, 'duration'));
        result.episodes.push({
          title: duration ? title + '（' + duration + '）' : title,
          url: 'qm:' + id + ':' + cid
        });
      });
      if (!result.episodes.length) throw new Error('这个专辑没有可播放的章节');
      return result;
    },

    // FIX4 / FIX5：cid 只当字符串用；播放时才换带签名的直链。
    // 音色：AI 书必须给一个它开了的 voice（不给会返回「该章节暂无可播放音频」），真人书传 voice 没用 → 一律先试原站默认
    audio: function (url) {
      var s = String(url || '');
      if (/^https?:\/\//i.test(s)) return s;
      var m = /^qm:(\d+):(\d+)$/.exec(s);
      if (!m) throw new Error('章节地址无效，请刷新目录');
      var host = this.host, bookId = m[1], cid = m[2];
      var info = metaCache[bookId];
      var tries = [], pref = '', i;
      try { pref = trim(String(host.getPref('voice', '原站默认') || '')); } catch (e) { pref = ''; }
      for (i = 0; i < VOICES.length; i++) if (VOICES[i][0] === pref) pref = VOICES[i][1];
      if (info) {
        if (pref && info.voices.indexOf(pref) >= 0) tries.push(pref);
        if (info.mode === 'ai') {
          if (info.defaultVoice) tries.push(info.defaultVoice);
          info.voices.forEach(function (v) { tries.push(v); });
        } else {
          tries.push('');     // 真人书：不带 voice 才是原样
          info.voices.forEach(function (v) { tries.push(v); });
        }
      } else {
        // 没经过详情页（比如从搜索直接播）：按「设置 → 默认 → 常见音色」试
        if (pref) tries.push(pref);
        tries.push('');
        VOICES.forEach(function (v) { tries.push(v[1]); });
      }
      var seen = {}, reason = '';
      for (i = 0; i < tries.length && i < 5; i++) {
        var voice = tries[i];
        if (seen['v' + voice]) continue;
        seen['v' + voice] = true;
        var d = api(host, '/api/audio/chapter?id=' + bookId + '&cid=' + cid + '&voice=' + voice).data || {};
        var audio = http(val(d, 'url'));
        if (audio) return { url: audio, headers: { 'User-Agent': UA } };
        reason = trim(val(d, 'reason')) || reason;
      }
      throw new Error(reason || '七猫没有给出播放地址');
    },

    coverHeaders: function (url) {
      return String(url || '').indexOf('wtzw.com') >= 0 ? { 'Referer': SITE + '/' } : null;
    }
  });
})();
