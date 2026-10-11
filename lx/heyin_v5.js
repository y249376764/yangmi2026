/**
 * @name 合音聚合 · 七平台全线路 v5.0
 * @description QQ/网易/酷狗/酷我/咪咕/汽水/B站 全线路池自动切换 (2026-10-11 接口大检修版)
 * @version 5.0.0
 * @author 星火
 * @homepage https://navpage-2026.surge.sh/
 */

/* =========================================================
 *  洛雪音乐(LX Music)自定义音源 v5.0 全包
 *  平台: QQ(tx) / 网易(wy) / 酷狗(kg) / 酷我(kw) / 咪咕(mg) / 汽水(qs) / B站兜底
 *  特性: 每个平台一个线路池, 顺序尝试失败自动切换
 *  2026-10-11 检修: 长青海棠/星海/酷我车机/QQ vkeys 已死, 全部换新
 *  洛雪源槽位: kw/kg/tx/wy/mg 内置, qs 需客户端支持(不支持自动忽略)
 * ========================================================= */

const { EVENT_NAMES, request, on, send, utils } = globalThis.lx
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
const UA_MOBILE = 'LX-Music-Mobile'

/* ---------- 基础工具 ---------- */
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
const extractUrlFromBody = (body) => {
  if (!body) return ''
  if (typeof body === 'string') {
    const m = body.match(/https?:\/\/[^\s"'<>]+/)
    return m ? m[0].replace(/\\u0026/g, '&') : ''
  }
  return pickUrl(body, [['url'], ['data', 'url'], ['data', 0, 'url'], ['link'], ['data', 'link']])
}

/* 线路池: 顺序尝试, 全部失败抛错 */
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

/* =========================================================
 *  一、网易云音乐 (wy) 线路池
 * ========================================================= */
const wyEapiKey = 'e82ckenh8dichen8'
const wyAesEcb = (text, key) => {
  const pad = 16 - (text.length % 16)
  const padded = text + String.fromCharCode(pad).repeat(pad)
  const enc = utils.crypto.aesEncrypt(padded, 'aes-128-ecb', key, '')
  let hex = ''
  for (let i = 0; i < enc.length; i++) hex += (enc[i] < 16 ? '0' : '') + enc[i].toString(16)
  return hex.toUpperCase()
}
const wyEapi = (urlPath, object) => {
  const text = JSON.stringify(object)
  const digest = md5('nobody' + urlPath + 'use' + text + 'md5forencrypt')
  const data = urlPath + '-36cd479b6b5-' + text + '-36cd479b6b5-' + digest
  return wyAesEcb(data, wyEapiKey)
}
const wyQualityMap = { '128k': 'standard', '320k': 'exhigh', flac: 'lossless', flac24bit: 'lossless' }

const wyLines = [
  // L1 eapi官方 (2026-10-11实测免费歌直链可用)
  async ({ id, quality }) => {
    const apiPath = '/api/song/enhance/player/url/v1'
    const params = wyEapi(apiPath, { ids: [Number(id)], level: wyQualityMap[quality] || 'exhigh', encodeType: 'mp3' })
    const url = 'https://interface3.music.163.com/eapi' + apiPath + '?params=' + encodeURIComponent(params)
    const resp = await httpPost(url, '', {
      headers: { 'User-Agent': UA, Referer: 'https://music.163.com', Cookie: 'os=pc; appver=8.9.70', 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    const d = resp.body
    const u = d && d.data && d.data[0] && d.data[0].url
    if (u && u !== '') return String(u).replace(/\\u0026/g, '&')
    throw new Error('eapi无链接(可能付费)')
  },
  // L2 bugpk (128k稳, 2026-10-11实测; 付费歌返回163外链死链须过滤)
  async ({ id, quality }) => {
    const url = 'https://api.bugpk.com/api/163_music?type=url&id=' + id + '&br=' + (quality === '128k' ? '128' : '320')
    const resp = await httpGet(url, { headers: { 'User-Agent': UA } })
    const u = pickUrl(resp.body, [['data', 'url'], ['data', 0, 'url'], ['url']])
    // 过滤 163 外链死链 (music.163.com/song/media/outer 302到404)
    if (u && !/music\.163\.com\/song\/media\/outer/.test(u)) return u
    throw new Error('bugpk无链接或付费死链')
  },
  // L3 溯音163 oiapi (免费歌直链, 2026-10-11实测)
  async ({ id }) => {
    const url = 'https://oiapi.net/api/Music_163?id=' + id
    const resp = await httpGet(url, { headers: { 'User-Agent': UA } })
    const d = resp.body
    const arr = d && d.data
    const u = arr && (Array.isArray(arr) ? arr[0] : arr) && (Array.isArray(arr) ? arr[0].url : arr.url)
    if (u && /^https?:/.test(u)) return u
    throw new Error('oiapi无链接(可能付费)')
  },
]

/* =========================================================
 *  二、QQ音乐 (tx) 线路池
 * ========================================================= */
const txFileConfig = {
  '128k': { s: 'M500', e: '.mp3' },
  '320k': { s: 'M800', e: '.mp3' },
  flac: { s: 'F000', e: '.flac' },
  flac24bit: { s: 'F000', e: '.flac' },
}
const txLines = [
  // L1 官方 vkey (2026-10-11实测部分歌能出purl, 游客受限尽力)
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

/* =========================================================
 *  三、酷狗音乐 (kg) 线路池 (官方接口已SSA风控, 走B站兜底)
 * ========================================================= */
const kgLines = [
  // L1 官方getdata (2026-10-11实测SSA风控30020, 保留尽力)
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

/* =========================================================
 *  四、酷我音乐 (kw) 线路池
 * ========================================================= */
const kwLines = [
  // L1 anti.s官方 (2026-10-11实测mp3直链稳定!)
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
  // L2 溯音酷我 (歌名搜索出直链, 2026-10-11实测 128k/320k 可用!)
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

/* =========================================================
 *  五、咪咕音乐 (mg) 线路池 (官方已挂, 走B站兜底)
 * ========================================================= */
const mgLines = [
  // L1 官方 (2026-10-11实测301/空, 保留尽力)
  async ({ id }) => {
    const url = 'https://music.migu.cn/v3/api/music/audioPlayer/getPlayInfo?copyrightId=' + id
    const resp = await httpGet(url, { headers: { 'User-Agent': UA, Referer: 'https://music.migu.cn/' } })
    const u = pickUrl(resp.body, [['data', 'url'], ['url']])
    if (u) return u
    throw new Error('咪咕官方无链接')
  },
]

/* =========================================================
 *  六、汽水音乐 (qs) 线路池 (官方风控, 走B站兜底)
 * ========================================================= */
const qsLines = [
  // L1 汽水H5 (2026-10-11实测风控, 保留尽力)
  async ({ id }) => {
    const url = 'https://api.qishui.com/luna/h5/track?track_id=' + id
    const resp = await httpGet(url, { headers: { 'User-Agent': UA } })
    const d = resp.body
    const songStr = d && d.track_player && d.track_player.video_model
    if (!songStr) throw new Error('汽水无数据')
    try {
      const parsed = JSON.parse(songStr)
      const song = parsed.video_list && parsed.video_list[0]
      if (song && song.main_url) return song.main_url
    } catch (e) { /* 继续 */ }
    throw new Error('汽水无链接')
  },
]

/* =========================================================
 *  七、B站 (各源兜底, 2026-10-11实测可用)
 * ========================================================= */
const biliSearch = async (keyword) => {
  const url = 'https://api.bilibili.com/x/web-interface/wbi/search/type?search_type=video&keyword=' + encodeURIComponent(keyword)
  const resp = await httpGet(url, { headers: { 'User-Agent': UA, Referer: 'https://www.bilibili.com' } })
  const list = resp.body && resp.body.data && resp.body.data.result
  if (!Array.isArray(list) || !list.length) throw new Error('B站无结果')
  const target = list.find(v => /音乐|纯音乐|翻唱|cover|MV/.test(v.title || '')) || list[0]
  return { bvid: target.bvid }
}
const biliCid = async (bvid) => {
  const url = 'https://api.bilibili.com/x/web-interface/view?bvid=' + bvid
  const resp = await httpGet(url, { headers: { 'User-Agent': UA, Referer: 'https://www.bilibili.com' } })
  const pages = resp.body && resp.body.data && resp.body.data.pages
  if (Array.isArray(pages) && pages.length) return pages[0].cid
  throw new Error('B站获取cid失败')
}
const biliPlay = async (bvid, cid) => {
  const url = 'https://api.bilibili.com/x/player/playurl?bvid=' + bvid + '&cid=' + cid + '&qn=16&fnver=0&fnval=4048&fourk=1'
  const resp = await httpGet(url, { headers: { 'User-Agent': UA, Referer: 'https://www.bilibili.com', Origin: 'https://www.bilibili.com' } })
  const dash = resp.body && resp.body.data && resp.body.data.dash
  if (dash && Array.isArray(dash.audio) && dash.audio.length) {
    const audio = dash.audio.sort((a, b) => (b.bandwidth || 0) - (a.bandwidth || 0))[0]
    return audio.baseUrl || audio.base_url
  }
  throw new Error('B站dash无音频流')
}
const biliLine = async ({ keyword }) => {
  if (!keyword) throw new Error('B站无关键词')
  const { bvid } = await biliSearch(keyword)
  const cid = await biliCid(bvid)
  return biliPlay(bvid, cid)
}

/* =========================================================
 *  六、兜底: 酷我搜索 → anti.s 直链 (2026-10-11实测双官方接口稳定)
 *  任何平台失败时用歌名+歌手去酷我搜 rid, 再走 anti.s 拿直链
 * ========================================================= */
const kwSearchLine = async ({ keyword, musicInfo }) => {
  const kwName = keyword || ((musicInfo && musicInfo.name) || '')
  if (!kwName) throw new Error('无关键词')
  // 步骤1: 酷我搜索拿rid (官方接口, 稳定)
  const searchUrl = 'http://search.kuwo.cn/r.s?all=' + encodeURIComponent(kwName) + '&ft=music&itemset=web_2013&client=kt&pn=0&rn=10&rformat=json&encoding=utf8'
  const resp = await httpGet(searchUrl, { headers: { 'User-Agent': UA } })
  let rid = ''
  const raw = typeof resp.body === 'string' ? resp.body : JSON.stringify(resp.body)
  // 单引号JSON, 用正则逐个提取并过滤伴奏/DJ/翻唱
  const m = raw.match(/DC_TARGETID['"]?\s*[:：]\s*['"]?(\d+)/g)
  if (m && m.length) {
    const ids = m.map(x => (x.match(/\d+/) || [''])[0])
    const names = raw.match(/SONGNAME['"]?\s*[:：]\s*['"]([^'"]*)/g) || []
    for (let i = 0; i < ids.length; i++) {
      const nm = names[i] ? names[i].replace(/SONGNAME['"]?\s*[:：]\s*['"]/i, '').toLowerCase() : ''
      // 过滤伴奏/DJ/翻唱/纯音乐
      if (nm && /伴奏|dj|翻唱|cover|remix|纯音乐|现场|live|ktv/.test(nm)) continue
      rid = ids[i]
      break
    }
    if (!rid && ids.length) rid = ids[0]
  }
  if (!rid) throw new Error('酷我搜索无结果')
  // 步骤2: anti.s 拿直链 (实测稳定)
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

/* =========================================================
 *  事件注册与初始化
 * ========================================================= */
const SOURCES = {
  wy: { name: '网易云', type: 'music', actions: ['musicUrl'], qualitys: ['128k', '320k', 'flac', 'flac24bit'] },
  tx: { name: 'QQ音乐', type: 'music', actions: ['musicUrl'], qualitys: ['128k', '320k', 'flac', 'flac24bit'] },
  kg: { name: '酷狗音乐', type: 'music', actions: ['musicUrl'], qualitys: ['128k', '320k', 'flac', 'flac24bit'] },
  kw: { name: '酷我音乐', type: 'music', actions: ['musicUrl'], qualitys: ['128k', '320k', 'flac', 'flac24bit'] },
  mg: { name: '咪咕音乐', type: 'music', actions: ['musicUrl'], qualitys: ['128k', '320k', 'flac'] },
  qs: { name: '汽水音乐', type: 'music', actions: ['musicUrl'], qualitys: ['128k'] },
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
      lines = [...wyLines, () => kwSearchLine({ keyword: biliKeyword, musicInfo }), () => biliLine({ keyword: biliKeyword })]
      break
    case 'tx':
      lines = [...txLines, () => kwSearchLine({ keyword: biliKeyword, musicInfo }), () => biliLine({ keyword: biliKeyword })]
      break
    case 'kg':
      lines = [...kgLines, () => kwSearchLine({ keyword: biliKeyword, musicInfo }), () => biliLine({ keyword: biliKeyword })]
      break
    case 'kw':
      lines = [...kwLines, () => kwSearchLine({ keyword: biliKeyword, musicInfo }), () => biliLine({ keyword: biliKeyword })]
      break
    case 'mg':
      lines = [...mgLines, () => kwSearchLine({ keyword: biliKeyword, musicInfo }), () => biliLine({ keyword: biliKeyword })]
      break
    case 'qs':
      lines = [...qsLines, () => kwSearchLine({ keyword: biliKeyword, musicInfo }), () => biliLine({ keyword: biliKeyword })]
      break
    default:
      return Promise.reject(new Error('unsupported source: ' + source))
  }

  return tryLines(lines, ctx).catch(err => {
    console.log('[' + source + ']', err.message)
    return Promise.reject(err)
  })
})

send(EVENT_NAMES.inited, {
  status: true,
  openDevTools: false,
  sources: SOURCES,
})
