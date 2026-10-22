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

const kgLines = [
  async ({ id, musicInfo }) => {
    const hash = (musicInfo && musicInfo.hash) || id || ''
    if (!hash) throw new Error('酷狗缺hash')
    const resp = await httpGet('https://cyapi.top/API/kugou.php?apikey=' + CY_KEY + '&type=json&id=' + hash, { headers: { 'User-Agent': UA } })
    const u = grab(resp.body, [['data', 'url']])
    if (u) return u
    throw new Error('迟言酷狗无链接')
  },
  async ({ musicInfo }) => {
    const kw = nameOf(musicInfo)
    if (!kw) throw new Error('酷狗缺歌名')
    const resp = await httpGet('https://api.xcvts.cn/api/music/kugou?msg=' + encodeURIComponent(kw) + '&n=1', { headers: { 'User-Agent': UA } })
    const u = grab(resp.body, [['data', 'music_url'], ['data', 'url'], ['music_url'], ['url']])
    if (u) return u
    throw new Error('xcvts酷狗无链接')
  },
  async ({ id, musicInfo }) => {
    const hash = (musicInfo && musicInfo.hash) || id || ''
    if (!hash) throw new Error('酷狗缺hash')
    const url = 'https://wwwapi.kugou.com/yy/index.php?r=play/getdata&hash=' + hash + '&platid=4&album_id=' + ((musicInfo && musicInfo.albumId) || '') + '&mid=00000000000000000000000000000000'
    const resp = await httpGet(url, { headers: { 'User-Agent': UA, Referer: 'https://www.kugou.com/' } })
    const u = grab(resp.body, [['data', 'play_backup_url'], ['data', 'play_url']])
    if (u) return u
    throw new Error('酷狗官方风控')
  },
]

const kwLines = [
  async ({ id }) => {
    const resp = await httpGet('http://nmobi.kuwo.cn/mobi.s?f=web&user=0&source=kwplayerhd_ar_4.3.0.8_tianbao_T1A_qirui.apk&type=convert_url_with_sign&rid=' + id + '&br=320kmp3', { headers: { 'User-Agent': UA, Referer: 'http://www.kuwo.cn/' } })
    const u = grab(resp.body, [['data', 'url'], ['url']])
    if (u) return u
    throw new Error('mobi320无链接')
  },
  async ({ id }) => {
    const resp = await httpGet('http://nmobi.kuwo.cn/mobi.s?f=web&user=0&source=kwplayerhd_ar_4.3.0.8_tianbao_T1A_qirui.apk&type=convert_url_with_sign&rid=' + id + '&br=2000kflac', { headers: { 'User-Agent': UA, Referer: 'http://www.kuwo.cn/' } })
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
]

const mgLines = [
  async ({ musicInfo }) => {
    const kw = nameOf(musicInfo)
    if (!kw) throw new Error('咪咕缺歌名')
    const resp = await httpGet('https://oiapi.net/api/MiGu_Music?msg=' + encodeURIComponent(kw) + '&n=1', { headers: { 'User-Agent': UA } })
    const u = grab(resp.body, [['data', 'url']])
    if (u) return u.replace('MP3_128_16', 'MP3_320_16')
    throw new Error('溯音咪咕无链接')
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

const pickId = (source, mi) => {
  if (!mi) return ''
  const s = (v) => (v == null ? '' : String(v))
  if (source === 'wy') return s(mi.songId || mi.songid || mi.id)
  if (source === 'tx') return s(mi.songmid || mi.songMid || mi.mid || mi.id)
  if (source === 'kg') return s(mi.hash || mi.Hash || mi.albumAudioId || mi.id)
  if (source === 'kw') return s(mi.rid || mi.musicrid || mi.songId || mi.id)
  if (source === 'mg') return s(mi.copyrightId || mi.songId || mi.id)
  return s(mi.id || mi.songmid)
}

on(EVENT_NAMES.request, ({ source, action, info }) => {
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