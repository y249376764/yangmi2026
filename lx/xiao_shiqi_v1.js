/**
 * @name 小十七聚合 · 17号优质音源 v1.0
 * @description 2026-10-17 优质音源提取聚合: 网易/QQ/酷我/咪咕 多线路自动切换 (实测可用端点)
 * @version 1.0.0
 * @author 星火
 * @homepage https://navpage-2026.surge.sh/
 */

/* =========================================================
 *  洛雪音乐(LX Music)自定义音源 · 小十七聚合 v1.0
 *  数据源: 77f77.48364836.xyz/lx/ V261017/优质/ 6个音源实测提取
 *  平台: 网易(wy) / QQ(tx) / 酷我(kw) / 咪咕(mg) / 酷狗(kg)
 *  特性: 每平台线路池顺序尝试, 失败自动切换
 *  实测(2026-10-20): 
 *    HYWmusic 103.79.184.97 聚合接口 wy/tx/kw 通
 *    GDStudio 网易直链 通 | c.wwwweb.top 网易 通
 *    a.aa.cab QQ 通 | oiapi 咪咕 通
 *    酷狗 kg 全源暂挂(长青海棠/酷狗安妮/ChKSz 均失败, 保留HYW尝试)
 *  洛雪源槽位: kw/kg/tx/wy/mg 内置
 * ========================================================= */

const { EVENT_NAMES, request, on, send, utils } = globalThis.lx
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'

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

const parseBody = (resp) => {
  let body = resp && resp.body
  if (typeof body === 'string') {
    try { body = JSON.parse(body) } catch (e) { return body }
  }
  return body
}
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
const extractUrl = (body) => {
  if (!body) return ''
  if (typeof body === 'string') {
    const m = body.match(/https?:\/\/[^\s"'<>]+/)
    return m ? m[0].replace(/\\u0026/g, '&') : ''
  }
  return pickUrl(body, [['url'], ['data', 'url'], ['data', 0, 'url'], ['data', 'music'], ['urls', 0]])
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
const wyQualityMap = { '128k': '128k', '320k': '320k', flac: 'flac', flac24bit: 'flac24bit' }

const wyLines = [
  // L1 星海GDAPI官方后端 (2026-10-20实测: music-api.gdstudio.xyz 网易 128/320 直链)
  async ({ id, quality }) => {
    const brMap = { '128k': '128', '320k': '320', flac: '740', flac24bit: '740' }
    const br = brMap[quality] || '320'
    const resp = await httpGet('https://music-api.gdstudio.xyz/api.php?types=url&source=netease&id=' + id + '&br=' + br, { headers: { 'User-Agent': UA } })
    const body = parseBody(resp)
    const url = pickUrl(body, [['url']])
    if (!url) throw new Error('GDStudio无链接')
    return url
  },
  // L2 c.wwwweb.top (2026-10-20实测: wy 128/320 直链)
  async ({ id, quality }) => {
    const level = wyQualityMap[quality] || '128k'
    const resp = await httpPost('https://c.wwwweb.top/music/url', { source: 'wy', musicId: String(id), quality: level }, { headers: { 'Content-Type': 'application/json', 'User-Agent': UA } })
    const body = parseBody(resp)
    if (body && body.code === 200 && body.url) return body.url
    throw new Error('c.wwwweb失败')
  },
  // L3 HYWmusic 聚合接口 (2026-10-20实测: wy 128/320 直链)
  async ({ id, quality }) => {
    const q = wyQualityMap[quality] || '128k'
    const resp = await httpGet('http://103.79.184.97/api/music/url?platform=wy&songId=' + encodeURIComponent(String(id)) + '&quality=' + q + '&key=6C1F-53W0-GRKI-EVFG', { headers: { 'User-Agent': UA, 'X-Card-Key': '6C1F-53W0-GRKI-EVFG' } })
    const body = parseBody(resp)
    if (body && body.code === 200 && body.url) return body.url
    throw new Error('HYW-wy失败')
  },
]

/* =========================================================
 *  二、QQ音乐 (tx) 线路池
 * ========================================================= */
const txQualityMap = { '128k': '128k', '320k': '320k', flac: 'flac', flac24bit: 'flac24bit' }

const txLines = [
  // L1 HYWmusic 聚合接口 (实测: tx 直链 m4a/mp3)
  async ({ id, quality }) => {
    const q = txQualityMap[quality] || '128k'
    const resp = await httpGet('http://103.79.184.97/api/music/url?platform=tx&songId=' + encodeURIComponent(String(id)) + '&quality=' + q + '&key=6C1F-53W0-GRKI-EVFG', { headers: { 'User-Agent': UA, 'X-Card-Key': '6C1F-53W0-GRKI-EVFG' } })
    const body = parseBody(resp)
    if (body && body.code === 200 && body.url) return body.url
    throw new Error('HYW-tx失败')
  },
  // L2 a.aa.cab (实测: QQ 直链 mp3)
  async ({ id, quality }) => {
    const typeMap = { '128k': '0', '320k': '1', flac: '4', flac24bit: '4' }
    const type = typeMap[quality] || '0'
    const resp = await httpGet('https://a.aa.cab/qq.music?msg=' + encodeURIComponent(String(id)) + '&n=1&type=' + type, { headers: { 'User-Agent': UA } })
    const body = parseBody(resp)
    const url = pickUrl(body, [['data', 'music'], ['data', 'url'], ['url']])
    if (!url) throw new Error('aa.cab无链接')
    return url
  },
]

/* =========================================================
 *  三、酷我音乐 (kw) 线路池
 * ========================================================= */
const kwQualityMap = { '128k': '128k', '320k': '320k', flac: 'flac', flac24bit: 'flac24bit' }

const kwLines = [
  // L1 HYWmusic 聚合接口 (实测: kw 直链 mp3)
  async ({ id, quality }) => {
    const q = kwQualityMap[quality] || '128k'
    const resp = await httpGet('http://103.79.184.97/api/music/url?platform=kw&songId=' + encodeURIComponent(String(id)) + '&quality=' + q + '&key=6C1F-53W0-GRKI-EVFG', { headers: { 'User-Agent': UA, 'X-Card-Key': '6C1F-53W0-GRKI-EVFG' } })
    const body = parseBody(resp)
    if (body && body.code === 200 && body.url) return body.url
    throw new Error('HYW-kw失败')
  },
]

/* =========================================================
 *  四、咪咕音乐 (mg) 线路池
 * ========================================================= */
const mgQualityMap = { '128k': '128k', '320k': '320k' }

const mgLines = [
  // L1 HYWmusic 聚合接口
  async ({ id, quality }) => {
    const q = mgQualityMap[quality] || '128k'
    const resp = await httpGet('http://103.79.184.97/api/music/url?platform=mg&songId=' + encodeURIComponent(String(id)) + '&quality=' + q + '&key=6C1F-53W0-GRKI-EVFG', { headers: { 'User-Agent': UA, 'X-Card-Key': '6C1F-53W0-GRKI-EVFG' } })
    const body = parseBody(resp)
    if (body && body.code === 200 && body.url) return body.url
    throw new Error('HYW-mg失败')
  },
]

/* =========================================================
 *  五、酷狗音乐 (kg) 线路池 (2026-10-20 全源暂挂, 保留HYW尝试)
 * ========================================================= */
const kgQualityMap = { '128k': '128k', '320k': '320k', flac: 'flac' }

const kgLines = [
  async ({ id, quality }) => {
    const q = kgQualityMap[quality] || '128k'
    const resp = await httpGet('http://103.79.184.97/api/music/url?platform=kg&songId=' + encodeURIComponent(String(id)) + '&quality=' + q + '&key=6C1F-53W0-GRKI-EVFG', { headers: { 'User-Agent': UA, 'X-Card-Key': '6C1F-53W0-GRKI-EVFG' } })
    const body = parseBody(resp)
    if (body && body.code === 200 && body.url) return body.url
    throw new Error('HYW-kg失败')
  },
]

/* =========================================================
 *  统一入口
 * ========================================================= */
const linePools = { wy: wyLines, tx: txLines, kw: kwLines, mg: mgLines, kg: kgLines }

on(EVENT_NAMES.request, ({ action, source, info }) => {
  if (action !== 'musicUrl') return Promise.reject('not support: ' + action)
  const pool = linePools[source]
  if (!pool) return Promise.reject('不支持平台: ' + source)
  const mi = info.musicInfo || {}
  const id = mi.songmid || mi.songId || mi.id || mi.hash || mi.rid || mi.musicId || mi.copyrightId || ''
  if (!id) return Promise.reject('缺少歌曲ID')
  return tryLines(pool, { id: String(id), quality: info.type || '128k' })
})

/* =========================================================
 *  sources 声明
 * ========================================================= */
const qs = {
  wy: ['128k', '320k', 'flac', 'flac24bit'],
  tx: ['128k', '320k', 'flac', 'flac24bit'],
  kw: ['128k', '320k', 'flac', 'flac24bit'],
  mg: ['128k', '320k'],
  kg: ['128k', '320k', 'flac'],
}
const musicSources = {}
Object.keys(qs).forEach((k) => {
  musicSources[k] = { name: k, type: 'music', actions: ['musicUrl'], qualitys: qs[k] }
})

send(EVENT_NAMES.inited, { status: true, openDevTools: false, sources: musicSources })
