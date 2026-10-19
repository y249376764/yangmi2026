// 聚影 pyDriver.js 增强版：自动检测 chaquopy 插件路径
// 兼容: hiker://files/plugins/chaquopy/ (海阔标准) 和 hiker://files/data/chaquopy/ (旧版)
var PythonHiker = null;
// 尝试多个可能的 PythonHiker.js 路径
var pyCandidates = [
    "hiker://files/plugins/chaquopy/PythonHiker.js",
    "hiker://files/data/chaquopy/PythonHiker.js",
    "hiker://files/data2/星集Media/plug/jarLoad/chaquopy/PythonHiker.js"
];
for (var i = 0; i < pyCandidates.length; i++) {
    try {
        if (fileExist(pyCandidates[i])) {
            PythonHiker = $.require(pyCandidates[i]);
            log("PythonHiker 加载成功: " + pyCandidates[i]);
            break;
        }
    } catch (e) { }
}
if (!PythonHiker) {
    // 插件未安装，尝试自动安装
    try {
        var inst = $.require("hiker://page/pyInstall#fullTheme##noRecordHistory##noHistory#");
        log("未找到 PythonHiker，引导安装 chaquopy 插件");
    } catch (e2) { }
}

// py源获取本地文件路径
function getPyFile(url) {
    if(url.startsWith('hiker')){
        url = getPath(url).slice(7);
    }else if(url.startsWith('file://')){
        url = url.slice(7);
    }
    return url;
}
// 初始化py源修正相关模块方法
function initPyModule(api_url) {
    if(!PythonHiker){
        return null;
    }
    try{
        var pyModule = PythonHiker.runPy(getPyFile(api_url)).callAttr("Spider");
    }catch(e){
        if(e.message.includes('getName')){
            PythonHiker.evalCode(`def getName(self):
                return "`);
            var pyModule = PythonHiker.runPy(getPyFile(api_url)).callAttr("Spider");
        }
    }
    
    if(!pyModule.get("getName")){
        pyModule.put("getName", PythonHiker.wrapperJsFunc(function(){
            return "";
        }));
    }

    if(!pyModule.get("setCache")){
        // 注入 setCache 方法
        pyModule.put("setCache", PythonHiker.wrapperJsFunc(function(key, value){
            putMyVar("py_"+key, value);
            return true;
        }));
    }

    if(!pyModule.get("getCache")){
        // 注入 getCache 方法
        pyModule.put("getCache", PythonHiker.wrapperJsFunc(function(key){
            return getMyVar("py_"+key, "");
        }));
    }

    return pyModule;
}

$.exports = {
    getPyFile: getPyFile,
    initPyModule: initPyModule,
    isReady: function(){ return PythonHiker != null; }
};
