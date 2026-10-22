/**
 * @name 合音聚合 · 五平台三线路 v9
 * @description 网易/QQ/酷狗/酷我/咪咕 五平台，每平台 3 条线路自动降级
 * @version 9.0.0
 * @author 星火
 * @homepage https://navpage-2026.surge.sh/
 */

const { EVENT_NAMES, request, on, send, utils } = globalThis.lx
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
const UA_MOBILE = 'LX-Music-Mobile'
const UA_ANDROID = 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36'

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

const isClipUrl = (u) => {
  if (!u || typeof u !== 'string') return true
  if (/\/resource\/n[12]\//i.test(u)) return true
  if (/\/(nf|cn)\/resource\//i.test(u)) return true
  if (/\/RS0?\d/i.test(u)) return true
  if (/[?&](try|preview|short)=/i.test(u)) return true
  if (/\/(try|preview|short)\//i.test(u)) return true
  return false
}

const grab = (obj, paths) => {
  for (const path of paths) {
    let val = obj
    for (const key of path) {
      if (val == null) { val = undefined; break }
      val = val[key]
    }
    if (Array.isArray(val)) val = val[0]
    if (typeof val === 'string' && /^https?:/.test(val)) return val.replace(/\\u0026/g, '&')
    if (typeof val === 'string' && val.startsWith('//')) return 'https:' + val
  }
  return ''
}

const tryLines = async (lines, ctx) => {
  let lastErr = null
  for (let i = 0; i < lines.length; i++) {
    try {
      const url = await lines[i](ctx)
      if (url && /^https?:/.test(url) && !isClipUrl(url)) return url
      if (url && isClipUrl(url)) { lastErr = new Error('试听片段'); continue }
      lastErr = new Error('空链接')
    } catch (err) { lastErr = err }
  }
  throw new Error(lastErr ? lastErr.message : '所有线路失败')
}

const nameOf = (mi) => {
  if (!mi) return ''
  const singer = (mi.singer && mi.singer[0] && mi.singer[0].name) ||
    (mi.artist && mi.artist[0] && mi.artist[0].name) ||
    (typeof mi.singer === 'string' ? mi.singer : '')
  return mi.name ? (mi.name + (singer ? ' ' + singer : '')).trim() : ''
}

const htResolve = async (source, rid, level) => {
  const resp = await httpPost('https://musicserver.haitangw.cc/v1/music/resolve-url',
    JSON.stringify({ source, rid: String(rid), level: level || 'standard' }),
    { headers: { 'Content-Type': 'application/json; charset=utf-8', 'User-Agent': 'okhttp/5.0.0-alpha.14' } })
  const u = grab(resp.body, [['data', 'url']])
  if (u) return u
  throw new Error('海棠无链接')
}

const CY_KEY = '1ffdf5733f5d538760e63d7e46ba17438d9f7b9dfc18c51be1109386fd74c3a1'

const wySearchId = async (keyword) => {
  if (!keyword) return ''
  const url = 'https://music-api.gdstudio.xyz/api.php?types=search&source=netease&name=' + encodeURIComponent(keyword) + '&count=5&pages=1'
  try {
    const resp = await httpGet(url, { headers: { 'User-Agent': UA_MOBILE, Accept: 'application/json' } })
    const arr = resp.body
    if (Array.isArray(arr)) {
      for (let i = 0; i < arr.length; i++) {
        const it = arr[i]
        if (it && it.id) return String(it.id)
      }
    }
  } catch (e) {}
  return ''
}

const wyLines = [
  async ({ id, quality }) => {
    const brMap = { '128k': '128', '320k': '320', flac: '740', flac24bit: '740' }
    const url = 'https://music-api.gdstudio.xyz/api.php?use_xbridge3=true&loader_name=forest&need_sec_link=1&sec_link_scene=im&theme=light&types=url&source=netease&id=' + id + '&br=' + (brMap[quality] || '320')
    const resp = await httpGet(url, { headers: { 'User-Agent': UA_MOBILE, Accept: 'application/json' } })
    const u = grab(resp.body, [['url']])
    if (u) return u
    throw new Error('GDAPI无链接')
  },
  async ({ id }) => {
    const resp = await httpPost('https://c.wwwweb.top/music/url',
      JSON.stringify({ source: 'wy', musicId: String(id), quality: '320k' }),
      { headers: { 'Content-Type': 'application/json', 'User-Agent': UA_ANDROID } })
    const u = grab(resp.body, [['url'], ['data', 'url']])
    if (u) return u
    throw new Error('wwwweb无链接')
  },
  async ({ id }) => {
    const resp = await httpGet('https://oiapi.net/api/Music_163?id=' + id, { headers: { 'User-Agent': UA } })
    const u = grab(resp.body, [['data', 0, 'url'], ['data', 'url'], ['url']])
    if (u) return u
    throw new Error('溯音网易无链接')
  },
  async ({ id, keyword, quality }) => {
    const rid = id || await wySearchId(keyword)
    if (!rid) throw new Error('网易搜索无结果')
    const brMap = { '128k': '128', '320k': '320', flac: '740', flac24bit: '740' }
    const url = 'https://music-api.gdstudio.xyz/api.php?use_xbridge3=true&loader_name=forest&need_sec_link=1&sec_link_scene=im&theme=light&types=url&source=netease&id=' + rid + '&br=' + (brMap[quality] || '320')
    const resp = await httpGet(url, { headers: { 'User-Agent': UA_MOBILE, Accept: 'application/json' } })
    const u = grab(resp.body, [['url']])
    if (u) return u
    throw new Error('网易搜索兜底无链接')
  },
  async ({ keyword }) => {
    const rid = await wySearchId(keyword)
    if (!rid) throw new Error('网易搜索无结果')
    const resp = await httpGet('https://oiapi.net/api/Music_163?id=' + rid, { headers: { 'User-Agent': UA } })
    const u = grab(resp.body, [['data', 0, 'url'], ['data', 'url'], ['url']])
    if (u) return u
    throw new Error('溯音搜索兜底无链接')
  },
]

const txLines = [
  async ({ musicInfo }) => {
    const kw = nameOf(musicInfo)
    if (!kw) throw new Error('QQ缺歌名')
    const resp = await httpGet('https://cyapi.top/API/qq_music.php?apikey=' + CY_KEY + '&msg=' + encodeURIComponent(kw) + '&n=1&type=json&quality=320', { headers: { 'User-Agent': UA } })
    const u = grab(resp.body, [['url'], ['data', 'url'], ['music']])
    if (u) return u
    throw new Error('迟言QQ无链接')
  },
  async ({ musicInfo }) => {
    const kw = nameOf(musicInfo)
    if (!kw) throw new Error('QQ缺歌名')
    const resp = await httpGet('https://a.aa.cab/qq.music?msg=' + encodeURIComponent(kw) + '&n=1', { headers: { 'User-Agent': UA } })
    const u = grab(resp.body, [['data', 'music'], ['music'], ['data', 'url']])
    if (u) return u
    throw new Error('aa.cab无链接')
  },
  async ({ musicInfo }) => {
    const songmid = musicInfo.songmid || musicInfo.id || ''
    if (!songmid) throw new Error('QQ缺mid')
    const resp = await httpGet('https://api.vkeys.cn/v2/music/tencent/geturl?mid=' + songmid, { headers: { 'User-Agent': UA } })
    const u = grab(resp.body, [['data', 'url'], ['url']])
    if (u) return u
    throw new Error('vkeys无链接')
  },
]

const kgSearchHash = async (keyword) => {
  if (!keyword) return ''
  try {
    const resp = await httpGet('https://cyapi.top/API/kugou.php?apikey=' + CY_KEY + '&type=json&msg=' + encodeURIComponent(keyword), { headers: { 'User-Agent': UA } })
    const d = resp.body
    const list = d && d.list
    if (Array.isArray(list)) {
      for (let i = 0; i < list.length; i++) {
        const it = list[i]
        if (it && it.id) return String(it.id)
      }
    }
  } catch (e) {}
  return ''
}

const kgLines = [
  async ({ id, musicInfo }) => {
    const hash = (musicInfo && musicInfo.hash) || id || ''
    if (!hash) throw new Error('酷狗缺hash')
    const resp = await httpGet('https://cyapi.top/API/kugou.php?apikey=' + CY_KEY + '&type=json&id=' + hash, { headers: { 'User-Agent': UA } })
    const d = resp.body || {}
    const name = d.data && d.data.songName
    if (!name) throw new Error('迟言酷狗hash无效')
    const u = grab(d, [['data', 'url']])
    if (u) return u
    throw new Error('迟言酷狗无链接')
  },
  async ({ id, musicInfo, keyword, quality }) => {
    const hash = (musicInfo && musicInfo.hash) || (id && /^[0-9A-Fa-f]{32}$/.test(id) ? id : '') || await kgSearchHash(keyword)
    if (!hash) throw new Error('酷狗无可用hash')
    const resp = await httpGet('https://cyapi.top/API/kugou.php?apikey=' + CY_KEY + '&type=json&id=' + hash, { headers: { 'User-Agent': UA } })
    const d = resp.body || {}
    if (!(d.data && d.data.songName)) throw new Error('酷狗hash无效')
    const u = grab(d, [['data', 'url']])
    if (u) return u
    throw new Error('酷狗备用无链接')
  },
  async ({ musicInfo }) => {
    const kw = nameOf(musicInfo)
    if (!kw) throw new Error('酷狗缺歌名')
    const hash = await kgSearchHash(kw)
    if (!hash) throw new Error('酷狗搜索无结果')
    const resp = await httpGet('https://cyapi.top/API/kugou.php?apikey=' + CY_KEY + '&type=json&id=' + hash, { headers: { 'User-Agent': UA } })
    const u = grab(resp.body || {}, [['data', 'url']])
    if (u && await probe(u)) return u
    throw new Error('酷狗搜索直取无链接')
  },
  async ({ musicInfo }) => {
    const kw = nameOf(musicInfo)
    if (!kw) throw new Error('酷狗缺歌名')
    for (let n = 1; n <= 3; n++) {
      try {
        const resp = await httpGet('https://api.xcvts.cn/api/music/kugou?msg=' + encodeURIComponent(kw) + '&n=' + n, { headers: { 'User-Agent': UA } })
        const u = grab(resp.body, [['data', 'music_url'], ['data', 'url'], ['music_url']])
        if (u && await probe(u)) return u
      } catch (e) {}
    }
    throw new Error('xcvts酷狗无可用链接')
  },
  async ({ id, musicInfo }) => {
    const hash = (musicInfo && musicInfo.hash) || id || ''
    if (!hash) throw new Error('酷狗缺hash')
    const url = 'https://wwwapi.kugou.com/yy/index.php?r=play/getdata&hash=' + hash + '&platid=4&album_id=' + ((musicInfo && musicInfo.albumId) || '') + '&mid=00000000000000000000000000000000'
    const resp = await httpGet(url, { headers: { 'User-Agent': UA, Referer: 'https://www.kugou.com/' } })
    const d = resp.body || {}
    if (d.data && d.data.song_name === '') throw new Error('酷狗官方hash无效')
    const u = grab(d, [['data', 'play_backup_url'], ['data', 'play_url']])
    if (u) return u
    throw new Error('酷狗官方风控')
  },
]

const kwLines = [
  async ({ id, musicInfo }) => {
    const rid = /^\d+$/.test(String(id || '')) ? id : ''
    if (!rid) throw new Error('酷我rid非数字')
    const resp = await httpGet('http://nmobi.kuwo.cn/mobi.s?f=web&user=0&source=kwplayerhd_ar_4.3.0.8_tianbao_T1A_qirui.apk&type=convert_url_with_sign&rid=' + rid + '&br=320kmp3', { headers: { 'User-Agent': UA, Referer: 'http://www.kuwo.cn/' } })
    const u = grab(resp.body, [['data', 'url'], ['url']])
    if (u) return u
    throw new Error('mobi320无链接')
  },
  async ({ id }) => {
    const rid = /^\d+$/.test(String(id || '')) ? id : ''
    if (!rid) throw new Error('酷我rid非数字')
    const resp = await httpGet('http://nmobi.kuwo.cn/mobi.s?f=web&user=0&source=kwplayerhd_ar_4.3.0.8_tianbao_T1A_qirui.apk&type=convert_url_with_sign&rid=' + rid + '&br=2000kflac', { headers: { 'User-Agent': UA, Referer: 'http://www.kuwo.cn/' } })
    const u = grab(resp.body, [['data', 'url'], ['url']])
    if (u) return u
    throw new Error('mobiFLAC无链接')
  },
  async ({ musicInfo }) => {
    const kw = nameOf(musicInfo)
    if (!kw) throw new Error('酷我缺歌名')
    const resp = await httpGet('https://oiapi.net/api/Kuwo?msg=' + encodeURIComponent(kw) + '&n=1', { headers: { 'User-Agent': UA } })
    const direct = grab(resp.body, [['data', 'url']])
    if (direct) return direct
    const msg = resp.body && resp.body.message
    if (msg) {
      const m = String(msg).match(/音乐链接[：:](https?:\/\/\S+)/)
      if (m && m[1]) return m[1]
    }
    throw new Error('溯音酷我无链接')
  },
  async ({ musicInfo }) => {
    const kw = nameOf(musicInfo)
    if (!kw) throw new Error('酷我缺歌名')
    const list = await kwSearch(kw, 1, 5)
    for (let i = 0; i < list.length; i++) {
      const rid = list[i].songmid
      if (!rid) continue
      try {
        const resp = await httpGet('http://nmobi.kuwo.cn/mobi.s?f=web&user=0&source=kwplayerhd_ar_4.3.0.8_tianbao_T1A_qirui.apk&type=convert_url_with_sign&rid=' + rid + '&br=320kmp3', { headers: { 'User-Agent': UA, Referer: 'http://www.kuwo.cn/' } })
        const u = grab(resp.body, [['data', 'url'], ['url']])
        if (u && !isClipUrl(u) && await probe(u)) return u
      } catch (e) {}
    }
    throw new Error('酷我多结果无可用链接')
  },
]

const probe = async (url) => {
  if (!url || !/^https?:\/\//i.test(url)) return false
  try {
    const r = await httpGet(url, { headers: { 'User-Agent': UA, Range: 'bytes=0-16383' } })
    const h = r.headers || {}
    const ct = String(h['content-type'] || h['Content-Type'] || '')
    if (/json|xml/i.test(ct)) return false
    const body = typeof r.body === 'string' ? r.body : ''
    if (/x-error-info|^\s*<html|^\s*<\?xml/i.test(body)) return false
    const head = body.slice(0, 3)
    const magic = head === 'ID3' || (body.charCodeAt(0) & 0xFF) === 0xFF
    const cr = String(h['content-range'] || h['Content-Range'] || '')
    const m = /\/(\d+)\s*$/.exec(cr)
    if (m) return Number(m[1]) > 500000
    const cl = Number(h['content-length'] || h['Content-Length'] || 0)
    if (magic && (cl > 100000 || body.length > 8000)) return true
    if (cl > 500000 && !/text\/html/i.test(ct)) return true
    if (/audio|octet-stream|mpeg/i.test(ct) && cl > 500000) return true
    return false
  } catch (e) { return false }
}

const mgLines = [
  async ({ musicInfo }) => {
    const kw = nameOf(musicInfo)
    if (!kw) throw new Error('咪咕缺歌名')
    const resp = await httpGet('https://oiapi.net/api/MiGu_Music?msg=' + encodeURIComponent(kw) + '&n=1', { headers: { 'User-Agent': UA } })
    const u = grab(resp.body, [['data', 'url']])
    if (!u) throw new Error('溯音咪咕无链接')
    const hi = u.replace('MP3_128_16', 'MP3_320_16')
    if (hi !== u && await probe(hi)) return hi
    if (await probe(u)) return u
    throw new Error('咪咕链接不可达')
  },
  async ({ musicInfo }) => {
    const kw = nameOf(musicInfo)
    if (!kw) throw new Error('咪咕缺歌名')
    for (let n = 2; n <= 3; n++) {
      try {
        const resp = await httpGet('https://oiapi.net/api/MiGu_Music?msg=' + encodeURIComponent(kw) + '&n=' + n, { headers: { 'User-Agent': UA } })
        const u = grab(resp.body, [['data', 'url']])
        if (!u) continue
        const hi = u.replace('MP3_128_16', 'MP3_320_16')
        if (hi !== u && await probe(hi)) return hi
        if (await probe(u)) return u
      } catch (e) {}
    }
    throw new Error('溯音咪咕多结果无链接')
  },
  async ({ musicInfo }) => {
    const kw = nameOf(musicInfo)
    if (!kw) throw new Error('咪咕缺歌名')
    const resp = await httpGet('https://oiapi.net/api/MiGu_Music?msg=' + encodeURIComponent(kw) + '&n=1', { headers: { 'User-Agent': UA } })
    const u = grab(resp.body, [['data', 'url']])
    if (u) return u
    throw new Error('溯音咪咕128k无链接')
  },
  async ({ musicInfo }) => {
    const kw = nameOf(musicInfo)
    if (!kw) throw new Error('咪咕缺歌名')
    const resp = await httpGet('https://oiapi.net/api/MiGu_Music?msg=' + encodeURIComponent(kw) + '&n=1', { headers: { 'User-Agent': UA } })
    const u = grab(resp.body, [['data', 'url']])
    if (u) {
      const flac = u.replace('MP3_128_16_Stero', 'FLAC_128_16_Stero').replace(/MP3_128_16/, 'FLAC_128_16')
      if (flac !== u) return flac
    }
    throw new Error('溯音咪咕无损无链接')
  },
]

const SOURCES = {
  wy: { name: '网易云', type: 'music', actions: ['musicUrl'], qualitys: ['128k', '320k', 'flac', 'flac24bit'] },
  tx: { name: 'QQ音乐', type: 'music', actions: ['musicUrl'], qualitys: ['128k', '320k', 'flac', 'flac24bit'] },
  kg: { name: '酷狗音乐', type: 'music', actions: ['musicUrl'], qualitys: ['128k', '320k', 'flac', 'flac24bit'] },
  kw: { name: '酷我音乐', type: 'music', actions: ['musicUrl'], qualitys: ['128k', '320k', 'flac', 'flac24bit'] },
  mg: { name: '咪咕音乐', type: 'music', actions: ['musicUrl'], qualitys: ['128k', '320k', 'flac', 'flac24bit'] },
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
  if (source === 'mg') return firstStr(mi.copyrightId, common)
  return common
}

const wySearch = async (keyword, page, limit) => {
  const url = 'https://music-api.gdstudio.xyz/api.php?types=search&source=netease&name=' + encodeURIComponent(keyword) + '&count=' + limit + '&pages=' + page
  const resp = await httpGet(url, { headers: { 'User-Agent': UA_MOBILE, Accept: 'application/json' } })
  const arr = Array.isArray(resp.body) ? resp.body : []
  return arr.map((it) => ({
    songmid: String(it.id),
    name: it.name || '',
    singer: (it.artist || []).join(' / '),
    albumName: it.album || '',
    interval: it.duration ? Math.floor(it.duration / 60) + ':' + String(it.duration % 60).padStart(2, '0') : '',
  }))
}

const txSearch = async (keyword, page, limit) => {
  const resp = await httpGet('https://cyapi.top/API/qq_music.php?apikey=' + CY_KEY + '&type=json&msg=' + encodeURIComponent(keyword), { headers: { 'User-Agent': UA } })
  const list = (resp.body && resp.body.list) || []
  return list.slice(0, limit).map((it) => ({
    songmid: String(it.songmid || it.mid || it.id || ''),
    name: it.SongName || it.songname || it.name || '',
    singer: it.SingerName || it.singer || '',
    albumName: it.AlbumName || it.album || '',
    interval: '',
  }))
}

const kgSearch = async (keyword, page, limit) => {
  const resp = await httpGet('https://cyapi.top/API/kugou.php?apikey=' + CY_KEY + '&type=json&msg=' + encodeURIComponent(keyword), { headers: { 'User-Agent': UA } })
  const list = (resp.body && resp.body.list) || []
  return list.slice(0, limit).map((it) => ({
    songmid: String(it.id || ''),
    name: it.SongName || it.songname || it.name || '',
    singer: it.SingerName || it.singer || '',
    albumName: it.AlbumName || it.album || '',
    interval: '',
  }))
}

const kwSearch = async (keyword, page, limit) => {
  const resp = await httpGet('https://search.kuwo.cn/r.s?all=' + encodeURIComponent(keyword) + '&ft=music&itemset=web_2013&client=kt&pn=0&rn=' + limit + '&rformat=json&encoding=utf8', { headers: { 'User-Agent': UA } })
  const raw = typeof resp.body === 'string' ? resp.body : ''
  const out = []
  const blocks = raw.split("{'AARTIST'").slice(1)
  for (let i = 0; i < blocks.length && out.length < limit; i++) {
    const b = blocks[i]
    const rid = /'MUSICRID':'MUSIC_(\d+)'/.exec(b)
    const nm = /'NAME':'([^']*)'/.exec(b)
    const ar = /'ARTIST':'([^']*)'/.exec(b)
    const al = /'ALBUM':'([^']*)'/.exec(b)
    const du = /'DURATION':'([^']*)'/.exec(b)
    if (!rid || !nm) continue
    const dur = Number(du ? du[1] : 0)
    out.push({
      songmid: rid[1],
      name: nm[1].replace(/&nbsp;/g, ' '),
      singer: ar ? ar[1].replace(/&nbsp;/g, ' ').replace(/\\+u0026/g, '&') : '',
      albumName: al ? al[1].replace(/&nbsp;/g, ' ') : '',
      interval: dur ? Math.floor(dur / 60) + ':' + String(dur % 60).padStart(2, '0') : '',
    })
  }
  return out
}

const mgSearch = async (keyword, page, limit) => {
  const resp = await httpGet('https://oiapi.net/api/MiGu_Music?msg=' + encodeURIComponent(keyword) + '&n=1', { headers: { 'User-Agent': UA } })
  const d = (resp.body && resp.body.data) || {}
  if (!d.song) return []
  return [{ songmid: String(d.copyrightId || ''), name: d.song, singer: (d.singers || []).join(' / '), albumName: d.album || '', interval: '' }]
}

const SEARCHERS = { wy: wySearch, tx: txSearch, kg: kgSearch, kw: kwSearch, mg: mgSearch }

on(EVENT_NAMES.request, async ({ source, action, info }) => {
  if (action === 'musicSearch') {
    const { keyword, page = 1, limit = 20 } = info || {}
    const fn = SEARCHERS[source]
    if (!fn) return Promise.reject(new Error('unsupported source: ' + source))
    try {
      const list = await fn(String(keyword || ''), Number(page) || 1, Number(limit) || 20)
      return { list, allPage: 1, limit: Number(limit) || 20, total: list.length }
    } catch (e) {
      return Promise.reject(new Error('搜索失败: ' + (e.message || '')))
    }
  }
  if (action !== 'musicUrl') return Promise.reject(new Error('action not support'))
  const { musicInfo, type } = info
  const id = pickId(source, musicInfo)
  const ctx = { id, quality: type, keyword: nameOf(musicInfo), musicInfo }
  let lines = []
  switch (source) {
    case 'wy': lines = wyLines; break
    case 'tx': lines = txLines; break
    case 'kg': lines = kgLines; break
    case 'kw': lines = kwLines; break
    case 'mg': lines = mgLines; break
    default: return Promise.reject(new Error('unsupported source: ' + source))
  }
  return tryLines(lines, ctx)
})

send(EVENT_NAMES.inited, {
  status: true,
  openDevTools: false,
  sources: SOURCES,
})