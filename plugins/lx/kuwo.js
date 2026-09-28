// 标准洛雪插件样例 - 用于测试转换器
export default {
    platform: "酷我音乐",
    version: "1.0.0",
    srcUrl: "https://example.com/kuwo.js",
    description: "测试用酷我插件",
    cacheControl: "no-cache",
    primaryKey: "$guid",
    supportedSearchType: ["songs", "albums", "playLists", "mvs"],
    defaultSearchType: "songs",
    request: {
      headers: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.kuwo.cn/",
        "csrf": "abc123"
      }
    },
    search: {
      songs: async (page, { keyword }) => {
        const url = `https://search.kuwo.cn/r.s?client=kt&all=${keyword}&pn=${page - 1}&rn=30&ver=kwplayer_ar_12.2.0.0&ft=music&vipver=1&encoding=utf8&rformat=json&mobi=1`;
        const res = await fetch(url);
        const data = await res.json();
        return data.abslist.map(item => ({
          id: item.MUSICRID.replace('MUSIC_', ''),
          title: item.SONGNAME,
          artist: item.ARTIST,
          album: item.ALBUM,
          artwork: `https://img1.kuwo.cn/star/albumcover/300/${item.ALBUMID}.jpg`
        }));
      }
    },
    getMediaSource: async (song, quality) => {
      const url = `https://antiserver.kuwo.cn/anti.s?type=convert_url&rid=${song.id}&format=mp3&response=url`;
      const res = await fetch(url);
      const text = await res.text();
      return {
        url: text.trim(),
        headers: { "User-Agent": "Mozilla/5.0" }
      };
    }
};
