// @name 小听·说书风6音色
// @schema 1
// @version 2.0.0
// @uuid custom_tts_xiaoting_20261027
// @author User
// @url http://127.0.0.1:8075/tts
// @enabled true
// @cookieJar false
// @audioType audio/mpeg
// @defaultSpeed 48
// @defaultVolume 50
// @defaultPitch 47
// @sampleText 话说天下大势，分久必合，合久必分。这日清晨，山间薄雾未散，一个少年正挑着担子走过独木桥。
// @capabilities synthesis_speed,synthesis_pitch
// @description 说书风6音色：云健/云希/云扬/晓晓/晓伊/晓北，舒缓叙事旁白，语速稍慢音调略低
//
// ★ 部署：把 @url 改成你自己的服务器地址，例如 http://你的IP:8075/tts
//   服务端见同目录 tts_server.py（edge-tts，一条命令起）
//   注意：云逸/晓辰/潇潇 三个音色 2026-10 已被微软下线，本版已替换为可用音色

var VOICES;

function voiceCatalog() {
    if (VOICES) {
        return VOICES;
    }
    VOICES = [
        {
            name: "云健",
            id: "zh-CN-YunjianNeural",
            gender: "male",
            profile: "说书",
            categories: ["Novel"],
            personalities: ["Calm"],
            styles: [],
            roles: [],
            roleHints: ["舒缓叙事", "沧桑"],
            styleValue: "narration-relaxed"
        },
        {
            name: "云希",
            id: "zh-CN-YunxiNeural",
            gender: "male",
            profile: "说书",
            categories: ["Novel"],
            personalities: ["Calm"],
            styles: [],
            roles: [],
            roleHints: ["年轻", "轻快"],
            styleValue: "narration-relaxed"
        },
        {
            name: "云扬",
            id: "zh-CN-YunyangNeural",
            gender: "male",
            profile: "说书",
            categories: ["Novel"],
            personalities: ["Calm"],
            styles: [],
            roles: [],
            roleHints: ["沉稳", "播报"],
            styleValue: "narration-relaxed"
        },
        {
            name: "晓晓",
            id: "zh-CN-XiaoxiaoNeural",
            gender: "female",
            profile: "说书",
            categories: ["Novel"],
            personalities: ["Calm"],
            styles: [],
            roles: [],
            roleHints: ["温柔", "标准女声"],
            styleValue: "narration-relaxed"
        },
        {
            name: "晓伊",
            id: "zh-CN-XiaoyiNeural",
            gender: "female",
            profile: "说书",
            categories: ["Novel"],
            personalities: ["Calm"],
            styles: [],
            roles: [],
            roleHints: ["活泼", "少女"],
            styleValue: "narration-relaxed"
        },
        {
            name: "晓北",
            id: "zh-CN-liaoning-XiaobeiNeural",
            gender: "female",
            profile: "说书",
            categories: ["Novel"],
            personalities: ["Calm"],
            styles: [],
            roles: [],
            roleHints: ["东北口音", "幽默"],
            styleValue: "narration-relaxed"
        }
    ];
    return VOICES;
}

function options() {
    return {
        api: "http://127.0.0.1:8075/tts",
        speed: 48,
        pitch: 47
    };
}

function voices(speechRate, speechPitch) {
    return voiceCatalog();
}

function filterText(text) {
    if (!text) {
        return "";
    }
    var out = [];
    var lines = String(text).split(/\r?\n/);
    for (var i = 0; i < lines.length; i++) {
        var l = lines[i];
        l = l.replace(/^\s+|\s+$/g, "");
        if (!l) {
            continue;
        }
        // 章节名
        if (/^(第[\d零一二三四五六七八九十百千]+章|楔子|序章|引子|番外|尾声|后记|正文)/.test(l) && l.length < 40) continue;
        // 更新日期行
        if (/^(更新于|更新时间|最新更新|更新至|最后更新|更新日期|发布时间)/.test(l)) continue;
        // 站点/广告行
        if (/^(本站|请收藏|收藏本站|首发|最新章节|推荐阅读|加入书架|投推荐票|各位书友|天才一秒记住|一秒记住|无弹窗|手机阅读|请记住|如果您觉得|欢迎来到|顶点|笔趣阁|书旗|番茄小说)/.test(l)) continue;
        // 纯数字/URL行
        if (/^[\d\s\.\-—]+$/.test(l)) continue;
        if (/^https?:\/\//.test(l)) continue;
        // 乱码行
        if (/^[=\-_*~]{3,}$/.test(l)) continue;
        // 行内清理
        l = l.replace(/[“”"]/g, '"').replace(/[‘’']/g, "'");
        l = l.replace(/…+/g, "……").replace(/\.{3,}/g, "……");
        l = l.replace(/\s{2,}/g, " ").replace(/^[\s\u3000]+|[\s\u3000]+$/g, "");
        if (!l) {
            continue;
        }
        out.push(l);
    }
    return out.join("\n");
}

function synthesize(text, voice, opts) {
    opts = opts || {};
    var api = opts.api || "http://127.0.0.1:8075/tts";
    var speed = opts.speed || 48;
    var pitch = opts.pitch || 47;
    // 阅读NG speed/pitch 0-100，转成 -50~+50 再调成 Next 参数
    var rate = Math.round((speed - 50) * 0.6);
    var p = Math.round((pitch - 50) * 0.6) - 5;
    var style = "narration-relaxed";
    if (voice && voice.extra && voice.extra.style_value) {
        style = voice.extra.style_value;
    }
    var url = api + "?t=" + encodeURIComponent(text) + "&v=" + encodeURIComponent(voice.id) + "&r=" + rate + "&p=" + p + "&s=" + style;
    return url;
}