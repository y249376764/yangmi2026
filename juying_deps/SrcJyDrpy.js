const codePath = module.modulePath.slice(0, module.modulePath.lastIndexOf("/") + 1);
const JSEngine = com.example.hikerview.service.parser.JSEngine;
const drpyMap = new Map();
const GMkey = module.importParam;
function oldbuildJsEnv(ticket) {
    let code = String.raw`
    // const my_rule = '
    const MY_RULE = ${my_rule};
    const my_rule = JSON.stringify(MY_RULE);
    const MY_TICKET = "${ticket || ""}";
    eval(getJsPlugin());
    eval(getJsLazyPlugin());
    `;
    return code;
}

function buildJsEnv(ticket) {
    MY_RULE.title = MY_RULE._title || MY_RULE.title;
    let my_rule = JSON.stringify(MY_RULE);

    let code = `
    let my_rule = '';
    my_rule = null;
    const MY_RULE = ${my_rule};
    const MY_TICKET = "${ticket || ""}";
    eval(getJsPlugin());
    eval(getJsLazyPlugin());
    `;
    return code;
}

function sync(func, sp) {
    return new org.mozilla.javascript.Synchronizer(func, sp || {});
}

function createDrpy(sdata) {
    let func = buildJsEnv;
    if (typeof my_rule != "undefined" && my_rule != null) {
        func = oldbuildJsEnv;
    }
    JSEngine.getInstance().evalJS(func(MY_TICKET) + "\n!" + $.toString((sdata, codePath, GMkey, MY_TICKET) => {
        const localKey = "drpy";
        const CryptoUtil = $.require("hiker://assets/crypto-java.js");
        globalThis.local = {
            set(rulekey, k, v) {
                storage0.setItem(localKey + "@" + rulekey + "@" + k, v);
            },
            get(rulekey, k, v) {
                return storage0.getItem(localKey + "@" + rulekey + "@" + k, "") || v;
            },
            delete(rulekey, k) {
                storage0.clearItem(localKey + "@" + rulekey + "@" + k);
            }
        };
        eval(getCryptoJS());
        globalThis.CryptoJS = CryptoJS;

        if (getItem("drpy调试日志")!="1") {
            console.log = function () {
                return;
            };
        }
        
        globalThis.getProxy = function () {
            let proxyUrl = startProxyServer($.toString((sdata, codepath, title) => {
                let {GM} = $.require(codepath + "plugins/globalmap.js");
                GM.setSelfKey(title);
                let drpy = GM.defineModule("SrcJyDrpy", codepath + "SrcJyDrpy.js").get(sdata);

                let params = {};
                for (let key in MY_PARAMS) {
                    params[key] = String(MY_PARAMS[key][0]);
                }
                
                let result = drpy.proxy(params);
                let [code, media_type, data, headers, isReturnBytes] = result;
                headers = Object.assign({}, {
                    'Content-Type': media_type,
                }, headers);
                if(typeof data==="string"&&data.startsWith("data:")&&data.includes("base64,")){
                    data = _base64.decode(data.split("base64,")[1], _base64.NO_WRAP);
                }
                return {
                    statusCode: code,
                    body: data,
                    headers: headers,
                };
            }, sdata, codePath, MY_RULE._title||MY_RULE.title));
            return proxyUrl + "?do=js";
        }
        
        let $request = request;
        let $post = post;
        function readFileToString(filePath) {
            const StringBuilder = java.lang.StringBuilder;
            const BufferedReader = java.io.BufferedReader;
            const File = java.io.File;
            const FileReader = java.io.FileReader;

            let file = new File(filePath);
            if (!file.exists()) return "";
            let fileContent = new StringBuilder();
            let br = null;
            try {
                br = new BufferedReader(new FileReader(file));
                let line;
                while ((line = br.readLine()) != null) {
                    fileContent.append(line).append("\n");
                }
            } catch (e) {
                fileContent.append("");
            } finally {
                try {
                    if (br != null) {
                        br.close();
                    }
                } catch (e) { }
            }
            return String(fileContent.toString());
        }
        function hasPropertyIgnoreCase(obj, propertyName) {
            return Object.keys(obj).some(key =>
                key.toLowerCase() === propertyName.toLowerCase()
            );
        }

        function valueStartsWith(obj, propertyName, prefix) {
            const key = Object.keys(obj).find(key =>
                key.toLowerCase() === propertyName.toLowerCase()
            );
            return key !== undefined && obj[key].startsWith(prefix);
        }

        globalThis.req = function (url, cobj) {
            try {
                let res = {};
                let obj = Object.assign({}, cobj);
                if (obj.data) {
                    obj.body = obj.data;
                    if ((obj.postType && obj.postType == "form") || (hasPropertyIgnoreCase(obj.headers, "Content-Type") && valueStartsWith(obj.headers, "Content-Type", "application/x-www-form-urlencoded"))) {
                        let temp_obj = obj.data;
                        obj.body = Object.keys(temp_obj).map(key => {
                            return `${key}=${temp_obj[key]}`;
                        }).join('&');
                    }
                    delete obj.data;
                }

                if (obj.hasOwnProperty("redirect")) obj.redirect = !!obj.redirect;
                if (obj.buffer === 2) {
                    obj.toHex = true;
                }
                obj.headers = Object.assign({
                    Cookie: "#noCookie#"
                }, obj.headers);
                if (url === "https://api.nn.ci/ocr/b64/text" && obj.headers) {
                    obj.headers["Content-Type"] = "text/plain";
                }
                let isFile = url.startsWith("file://");
                if (isFile && (url.includes("?type=") || url.includes("?params="))) {
                    url = url.slice(0, url.lastIndexOf("?"));
                }
                for (let key in obj.headers) {
                    if (typeof obj.headers[key] !== "string") {
                        obj.headers[key] = String(obj.headers[key]);
                    }
                }
                let r = "";
                if (isFile) {
                    r = readFileToString(url.replace("file://", ""));
                } else {
                    r = $request(url, obj);
                }
                if (obj.withHeaders) {
                    r = JSON.parse(r);
                    res.content = r.body;
                    res.headers = {};
                    for (let [k, v] of Object.entries(r.headers || {})) {
                        res.headers[k] = v[0];
                    }
                } else {
                    res.content = r;
                }
                if (obj.buffer === 2) {
                    res.content = CryptoUtil.Data.parseHex(res.content).toBase64(_base64.NO_WRAP);
                }
                return res;
            } catch (e) {
                log("Error" + e.toString());
            }
        }
        globalThis.pdfa = _pdfa;
        globalThis.pd = _pd;
        globalThis.pdfh = _pdfh;
        String.prototype.replaceAll = function (search, replacement) {
            return this.split(search).join(replacement);
        };
        let $toString = Function.prototype.toString;
        Function.prototype.toString = function () {
            return $toString.apply(this).trim();
        };
        //let {GM} = $.require("http://hiker.nokia.press/hikerule/rulelist.json?id=6916&auth=1d35e8f0-22e8-5270-a9d1-826f53f177ad");
        // ★ 防御式加载：清缓存后加载，并校验 init 是否真的拿到
        //   原写法 $.require 拿到什么就直接用，一旦返回 {} 或 undefined，
        //   后面 drpy.init() 才报"找不到函数 init"，现象和文件缺失一模一样，极难排查
        let drpy2 = null;
        function _loadDrpy() {
            try { return $.require(codePath + 'drpy/drpy2.js'); } catch (eL) { return null; }
        }
        try { $.require.cache.delete($.require.resolve(codePath + 'drpy/drpy2.js')); } catch (eC) { }
        drpy2 = _loadDrpy();
        if (!drpy2 || typeof drpy2.init !== 'function') {
            // 再试一次（有些版本 require 有缓存/竞态）
            try { $.require.cache.delete($.require.resolve(codePath + 'drpy/drpy2.js')); } catch (eC2) { }
            drpy2 = _loadDrpy();
        }
        if (!drpy2 || typeof drpy2.init !== 'function') {
            // 兜底：有些环境 require 返回的是 {default: {...}}
            try {
                let _r = $.require(codePath + 'drpy/drpy2.js');
                if (_r && _r.default && typeof _r.default.init === 'function') { drpy2 = _r.default; }
            } catch (eD) { }
        }
        // ★ 加载失败【不要】放进缓存
        //   原来无条件 put，坏对象（{}）被塞进 GM/drpyMap，
        //   于是第一次报"找不到函数 init"，刷新后从缓存取出同一个坏对象
        //   改成调 getRule() 就报"找不到函数 getRule" —— 两个报错行号不同就是这么来的
        if (!drpy2 || typeof drpy2.init !== 'function') {
            log('drpy2 引擎加载失败：' + codePath + 'drpy/drpy2.js 未取到 init');
            try { drpyMap.delete(sdata.key); } catch (eDel) { }
            return;
        }
        GM.has(GMkey, (DrpyManage) => {
            DrpyManage.put(sdata.key, drpy2);
        });
    }, sdata, codePath, GMkey, MY_TICKET) + ";\n", "", false);
}

function createNewDrpy(sdata) {
    createDrpy(sdata);
    let drpy = drpyMap.get(sdata.key);
    // ★ 取出来先校验，坏了就抛明确错误，不要让 init 裸崩
    if (!drpy || typeof drpy.init !== 'function') {
        throw new Error('drpy2 引擎未就绪（init 缺失），hipy_t3 源无法运行；请确认 hiker://files/rules/Src/Juying2/drpy/drpy2.js 是 ES5 版');
    }
    drpy.init(sdata.ext);
    //log(sdata.key + ">init");
    return drpy;
}

function getext(jkdata) {
    let extp = "";
    if(jkdata.ext && jkdata.ext.includes('?')){
        extp = '?' + jkdata.ext.split('?')[1];
    }
    let gmParams = globalMap0.getVar('Src_Jy_gmParams');
    if (/^hiker/.test(jkdata.url)) {
        if(jkdata.url.startsWith(gmParams.libspath)){//收藏、历史进入的，旧的data需要修正url地址
            jkdata.url = gmParams.jkfilespath + jkdata.url.substr(jkdata.url.lastIndexOf('/')+1);
        }
        if (!fileExist(jkdata.url)) {
            if(!fileExist(gmParams.jkfile)){
                jkdata.url = gmParams.cachepath + jkdata.url.substr(jkdata.url.lastIndexOf('/')+1);
            }
            if (jkdata.ext) {
                let content = gmParams.getContnet(jkdata.ext.split('?')[0]);
                if (content) {
                    writeFile(jkdata.url, content);
                }
            }
        }
        if (fileExist(jkdata.url)) {
            return getPath(jkdata.url) + extp;
        }
    }else if(/^file/.test(jkdata.url) && fileExist(jkdata.url)){
        return jkdata.url + extp;
    }
    return '';
}

function get(jkdata) {
    let key = jkdata.key || jkdata.name;
    let ext = jkdata.key?jkdata.ext:getext(jkdata);
    let sdata = {key:key, ext:ext};
    return sync(() => {
        //log(drpyMap.size)
        if (drpyMap.has(key)) {
            //log("取缓存>" + key)
            let drpy = drpyMap.get(key);
            // ★ 原写法直接 drpy.getRule()，坏对象缓存进来后这里裸崩
            //   （"找不到函数 getRule"）——先校验再调用
            if(drpy && typeof drpy.getRule === 'function' && typeof drpy.init === 'function') {
                try {
                    if(Object.keys(drpy.getRule()).length > 0){
                        return drpy;
                    }
                } catch (eGR) { }
            }
            drpyMap.delete(key);
        }
        if (drpyMap.size >= 16) {
            //log("删缓存>"+Array.from(drpyMap.keys()).at(0))
            del(Array.from(drpyMap.keys()).at(0));
        }
        //log(sdata);
        let drpy = createNewDrpy(sdata);
        return drpy;
    }, this).call();
}

function put(key, drpy) {
    sync(() => drpyMap.set(key, drpy), this).call();
}

function del(key) {
    sync(() => {
        //log("删除" + key);
        drpyMap.delete(key);
    }, this).call();
}

function clear() {
    sync(() => {
        drpyMap.clear();
    }, this).call();
}
$.exports = {
    get,
    clear,
    put
}