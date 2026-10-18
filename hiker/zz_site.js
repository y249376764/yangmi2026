function zsiteMini() {
setPageTitle("站点管理");
var DEFAULT_DIRS = "hiker://files/zz_repo/\n/storage/emulated/0/Download/QQ/\n/sdcard/TVBox/py/\n/sdcard/TVBox/Python/\n/sdcard/Download/py/\n/sdcard/Download/蜘蛛/\n/sdcard/TV/py/\n/sdcard/蜘蛛/";
var RULES = [
    ["官源", ["iqiyi", "youku", "tencent", "mgtv", "douban", "bilibilivd", "bilibili_ts", "cctv", "yangshi", "央视", "芒果", "爱奇艺", "优酷", "腾讯"]],
    ["音频", ["audio", "music", "tingshu", "tingyou", "ximalaya", "yitingshu", "yuetingba", "ting365", "ting39", "geci", "kuwo", "fm", "radio", "听书", "有声", "电台", "广播", "评书", "相声"]],
    ["小说", ["novel", "book", "xiaoshuo", "wenxue", "shucheng", "biqu", "kanshu", "小说", "书城", "文学", "阅读", "笔趣"]],
    ["动漫", ["anime", "dongman", "fanju", "comic", "yinghua", "acg", "动漫", "番剧", "樱花"]],
    ["直播", ["live", "iptv", "zhibo", "直播", "卫视", "频道"]],
    ["短剧", ["duanju", "duanpian", "短剧", "微剧"]],
    ["高清", ["4k", "riben4k", "pianku4k", "高清"]]
];

// ★ v37：导入列表持久化到文件（更新规则不清）
var SITES_FILE = "hiker://files/zz_sites.json";
function accSitesSave(_arr) {
    if (!_arr) { _arr = []; }
    try { writeFile(SITES_FILE, JSON.stringify(_arr)); } catch (_as1) { }
    try { setItem("acc_sites", JSON.stringify(_arr)); } catch (_as2) { }
}
function accSitesLoad() {
    var _sl = [];
    try { var _srf = readFile(SITES_FILE); if (_srf) { _sl = JSON.parse(String(_srf)); if (!_sl) { _sl = []; } } } catch (_sl1) { _sl = []; }
    if (!_sl.length) { try { var _srg = getItem("acc_sites", ""); if (_srg) { _sl = JSON.parse(_srg); if (!_sl) { _sl = []; } } } catch (_sl2) { _sl = []; } }
    return _sl;
}
function accDirs() {
    var raw = "";
    try { raw = getItem("acc_dirs", "") || ""; } catch (e) { }
    if (!raw) { raw = DEFAULT_DIRS; }
    var out = [];
    var arr = String(raw).split("\n");
    for (var i = 0; i < arr.length; i++) { var s = String(arr[i] || "").trim(); if (s) { out.push(s); } }
    return out;
}
function accTag(stem) {
    var t = String(stem).toLowerCase();
    for (var i = 0; i < RULES.length; i++) {
        var ks = RULES[i][1];
        for (var k = 0; k < ks.length; k++) { if (t.indexOf(ks[k]) > -1) { return RULES[i][0]; } }
    }
    return "影视";
}

function cleanName(nm) {
    var s = String(nm || "").replace(/\.py$/i, "");
    var idx = s.indexOf("TG群");
    if (idx > -1) { s = s.substring(0, idx); }
    var idx2 = s.indexOf("TG频道");
    if (idx2 > -1) { s = s.substring(0, idx2); }
    return s;
}
function accScan() {
    var dirs = accDirs(); var found = []; var seen = {};
    for (var i = 0; i < dirs.length; i++) {
        try {
            var _dirp = String(dirs[i] || "");
            if (_dirp.indexOf("hiker://") === 0) { try { _dirp = getPath(_dirp).slice(7); } catch (_dp1) { } }
            var f = new java.io.File(_dirp);
            if (!f.exists() || !f.isDirectory()) { continue; }
            var fs = f.listFiles(); if (!fs) { continue; }
            for (var q = 0; q < fs.length; q++) {
                var nm = String(fs[q].getName());
                if (!nm.toLowerCase().endsWith(".py")) { continue; }
                var _fp = dirs[i] + nm;
                // ★ v40：按完整路径去重（不同目录同名文件全部显示）
                if (seen[_fp]) { continue; }
                seen[_fp] = 1;
                var _hideRaw = "";
                try { _hideRaw = getItem("acc_hide", "") || ""; } catch (_he) { }
                if (_hideRaw && String(_hideRaw).indexOf(_fp) > -1) { continue; }
                found.push({ name: nm, path: _fp, size: fs[q].length(), tag: accTag(nm.replace(/\.py$/i, "")) });
            }
        } catch (e) { }
    }
    var _ctRaw = "";
    try { _ctRaw = getItem("acc_ctag", "") || ""; } catch (_cte) { _ctRaw = ""; }
    if (_ctRaw) {
        try {
            var _cm = JSON.parse(_ctRaw);
            for (var _cj = 0; _cj < found.length; _cj++) {
                var _cv = _cm[found[_cj].path];
                if (_cv) { found[_cj].tag = String(_cv); }
            }
        } catch (_cpe) { }
    }
    return found;
}

// ★ 聚影模式：站点管理也显示导入列表(acc_sites) + 扫描合并
var _scL = accSitesLoad();
var _scnL = accScan();
var _seenL = {};
for (var _sl2 = 0; _sl2 < _scL.length; _sl2++) { if (_scL[_sl2] && _scL[_sl2].path) { _seenL[String(_scL[_sl2].path)] = 1; } }
for (var _s2 = 0; _s2 < _scnL.length; _s2++) { if (_seenL[String(_scnL[_s2].path)]) { continue; } _seenL[String(_scnL[_s2].path)] = 1; _scL.push(_scnL[_s2]); }
var sites = _scL;
var filter = "";
try { filter = getMyVar("zsite_filter", "") || ""; } catch (e) { }
// ★ v42：站点搜索（参考聚影）——输入关键词过滤站名
var zq = "";
try { zq = getMyVar("zsite_q", "") || ""; } catch (e) { }
var zqLow = String(zq).toLowerCase();

var d = [];
d.push({
    title: "站点管理 · 共 " + sites.length + " 个",
    desc: "点站点可打开 / 删除 / 复制路径",
    col_type: "text_center_1",
    url: "hiker://empty"
});
// ★ v43：搜索框——单独一排（标准 input 写法，参考首页搜索框/聚影）
d.push({
    title: "🔍 搜索站点",
    desc: zq ? "当前过滤：「" + zq + "」· 输入新词回车搜索，删除后回车清空" : "输入站点名称关键词（如 douban / 影视 / 4k），回车过滤",
    col_type: "input",
    url: $.toString(function () {
        var kwv = String(input || "").trim();
        try { putMyVar("zsite_q", kwv); } catch (_zq1) { }
        refreshPage(false);
        return "hiker://empty";
    })
});

var shown = 0;
var _curPy = "";
try { _curPy = getMyVar("acc_py", "") || ""; } catch (_cpv) { }


for (var i = 0; i < sites.length; i++) {
    if (filter && sites[i].tag != filter) { continue; }
    // ★ v42：站名包含搜索词才显示（本地过滤）
    if (zqLow) {
        var _zqn = String(cleanName(sites[i].name)).toLowerCase();
        var _zqp = String(sites[i].path).toLowerCase();
        if (_zqn.indexOf(zqLow) < 0 && _zqp.indexOf(zqLow) < 0) { continue; }
    }
    shown++;
    d.push({
        title: (String(sites[i].path) == String(_curPy) ? "★ " : "") + cleanName(sites[i].name),
        desc: (sites[i].size / 1024).toFixed(1) + "KB · " + sites[i].tag + "\n" + String(sites[i].path),
        col_type: "text_2",
        extra: {
            longClick: [
                { title: "删除此站点", js: $.toString(function (pp) {
                    var nmx = String(pp).split("/").pop();
                    try { putMyVar("acc_del_path", String(pp || "")); } catch (_dp0) { }
                    return $("确定删除此站点？\\n" + nmx).confirm(function () {
                    var pp2 = getMyVar("acc_del_path", "") || "";
                    var rp = String(pp2 || "");
                        if (rp.indexOf("hiker://") === 0) { try { rp = getPath(rp).slice(7); } catch (_e0) { } }
                        else if (rp.indexOf("file://") === 0) { rp = rp.slice(7); }
                        var okDel = false;
                        var rpH = String(pp2 || "");
                        if (rpH.indexOf("hiker://") === 0) { try { deleteFile(rpH); okDel = true; } catch (_e1b) { } }
                        if (!okDel) { try { var ff = new java.io.File(rp); if (ff.exists()) { okDel = ff.delete(); } } catch (_e1) { okDel = false; } }
                        if (!okDel) { try { deleteFile("file://" + rp); } catch (_e2) { } }
                        if (!okDel) { try { deleteFile(rp); } catch (_e3) { } }
                        try { if (!fileExist("file://" + rp)) { okDel = true; } } catch (_e4) { }
                        var hideRaw = "";
                        try { hideRaw = getItem("acc_hide", "") || ""; } catch (_e5) { }
                        var hideArr = String(hideRaw).split("\n");
                        var hdOut = [];
                        for (var _hi = 0; _hi < hideArr.length; _hi++) { var _hs = String(hideArr[_hi] || "").trim(); if (_hs) { hdOut.push(_hs); } }
                        if (hdOut.indexOf(rp) < 0) { hdOut.push(rp); }
                        try { setItem("acc_hide", hdOut.join("\n")); } catch (_e6) { }
                        if (String(getMyVar("acc_py", "")) == String(pp2)) { clearMyVar("acc_py"); try { setItem("acc_last_py", ""); } catch (_e7) { } }
                        refreshPage(false);
                        return "toast://" + (okDel ? "已删除文件" : "已移除（文件无权限删，已隐藏）");
                    });
                }, String(sites[i].path)) },
                { title: "修改分类", js: $.toString(function (pp) {
                    var it3 = JSON.parse(base64Decode(pp));
                    try { putMyVar("acc_cpath", String(it3.p || "")); } catch (_cp2) { }
                    return $("", "输入分类名（留空删除自定义）").input(function () {
                        var tg = String(input || "").trim();
                        var p3 = getMyVar("acc_cpath", "") || "";
                        var raw = "";
                        try { raw = getItem("acc_ctag", "") || ""; } catch (e) { }
                        var mp = {};
                        if (raw) { try { mp = JSON.parse(raw); } catch (e2) { mp = {}; } }
                        if (tg) { mp[p3] = tg; } else { delete mp[p3]; }
                        try { setItem("acc_ctag", JSON.stringify(mp)); } catch (e3) { }

                    try {
                        var _scf = readFile("hiker://files/zz_scan.json");
                        if (_scf) {
                            var _sco = JSON.parse(String(_scf));
                            if (_sco && _sco.s) {
                                for (var _sci = 0; _sci < _sco.s.length; _sci++) {
                                    if (String(_sco.s[_sci].path) == String(p3)) {
                                        _sco.s[_sci].tag = tg;
                                        break;
                                    }
                                }
                                try { writeFile("hiker://files/zz_scan.json", JSON.stringify(_sco)); } catch (_scw) { }
                            }
                        }
                    } catch (_sce2) { }
                        toast(tg ? ("已设为 " + tg) : "已恢复自动分类");
                        refreshPage(false);
                        return "hiker://empty";
                    });
                }, base64Encode(JSON.stringify({ p: String(sites[i].path) }))) },
                { title: "复制路径", js: $.toString(function (pp) { return "copy://" + String(pp); }, String(sites[i].path)) }
            ]
        },
        url: $(["打开", "修改分类", "删除", "复制路径"], 2).select(function (data) {
            var it = JSON.parse(base64Decode(data));
            if (input == "打开") {
                return $("hiker://empty#noHistory#").lazyRule(function (p) {
                    if (String(p).indexOf("cms://") === 0) {
                        putMyVar("acc_cms_api", String(p).slice(6));
                        putMyVar("acc_cms_tid", "");
                        putMyVar("acc_cms_vid", "");
                        return "hiker://page/cmscat#fullTheme#";
                    }
                    putMyVar("acc_py", p);
                    clearMyVar("acc_cat_id");
                    putMyVar("acc_pg", "1");
                    clearMyVar("acc_kw");
                    try { setItem("acc_last_py", p); } catch (e) { }
                    return "hiker://page/pyLoad#fullTheme#";
                }, String(it.p));
            } else if (input == "修改分类") {
                var it3 = JSON.parse(base64Decode(data));
                try { putMyVar("acc_cpath", String(it3.p || "")); } catch (_cp) { }
                return $("", "输入分类名（留空删除自定义）").input(function () {
                    var tg = String(input || "").trim();
                    var p3 = getMyVar("acc_cpath", "") || "";
                    var raw = "";
                    try { raw = getItem("acc_ctag", "") || ""; } catch (e) { }
                    var mp = {};
                    if (raw) { try { mp = JSON.parse(raw); } catch (e2) { mp = {}; } }
                    if (tg) { mp[p3] = tg; } else { delete mp[p3]; }
                    try { setItem("acc_ctag", JSON.stringify(mp)); } catch (e3) { }

                    try {
                        var _scf = readFile("hiker://files/zz_scan.json");
                        if (_scf) {
                            var _sco = JSON.parse(String(_scf));
                            if (_sco && _sco.s) {
                                for (var _sci = 0; _sci < _sco.s.length; _sci++) {
                                    if (String(_sco.s[_sci].path) == String(p3)) {
                                        _sco.s[_sci].tag = tg;
                                        break;
                                    }
                                }
                                try { writeFile("hiker://files/zz_scan.json", JSON.stringify(_sco)); } catch (_scw) { }
                            }
                        }
                    } catch (_sce2) { }
                    toast(tg ? ("已设为 " + tg) : "已恢复自动分类");
                    refreshPage(false);
                    return "hiker://empty";
                });
            } else if (input == "删除") {
                try { putMyVar("acc_del_data", String(data || "")); } catch (_dd0) { }
                return $("确定删除站点？\n" + String(it.n)).confirm(function () {
                    var it2 = JSON.parse(base64Decode(getMyVar("acc_del_data", "") || ""));
                    var pp = String(it2.p || "");
var rp = String(pp || "");
                    if (rp.indexOf("hiker://") === 0) { try { rp = getPath(rp).slice(7); } catch (_e0) { } }
                    else if (rp.indexOf("file://") === 0) { rp = rp.slice(7); }
                    var okDel = false;
                    var rpH = String(it2.p || "");
                    if (rpH.indexOf("hiker://") === 0) { try { deleteFile(rpH); okDel = true; } catch (_e1b) { } }
                    if (!okDel) { try { var ff = new java.io.File(rp); if (ff.exists()) { okDel = ff.delete(); } } catch (_e1) { okDel = false; } }
                    if (!okDel) { try { deleteFile("file://" + rp); } catch (_e2) { } }
                    if (!okDel) { try { deleteFile(rp); } catch (_e3) { } }
                    try { if (!fileExist("file://" + rp)) { okDel = true; } } catch (_e4) { }
                    var hideRaw = "";
                    try { hideRaw = getItem("acc_hide", "") || ""; } catch (_e5) { }
                    var hideArr = String(hideRaw).split("\n");
                    var hdOut = [];
                    for (var _hi = 0; _hi < hideArr.length; _hi++) { var _hs = String(hideArr[_hi] || "").trim(); if (_hs) { hdOut.push(_hs); } }
                    if (hdOut.indexOf(rp) < 0) { hdOut.push(rp); }
                    try { setItem("acc_hide", hdOut.join("\n")); } catch (_e6) { }
                    // ★ 聚影模式：同时从导入列表 acc_sites 移除
                    try {
                        var _dl = [];
                        try { var _dR = getItem("acc_sites", ""); if (_dR) { _dl = JSON.parse(_dR); if (!_dl) { _dl = []; } } } catch (_de2) { _dl = []; }
                        var _dOut = [];
                        for (var _d2 = 0; _d2 < _dl.length; _d2++) { if (String(_dl[_d2].path) !== pp) { _dOut.push(_dl[_d2]); } }
                        try { setItem("acc_sites", JSON.stringify(_dOut)); } catch (_de3) { }
                    } catch (_de4) { }
                    if (String(getMyVar("acc_py", "")) == String(pp2)) { clearMyVar("acc_py"); try { setItem("acc_last_py", ""); } catch (_e7) { } }
                    refreshPage(false);
                    return "toast://" + (okDel ? "已删除文件" : "已移除（文件无权限删，已隐藏）");
                });
            } else {
                return $("hiker://empty#noHistory#").lazyRule(function (txt) { return "copy://" + String(txt); }, String(it.p));
            }
        }, base64Encode(JSON.stringify({ n: String(sites[i].name).replace(/\.py$/i, ""), p: String(sites[i].path) })))
    });
}

if (shown == 0) {
    d.push({ title: "该分类下没有站点", col_type: "text_center_1", url: "hiker://empty" });
}

d.push({ title: "↻ 刷新", col_type: "scroll_button", url: $("hiker://empty#noHistory#").lazyRule(function () { refreshPage(true); return "hiker://empty"; }) });
setResult(d);

}