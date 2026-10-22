/**
 * @name 小听聚合 · 四平台多线路 v1
 * @description QQ/网易/酷狗/酷我 四平台，雾隐青山主源 + 小听兜底，无损优先
 * @version 1.0.0
 * @author 星火
 * @homepage https://navpage-2026.surge.sh/
 */

const { EVENT_NAMES, request, on, send } = globalThis.lx

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
const CY_KEY = '1ffdf5733f5d538760e63d7e46ba17438d9f7b9dfc18c51be1109386fd74c3a1'

const httpGet = (url, options = {}) => new Promise((resolve, reject) => {
  request(url, { method: 'get', timeout: 15000, ...options }, (err, resp) => {
    if (err) return reject(new Error(err.message || '网络错误'))
    if (!resp || resp.statusCode >= 400) return reject(new Error('HTTP ' + (resp && resp.statusCode)))
    resolve(resp)
  })
})

const httpPost = (url, body, options = {}) => new Promise((resolve, reject) => {
  const payload = typeof body === 'string' ? body : JSON.stringify(body)
  request(url, { method: 'post', timeout: 15000, body: payload, ...options }, (err, resp) => {
    if (err) return reject(new Error(err.message || '网络错误'))
    if (!resp || resp.statusCode >= 400) return reject(new Error('HTTP ' + (resp && resp.statusCode)))
    resolve(resp)
  })
})

const grab = (obj, paths) => {
  for (let i = 0; i < paths.length; i++) {
    let val = obj
    const path = paths[i]
    for (let j = 0; j < path.length; j++) {
      if (val == null) { val = undefined; break }
      val = val[path[j]]
    }
    if (val != null && val !== '') return val
  }
  return ''
}

const jsonOf = (resp) => {
  let v = resp && resp.body
  for (let i = 0; i < 3; i++) {
    if (v && typeof v === 'object') return v
    if (typeof v !== 'string') break
    const s = v.trim()
    if (!s) return {}
    try { v = JSON.parse(s) } catch (e) { return {} }
  }
  return (v && typeof v === 'object') ? v : {}
}

const isClipUrl = (u) => {
  if (!u || typeof u !== 'string') return true
  if (/\/resource\/n[12]\//i.test(u)) return true
  if (/\/(nf|cn)\/resource\//i.test(u)) return true
  if (/\/RS0?\d/i.test(u)) return true
  if (/[?&](try|preview|short)=/i.test(u)) return true
  if (/\/(try|preview|short)\//i.test(u)) return true
  return false
}

const firstStr = function () {
  for (let i = 0; i < arguments.length; i++) {
    const v = arguments[i]
    if (v != null && String(v) !== '') return String(v)
  }
  return ''
}

const pickId = (source, mi) => {
  if (!mi) return ''
  const common = firstStr(mi.songmid, mi.mid, mi.songId, mi.songid, mi.id)
  if (source === 'kg') return firstStr(mi.hash, mi.Hash, common)
  if (source === 'kw') return firstStr(mi.rid, mi.musicrid, common)
  return common
}

const nameOf = (mi) => {
  if (!mi) return ''
  const n = firstStr(mi.name, mi.title, mi.SongName)
  const s = mi.singer || mi.artists || mi.SingerName
  let singer = ''
  if (Array.isArray(s)) {
    singer = s.map(function (a) { return (a && a.name) || '' }).filter(Boolean).join(' ')
  } else {
    singer = String(s || '')
  }
  return (String(n || '') + ' ' + singer).trim()
}

const norm = (s) => String(s || '').toLowerCase().replace(/[\s\-_()（）\[\]【】·、,，.。!！?？'"“”‘’]/g, '')

const nameHit = (want, got) => {
  const a = norm(want)
  const b = norm(got)
  if (!a || !b) return false
  return b.indexOf(a) >= 0 || a.indexOf(b) >= 0
}

const BADVER = /(dj|ktv|伴奏|伴唱|纯音乐|remix|翻唱|cover|铃声|片段|试听|live|演唱会|现场|女声|男声|童声|钢琴|吉他|口琴|8d|3d|环绕|抖音|快手|慢摇|广场舞|串烧|混音|改编|清唱|和声)/i

const isBadVer = (name) => BADVER.test(String(name || ''))

const AUDIO_EXT = /\.(flac|mp3|m4a|aac|ogg|wav|ape)(\?|$)/i
const AUDIO_HOST = /(qqmusic\.qq\.com|music\.126\.net|kuwo\.cn|kugou\.com|bdycdn\.cn|migu\.cn)/i

const verify = async (url) => {
  if (!url || !/^https?:\/\//i.test(url)) return false
  const sure = AUDIO_EXT.test(url) || AUDIO_HOST.test(url)
  try {
    const resp = await httpGet(url, { headers: { 'User-Agent': UA, Range: 'bytes=0-255' } })
    const h = resp.headers || {}
    const ct = String(h['content-type'] || h['Content-Type'] || '').toLowerCase()
    if (/audio|flac|mpeg|mp3|m4a|ogg/.test(ct)) return true
    if (/text\/html|application\/json/.test(ct)) return false
    const b = String(resp.body || '')
    if (b.indexOf('<html') >= 0 || b.indexOf('<!DOCTYPE') >= 0 || b.indexOf('302 Found') >= 0) return false
    return b.length > 400 || sure
  } catch (e) { return sure }
}

const LEVELS = {
  '128k': ['standard'],
  '320k': ['exhigh', 'standard'],
  'flac': ['lossless', 'exhigh', 'standard'],
  'flac24bit': ['hires', 'lossless', 'exhigh', 'standard']
}

const htResolve = async (source, rid, level) => {
  const resp = await httpPost('https://musicserver.haitangw.cc/v1/music/resolve-url',
    JSON.stringify({ source, rid: String(rid), level: level || 'standard' }),
    { headers: { 'Content-Type': 'application/json; charset=utf-8', 'User-Agent': 'okhttp/5.0.0-alpha.14' } })
  const d = jsonOf(resp)
  const u = grab(d, [['data', 'url']])
  if (u && /^https?:/.test(u) && !isClipUrl(u)) return u
  throw new Error('雾隐青山无链接')
}

const xtResolve = async (keyword, quality) => {
  if (!keyword) throw new Error('无歌名')
  const brs = quality === '128k' ? [0, 1] : [1, 0]
  for (let i = 0; i < brs.length; i++) {
    try {
      const resp = await httpGet('https://oiapi.net/API/Kuwo/?n=1&br=' + brs[i] + '&msg=' + encodeURIComponent(keyword),
        { headers: { 'User-Agent': UA } })
      const d = jsonOf(resp)
      const u = grab(d, [['data', 'url']])
      if (!u || !/^https?:/.test(u) || isClipUrl(u)) continue
      const got = String(grab(d, [['data', 'song']]) || '')
      if (got && !nameHit(keyword, got)) continue
      return u
    } catch (e) { /* 换下一档 */ }
  }
  throw new Error('小听无链接')
}

const wrap = (source, mi) => {
  const id = pickId(source, mi)
  const name = firstStr(mi && mi.name, mi && mi.title, mi && mi.SongName)
  const s = (mi && (mi.singer || mi.artists || mi.SingerName)) || ''
  let singer = ''
  if (Array.isArray(s)) {
    singer = s.map(function (a) { return (a && a.name) || '' }).filter(Boolean).join(' / ')
  } else {
    singer = String(s || '')
  }
  const album = (mi && mi.album && mi.album.name) || (mi && mi.AlbumName) || ''
  const pic = (mi && mi.album && mi.album.picUrl) || (mi && mi.Image) || ''
  return {
    name: String(name),
    singer: String(singer),
    source: source,
    songmid: String(id),
    id: String(id),
    hash: source === 'kg' ? String(id) : '',
    rid: source === 'kw' ? String(id) : '',
    albumName: String(album),
    img: String(pic),
    interval: '00:00'
  }
}

const txSearch = async (keyword, page, limit) => {
  const body = {
    comm: { ct: 19, cv: 1845 },
    req_1: {
      method: 'DoSearchForQQMusicDesktop',
      module: 'music.search.SearchCgiService',
      param: { num_per_page: limit, page_num: page, query: keyword, search_type: 0 }
    }
  }
  const resp = await httpPost('https://u.y.qq.com/cgi-bin/musicu.fcg', JSON.stringify(body),
    { headers: { 'Content-Type': 'application/json', 'User-Agent': UA, Referer: 'https://y.qq.com/' } })
  const d = jsonOf(resp)
  const L = ((((d.req_1 || {}).data || {}).body || {}).song || {}).list || []
  const out = []
  for (let i = 0; i < L.length; i++) out.push(wrap('tx', L[i]))
  return out
}

const wySearch = async (keyword, page, limit) => {
  const offset = (page - 1) * limit
  const resp = await httpGet('http://music.163.com/api/search/get/web?type=1&offset=' + offset +
    '&limit=' + limit + '&s=' + encodeURIComponent(keyword),
    { headers: { 'User-Agent': UA, Referer: 'http://music.163.com/' } })
  const d = jsonOf(resp)
  const L = ((d.result || {}).songs) || []
  const out = []
  for (let i = 0; i < L.length; i++) out.push(wrap('wy', L[i]))
  return out
}

const kgSearch = async (keyword, page, limit) => {
  const resp = await httpGet('https://cyapi.top/API/kugou.php?apikey=' + CY_KEY +
    '&type=json&msg=' + encodeURIComponent(keyword), { headers: { 'User-Agent': UA } })
  const d = jsonOf(resp)
  const L = d.list || []
  const all = []
  for (let i = 0; i < L.length; i++) all.push(wrap('kg', L[i]))
  return rankList(keyword, all).slice(0, limit)
}

const kwSearch = async (keyword, page, limit) => {
  const resp = await httpGet('https://search.kuwo.cn/r.s?all=' + encodeURIComponent(keyword) +
    '&ft=music&itemset=web_2013&client=kt&pn=0&rn=' + Math.max(limit * 4, 30) + '&rformat=json&encoding=utf8',
    { headers: { 'User-Agent': UA } })
  const body = String(resp.body || '')
  const blocks = body.split("},{'")
  const all = []
  for (let i = 0; i < blocks.length; i++) {
    const b = blocks[i]
    const nm = /'SONGNAME':'([^']+)'/.exec(b)
    const rid = /'MUSICRID':'MUSIC_(\d+)'/.exec(b)
    if (!nm || !rid) continue
    const ar = /'ARTIST':'([^']+)'/.exec(b)
    const al = /'ALBUM':'([^']+)'/.exec(b)
    all.push(wrap('kw', {
      name: nm[1].replace(/&nbsp;/g, ' '),
      singer: ar ? ar[1].replace(/&nbsp;/g, ' ') : '',
      AlbumName: al ? al[1].replace(/&nbsp;/g, ' ') : '',
      rid: rid[1]
    }))
  }
  return rankList(keyword, all).slice(0, limit)
}

const rankList = (keyword, list) => {
  const k = norm(keyword)
  const best = []
  const clean = []
  const rest = []
  for (let i = 0; i < list.length; i++) {
    const it = list[i]
    const nm = norm(it.name)
    if (isBadVer(it.name)) { rest.push(it); continue }
    if (nm === k) best.push(it)
    else if (nm.indexOf(k) >= 0 || k.indexOf(nm) >= 0) clean.push(it)
    else rest.push(it)
  }
  return best.concat(clean, rest)
}

const SEARCHERS = () => ({ wy: wySearch, tx: txSearch, kg: kgSearch, kw: kwSearch })

const lineSet = (source) => {
  return [
    async (ctx) => {
      const lvs = LEVELS[ctx.quality] || ['standard']
      for (let i = 0; i < lvs.length; i++) {
        try {
          const u = await htResolve(source, ctx.id, lvs[i])
          if (u) return u
        } catch (e) { /* 降下一档 */ }
      }
      throw new Error('雾隐青山按 ID 失败')
    },
    async (ctx) => {
      if (!ctx.keyword) throw new Error('无歌名')
      return await xtResolve(ctx.keyword, ctx.quality)
    },
    async (ctx) => {
      const other = source === 'tx' ? 'wy' : 'tx'
      const all = SEARCHERS()
      const searcher = all[other]
      if (!searcher || !ctx.keyword) throw new Error('无跨平台搜索')
      const list = await searcher(ctx.keyword, 1, 5)
      if (!list || !list.length) throw new Error('跨平台无结果')
      const n = Math.min(list.length, 3)
      for (let i = 0; i < n; i++) {
        try {
          const u = await htResolve(other, list[i].songmid, 'standard')
          if (u) return u
        } catch (e) { /* 换下一条 */ }
      }
      throw new Error('跨平台兜底失败')
    }
  ]
}

const LINES = { tx: lineSet('tx'), wy: lineSet('wy'), kg: lineSet('kg'), kw: lineSet('kw') }

const tryLines = async (lines, ctx) => {
  let lastErr = null
  for (let i = 0; i < lines.length; i++) {
    try {
      const url = await lines[i](ctx)
      if (!url || !/^https?:\/\//.test(url)) { lastErr = new Error('空链接'); continue }
      if (isClipUrl(url)) { lastErr = new Error('试听片段'); continue }
      if (await verify(url)) return url
      lastErr = new Error('地址不可用')
    } catch (err) { lastErr = err }
  }
  throw new Error(lastErr ? lastErr.message : '所有线路失败')
}

const SOURCES = {
  tx: { name: 'QQ音乐', type: 'music', actions: ['musicUrl'], qualitys: ['128k', '320k', 'flac', 'flac24bit'] },
  wy: { name: '网易云', type: 'music', actions: ['musicUrl'], qualitys: ['128k', '320k', 'flac', 'flac24bit'] },
  kg: { name: '酷狗音乐', type: 'music', actions: ['musicUrl'], qualitys: ['128k', '320k', 'flac', 'flac24bit'] },
  kw: { name: '酷我音乐', type: 'music', actions: ['musicUrl'], qualitys: ['128k', '320k', 'flac', 'flac24bit'] }
}

on(EVENT_NAMES.request, async ({ source, action, info }) => {
  if (action === 'musicSearch') {
    const { keyword, page = 1, limit = 20 } = info || {}
    const fn = SEARCHERS()[source]
    if (!fn) return Promise.reject(new Error('不支持的平台: ' + source))
    try {
      const list = await fn(String(keyword || ''), Number(page) || 1, Number(limit) || 20)
      return { list, allPage: 1, limit: Number(limit) || 20, total: list.length }
    } catch (e) {
      return Promise.reject(new Error('搜索失败: ' + (e.message || '')))
    }
  }
  if (action !== 'musicUrl') return Promise.reject(new Error('action not support'))
  const { musicInfo, type } = info || {}
  const id = pickId(source, musicInfo)
  const keyword = nameOf(musicInfo)
  const ctx = { id, quality: type, keyword, musicInfo }
  const lines = LINES[source]
  if (!lines) return Promise.reject(new Error('不支持的平台: ' + source))
  const url = await tryLines(lines, ctx)
  return Promise.resolve(url)
})

send(EVENT_NAMES.inited, {
  status: true,
  openDevTools: false,
  sources: SOURCES
})
