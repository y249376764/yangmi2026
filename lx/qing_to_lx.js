/*!
 * @name 青听转洛雪[海棠直链]
 * @description 青听音乐内置源转换: 网易云+酷我 海棠直链播放, 搜索由洛雪原生完成
 * @version 1.0.0
 * @author hermes
 */
const { EVENT_NAMES, request, on, send } = globalThis.lx;

// 海棠播放接口(青听同源, 2026-10-01实测: 网易wy.php/酷我music/kw.php 均200可播)
const HOST = "https://music.haitangw.cc";
const PLAY_PATHS = {
  wy: "/wy/wy.php",       // 网易: id=歌曲数字ID
  kw: "/music/kw.php",    // 酷我: id=rid(DC_TARGETID)
};

// 音质映射: 洛雪音质 -> 海棠 level
const QUALITY_MAP = {
  wy: { standard: "standard", exhigh: "exhigh", lossless: "lossless", hires: "hires" },
  kw: { standard: "standard", exhigh: "exhigh", lossless: "lossless" },
};

// 平台配置
const sourceConfig = {
  wy: { name: "网易云[海棠]", type: "music", actions: ["musicUrl"], qualitys: ["standard", "exhigh", "lossless", "hires"] },
  kw: { name: "酷我[海棠]", type: "music", actions: ["musicUrl"], qualitys: ["standard", "exhigh", "lossless"] },
};

function httpRequest(url, options = {}) {
  return new Promise((resolve, reject) => {
    request(url, Object.assign({ method: "GET" }, options), (err, resp) => {
      if (err) return reject(err);
      resolve(resp);
    });
  });
}

// 从 songInfo 取平台ID
function getPlatformId(platform, musicInfo) {
  // 洛雪 songInfo 会带各平台专属字段
  if (platform === "wy") {
    return musicInfo.songId || musicInfo.songmid || musicInfo.id || null;
  }
  if (platform === "kw") {
    return musicInfo.rid || musicInfo.musicId || musicInfo.songmid || musicInfo.id || null;
  }
  return null;
}

// ---- 平台搜索(歌名+歌手 -> 歌曲ID) ----
function searchKeywords(musicInfo) {
  const name = (musicInfo.name || "").trim();
  const singer = (musicInfo.singer || musicInfo.artist || "").trim();
  const list = [];
  if (name && singer) list.push(`${name} ${singer}`);
  if (name) list.push(name);
  if (name && singer) list.push(`${name} ${singer.split(/[、,，\/]/)[0]}`);
  return list;
}

// 网易云搜索: 官方公开接口
async function searchWy(keyword) {
  const url = `https://music.163.com/api/search/get/web?s=${encodeURIComponent(keyword)}&type=1&limit=5&offset=0`;
  const resp = await httpRequest(url, {
    headers: { "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15", Referer: "https://music.163.com/" },
  });
  const body = typeof resp.body === "string" ? JSON.parse(resp.body)
    : Buffer.isBuffer(resp.body) ? JSON.parse(resp.body.toString("utf-8"))
    : resp.body;
  const songs = (body && body.result && body.result.songs) || [];
  return songs[0] ? songs[0].id : null;
}

// 酷我搜索: 官方公开接口
async function searchKw(keyword) {
  const url = `https://search.kuwo.cn/r.s?all=${encodeURIComponent(keyword)}&ft=music&itemset=web_2016&client=kt&pn=0&rn=5&rformat=json&encoding=utf8`;
  const resp = await httpRequest(url, {
    headers: { "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15", Referer: "http://www.kuwo.cn/" },
  });
  // 酷我返回python dict风格(单引号)或json
  const text = String(resp.body || "");
  let list = [];
  try {
    const json = JSON.parse(text);
    list = (json && json.abslist) || [];
  } catch (e) {
    try {
      // 单引号dict -> 双引号json
      const fixed = text.replace(/'/g, '"').replace(/None/g, "null").replace(/True/g, "true").replace(/False/g, "false");
      const json2 = JSON.parse(fixed);
      list = (json2 && json2.abslist) || [];
    } catch (e2) {
      list = [];
    }
  }
  return list[0] ? list[0].DC_TARGETID : null;
}

async function searchPlatformId(platform, musicInfo) {
  const keywords = searchKeywords(musicInfo);
  for (const kw of keywords) {
    try {
      const id = platform === "wy" ? await searchWy(kw) : await searchKw(kw);
      if (id) return id;
    } catch (e) { /* continue */ }
  }
  return null;
}

function pickQuality(quality, platform) {
  const q = String(quality || "standard").toLowerCase();
  const map = QUALITY_MAP[platform] || {};
  return map[q] || map.standard || "standard";
}

// 获取播放URL: 优先用songInfo自带ID, 否则搜索兜底, 再拼海棠直链
async function getMusicUrl(platform, musicInfo, quality) {
  // 1. songInfo 自带平台ID
  let id = getPlatformId(platform, musicInfo);
  // 2. 搜索兜底
  if (!id) {
    id = await searchPlatformId(platform, musicInfo);
  }
  if (!id) throw new Error("找不到歌曲ID: " + platform);
  const path = PLAY_PATHS[platform];
  if (!path) throw new Error("不支持平台: " + platform);
  const level = pickQuality(quality, platform);
  const url = `${HOST}${path}?type=mp3&id=${encodeURIComponent(String(id))}&level=${encodeURIComponent(level)}`;

  // 验证可播: 发一次GET, 若4xx则降级standard重试
  const resp = await httpRequest(url, {
    headers: { "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15" },
  });
  if (resp.statusCode >= 400) {
    return `${HOST}${path}?type=mp3&id=${encodeURIComponent(String(id))}&level=standard`;
  }
  return url;
}

// 事件处理
on(EVENT_NAMES.request, ({ action, source, info }) => {
  if (action !== "musicUrl") return Promise.reject(new Error("action not support: " + action));
  if (!info || !info.musicInfo) return Promise.reject(new Error("缺少musicInfo"));
  return getMusicUrl(source, info.musicInfo, info.type)
    .then(url => Promise.resolve(url))
    .catch(err => Promise.reject(err));
});

send(EVENT_NAMES.inited, {
  openDevTools: false,
  sources: sourceConfig,
});
