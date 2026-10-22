/**
 * 小听 · 聚合音源
 * 网易 / QQ / 酷狗 / 酷我
 * 更多资源请到 https://navpage-2026.surge.sh/
 * @version 1.0.0
 */
const { EVENT_NAMES, request, on, utils, send } = globalThis.lx
const { buffer, crypto } = utils

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
const H = { 'User-Agent': UA }

function httpGet(url, opts) {
  return new Promise((resolve, reject) => {
    const o = Object.assign({ method: 'get', headers: Object.assign({}, H), timeout: 12000 }, opts || {})
    if (o.headers && opts && opts.headers) o.headers = Object.assign({}, H, opts.headers)
    request(url, o, (err, resp) => {
      if (err) return reject(err)
      if (resp.statusCode >= 300 && resp.statusCode < 400 && resp.headers.location) {
        return resolve(httpGet(new URL(resp.headers.location, url).href, opts))
      }
      resolve({ body: resp.body, headers: resp.headers, statusCode: resp.statusCode })
    })
  })
}

function text(url, opts) {
  return httpGet(url, opts).then(r => typeof r.body === 'string' ? r.body : buffer.bufToString(r.body))
}

function json(url, opts) {
  return text(url, opts).then(s => JSON.parse(s))
}

function probe(url) {
  if (!url || /^https?:\/\//.test(url) === false) return Promise.resolve(0)
  return httpGet(url, { headers: Object.assign({}, H, { Range: 'bytes=0-1' }) })
    .then(r => {
      const cr = r.headers['content-range'] || ''
      const m = /\/(\d+)\s*$/.exec(cr)
      return m ? Number(m[1]) : 0
    })
    .catch(() => 0)
}

const PLATFORMS = {
  wy: { name: '网易音乐', actions: ['musicUrl'], qualitys: ['128k', '320k'] },
  tx: { name: 'QQ音乐', actions: ['musicUrl'], qualitys: ['128k', '320k'] },
  kg: { name: '酷狗音乐', actions: ['musicUrl'], qualitys: ['128k', '320k'] },
  kw: { name: '酷我音乐', actions: ['musicUrl'], qualitys: ['128k', '320k'] },
}

async function crossFind(info) {
  const name = ((info && info.name) || '').trim()
  const singer = ((info && info.singer) || '').trim()
  const kw = (name + ' ' + singer).trim()
  if (!kw) return ''
  try {
    const d = await json('https://oiapi.net/api/Kuwo?msg=' + encodeURIComponent(kw))
    const pure = [], other = []
    for (const it of ((d && d.data) || []).slice(0, 10)) {
      const nm = it.song || ''
      if (BAD.test(nm)) other.push(it)
      else if (nm.trim() === name) pure.push(it)
      else other.push(it)
    }
    for (const it of pure.concat(other)) {
      try {
        const u = (await text('http://antiserver.kuwo.cn/anti.s?type=convert_url&format=mp3&response=url&rid=' + it.rid)).trim()
        if (/^https?:\/\//.test(u) && (await probe(u)) > 800000) return u
      } catch (e) {}
    }
  } catch (e) {}
  try {
    const d = await json('https://a.aa.cab/qq.music?n=1&msg=' + encodeURIComponent(kw))
    const u = d && d.data && d.data.music ? d.data.music : ''
    if (u) return u
  } catch (e) {}
  return ''
}

const BAD = /live|伴奏|remix|dj|3d|环绕|翻唱|纯音乐|片段|chunk|cover|instrumental/i

async function netease(info, id) {
  const sid = id || (info && (info.songmid || info.songId || info.id))
  if (!sid) throw new Error('网易缺少歌曲ID')
  let url = ''
  try {
    const d = await json('https://music-api.gdstudio.xyz/api.php?types=url&source=netease&id=' + sid + '&br=320')
    url = d && d.url ? d.url : ''
  } catch (e) {}
  if (!url) {
    try {
      const d = await json('https://oiapi.net/api/Music_163?id=' + sid)
      const arr = d && d.data
      if (Array.isArray(arr) && arr.length && arr[0].url) url = arr[0].url
      else if (arr && arr.url) url = arr.url
    } catch (e) {}
  }
  if (!url) {
    try {
      const d = await json('https://oiapi.net/api/Music_163?msg=' + encodeURIComponent((info && info.name) || ''))
      const arr = d && d.data
      if (Array.isArray(arr) && arr.length && arr[0].url) url = arr[0].url
    } catch (e) {}
  }
  if (!url) {
    url = await crossFind(info)
  }
  if (!url) throw new Error('网易未取到播放地址')
  return url
}

async function tencent(info, id) {
  const name = ((info && info.name) || '').trim()
  const singer = ((info && info.singer) || '').trim()
  const kw = (name + ' ' + singer).trim()
  if (!kw) throw new Error('QQ缺少歌名')
  const d = await json('https://a.aa.cab/qq.music?n=1&msg=' + encodeURIComponent(kw))
  const url = d && d.data && d.data.music ? d.data.music : ''
  if (!url) throw new Error('QQ未取到播放地址')
  return url
}

const KG_KEY = '1ffdf5733f5d538760e63d7e46ba17438d9f7b9dfc18c51be1109386fd74c3a1'

async function kugou(info, id) {
  const name = ((info && info.name) || '').trim()
  const singer = ((info && info.singer) || '').trim()
  const kw = (name + ' ' + singer).trim()

  if (id) {
    try {
      const d = await json('https://cyapi.top/API/kugou.php?apikey=' + KG_KEY + '&type=json&id=' + id)
      const u = d && d.data && d.data.url ? d.data.url : ''
      if (/^https?:\/\//.test(u)) return u
    } catch (e) {}
  }

  if (!kw) throw new Error('酷狗缺少歌名')

  try {
    const d = await json('https://cyapi.top/API/kugou.php?apikey=' + KG_KEY + '&type=json&msg=' + encodeURIComponent(kw))
    const list = (d && d.list) || []
    if (list.length) {
      const d2 = await json('https://cyapi.top/API/kugou.php?apikey=' + KG_KEY + '&type=json&id=' + list[0].id)
      const u = d2 && d2.data && d2.data.url ? d2.data.url : ''
      if (/^https?:\/\//.test(u)) return u
    }
  } catch (e) {}

  try {
    const d = await json('https://api.xcvts.cn/api/music/kugou?msg=' + encodeURIComponent(kw) + '&n=1')
    const u = d && d.music_url ? d.music_url : ''
    if (/^https?:\/\//.test(u)) return u
  } catch (e) {}

  throw new Error('酷狗未取到播放地址')
}

async function kuwo(info, id) {
  const name = ((info && info.name) || '').trim()
  const singer = ((info && info.singer) || '').trim()
  const rid = id || (info && (info.songmid || info.rid))
  const anti = r => 'http://antiserver.kuwo.cn/anti.s?type=convert_url&format=mp3&response=url&rid=' + r

  if (rid) {
    try {
      const u = (await text(anti('MUSIC_' + rid))).trim()
      if (/^https?:\/\//.test(u) && (await probe(u)) > 800000) return u
    } catch (e) {}
  }

  const kw = (name + ' ' + singer).trim()
  if (!kw) throw new Error('酷我缺少歌名')
  const d = await json('https://oiapi.net/api/Kuwo?msg=' + encodeURIComponent(kw))
  const list = (d && d.data) || []
  const pure = [], other = []
  for (const it of list.slice(0, 10)) {
    const nm = (it.song || '')
    if (BAD.test(nm)) other.push(it)
    else if (nm.trim() === name) pure.push(it)
    else other.push(it)
  }
  for (const it of pure.concat(other)) {
    try {
      const u = (await text(anti(it.rid))).trim()
      if (/^https?:\/\//.test(u) && (await probe(u)) > 800000) return u
    } catch (e) {}
  }
  throw new Error('酷我未取到完整播放地址')
}

on(EVENT_NAMES.request, ({ source, action, info }) => {
  if (action !== 'musicUrl') return Promise.reject(new Error('不支持的操作'))
  const id = (info && (info.songmid || info.hash || info.id)) || ''
  const handlers = { wy: netease, tx: tencent, kg: kugou, kw: kuwo }
  const fn = handlers[source]
  if (!fn) return Promise.reject(new Error('未知平台: ' + source))
  return fn(info, id).then(url => Promise.resolve(url))
})

globalThis.lx.send(EVENT_NAMES.inited, {
  status: true,
  openDevTools: false,
  sources: PLATFORMS,
})
