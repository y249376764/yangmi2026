/**
 * @name 小听合集 · 万象音源卷
 * @description 酷狗/网易/咪咕/B站/QQ 五平台，星海+咪咕官方+官方搜索多线路
 * @version 1.0.0
 * @author 星火
 * @homepage https://navpage-2026.surge.sh/
 */

const { EVENT_NAMES } = globalThis.lx

const HDR = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' }
const MUA = 'Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36'
const XH = 'https://yy.zddyr.top/lx/api/'
const MIGU_KEY = 'Jk8qzuePiJ1qE3mDYhLQ3T73DtDoAhLP'

const toBytes = (b) => {
  if (!b) return Buffer.alloc(0)
  if (Buffer.isBuffer(b)) return b
  if (b instanceof Uint8Array || Array.isArray(b)) return Buffer.from(b)
  if (typeof b === 'object' && b.type === 'Buffer' && Array.isArray(b.data)) return Buffer.from(b.data)
  const s = String(b)
  if (/[^\x00-\xff]/.test(s)) return Buffer.from(s, 'utf8')
  return Buffer.from(s, 'latin1')
}
const fixPy = (s) => {
  const t = String(s).trim()
  if (t.indexOf("'") < 0) return t
  let out = ''
  let inStr = false
  for (let i = 0; i < t.length; i++) {
    const c = t[i]
    if (inStr) {
      if (c === '\\' ) {
        const n = t[i + 1]
        if (n === "'") { out += "'"; i++; continue }
        if (n === '"') { out += '\\"'; i++; continue }
        out += c
        continue
      }
      if (c === "'") { out += '"'; inStr = false; continue }
      if (c === '"') { out += '\\"'; continue }
      out += c
    } else {
      if (c === "'") { out += '"'; inStr = true; continue }
      out += c
    }
  }
  return out
}

const jsonOf = (resp) => {
  const body = resp && resp.body
  if (!body) return {}
  if (typeof body === 'object' && !Buffer.isBuffer(body) && !(body instanceof Uint8Array) && !Array.isArray(body) && !(body.type === 'Buffer' && Array.isArray(body.data))) return body
  let txt
  if (typeof body === 'string') {
    txt = /[^\x00-\xff]/.test(body) ? body : toBytes(body).toString('utf8')
  } else {
    txt = toBytes(body).toString('utf8')
  }
  for (let i = 0; i < 3; i++) {
    const s = txt.trim()
    if (!s || s[0] === '<') return {}
    try {
      const v = JSON.parse(s)
      if (v && typeof v === 'object') return v
      txt = String(v)
    } catch (e) {
      try {
        const v2 = JSON.parse(fixPy(s))
        if (v2 && typeof v2 === 'object') return v2
      } catch (e2) {
        return {}
      }
      return {}
    }
  }
  return {}
}

const httpGet = (url, opts) => new Promise((resolve, reject) => {
  const o = Object.assign({ method: 'get', timeout: 15000 }, opts || {})
  o.headers = o.rawHeaders ? (o.headers || {}) : Object.assign({}, HDR, o.headers || {})
  delete o.rawHeaders
  globalThis.lx.request(url, o, (err, resp) => {
    if (err) return reject(err)
    const code = resp && resp.statusCode
    if (code && code >= 400) return reject(new Error('HTTP ' + code))
    resolve(resp)
  })
})

const httpPost = (url, body, opts) => new Promise((resolve, reject) => {
  const o = Object.assign({ method: 'post', body: typeof body === 'string' ? body : JSON.stringify(body), timeout: 15000 }, opts || {})
  o.headers = Object.assign({}, HDR, o.headers || {})
  globalThis.lx.request(url, o, (err, resp) => {
    if (err) return reject(err)
    const code = resp && resp.statusCode
    if (code && code >= 400) return reject(new Error('HTTP ' + code))
    resolve(resp)
  })
})

const norm = (s) => String(s || '').toLowerCase().replace(/[\s\-_()（）\[\]【】·、,，.。!！?？"'“”‘’]/g, '')
const BADVER = /(dj|ktv|伴奏|伴唱|纯音乐|remix|翻唱|cover|铃声|片段|试听|演唱会|现场|女声版|男声版|童声|钢琴版|吉他版|口琴|8d|3d|环绕|抖音|快手|慢摇|广场舞|串烧|混音|改编|清唱|和声|铃声)/i
const isBadVer = (n) => BADVER.test(String(n || ''))
const nameHit = (a, b) => {
  const x = norm(a), y = norm(b)
  if (!x || !y) return false
  return x === y || x.indexOf(y) >= 0 || y.indexOf(x) >= 0
}

const rankList = (keyword, list) => {
  const k = norm(keyword)
  const best = [], clean = [], rest = []
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

const mk = (source, id, name, singer, album, pic, extra) => {
  const it = { source, id: String(id), name: String(name || ''), singer: String(singer || ''), album: String(album || ''), pic: String(pic || '') }
  if (extra) Object.assign(it, extra)
  return it
}

const firstStr = function () {
  for (let i = 0; i < arguments.length; i++) {
    const v = arguments[i]
    if (v !== undefined && v !== null && String(v).trim() !== '') return String(v)
  }
  return ''
}

const kgSearch = async (kw, page, limit) => {
  const u = 'https://songsearch.kugou.com/song_search_v2?keyword=' + encodeURIComponent(kw) +
    '&page=' + page + '&pagesize=' + Math.max(limit * 4, 30) +
    '&userid=0&clientver=&platform=WebFilter&filter=2&iscorrection=1&privilege_filter=0&area_code=1'
  const d = jsonOf(await httpGet(u, { headers: { Referer: 'https://www.kugou.com/' } }))
  const L = ((d.data || {}).lists) || []
  const out = []
  for (let i = 0; i < L.length; i++) {
    const x = L[i]
    const hash = firstStr(x.SQFileHash, x.HQFileHash, x.FileHash)
    if (!hash) continue
    out.push(mk('kg', hash, x.SongName || '', x.SingerName || '', x.AlbumName || '', '', { kgHash: hash, kgAlbum: x.AlbumID }))
  }
  return rankList(kw, out).slice(0, limit)
}

const wySearch = async (kw, page, limit) => {
  const u = 'https://music.163.com/api/search/get/web?s=' + encodeURIComponent(kw) + '&type=1&limit=' + Math.max(limit * 3, 30) + '&offset=' + ((page - 1) * 30)
  const d = jsonOf(await httpGet(u, { headers: Object.assign({}, HDR, { Referer: 'https://music.163.com/' }) }))
  const L = ((d.result || {}).songs) || []
  const out = []
  for (let i = 0; i < L.length; i++) {
    const x = L[i]
    const ar = (x.artists || []).map(a => a.name).join('/')
    const al = x.album || {}
    out.push(mk('wy', x.id, x.name, ar, al.name || '', al.picUrl || '', { wyId: x.id }))
  }
  return rankList(kw, out).slice(0, limit)
}

const kwSearch = async (kw, page, limit) => {
  const u = 'https://search.kuwo.cn/r.s?all=' + encodeURIComponent(kw) +
    '&ft=music&itemset=web_2013&client=kt&pn=0&rn=' + Math.max(limit * 4, 30) + '&rformat=json&encoding=utf8'
  const d = jsonOf(await httpGet(u, { headers: Object.assign({}, HDR, { Referer: 'https://www.kuwo.cn/' }) }))
  const L = []
  const abs = d.abslist || d.data || []
  for (let i = 0; i < abs.length; i++) {
    const x = abs[i]
    const rid = String(x.MUSICRID || x.DC_TARGETID || x.rid || '').replace(/^MUSIC_/, '')
    if (!rid) continue
    L.push(mk('kw', rid, String(x.SONGNAME || x.name || '').replace(/&nbsp;/g, ' '), String(x.ARTIST || x.artist || '').replace(/&nbsp;/g, ' '), String(x.ALBUM || x.album || '').replace(/&nbsp;/g, ' '), '', { kwRid: rid }))
  }
  return rankList(kw, L).slice(0, limit)
}

const mgSearch = async (kw, page, limit) => {
  const u = 'https://c.musicapp.migu.cn/MIGUM2.0/v1.0/content/search_all.do?text=' + encodeURIComponent(kw) +
    '&pageNo=' + page + '&pageSize=' + Math.max(limit * 2, 20) + '&searchSwitch=' + encodeURIComponent('{"song":1}')
  const d = jsonOf(await httpGet(u, { headers: Object.assign({}, HDR, { Referer: 'https://m.music.migu.cn/' }) }))
  const L = (((d.songResultData || {}).result) || [])
  const out = []
  for (let i = 0; i < L.length; i++) {
    const x = L[i]
    const ar = (x.singerList || []).map(s => s.name).join('/')
    const cid = x.copyrightId
    if (!cid) continue
    out.push(mk('mg', cid, x.name || x.songName || '', ar, x.album || '', (x.imgItems || [{}])[0].img || '', { mgCid: cid }))
  }
  return rankList(kw, out).slice(0, limit)
}

const biliSearch = async (kw, page, limit) => {
  const u = 'https://api.bilibili.com/x/web-interface/search/type?search_type=video&keyword=' + encodeURIComponent(kw) + '&page=' + page
  const d = jsonOf(await httpGet(u, { rawHeaders: 1, headers: { 'User-Agent': 'Mozilla/5.0' } }))
  const L = ((d.data || {}).result) || []
  const out = []
  for (let i = 0; i < L.length; i++) {
    const x = L[i]
    if (!x.bvid) continue
    const title = String(x.title || '').replace(/<[^>]+>/g, '')
    out.push(mk('bili', x.bvid, title, x.author || '', '', firstStr(x.pic, '').replace(/^\/\//, 'https://'), { bvid: x.bvid }))
  }
  return rankList(kw, out).slice(0, Math.min(limit, 10))
}

const xhResolve = async (source, mid, quality) => {
  const u = XH + '?source=' + encodeURIComponent(source) + '&name=&songmid=' + encodeURIComponent(mid) + '&quality=' + encodeURIComponent(quality)
  const d = jsonOf(await httpGet(u))
  if (Number(d.code) !== 200) return ''
  const url = firstStr(d.url, (d.data || {}).url)
  if (!/^https?:\/\//i.test(url)) return ''
  return url
}


const xtResolve = async (it, q) => {
  const nm = String((it && it.name) || '').trim()
  if (!nm) return ''
  const br = (q === 'flac' || q === 'flac24bit') ? '1' : '0'
  const u = 'https://oiapi.net/API/Kuwo/?n=1&br=' + br + '&msg=' + encodeURIComponent(nm)
  const d = jsonOf(await httpGet(u))
  const url = firstStr((d.data || {}).url, d.url)
  if (!/^https?:\/\//i.test(url)) return ''
  const song = firstStr((d.data || {}).song, d.song)
  if (song && !nameHit(song, nm)) return ''
  return url
}

const mgDecode = (buf) => {
  const arr = toBytes(buf)
  if (arr.length < 4 || arr[0] !== 0xab || arr[1] !== 0xcd || arr[2] !== 0x01) return null
  const off = arr[3]
  const kb = Buffer.from(MIGU_KEY, 'utf8')
  const out = Buffer.alloc(arr.length - 4)
  for (let i = 4; i < arr.length; i++) out[i - 4] = (arr[i] + off - kb[(i - 4) % kb.length] + 256) % 256
  try {
    return JSON.parse(out.toString('utf8'))
  } catch (e) {
    return null
  }
}

const mgResolve = async (cid, quality) => {
  const tone = quality === '320k' || quality === 'flac' || quality === 'flac24bit' ? 'HQ' : 'PQ'
  const infoUrl = 'https://c.musicapp.migu.cn/MIGUM2.0/v1.0/content/resourceinfo.do?resourceType=2&copyrightId=' + encodeURIComponent(cid)
  const ri = jsonOf(await httpGet(infoUrl, { headers: Object.assign({}, HDR, { channel: '0140210', Referer: 'https://m.music.migu.cn/' }) }))
  const res = ((ri.resource || [])[0]) || {}
  const contentId = firstStr(res.contentId)
  if (!contentId) return ''
  const u = 'https://c.musicapp.migu.cn/strategy/listen-url/h5/v2.4?contentId=' + encodeURIComponent(contentId) +
    '&copyrightId=' + encodeURIComponent(cid) + '&resourceType=2&netType=01&toneFlag=' + tone +
    '&scene=&lowerQualityContentId=' + encodeURIComponent(contentId)
  const resp = await httpGet(u, { headers: Object.assign({}, MUA ? { 'User-Agent': MUA } : {}, { birth: 'h5page', channel: '014X031', Referer: 'https://y.migu.cn/', 'location-data': '30.6698676660,104.1229614820', 'location-info': ' ' }) })
  const json = mgDecode(resp.body)
  if (!json) return ''
  let url = firstStr((json.data || {}).url, json.url)
  if (!url) return ''
  if (tone === 'HQ') url = url.replace('MP3_128', 'MP3_320')
  if (!url) return ''
  return url
}

const biliResolve = async (bvid) => {
  const v = jsonOf(await httpGet('https://api.bilibili.com/x/web-interface/view?bvid=' + encodeURIComponent(bvid), { rawHeaders: 1, headers: { 'User-Agent': 'Mozilla/5.0' } }))
  const info = (v.data || {})
  const cid = info.cid
  if (!cid) return ''
  const p = jsonOf(await httpGet('https://api.bilibili.com/x/player/playurl?bvid=' + encodeURIComponent(bvid) + '&cid=' + cid + '&fnval=16&fourk=1', { rawHeaders: 1, headers: { 'User-Agent': 'Mozilla/5.0', Referer: 'https://www.bilibili.com/' } }))
  const dash = ((p.data || {}).dash) || {}
  const audios = dash.audio || []
  if (audios.length) {
    audios.sort((a, b) => (b.bandwidth || 0) - (a.bandwidth || 0))
    const u = audios[0].baseUrl || audios[0].base_url
    if (u) return u
  }
  const durl = ((p.data || {}).durl) || []
  return durl.length ? firstStr(durl[0].url) : ''
}

const LINES = {
  kg: [
    { name: '星海', fn: (it, q) => xhResolve('kg', it.kgHash, q === 'flac24bit' ? 'flac' : (q === '128k' ? '128kmp3' : (q === '320k' ? '320kmp3' : 'flac'))) }
  ],
  wy: [
    { name: '星海', fn: (it, q) => xhResolve('netease', it.wyId, q === '128k' ? 'standard' : (q === '320k' ? 'exhigh' : (q === 'flac' ? 'hires' : 'jymaster'))) }
  ],
  mg: [
    { name: '咪咕官方', fn: (it, q) => mgResolve(it.mgCid, q) }
  ],
  bili: [
    { name: 'B站官方', fn: (it) => biliResolve(it.bvid) }
  ],
  kw: [
    { name: '星海', fn: (it, q) => xhResolve('kw', it.kwRid, q === '128k' ? '128kmp3' : (q === '320k' ? '320kmp3' : 'flac')) },
    { name: '小听', fn: (it, q) => xtResolve(it, q) }
  ]
}

const SEARCHERS = () => ({ kg: kgSearch, wy: wySearch, kw: kwSearch, mg: mgSearch, bili: biliSearch })

const lookup = async (keyword, info) => {
  const q = String((info && info.keyword) || (info && info.musicInfo && info.musicInfo.name) || keyword || '').trim()
  if (!q) return null
  const s = SEARCHERS()
  const order = ['kg', 'wy', 'mg', 'kw', 'bili']
  for (let i = 0; i < order.length; i++) {
    try {
      const list = await s[order[i]](q, 1, 5)
      if (list && list.length) return list[0]
    } catch (e) {}
  }
  return null
}

const tryLines = async (source, info) => {
  const quality = String((info && info.type) || '320k')
  const it = info && info.musicInfo ? info.musicInfo : info
  let target = it
  if (!target || !target.id || String(target.id).length < 2) target = await lookup(target && target.name, info)
  if (!target) {
    const lk = await lookup((info && info.keyword) || (target && target.name), info)
    if (!lk) throw new Error('未找到歌曲')
    target = lk
  }
  const lines = LINES[target.source] || []
  const errs = []
  for (let i = 0; i < lines.length; i++) {
    try {
      const u = await lines[i].fn(target, quality)
      if (u && /^https?:\/\//i.test(u)) return u
      errs.push(lines[i].name + ':空')
    } catch (e) {
      errs.push(lines[i].name + ':' + e.message)
    }
  }
  throw new Error('全部线路失败(' + (target.source || '?') + '/' + quality + '): ' + errs.join(';'))
}

module.exports = {
  platform: 'xiaoting',
  version: '1.0.0',
  author: '星火',
  srcUrl: 'https://navpage-2026.surge.sh/',
  supportedSources: ['kg', 'wy', 'mg', 'kw', 'bili'],
  qualitys: ['128k', '320k', 'flac', 'flac24bit'],
  actions: ['musicSearch', 'musicUrl'],
  async musicSearch({ source, info }, cb) {
    try {
      const s = SEARCHERS()[source]
      if (!s) return cb(new Error('不支持该平台: ' + source))
      const kw = String((info && info.keyword) || '').trim()
      if (!kw) return cb(new Error('缺少关键词'))
      const list = await s(kw, Number((info && info.page) || 1), Number((info && info.limit) || 30))
      cb(null, list)
    } catch (e) {
      cb(e)
    }
  },
  async musicUrl({ source, info }, cb) {
    try {
      const u = await tryLines(source, info)
      cb(null, u)
    } catch (e) {
      cb(e)
    }
  }
}
