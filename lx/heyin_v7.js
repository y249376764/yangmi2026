/**
 * @name 合音聚合 · 四平台双线路 v7
 * @description 网易/腾讯/酷我/酷狗 四平台多线路自动切换（QQ加vkeys线）
 * @version 7.0.0
 * @author 星火
 * @homepage https://navpage-2026.surge.sh/
 */

const { EVENT_NAMES, request, on, send, utils } = globalThis.lx
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
const UA_MOBILE = 'LX-Music-Mobile'

const httpGet = (url, options = {}) => new Promise((resolve, reject) => {
  request(url, { method: 'get', timeout: 15000, ...options }, (err, resp) => {
    if (err) return reject(new Error(err.message || '网络错误'))
    if (!resp || resp.statusCode >= 400) return reject(new Error('HTTP ' + (resp && resp.statusCode)))
    resolve(resp)
  })
})
const httpPost = (url, body, options = {}) => new Promise((resolve, reject) => {
  const payload = typeof body === 'string' ? body : JSON.stringify(body)
  request(url, { method: 'post', timeout: 15000, ...options }, (err, resp) => {
    if (err) return reject(new Error(err.message || '网络错误'))
    if (!resp || resp.statusCode >= 400) return reject(new Error('HTTP ' + (resp && resp.statusCode)))
    resolve(resp)
  })
})
const md5 = (str) => { try { return utils.crypto.md5(str) } catch (e) { return '' } }

const pickUrl = (obj, paths) => {
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
      if (url && /^https?:/.test(url)) return url
      throw new Error('空链接')
    } catch (err) { lastErr = err }
  }
  throw new Error(lastErr ? lastErr.message : '所有线路失败')
}

/* ========== 网易云音乐 (wy) ========== */
const wyQualityMap = { '128k': 'standard', '320k': 'exhigh', flac: 'lossless', flac24bit: 'lossless' }
const wyLines = [
  async ({ id, quality }) => {
    const brMap = { '128k': '128', '320k': '320', flac: '740', flac24bit: '740' }
    const br = brMap[quality] || '320'
    const url = 'https://music-api.gdstudio.xyz/api.php?use_xbridge3=true&loader_name=forest&need_sec_link=1&sec_link_scene=im&theme=light&types=url&source=netease&id=' + id + '&br=' + br
    const resp = await httpGet(url, { headers: { 'User-Agent': UA_MOBILE, Accept: 'application/json' } })
    const d = resp.body
    const u = d && d.url
    if (u && /^https?:/.test(u)) return u
    throw new Error('GDAPI无链接(可能付费)')
  },
  async ({ id, quality }) => {
    const url = 'https://oiapi.net/api/Music_163?id=' + id
    const resp = await httpGet(url, { headers: { 'User-Agent': UA } })
    const d = resp.body
    const arr = d && d.data
    const item = arr && (Array.isArray(arr) ? arr[0] : arr)
    const u = item && item.url
    if (u && /^https?:/.test(u)) return u
    throw new Error('oiapi无链接(可能付费)')
  },
]

/* ========== QQ音乐 (tx) ========== */
const txFileConfig = {
  '128k': { s: 'M500', e: '.mp3' },
  '320k': { s: 'M800', e: '.mp3' },
  flac: { s: 'F000', e: '.flac' },
  flac24bit: { s: 'F000', e: '.flac' },
}
const txLines = [
  async ({ musicInfo }) => {
    const songmid = musicInfo.songmid || musicInfo.id || ''
    if (!songmid) throw new Error('QQ缺mid')
    const url = 'https://api.vkeys.cn/v2/music/tencent/geturl?mid=' + songmid
    const resp = await httpGet(url, { headers: { 'User-Agent': UA } })
    const d = resp.body
    const u = d && d.data && d.data.url
    if (u && /^https?:/.test(u)) return u
    throw new Error('vkeys无链接(付费或无音质)')
  },
  async ({ musicInfo, quality }) => {
    const fileCfg = txFileConfig[quality] || txFileConfig['128k']
    const songmid = musicInfo.songmid || musicInfo.id || ''
    if (!songmid) throw new Error('QQ缺mid')
    const strMediaMid = musicInfo.strMediaMid || musicInfo.mediaMid || songmid
    const file = fileCfg.s + strMediaMid + fileCfg.e
    const reqData = {
      req_0: {
        module: 'vkey.GetVkeyServer', method: 'CgiGetVkey',
        param: { filename: [file], guid: '10000', songmid: [songmid], songtype: [0], uin: '0', loginflag: 1, platform: '20' },
      },
      loginUin: '0', comm: { uin: '0', format: 'json', ct: 24, cv: 0 },
    }
    const url = 'https://u.y.qq.com/cgi-bin/musicu.fcg?format=json&data=' + encodeURIComponent(JSON.stringify(reqData))
    const resp = await httpGet(url, { headers: { 'User-Agent': UA, Referer: 'https://y.qq.com' } })
    const d = resp.body
    const info = d && d.req_0 && d.req_0.data && d.req_0.data.midurlinfo && d.req_0.data.midurlinfo[0]
    const purl = info && info.purl
    const sip = d && d.req_0 && d.req_0.data && d.req_0.data.sip && d.req_0.data.sip[0]
    if (purl && sip) return sip + purl
    if (purl) return 'https://isure.stream.qqmusic.qq.com/' + purl
    throw new Error('官方vkey无purl(游客受限)')
  },
]

/* ========== 酷狗音乐 (kg) ========== */
const kgLines = [
  async ({ id, musicInfo }) => {
    const hash = (musicInfo && musicInfo.hash) || id || ''
    if (!hash) throw new Error('酷狗缺hash')
    const url = 'https://wwwapi.kugou.com/yy/index.php?r=play/getdata&hash=' + hash + '&platid=4&album_id=' + ((musicInfo && musicInfo.albumId) || '') + '&mid=00000000000000000000000000000000'
    const resp = await httpGet(url, { headers: { 'User-Agent': UA, Referer: 'https://www.kugou.com/' } })
    const d = resp.body
    const u = d && d.data && (d.data.play_backup_url || d.data.play_url)
    if (u) return u
    throw new Error('酷狗官方风控')
  },
]

/* ========== 酷我音乐 (kw) ========== */
const kwLines = [
  async ({ id, quality }) => {
    const url = 'http://antiserver.kuwo.cn/anti.s?type=convert_url3&rid=' + id + '&format=' + (quality === 'flac' || quality === 'flac24bit' ? 'flac' : 'mp3') + '&response=url'
    const resp = await httpGet(url, { headers: { 'User-Agent': UA, Referer: 'http://www.kuwo.cn/' } })
    const body = resp.body
    let u = ''
    if (typeof body === 'string') u = String(body).trim()
    else if (body && typeof body.url === 'string') u = body.url
    else if (body && body.data && typeof body.data.url === 'string') u = body.data.url
    if (/^https?:/.test(u)) return u
    throw new Error('anti.s无链接')
  },
  async ({ musicInfo, quality }) => {
    if (!musicInfo || !musicInfo.name) throw new Error('溯音酷我需要歌名')
    const name = musicInfo.name + ((musicInfo.singer && musicInfo.singer[0] && musicInfo.singer[0].name) ? ' ' + musicInfo.singer[0].name : '')
    const br = quality === 'flac' || quality === 'flac24bit' ? 1 : (quality === '320k' ? 5 : 7)
    const url = 'https://oiapi.net/api/Kuwo?msg=' + encodeURIComponent(name) + '&n=1&br=' + br
    const resp = await httpGet(url, { headers: { 'User-Agent': UA } })
    const body = resp.body
    if (body && body.data && typeof body.data.url === 'string' && /^https?:/.test(body.data.url)) return body.data.url
    if (body && body.message) {
      const m = String(body.message).match(/音乐链接[：:](https?:\/\/\S+)/)
      if (m && m[1]) return m[1]
    }
    throw new Error('溯音酷我无链接')
  },
]

/* ========== 兜底: 酷我搜索 → anti.s ========== */
const kwSearchLine = async ({ keyword, musicInfo }) => {
  const kwName = keyword || ((musicInfo && musicInfo.name) || '')
  if (!kwName) throw new Error('无关键词')
  const searchUrl = 'http://search.kuwo.cn/r.s?all=' + encodeURIComponent(kwName) + '&ft=music&itemset=web_2013&client=kt&pn=0&rn=10&rformat=json&encoding=utf8'
  const resp = await httpGet(searchUrl, { headers: { 'User-Agent': UA } })
  let rid = ''
  const raw = typeof resp.body === 'string' ? resp.body : JSON.stringify(resp.body)
  const m = raw.match(/DC_TARGETID['"]?\s*[:：]\s*['"]?(\d+)/g)
  if (m && m.length) {
    const ids = m.map(x => (x.match(/\d+/) || [''])[0])
    const names = raw.match(/SONGNAME['"]?\s*[:：]\s*['"]([^'"]*)/g) || []
    for (let i = 0; i < ids.length; i++) {
      const nm = names[i] ? names[i].replace(/SONGNAME['"]?\s*[:：]\s*['"]/i, '').toLowerCase() : ''
      if (nm && /伴奏|dj|翻唱|cover|remix|纯音乐|现场|live|ktv/.test(nm)) continue
      rid = ids[i]
      break
    }
    if (!rid && ids.length) rid = ids[0]
  }
  if (!rid) throw new Error('酷我搜索无结果')
  const url = 'http://antiserver.kuwo.cn/anti.s?type=convert_url3&rid=' + rid + '&format=mp3&response=url'
  const resp2 = await httpGet(url, { headers: { 'User-Agent': UA, Referer: 'http://www.kuwo.cn/' } })
  const body = resp2.body
  let u = ''
  if (typeof body === 'string') u = String(body).trim()
  else if (body && typeof body.url === 'string') u = body.url
  else if (body && body.data && typeof body.data.url === 'string') u = body.data.url
  if (/^https?:/.test(u)) return u
  throw new Error('酷我兜底anti.s无链接')
}

const SOURCES = {
  wy: { name: '网易云', type: 'music', actions: ['musicUrl'], qualitys: ['128k', '320k', 'flac', 'flac24bit'] },
  tx: { name: 'QQ音乐', type: 'music', actions: ['musicUrl'], qualitys: ['128k', '320k', 'flac', 'flac24bit'] },
  kg: { name: '酷狗音乐', type: 'music', actions: ['musicUrl'], qualitys: ['128k', '320k', 'flac', 'flac24bit'] },
  kw: { name: '酷我音乐', type: 'music', actions: ['musicUrl'], qualitys: ['128k', '320k', 'flac', 'flac24bit'] },
}

on(EVENT_NAMES.request, ({ source, action, info }) => {
  if (action !== 'musicUrl') return Promise.reject(new Error('action not support'))
  const { musicInfo, type } = info
  const id = musicInfo.songmid || musicInfo.hash || musicInfo.id || musicInfo.songId || musicInfo.songid || ''
  const singerName = (musicInfo.singer && musicInfo.singer[0] && musicInfo.singer[0].name) || (musicInfo.artist && musicInfo.artist[0] && musicInfo.artist[0].name) || (typeof musicInfo.singer === 'string' ? musicInfo.singer : '')
  const keyword = musicInfo.name ? (musicInfo.name + (singerName ? ' ' + singerName : '')).trim() : ''
  const biliKeyword = musicInfo.name ? musicInfo.name.trim() : keyword

  const ctx = { id, quality: type, keyword, musicInfo }
  let lines = []

  switch (source) {
    case 'wy':
      lines = [...wyLines, () => kwSearchLine({ keyword: biliKeyword, musicInfo })]
      break
    case 'tx':
      lines = [...txLines, () => kwSearchLine({ keyword: biliKeyword, musicInfo })]
      break
    case 'kg':
      lines = [...kgLines, () => kwSearchLine({ keyword: biliKeyword, musicInfo })]
      break
    case 'kw':
      lines = [...kwLines, () => kwSearchLine({ keyword: biliKeyword, musicInfo })]
      break
    default:
      return Promise.reject(new Error('unsupported source: ' + source))
  }

  return tryLines(lines, ctx).catch(err => {
    return Promise.reject(err)
  })
})

send(EVENT_NAMES.inited, {
  status: true,
  openDevTools: false,
  sources: SOURCES,
})
