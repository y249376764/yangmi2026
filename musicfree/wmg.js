// 咪咕音乐（自建 miguMusic-api-enhanced 服务）
// 数据源:温部署，合作伙伴；@云汀喵
// 声明；此项目温部署。没本人的允许私自修改编译，还有ddos服务器的按网络安全法处理。
//插件demo：由官方music free skill开发
//原作者；猫头猫
const axios = require('axios');

const BASE_URL = 'http://101.200.224.166/musicfree/index.php';
const QUALITY_MAP = { low: 'LQ', standard: 'PQ', high: 'HQ', super: 'SQ' };

const API_KEY = '60b0413e3e00aecbd56257f60e803e02';

async function request(action, params) {
    const res = await axios.get(BASE_URL, {
        params: Object.assign({ key: API_KEY, action }, params),
        timeout: 9000,
    });
    const body = res.data;
    if (body === null || typeof body !== 'object') {
        throw new Error('接口返回异常');
    }
    if (body.code !== undefined && body.code !== 0 && body.code !== 200 && body.success === false) {
        throw new Error(body.message || body.msg || '接口返回错误: ' + body.code);
    }
    if (body.error) throw new Error(body.error);
    return body;
}

function toMusicItem(x) {
    if (!x) return null;
    const item = {
        id: String(x.id),
        title: x.title,
        artist: x.artist || '未知歌手',
    };
    if (x.album) item.album = x.album;
    if (x.artwork) item.artwork = x.artwork;
    if (x.duration) item.duration = Number(x.duration);
    if (x.lrc) item.lrc = x.lrc;
    if (x.copyrightId) item.copyrightId = x.copyrightId;
    if (x.albumId) item.albumId = x.albumId;
    if (x.resourceType) item.resourceType = x.resourceType;
    return item;
}

function toSheetItem(x) {
    if (!x) return null;
    const item = {
        id: String(x.id),
        title: x.title,
    };
    if (x.artwork) item.artwork = x.artwork;
    if (x.artist) item.artist = x.artist;
    if (x.description) item.description = x.description;
    if (x.worksNum) item.worksNum = Number(x.worksNum);
    if (x.playCount) item.playCount = Number(x.playCount);
    return item;
}

function toCommentItem(x) {
    if (!x || !x.nickName || x.comment === undefined) return null;
    const item = {
        nickName: x.nickName,
        comment: x.comment,
    };
    if (x.id) item.id = String(x.id);
    if (x.avatar) item.avatar = x.avatar;
    if (x.like) item.like = Number(x.like);
    if (x.createAt) item.createAt = Number(x.createAt);
    if (x.location) item.location = x.location;
    if (Array.isArray(x.replies) && x.replies.length) {
        item.replies = x.replies.map(toCommentItem).filter(Boolean);
    }
    return item;
}

module.exports = {
    platform: '温mg',
    version: '0.1',
    author: '温',
    description: '咪咕音乐源（自建 miguMusic-api-enhanced 服务），支持搜索、专辑、歌手、歌单、排行榜、歌词、评论、导入',
    cacheControl: 'no-cache',
    supportedSearchType: ['music', 'album', 'artist', 'sheet', 'lyric'],
    hints: {
        getMediaSource: ['免费音源通常为标准音质(PQ)，部分歌曲可能受版权限制无法获取音源'],
    },

    async search(query, page, type) {
        if (!query) return { isEnd: true, data: [] };
        const res = await request('search', {
            keyword: query,
            page: page || 1,
            type: type || 'music',
        });
        const list = res.data || [];

        let data = [];
        if (type === 'album') {
            data = list.map((x) => ({
                id: String(x.id),
                title: x.title,
                artist: x.artist,
                artwork: x.artwork,
                date: x.date,
                worksNum: x.totalCount ? Number(x.totalCount) : undefined,
            }));
        } else if (type === 'artist') {
            data = list.map((x) => ({
                id: String(x.id),
                name: x.name,
                avatar: x.avatar,
                fans: x.fans ? Number(x.fans) : undefined,
                description: x.description,
                worksNum: x.worksNum ? Number(x.worksNum) : undefined,
            }));
        } else if (type === 'sheet') {
            data = list.map(toSheetItem).filter(Boolean);
        } else {
            // music / lyric 均返回歌曲列表
            data = list.map(toMusicItem).filter(Boolean);
        }
        return { isEnd: res.isEnd === true, data };
    },

    async getMediaSource(musicItem, quality) {
        const params = { id: musicItem.id };
        const q = QUALITY_MAP[quality] || 'PQ';
        if (q) params.quality = q;
        if (musicItem.copyrightId) params.copyright_id = musicItem.copyrightId;
        if (musicItem.resourceType) params.resource_type = musicItem.resourceType;

        const res = await request('musicSource', params);
        if (!res.url) throw new Error('该歌曲暂无音源');
        return { url: res.url };
    },

    async getLyric(musicItem) {
        const res = await request('lyric', { id: musicItem.id });
        const result = {};
        if (res.rawLrc) result.rawLrc = res.rawLrc;
        if (res.translation) result.translation = res.translation;
        if (!result.rawLrc && !result.translation) throw new Error('该歌曲暂无歌词');
        return result;
    },

    async getAlbumInfo(albumItem, page) {
        const res = await request('albumInfo', {
            id: albumItem.id,
            page: page || 1,
        });
        const musicList = (res.musicList || []).map(toMusicItem).filter(Boolean);
        const result = { isEnd: res.isEnd === true, musicList };
        if (page === 1 || page === undefined) {
            const albumInfo = res.albumItem || {};
            result.albumItem = {
                id: String(albumItem.id),
                title: albumItem.title,
                artist: albumItem.artist,
                artwork: albumInfo.artwork || albumItem.artwork,
            };
        }
        return result;
    },

    async getArtistWorks(artistItem, page, type) {
        const t = type === 'album' ? 'album' : 'music';
        const res = await request('artistWorks', {
            id: artistItem.id,
            page: page || 1,
            type: t,
        });
        const list = res.data || [];
        if (t === 'album') {
            return {
                isEnd: res.isEnd === true,
                data: list.map((x) => ({
                    id: String(x.id),
                    title: x.title,
                    artist: x.artist,
                    artwork: x.artwork,
                    date: x.date,
                    worksNum: x.worksNum ? Number(x.worksNum) : undefined,
                })),
            };
        }
        return {
            isEnd: res.isEnd === true,
            data: list.map(toMusicItem).filter(Boolean),
        };
    },

    async getMusicSheetInfo(sheetItem, page) {
        const res = await request('sheetInfo', {
            id: sheetItem.id,
            page: page || 1,
        });
        const result = {
            isEnd: res.isEnd === true,
            musicList: (res.musicList || []).map(toMusicItem).filter(Boolean),
        };
        if ((page === 1 || page === undefined) && res.sheetItem) {
            result.sheetItem = toSheetItem(res.sheetItem);
        }
        return result;
    },

    async getRecommendSheetTags() {
        const res = await request('sheetTags', {});
        const out = {
            pinned: (res.pinned || []).map((t) => ({ id: String(t.id), title: t.title })),
            data: (res.data || [])
                .filter((g) => g && Array.isArray(g.data))
                .map((g) => ({
                    title: g.title,
                    data: g.data.map((t) => ({ id: String(t.id), title: t.title })),
                })),
        };
        return out;
    },

    async getRecommendSheetsByTag(tag, page) {
        let tagId = '';
        if (tag && typeof tag === 'object' && tag.id !== undefined) tagId = String(tag.id || '');
        else if (typeof tag === 'string') tagId = tag;
        const params = { page: page || 1 };
        if (tagId) params.tagId = tagId;
        const res = await request('sheetByTag', params);
        return {
            isEnd: res.isEnd === true,
            data: (res.data || []).map(toSheetItem).filter(Boolean),
        };
    },

    async importMusicItem(urlLike) {
        const text = String(urlLike || '');
        const nums = text.match(/\d{9,}/g);
        if (!nums) throw new Error('无法识别的咪咕单曲链接或 ID');
        const contentId = nums.find((n) => n.length >= 14);
        const params = contentId ? { id: contentId } : { copyright_id: nums[0] };
        const res = await request('musicInfo', params);
        const item = toMusicItem(res.music);
        if (!item) throw new Error('未找到该歌曲');
        return item;
    },

    async importMusicSheet(urlLike) {
        const text = String(urlLike || '').trim();
        const m =
            text.match(/playlist[A-Za-z]*[^\d]{0,14}(\d{6,12})/i) ||
            text.match(/createId[^\d]*(\d{6,12})/i);
        let pid = m ? m[1] : '';
        if (!pid && /^\d{6,12}$/.test(text)) pid = text;
        if (!pid) throw new Error('无法识别的咪咕歌单链接，请提供含歌单 ID 的链接或纯 ID');
        const res = await request('sheetImport', { id: pid });
        const list = (res.musicList || []).map(toMusicItem).filter(Boolean);
        if (!list.length) throw new Error('歌单为空或导入失败');
        return list;
    },

    async getMusicInfo(musicItem) {
        const res = await request('musicInfo', { id: musicItem.id });
        const fresh = toMusicItem(res.music);
        if (!fresh) throw new Error('未找到歌曲详情');
        return Object.assign({}, musicItem, fresh);
    },

    async getMusicComments(musicItem, page) {
        const res = await request('comments', {
            id: musicItem.id,
            page: page || 1,
        });
        return {
            isEnd: res.isEnd !== false,
            data: (res.data || []).map(toCommentItem).filter(Boolean),
        };
    },

    async getTopLists() {
        const res = await request('topLists', {});
        if (!Array.isArray(res)) return [];
        return res
            .filter((g) => g && Array.isArray(g.data))
            .map((g) => ({
                title: g.title,
                data: g.data.map((x) => ({
                    id: String(x.id),
                    title: x.title,
                    artwork: x.coverImg || x.artwork,
                    description: x.desc,
                })),
            }));
    },

    async getTopListDetail(topListItem, page) {
        const res = await request('topListDetail', {
            id: topListItem.id,
            page: page || 1,
        });
        const musicList = (res.musicList || []).map(toMusicItem).filter(Boolean);
        const result = { isEnd: res.isEnd === true, musicList };
        return result;
    },
};
