////本代码仅用于个人学习，请勿用于其他作用，下载后请24小时内删除，代码虽然是公开学习的，但请尊重作者，应留下说明
require((config.聚影||getPublicItem('聚影','')).replace(/[^/]*$/,'') + 'SrcJyPublic.js');//加载公共文件

function SRCSet() {
    addListener("onClose", $.toString(() => {
        clearMyVar('guanli');
        clearMyVar('批量选择模式');
        clearMyVar('duoselect');
        clearMyVar('jkdatalist');
        clearMyVar('seacrhJiekou');
        clearMyVar('onlyStopJk');
    }));

    if(getMyVar('guanli','')==""){putMyVar('guanli','jk');}

    let guanliType = getMyVar('guanli', 'jk');
    let d = [];
    d.push({
        title: '增加',
        url: $('hiker://empty#noRecordHistory##noHistory#').rule((guanliType) => {
            require(config.聚影.replace(/[^/]*$/,'') + 'SrcJySet.js');
            if(guanliType=="jk"){
                jiekou();
            }else{
                jiexi();
            }
        }, guanliType),
        img: getIcon("点播-接口增加.svg"),//"https://hikerfans.com/tubiao/more/25.png",
        col_type: "icon_small_4"
    });
    d.push({
        title: '操作',
        url: $(["批量选择","查看禁用","清空所有"],2,"选择操作功能项").select(()=>{
            if(input=="批量选择"){
                let sm;
                if(getMyVar('批量选择模式')){
                    clearMyVar('批量选择模式');
                    clearMyVar('duoselect');
                    sm = "退出批量选择模式";
                }else{
                    putMyVar('批量选择模式','1');
                    sm = "进入批量选择模式";
                }
                refreshPage(false);
                return "toast://"+sm;
            }else if(input=="清空所有"){
                if(getMyVar('guanli', 'jk')=="jk"){
                    var sm = "接口";
                }else{
                    var sm = "解析";
                }
                return $("确定要删除本地所有的"+sm+"吗？").confirm(()=>{
                    require(config.聚影.replace(/[^/]*$/,'') + 'SrcJyPublic.js');
                    deleteData(getMyVar('guanli', 'jk'));
                    refreshPage(false);
                    return 'toast://已全部清空';
                })
            }else if(input=="查看禁用"){
                let sm;
                if(getMyVar('onlyStopJk')){
                    clearMyVar('onlyStopJk');
                    sm = "退出仅显示禁用列表";
                }else{
                    putMyVar('onlyStopJk','1');
                    sm = "进入仅显示禁用列表";
                }
                refreshPage(false);
                return "toast://"+sm;
            }
        }),
        img: getIcon("点播-接口操作.svg"),//"https://hikerfans.com/tubiao/more/290.png",
        col_type: "icon_small_4"
    });
    d.push({
        title: '导入',
        url: $("","聚影口令").input(()=>{
            if(input==""){
                return 'toast://不能为空';
            }
            if(input.indexOf('@import=js:')>-1){
                input = input.split('@import=js:')[0].replace('云口令：','').trim();
            }
            require(config.聚影.replace(/[^/]*$/,'') + 'SrcJySet.js');
            return JYimport(input);
        }),
        img: getIcon("点播-接口导入.svg"),//"https://hikerfans.com/tubiao/more/43.png",
        col_type: "icon_small_4"
    });
    let pastes = getPastes();
    if(guanliType=="jk"){
        pastes.push('云口令文件');
    }
    
    let datalist = getDatas(guanliType);
    if(getMyVar('onlyStopJk')){
        datalist = datalist.filter(item => item.stop);
    }
    let selectgroup = guanliType=='jk'?getMyVar("Src_Jy_jiekouGroup",""):"";
    let jkdatalist = getGroupLists(datalist, selectgroup);

    if(getMyVar("seacrhJiekou")){
        jkdatalist = jkdatalist.filter(it=>{
            return it.name.indexOf(getMyVar("seacrhJiekou"))>-1;
        })
    }
    let yxdatalist = jkdatalist.filter(it=>{
        return !it.stop;
    });
    storage0.putMyVar("jkdatalist", jkdatalist);
    d.push({
        title: '分享',
        url: yxdatalist.length==0?'toast://有效数据为空，只能单个分享':$(pastes,2).select((lx)=>{
            require(config.聚影.replace(/[^/]*$/,'') + 'SrcJySet.js');
            return JYshare(lx, input);
        }, guanliType),
        img: getIcon("点播-接口分享.svg"),//"https://hikerfans.com/tubiao/more/3.png",
        col_type: "icon_small_4",
        extra: {
            longClick: [{
                title: '单接口分享剪贴板：' + getItem("sharePaste","自动选择"),
                js: $.toString(() => {
                    let pastes = getPastes();
                    pastes.unshift('自动选择');
                    return $(pastes,2,'指定单接口分享时用哪个剪贴板').select(() => {
                        if(input=="自动选择"){
                            clearItem("sharePaste");
                        }else{
                            setItem("sharePaste", input);
                        }
                        refreshPage(false);
                        return 'toast://单接口分享剪贴板已设置为：' + input;
                    })
                })
            }]
        }
    });
    d.push({
        col_type: "line"
    });
    
    d.push({
        title: "🔍",
        url: $.toString(() => {
            putMyVar("seacrhJiekou",input);
            refreshPage(false);
        }),
        desc: "搜你想要的...",
        col_type: "input",
        extra: {
            defaultValue: getMyVar('seacrhJiekou',''),
            titleVisible: true,
            onChange: $.toString(() => {
                if(input==""){
                    clearMyVar("seacrhJiekou");
                }
            })
        }
    });
    if(guanliType=='jk' && datalist.length){
        let sx = [];
        let selectkeys = getJkTags(datalist);
        selectkeys.forEach(it=>{
            sx.push({
                title: it,
                url: $('#noLoading#').lazyRule((it) => {
                    putMyVar("seacrhJiekou", it);
                    refreshPage(false);
                    return "hiker://empty";
                },it),
                col_type: 'scroll_button'
            })
        })
        if(sx.length>0){
            sx.unshift({
                title: "清除",
                url: !getMyVar("seacrhJiekou")?"hiker://empty":$('#noLoading#').lazyRule(() => {
                    clearMyVar("seacrhJiekou");
                    refreshPage(false);
                    return "hiker://empty";
                }),
                col_type: 'scroll_button'
            })
        }
        d = d.concat(sx);
        d.push({    
            col_type: "blank_block"
        });
        
        let groupNames = getJiekouGroups(datalist);
        groupNames.unshift("全部");
        let color = getItem("主题颜色","#6dc9ff");
        let lockgroups = Juconfig["lockgroups"] || [];
        groupNames.forEach(it =>{
            let obj = {
                title: (getMyVar("Src_Jy_jiekouGroup","全部")==it?`““””<b><span style="color: `+color+`">`+it+`</span></b>`:it) + (lockgroups.indexOf(it)>-1?"🔒":""),
                url: $('#noLoading#').lazyRule((it) => {
                    if(getMyVar("Src_Jy_jiekouGroup")!=it){
                        putMyVar("Src_Jy_jiekouGroup",it);
                        clearMyVar("seacrhJiekou");
                        refreshPage(false);
                    }
                    return "hiker://empty";
                },it),
                col_type: 'scroll_button',
                extra: {
                    backgroundColor: getMyVar("Src_Jy_jiekouGroup","全部")==it?"#20" + color.replace('#',''):""
                }
            }
            
            if(it == "全部"){
                obj.extra.longClick = [{
                    title: "列表排序：" + getItem("sourceListSort", "更新时间"),
                    js: $.toString(() => {
                        return $(["更新时间","接口名称","使用频率"], 1).select(() => {
                            setItem("sourceListSort", input);
                            refreshPage(false);
                        })
                    })
                }]
            }else{
                obj.extra.longClick = [{
                    title: lockgroups.indexOf(it)>-1?"解锁":"加锁",
                    js: $.toString((it) => {
                        require(config.聚影.replace(/[^/]*$/,'') + 'SrcJyPublic.js');
                        let lockgroups = Juconfig["lockgroups"] || [];
                        if(lockgroups.indexOf(it)>-1){
                            const hikerPop = $.require(config.聚影.replace(/[^/]*$/,'') + 'plugins/hikerPop.js');
                            if (hikerPop.canBiometric() !== 0) {
                                return "toast://无法调用生物学验证";
                            }
                            lockgroups = lockgroups.filter(item => item !== it);
                            let pop = hikerPop.checkByBiometric(() => {
                                Juconfig["lockgroups"] = lockgroups;
                                writeFile(cfgfile, JSON.stringify(Juconfig));
                                refreshPage(false);
                            });
                        }else{
                            lockgroups.push(it);
                            Juconfig["lockgroups"] = lockgroups;
                            writeFile(cfgfile, JSON.stringify(Juconfig));
                            refreshPage(false);
                        }
                    },it)
                }]
            }
            
            d.push(obj);
        })
    }
    if(getMyVar('批量选择模式')){
        d.push({
            col_type: "blank_block"
        });
        d.push({
            title: "反向选择",
            url: $('#noLoading#').lazyRule((jkdatalist) => {
                jkdatalist = JSON.parse(base64Decode(jkdatalist));
                require(config.聚影.replace(/[^/]*$/,'') + 'SrcJyPublic.js');
                duoselect(jkdatalist);
                return "toast://已反选";
            },base64Encode(JSON.stringify(jkdatalist))),
            col_type: 'scroll_button'
        })
        d.push({
            title: "删除所选",
            url: $('#noLoading#').lazyRule(() => {
                let duoselect = storage0.getMyVar('duoselect') || [];
                if(duoselect.length==0){
                    return "toast://未选择";
                }
                return $("确定要删除选择的"+duoselect.length+"个接口？").confirm((duoselect)=>{
                    require(config.聚影.replace(/[^/]*$/,'') + 'SrcJyPublic.js');
                    deleteData(getMyVar('guanli', 'jk'), duoselect);
                    refreshPage(false);
                    return 'toast://已删除选择';
                }, duoselect)
            }),
            col_type: 'scroll_button'
        })
        if(guanliType=='jk'){
            d.push({
                title: "调整分组",
                url: $('#noLoading#').lazyRule(()=>{
                        let duoselect = storage0.getMyVar('duoselect') || [];
                        if(duoselect.length>0){
                            return $("","选定的"+duoselect.length+"个接口新分组名").input((duoselect)=>{
                                input = input.trim();
                                if(input==""){
                                    return "hiker://empty";
                                }else if(input=="全部"){
                                    return "toast://分组名不能为：全部";
                                }else if(input.includes('[') || input.includes(']')){
                                    return "toast://分组名不能包含：[]";
                                }
                                require(config.聚影.replace(/[^/]*$/,'') + 'SrcJyPublic.js');
                                var filepath = getFile(getMyVar('guanli', 'jk'));
                                var datafile = fetch(filepath);
                                eval("var datalist=" + datafile+ ";");
                                datalist.forEach(data=>{
                                    if(duoselect.some(item => data.url==item.url)){
                                        if(input){
                                            data.group  = input;
                                        }else{
                                            delete data.group;
                                        }
                                    }
                                })
                                writeFile(filepath, JSON.stringify(datalist));
                                clearMyVar('duoselect');
                                refreshPage(false);
                                return "toast://已批量调整接口分组";
                            }, duoselect)
                        }else{
                            return "toast://请选择";
                        }
                    }),
                col_type: "scroll_button"
            });
            d.push({
                title: "禁用所选",
                url: $('#noLoading#').lazyRule(() => {
                    let duoselect = storage0.getMyVar('duoselect') || [];
                    if(duoselect.length==0){
                        return "toast://未选择";
                    }
                    return $("确定要禁用选择的"+duoselect.length+"个接口？").confirm((duoselect)=>{
                        require(config.聚影.replace(/[^/]*$/,'') + 'SrcJyPublic.js');
                        let sm = dataHandle(getMyVar('guanli', 'jk'), duoselect, '禁用');
                        refreshPage(false);
                        return 'toast://' + sm;
                    },duoselect)
                }),
                col_type: 'scroll_button'
            })
            d.push({
                title: "启用所选",
                url: $('#noLoading#').lazyRule(() => {
                    let duoselect = storage0.getMyVar('duoselect') || [];
                    if(duoselect.length==0){
                        return "toast://未选择";
                    }
                    return $("确定要启用选择的"+duoselect.length+"个接口？").confirm((duoselect)=>{
                        require(config.聚影.replace(/[^/]*$/,'') + 'SrcJyPublic.js');
                        let sm = dataHandle(getMyVar('guanli', 'jk'), duoselect, '启用');
                        refreshPage(false);
                        return 'toast://' + sm;
                    },duoselect)
                }),
                col_type: 'scroll_button'
            })

            d.push({
                title: "批量检测",
                url: $('#noLoading#').lazyRule((admin) => {
                    let nowtime = Date.now();
                    let checkSourcetime = getItem('checkSourcetime','0');
                    let oldtime = parseInt(checkSourcetime.split('|')[0]);
                    let h = checkSourcetime=="0"||admin=="1"?0:parseInt(checkSourcetime.split('|')[1]);
                    if (nowtime < (oldtime+h*60*60*1000)) {
                        return "toast://下次允许批量检测时间\n" + $.dateFormat(oldtime+h*60*60*1000, "yyyy-MM-dd HH:mm:ss");
                    }
                    let duoselect = storage0.getMyVar('duoselect') || [];
                    duoselect = duoselect.filter(v=>!v.stop);
                    if(duoselect.length==0){
                        return "toast://未选择";
                    }
                    if(getMyVar("批量检测_线程开始")=="1"){
                        return "toast://上一个任务还没有结束，请等待.";
                    }
                    storage0.putMyVar('批量检测_待检列表', duoselect);//写入待检测源

                    return $("hiker://empty#noRecordHistory##noHistory##noRefresh#").rule(() => {
                        addListener("onClose", $.toString(() => {
                            putMyVar("批量检测_退出页面","1");
                            let nowtime = Date.now();
                            setItem('checkSourcetime', nowtime+'|'+getMyVar("批量检测_下次时间", "0"));
                            clearMyVar("批量检测_下次时间");
                            clearMyVar("批量检测_待检列表");
                            clearMyVar("批量检测_中止线程");
                            clearMyVar("批量检测_复检模式");
                            clearMyVar("批量检测_失败列表");
                            clearMyVar("批量检测_当前进度");
                            clearMyVar("批量检测_复检列表");
                            clearMyVar('批量选择模式');
                            clearMyVar('duoselect');
                            refreshPage(true);
                        }));
                        function testSource() {
                            return $('#noLoading#').lazyRule(()=>{
                                if(getMyVar("批量检测_线程开始")=="1"){
                                    return "toast://上一个任务还没有结束，请等待.";
                                }
                                if(getMyVar("批量检测_当前进度")=="0"){
                                    return "toast://检测项目已结束";
                                }

                                require(config.聚影.replace(/[^/]*$/,'') + 'SrcJyPublic.js');
                                require(config.聚影.replace(/[^/]*$/,'') + 'SrcJyData.js');
                                let schedule = getMyVar("批量检测_当前进度","1");

                                let task = function (data) {
                                    let desc = data.message || '';
                                    let error = 0;
                                    if(schedule=="1"){
                                        if(!data.onlysearch){
                                            let yidata = getYiData(data, 1);
                                            if(yidata.fllists && yidata.fllists.length>0){
                                                if(yidata.vodlists && yidata.vodlists.length>1){
                                                    data.erurl = yidata.vodlists[0].vod_url;
                                                    data.ername = yidata.vodlists[0].vod_name;
                                                    desc += "一级列表检测正常";
                                                }else{
                                                    error = 1;
                                                    desc += "一级列表检测失败";
                                                }
                                            }else{
                                                error = 1;
                                                desc += "一级列表检测失败";
                                            }
                                        }else{
                                            desc += "仅搜索源，跳过一级列表检测";
                                        }
                                    }else if(schedule=="2"){
                                        if(data.searchable!='0'){
                                            let ssdata = getSsData("我的", data, 1);
                                            if(ssdata.error){
                                                desc += "\n搜索 ‘我的’ 检测出错";
                                                error = 1;
                                            }else if(ssdata.vodlists.length>0 && !data.erurl){
                                                data.erurl = ssdata.vodlists[0].vod_url;
                                                data.ername = ssdata.vodlists[0].vod_name;
                                                desc += "\n搜索 ‘我的’ 结果获取到>" + ssdata.vodlists.length;
                                            }
                                        }else{
                                            desc += "不支持搜索源，跳过搜索检测";
                                        }
                                    }else if(schedule=="3"){
                                        if(data.erurl){
                                            let erdata = getErData(data, data.erurl);
                                            let lists = erdata.lists || [];
                                            if(lists.length==0){
                                                error = 1;
                                                desc += "\n获取 ‘"+data.ername+"’ 选集列表失败";
                                            }else{
                                                desc += "\n获取 ‘"+data.ername+"’ 选集列表成功";
                                            }
                                        }else{
                                            desc += "\n未获取到二级链接，跳过二级选集检测";
                                        }
                                    }
                                    data.message = desc;

                                    return {error:error, data:data}
                                }

                                showLoading("批量检测中...");
                                let checkSourceList = storage0.getMyVar("批量检测_待检列表") || [];
                                let list = checkSourceList.filter(v=>{
                                    return schedule=="3"?v.erurl:v.url;
                                }).map((item) => {
                                    return {
                                        func: task,
                                        param: item,
                                        id: item.url
                                    }
                                });

                                clearMyVar("批量检测_退出页面");
                                putMyVar("批量检测_下次时间", "24");
                                putMyVar("批量检测_线程开始", "1");
                                log("批量检测_线程开始");

                                let success = 0;
                                let checknumber = list.length;
                                let failSourceList = storage0.getMyVar("批量检测_失败列表") || [];

                                if(list.length>0){
                                    be(list, {
                                        func: function (obj, id, error, taskResult) {
                                            if(taskResult.error){
                                                let data = taskResult.data;
                                                failSourceList.push(data);
                                                
                                                addItemBefore("testSource2", {
                                                    title: data.name,
                                                    desc: data.message,
                                                    url: $("hiker://empty#noRecordHistory##noHistory#").rule((data) => {
                                                        setPageTitle(data.name+"-接口测试");
                                                        require(config.聚影.replace(/[^/]*$/,'') + 'SrcJuying.js');
                                                        dianboyiji(data);
                                                    }, data),
                                                    col_type: "text_1",
                                                    extra: {
                                                        id: "failSource-" + data.url,
                                                        cls: "failSource",
                                                        longClick: [{
                                                            title: "禁用",
                                                            js: $.toString((data) => {
                                                                if(getMyVar("批量检测_线程开始")=="1"){
                                                                    return "toast://等待任务结束或中止线程";
                                                                }
                                                                let failSource = storage0.getMyVar("批量检测_失败列表") || [];
                                                                let index = failSource.indexOf(data);
                                                                if(index>-1){
                                                                    failSource.splice(index, 1);
                                                                    storage0.putMyVar("批量检测_失败列表", failSource);
                                                                }
                                                                deleteItem("failSource-" + data.url);
                                                                require(config.聚影.replace(/[^/]*$/,'') + 'SrcJyPublic.js');
                                                                let sm = dataHandle('jk', data, "禁用");
                                                                return "toast://" + sm;
                                                            }, data)
                                                        },{
                                                            title: "删除",
                                                            js: $.toString((data) => {
                                                                if(getMyVar("批量检测_线程开始")=="1"){
                                                                    return "toast://等待任务结束或中止线程";
                                                                }
                                                                let failSource = storage0.getMyVar("批量检测_失败列表") || [];
                                                                let index = failSource.indexOf(data);
                                                                if(index>-1){
                                                                    failSource.splice(index, 1);
                                                                    storage0.putMyVar("批量检测_失败列表", failSource);
                                                                }
                                                                deleteItem("failSource-" + data.url);
                                                                require(config.聚影.replace(/[^/]*$/,'') + 'SrcJyPublic.js');
                                                                deleteData('jk', data);
                                                                return "toast://已删除";
                                                            }, data)
                                                        },{
                                                            title: "保留",
                                                            js: $.toString((data) => {
                                                                if(getMyVar("批量检测_线程开始")=="1"){
                                                                    return "toast://等待任务结束或中止线程";
                                                                }
                                                                let failSource = storage0.getMyVar("批量检测_失败列表") || [];
                                                                let index = failSource.indexOf(data);
                                                                if(index>-1){
                                                                    failSource.splice(index, 1);
                                                                    storage0.putMyVar("批量检测_失败列表", failSource);
                                                                }
                                                                deleteItem("failSource-" + data.url);
                                                                return "toast://已保留，不处理";
                                                            }, data)
                                                        }]
                                                    }
                                                });
                                            }else{
                                                success++;
                                                let index = checkSourceList.indexOf(checkSourceList.filter(d => taskResult.data.url==d.url )[0]);
                                                checkSourceList[index] = taskResult.data;
                                            }
                                            
                                            updateItem("testSource", {
                                                title: (failSourceList.length+success) + "/" + checknumber + "，成功：" + success + "，失败：" + failSourceList.length,
                                                desc: "点击中止线程，停止批量检测",
                                                url: $().lazyRule(()=>{
                                                    putMyVar("批量检测_中止线程","1");
                                                    showLoading("正在拦截线程");
                                                    return "toast://正在拦截线程，停止批量检测";
                                                })
                                            });
                                            //log(id + ">>>" +error);

                                            if(getMyVar("批量检测_退出页面")=="1" || getMyVar("批量检测_中止线程")=="1"){
                                                log("批量检测_中止线程");
                                                return "break";
                                            }
                                        },
                                        param: {
                                        }
                                    })
                                }
                                
                                log("批量检测_线程结束");
                                clearMyVar("批量检测_线程开始"); 
                                clearMyVar("批量检测_中止线程");
                                
                                if(!getMyVar("批量检测_退出页面")){
                                    if(failSourceList.length>0){
                                        addItemAfter("testSource2", {
                                            title: "批量删除失效",
                                            url: $("#noLoading#").lazyRule((failnum) => {
                                                return $("确认要删除失败"+failnum+"个接口？").confirm(()=>{
                                                    let failSourceList = storage0.getMyVar("批量检测_失败列表") || [];
                                                    let checkSourceList = storage0.getMyVar("批量检测_待检列表") || [];
                                                    failSourceList.forEach(it=>{
                                                        let index = checkSourceList.indexOf(checkSourceList.filter(d => it.url==d.url )[0]);
                                                        checkSourceList.splice(index, 1);
                                                        deleteItem("failSource-" + it.url);
                                                    })
                                                    storage0.putMyVar("批量检测_待检列表",checkSourceList);

                                                    require(config.聚影.replace(/[^/]*$/,'') + 'SrcJyPublic.js');
                                                    deleteData("jk", failSourceList);
                                                    clearMyVar("批量检测_失败列表");
                                                    deleteItem("deleteAllFail");
                                                    return "toast://已批量删除";
                                                })
                                            },failSourceList.length),
                                            col_type : "text_center_1",
                                            extra: {
                                                id: "deleteAllFail"
                                            }
                                        })
                                        storage0.putMyVar("批量检测_失败列表", failSourceList);
                                    }
                                    
                                    storage0.putMyVar("批量检测_待检列表",checkSourceList);
                                    updateItem("testSource", {
                                        desc: "",
                                        url: "hiker://empty"
                                    });
                                    let checkFailSource = {
                                        title: "针对失败源进行复检",
                                        url: $("#noLoading#").lazyRule(() => {
                                            let recheckList = storage0.getMyVar("批量检测_复检列表") || [];
                                            let failSourceList = storage0.getMyVar("批量检测_失败列表") || [];
                                            failSourceList.forEach(it=>{
                                                if(recheckList.indexOf(it.url)==-1){
                                                    recheckList.push(it.url);
                                                }
                                            })
                                            let checkSourceList = storage0.getMyVar("批量检测_待检列表") || [];
                                            checkSourceList = checkSourceList.filter(v=>recheckList.indexOf(v.url)>-1);
                                            if(checkSourceList.length==0){
                                                deleteItem("recheckSource");
                                                return "toast://没有需复检的源";
                                            }
                                            storage0.putMyVar("批量检测_待检列表", checkSourceList);
                                            clearMyVar("批量检测_失败列表");
                                            clearMyVar("批量检测_当前进度");
                                            clearMyVar("批量检测_复检列表");
                                            refreshPage(true);
                                            return "hiker://empty";
                                        }),
                                        col_type : "text_center_1",
                                        extra: {
                                            id: "recheckSource"
                                        }
                                    }
                                    let schedule = getMyVar("批量检测_当前进度","1");
                                    if(schedule=="3"){
                                        putMyVar("批量检测_当前进度","0");
                                        updateItem("schedule_er", {title:"👌二级选集"});

                                        addItemAfter("testSource2", checkFailSource);
                                    }else{
                                        addItemAfter("testSource2", {
                                            title: "进行下一项检测",
                                            url: $("#noLoading#").lazyRule(() => {
                                                let schedule = getMyVar("批量检测_当前进度","1");
                                                if(schedule=="1"){
                                                    putMyVar("批量检测_当前进度","2");
                                                }else if(schedule=="2"){
                                                    putMyVar("批量检测_当前进度","3");
                                                }
                                                let recheckList = storage0.getMyVar("批量检测_复检列表") || [];
                                                let failSourceList = storage0.getMyVar("批量检测_失败列表") || [];
                                                failSourceList.forEach(it=>{
                                                    if(recheckList.indexOf(it.url)==-1){
                                                        recheckList.push(it.url);
                                                    }
                                                })
                                                storage0.putMyVar("批量检测_复检列表", recheckList);
                                                clearMyVar("批量检测_失败列表");
                                                refreshPage(true);
                                                return "hiker://empty";
                                            }),
                                            col_type : "text_center_1",
                                            extra: {
                                                id: "nextCheck"
                                            }
                                        })
                                    }
                                }

                                hideLoading();
                                return "toast://测试结束";
                            })
                        }
                        let checkSourceList = storage0.getMyVar("批量检测_待检列表") || [];
                        let d = [];
                        d.push({
                            title: "检测项目",
                            col_type: "rich_text"
                        })
                        let schedule = getMyVar("批量检测_当前进度","1");
                        d.push({
                            title: (schedule=="1"?"👉":"👌") + '一级列表',
                            col_type: 'text_3',
                            url: "hiker://empty"
                        });
                        d.push({
                            title: (schedule=="1"?"":schedule=="2"?"👉":"👌") + '搜索测试',
                            col_type: 'text_3',
                            url: $().lazyRule(()=>{
                                putMyVar("批量检测_当前进度","2");
                                refreshPage();
                                return "toast://跳过一级检测";
                            })
                        });
                        d.push({
                            title: (schedule=="1"||schedule=="2"?"":schedule=="3"?"👉":"👌") + '二级选集',
                            col_type: 'text_3',
                            url: "hiker://empty",
                            extra: {
                                id: "schedule_er"
                            }
                        });
                        d.push({
                            col_type: "line_blank"
                        });
                        d.push({
                            title: "待检测源：" + checkSourceList.length,
                            url: testSource(),
                            desc: "点击开始检测",
                            col_type : "text_center_1",
                            extra: {
                                id: "testSource"
                            }
                        })
                        d.push({
                            col_type: "blank_block",
                            extra: {
                                id: "testSource2"
                            }
                        });

                        setResult(d);
                    })
                }, Juconfig["checkSourceAdmin"] || 0),
                col_type: 'scroll_button',
                extra: {
                    longClick: [{
                        title: "清除",
                        js: $.toString(() => {
                            clearItem('checkSourcetime');
                            return "toast://可以了"
                        })
                    }]
                }
            })
        }else if(guanliType=='jx'){
            d.push({
                title: "重置排序",
                url: $('#noLoading#').lazyRule(() => {
                    let duoselect = storage0.getMyVar('duoselect') || [];
                    if(duoselect.length==0){
                        return "toast://未选择";
                    }
                    return $("确定要重置"+duoselect.length+"个解析的排序？").confirm((duoselect)=>{
                        require(config.聚影.replace(/[^/]*$/,'') + 'SrcJyPublic.js');
                        let sm = dataHandle('jx', duoselect, '重置排序');
                        refreshPage(false);
                        return 'toast://' + sm;
                    },duoselect)
                }),
                col_type: 'scroll_button'
            })
        }
    }

    jkdatalist.forEach(it => {
        let selectmenu,datatitle,datadesc;
        if(guanliType=="jk"){
            datadesc = it.url;
            selectmenu = ["分享","编辑", "删除", it.stop?"启用":"禁用", "置顶", "测试"];
        }else{
            datadesc = it.ext&&it.ext.flag?it.ext.flag.join(','):"";
            selectmenu = ["分享","编辑", "删除", it.stop?"启用":"禁用"];
        }
        datatitle = getDataTitle(it);

        d.push({
            title: it.stop?colorTitle(datatitle, '#f20c00'):datatitle,
            url: getMyVar('批量选择模式')?$('#noLoading#').lazyRule((data) => {
                data = JSON.parse(base64Decode(data));
                require(config.聚影.replace(/[^/]*$/,'') + 'SrcJyPublic.js');
                duoselect(data);
                return "hiker://empty";
            },base64Encode(JSON.stringify(it))):$(selectmenu, 2).select((data) => {
                data = JSON.parse(base64Decode(data));
                if (input == "分享") {
                    require(config.聚影.replace(/[^/]*$/,'') + 'SrcJySet.js');
                    return JYshare(getMyVar('guanli', 'jk'), getItem("sharePaste",""), data);
                } else if (input == "编辑") {
                    return $('hiker://empty#noRecordHistory##noHistory#').rule((data) => {
                        require(config.聚影.replace(/[^/]*$/,'') + 'SrcJySet.js');
                        if(getMyVar('guanli', 'jk')=="jk"){
                            jiekou(data);
                        }else{
                            jiexi(data);
                        }
                    }, data)
                } else if (input == "删除") {
                    return $("确定删除："+data.name).confirm((data)=>{
                        require(config.聚影.replace(/[^/]*$/,'') + 'SrcJyPublic.js');
                        deleteData(getMyVar('guanli', 'jk'), data);
                        refreshPage(false);
                        return 'toast://已删除:'+data.name;
                    }, data)
                } else if (input == "测试") {
                    return $("hiker://empty#noRecordHistory##noHistory#").rule((data) => {
                        setPageTitle(data.name+"-接口测试");
                        require(config.聚影.replace(/[^/]*$/,'') + 'SrcJuying.js');
                        dianboyiji(data);
                    }, data);
                } else {//置顶、禁用、启用
                    if(input == "置顶" && getItem("sourceListSort", "更新时间") != "更新时间"){
                        return "toast://无效操作，接口列表排序方式为：" + getItem("sourceListSort");
                    }
                    require(config.聚影.replace(/[^/]*$/,'') + 'SrcJyPublic.js');
                    let sm = dataHandle(getMyVar('guanli', 'jk'), data, input);
                    refreshPage(false);
                    return 'toast://' + sm;
                }
            }, base64Encode(JSON.stringify(it))),
            desc: '““””<small><font color=grey>'+datadesc+'</font></small>',
            col_type: "text_1",
            extra: {
                id: it.url
            }
        });
    })
    d.push({
        title: "‘‘’’<small><font color=#f20c00>当前接口数：" + jkdatalist.length + "，总有效数："+yxdatalist.length+"</font></small>",
        url: 'hiker://empty',
        col_type: 'text_center_1'
    });
    setResult(d);
    if(getMyVar('批量选择模式')){
        let duoselect = storage0.getMyVar('duoselect') || [];
        if(duoselect.length>0){
            duoselect.forEach(data=>{
                updateItem(data.url, {title: colorTitle(getDataTitle(data), '#3CB371')});
            }) 
        }
    }
}

function getapitype(apiurl) {
    if(apiurl){
        if(apiurl.includes('.vod')){
            return "v1";
        }else if(apiurl.includes('/app/')){
            return "app";
        }else if(apiurl.includes('app.php')){
            return "v2";
        }else if(/iptv|Chengcheng/.test(apiurl)){
            return "iptv";
        }else if(apiurl.includes('provide/vod/')){
            return "cms";
        }else{
            return "";
        }
    }else{
        return "";
    }
}

//接口保存
function jiekousave(urls, mode) {
    if(urls.length==0){return 0;}
    let num = 0;
    try{
        let datalist = [];
        let sourcedata = fetch(jkfile);
        if(sourcedata != ""){
            try{
                eval("datalist=" + sourcedata+ ";");
            }catch(e){}
        }
        if(mode==2){//全量模式时，先删除本地
            for(let i=0;i<datalist.length;i++){
                if(datalist[i].retain!=1){
                    if(datalist[i].url.startsWith('hiker://files/data/')){
                        deleteFile(datalist[i].url);
                    }
                    datalist.splice(i,1);
                    i = i - 1;
                }
            }
        }
        let olddatanum = datalist.length;

        urls.forEach(it=>{
            
            if(it.oldurl || mode==1){//覆盖已存在接口
                for(let i=0;i<datalist.length;i++){
                    if(datalist[i].url==it.url||datalist[i].url==it.oldurl){
                        datalist.splice(i,1);
                        break;
                    }
                }
            }

            if(it.url.startsWith(cachepath)){//缓存的数据文件转到data目录
                if(fileExist(it.url)){
                    let urlfile = jkfilespath + it.url.substr(it.url.lastIndexOf('/')+1);
                    let urlcontent = fetch(it.url);
                    if(it.type=="py"){
                        urlcontent = urlcontent.replace(/Cryptodome/g, "Crypto");
                    }
                    writeFile(urlfile, urlcontent);
                    it.url = urlfile;
                }else{
                    delete it['url'];
                }
            }else if(it.extstr){//带数据内容的保存到data目录
                writeFile(it.url, it.extstr);
            }else if(/^hiker|^file/.test(it.url) && !fileExist(it.url) && it.ext){
                if($.type(it.ext)=="string"){//本地数据文件转到data目录
                    if(it.ext.startsWith('file://') && fileExist(it.ext)){
                        let urlfile = jkfilespath + it.type + '_' + it.name + '.json';
                        writeFile(urlfile, fetch(it.ext));
                        it.url = urlfile;
                    }
                }else if($.type(it.ext)=="object"){//对象数据转存到data目录
                    let urlfile = jkfilespath + it.type + '_' + it.name + '.json';
                    writeFile(urlfile, JSON.stringify(it.ext));
                    it.url = urlfile;
                }else{
                    delete it['url'];
                }
            }

            it.name = it.name.replace('(drpy_t3)','').replace(/(?:[\u2700-\u27bf]|(?:\ud83c[\udde6-\uddff]){2}|[\ud800-\udbff][\udc00-\udfff]|[\u0023-\u0039]\ufe0f?\u20e3|\u3299|\u3297|\u303d|\u3030|\u24c2|\ud83c[\udd70-\udd71]|\ud83c[\udd7e-\udd7f]|\ud83c\udd8e|\ud83c[\udd91-\udd9a]|\ud83c[\udde6-\uddff]|\ud83c[\ude01-\ude02]|\ud83c\ude1a|\ud83c\ude2f|\ud83c[\ude32-\ude3a]|\ud83c[\ude50-\ude51]|\u203c|\u2049|[\u25aa-\u25ab]|\u25b6|\u25c0|[\u25fb-\u25fe]|\u00a9|\u00ae|\u2122|\u2139|\ud83c\udc04|[\u2600-\u26FF]|\u2b05|\u2b06|\u2b07|\u2b1b|\u2b1c|\u2b50|\u2b55|\u231a|\u231b|\u2328|\u23cf|[\u23e9-\u23f3]|[\u23f8-\u23fa]|\ud83c\udccf|\u2934|\u2935|[\u2190-\u21ff])|\(XPF\)|\(萝卜\)|\(神马\)|\(切\)|\(聚\)|\(优\)|\(神马\)|\(XB\)|\(SP\)|\(XP\)|[\x00-\x1F\x7F]/g,'');
            if(it.type=="cms"){
                it.url = it.url.replace('?ac=list','').replace('/vod?','/vod');//修正一下cms奇怪链接
            }

            function checkitem(item) {
                return item.url==it.url;
            }
            
            if(!datalist.some(checkitem)&&it.name&&it.url&&it.type){
                //if(!it.oldurl && olddatanum>0){
                //    it.group = it.group || "新导入";
                //}
                delete it['oldurl'];
                delete it['extstr'];
                if(it.ext && $.type(it.ext)=="string" && /^hiker|^file/.test(it.ext)){
                    if(!fileExist(it.ext)){
                        delete it['ext'];
                    }
                }

                datalist.push(it);
                num = num + 1;
            }
        })
        setJkSort(datalist, {fail: 0});
        if(num>0){writeFile(jkfile, JSON.stringify(datalist));}
    } catch (e) {
        log("导入失败：" + e.message + " 错误行#" + e.lineNumber); 
        return -1;
    }
    return num;
}
//解析保存
function jiexisave(urls, mode) {
    if(urls.length==0){return 0;}
    let num = 0;
    try{
        let datalist = [];
        let sourcedata = fetch(jxfile);
        if(sourcedata != ""){
            try{
                eval("datalist=" + sourcedata+ ";");
            }catch(e){}
        }
        if(mode==2){
            for(let i=0;i<datalist.length;i++){
                if(datalist[i].retain!=1){
                    datalist.splice(i,1);
                    i = i - 1;
                }
            }
        }
        
        urls.forEach(it=>{
            if(it.oldurl || mode==1){
                for(let i=0;i<datalist.length;i++){
                    if(datalist[i].url==it.url||datalist[i].url==it.oldurl){
                        datalist.splice(i,1);
                        break;
                    }
                }
            }

            function checkitem(item) {
                return item.url==it.url;
            }

            if(!datalist.some(checkitem)&&it.url&&it.name&&/^http|^functio/.test(it.url)){
                delete it['oldurl'];
                datalist.push(it);
                num = num + 1;
            }
        })
        if(num>0){writeFile(jxfile, JSON.stringify(datalist));}
    } catch (e) {
        log("导入失败：" + e.message + " 错误行#" + e.lineNumber); 
        num = -1;
    }
    return num;
}
//获取接口数组
function getGroupNames() {
    let gnames = [];
    getDatas("jk", 1).forEach(it => {
        if (it.group && gnames.indexOf(it.group) == -1) {
            gnames.push(it.group);
        }
    })
    return gnames;
}
//接口新增或编辑
function jiekou(data) {
    addListener("onClose", $.toString(() => {
        clearMyVar('apiname');
        clearMyVar('apiurl');
        clearMyVar('apitype');
        clearMyVar('apigroup');
        clearMyVar('apicate');
        clearMyVar('apidecrypt');
        clearMyVar('ishidecate');
        clearMyVar('isload');
        clearMyVar('isretain');
        clearMyVar('isSaveAs');
    }));

    var d = [];
    if(!data){
        setPageTitle("接口新增");
    }else{
        if(getMyVar('isload', '0')=="0"){
            setPageTitle("接口变更");
            putMyVar('apiname', data.name);
            putMyVar('apiurl', data.url);
            putMyVar('apitype', data.type);
            putMyVar('apigroup', data.group||"");
            putMyVar('apicate', data.categories?data.categories.join(","):"");
            putMyVar('apidecrypt', data.decrypt||"");
            putMyVar('isretain', data.retain||"");
            putMyVar('ishidecate', data.hidecate||"");
            putMyVar('isload', '1');
        }
    }
    d.push({
        title: 'apiname',
        col_type: 'input',
        desc: "接口名称",
        extra: {
            titleVisible: false,
            defaultValue: getMyVar('apiname', ''),
            onChange: 'putMyVar("apiname",input)'
        }
    });
    let keys = ["清除","[优]","[官]","[资]","[密]","[听]","[书]","[漫]","[盘]","[磁]"];
    keys.forEach(it=>{
        d.push({
            title: it,
            url: $('#noLoading#').lazyRule((it) => {
                let input = getMyVar('apiname', '').split('[')[0];
                if(it!="清除"){
                    input = input + it;
                }
                putMyVar("apiname", input);
                refreshPage(false);
                return "hiker://empty";
            },it),
            col_type: 'scroll_button'
        })
    })
    let apitype = getMyVar('apitype', '');
    d.push({
        title: data?'查看':'本地',
        col_type: 'input',
        desc: "接口地址",
        url: data?$.toString((data) => {
            let file = getMyVar('apiurl','');
            if(fileExist(file)){
                toast('如果有修改，接口不要点保存');
                let apiurl = getMyVar('apiurl','');
                let apitype = getMyVar('apitype', '');
                if(apiurl && apitype=="hipy_t3" && /^hiker|^file/.test(apiurl)){
                    //let {GM} = $.require(config.聚影.replace(/[^/]*$/,'') + 'plugins/globalmap.js');
                    let drpy = GM.defineModule("SrcJuDrpy", config.聚影.replace(/[^/]*$/,'') + "SrcJyDrpy.js").get(data);
                    let code = drpy.runMain("let main=" + $.toString((ext) => {
                        return () => getOriginalJs(request(ext, {
                            "method": "GET"
                        }));
                    }, apiurl));
                    writeFile(apiurl, code);
                }
                return "editFile://" + apiurl + "@js=back();";
            }else{
                return "toast://不存在，无法查看";
            }
        },data):$.toString(() => {
            if(MY_NAME=="海阔视界"&&getAppVersion()<5100){
                return "toast://软件版本过低";
            }
            return `fileSelect://`+$.toString(()=>{
                if(!MY_PATH){
                    return "toast://获取文件真实路径失败：不支持通过文件管理器获取，可手工填写文件路径";
                }
                putMyVar("apiurl", "file://" + MY_PATH);
                refreshPage();
                return "hiker://empty";
            })
        }),
        extra: {
            titleVisible: (data && /^hiker/.test(getMyVar('apiurl',''))) || (!data && /XPath|biubiu|XBPQ|XYQ|hipy_t3|py/.test(apitype))?true:false,
            defaultValue: getMyVar('apiurl',''),
            onChange: 'putMyVar("apiurl",input);'
        }
    });
    if(data && data.ext){
        d.push({
            title: data.ext,
            col_type: 'text_1',
            url: "hiker://empty"
        });
    }
    d.push({
        title: '类型：' + getMyVar('apitype', ''),
        col_type:'text_1',
        url:$(["v1","app","v2","iptv","cms","XPath","biubiu","XBPQ","XYQ","hipy_t3","hipy_t4","py","app类自动"],3).select(()=>{
            if(input=="app类自动"){
                clearMyVar('apitype');
            }else{
                putMyVar('apitype', input);
            }
            refreshPage(false);
            return'toast://已选择类型：' + input;
        })
    });
    
    let groupNames = getGroupNames();
    groupNames.push("自定义");
    groupNames.unshift("清除");
    d.push({
        title: '分组名称：' + getMyVar('apigroup', ''),
        col_type: 'text_1',
        url: $(groupNames, 2, "选择分组").select(() => {
            if(input=="自定义"){
                return $(getMyVar('apigroup', ''), "输入分组名称，为空则取类型").input(() => {
                    input = input.trim();
                    if(input==""){
                        return "hiker://empty";
                    }else if(input=="全部"){
                        return "toast://分组名不能为：全部";
                    }else if(input.includes('[') || input.includes(']')){
                        return "toast://分组名不能包含：[]";
                    }
                    putMyVar('apigroup', input);
                    refreshPage(false);
                    return 'toast://分组已设置为：' + input;
                })
            }else if(input=="清除"){
                putMyVar('apigroup', '');
                refreshPage(false);
                return 'toast://已清除分组';
            }else{
                putMyVar('apigroup', input);
                refreshPage(false);
            }
            return 'toast://分组已设置为：' + input;
        })
    });
    d.push({
        title: getMyVar('ishidecate')=="1"?'隐藏分类：是':'隐藏分类：否',
        col_type:'text_1',
        url:$('#noLoading#').lazyRule(()=>{
            if(getMyVar('ishidecate', '')!="1"){
                putMyVar('ishidecate', '1');
            }else{
                clearMyVar('ishidecate');
            }
            refreshPage(false);
            return 'toast://已切换';
        })
    });
    d.push({
        title: 'apicate',
        col_type: 'input',
        desc: getMyVar('ishidecate')=="1"?"设置需隐藏的分类名称，逗号分隔":"设置仅显示的分类名称，逗号分隔",
        extra: {
            titleVisible: false,
            defaultValue: getMyVar('apicate',''),
            onChange: 'putMyVar("apicate",input);'
        }
    });
    if(getMyVar('apitype', '')=='app'){
        d.push({
            title: 'decrypt',
            col_type: 'input',
            desc: "解密参数：key|iv|mode|padding",
            extra: {
                titleVisible: false,
                defaultValue: getMyVar('apidecrypt',''),
                onChange: 'putMyVar("apidecrypt",input);'
            }
        });
    }
    d.push({
        title: getMyVar('isretain')=="1"?'强制保留：是':'强制保留：否',
        desc: getMyVar('isretain')=="1"?'全量同步时保留此接口':'',
        col_type:'text_1',
        url:$('#noLoading#').lazyRule(()=>{
            if(getMyVar('isretain', '')!="1"){
                putMyVar('isretain', '1');
            }else{
                clearMyVar('isretain');
            }
            refreshPage(false);
            return 'toast://已切换';
        })
    });
    if(data){
        d.push({
            title: getMyVar('isSaveAs', '')!="1"?'保存方式：覆盖':'保存方式：另存',
            col_type: 'text_1',
            url: $('#noLoading#').lazyRule(()=>{
                if(getMyVar('isSaveAs', '')!="1"){
                    putMyVar('isSaveAs', '1');
                }else{
                    clearMyVar('isSaveAs');
                }
                refreshPage(false);
                return 'toast://已切换';
            })
        });
    }
    
    for (let i = 0; i < 10; i++) {
        d.push({
            col_type: "blank_block"
        })
    }
    
    if(data){
        d.push({
            title:'删除',
            col_type:'text_3',
            url: $("确定删除接口："+data.name).confirm((data)=>{
                require(config.聚影.replace(/[^/]*$/,'') + 'SrcJyPublic.js');
                deleteData('jk', data);
                back(true);
                return "toast://已删除";
            }, data)
        });   
    }else{
        d.push({
            title:'清空',
            col_type:'text_3',
            url:$("确定要清空上面填写的内容？").confirm(()=>{
                clearMyVar('apiname');
                clearMyVar('apiurl');
                clearMyVar('apitype');
                clearMyVar('apigroup');
                clearMyVar('apicate');
                clearMyVar('isretain');
                refreshPage(true);
                return "toast://已清空";
            })
        });
    }
    d.push({
        title:'保存',
        col_type:'text_3',
        url: $().lazyRule((data)=>{
            let apiurl = getMyVar('apiurl','').trim();
            if(!apiurl.startsWith('http') && !apiurl.startsWith('hiker://') && !apiurl.startsWith('file://')){
                return "toast://接口地址不正确";
            }
            require(config.聚影.replace(/[^/]*$/,'') + 'SrcJySet.js');
            let urls= [];
            
            let apiname = getMyVar('apiname','').trim();
            if(apiname&&apiurl){
                let apitype = getMyVar('apitype','');
                if(apitype.includes('自动')){
                    apitype = getapitype(apiurl);
                }
                if(!apitype){
                    return "toast://无法自动识别接口类型，请检查链接";
                }
                
                let urlfile = apiurl;
                let extfile;
                if(/XPath|biubiu|XBPQ|XYQ|hipy_t3|py/.test(apitype) && /^http|^file/.test(apiurl)){
                    extfile = apiurl;
                    urlfile = cachepath+apitype+"_"+extfile.substr(extfile.lastIndexOf('/') + 1);
                    if(extfile){
                        let contnet = getContnet(extfile);
                        if(contnet){
                            writeFile(urlfile, contnet);
                        }else{
                            return "toast://接口地址获取内容失败";
                        }
                    }
                }
                let arr = {"name": apiname, "type": apitype, "url": urlfile};
                let apigroup = getMyVar('apigroup');
                if(apigroup){
                    arr['group'] = apigroup;
                }
                let apicate = getMyVar('apicate','');
                if(apicate){
                    apicate = apicate.replace('，',',');
                    arr['categories'] = apicate.split(',').filter(v=>v);
                }
                let apidecrypt = getMyVar('apidecrypt','');
                if(apidecrypt){
                    arr['decrypt'] = apidecrypt;
                }
                let isretain = getMyVar('isretain')=="1"?1:0;
                if(isretain){
                    arr['retain'] = 1;
                }
                let ishidecate = getMyVar('ishidecate')=="1"?1:0;
                if(ishidecate){
                    arr['hidecate'] = 1;
                }
                if(data){
                    if(data.ext){
                        arr['ext'] = data.ext;
                    }
                    if(getMyVar('isSaveAs', '')!="1"){
                        arr['oldurl'] = data.url;
                    }
                }else if(extfile){
                    arr['ext'] = extfile;
                }
                urls.push(arr);
            }else{
                return "toast://无法保存，检查项目填写完整性";
            }
            if(urls.length==0){
                    return'toast://失败>无数据';
            }else{
                var jknum = jiekousave(urls);
                if(jknum<0){
                    return'toast://失败>内容异常';
                }else if(jknum==0&&urls.length==1){
                    return'toast://已存在';
                }else{
                    clearMyVar('Src_Jy_dianbo$classCache');
                    back(true);
                    if(urls.length==1){
                        return "toast://保存成功";
                    }else{
                        return "toast://合计："+urls.length+"，保存："+jknum;
                    }
                }
            } 
        }, data)
    });
    d.push({
        title:'测试',
        col_type:'text_3',
        url: $('#noLoading#').lazyRule((data)=>{
            if(!data){
                let apiurl = getMyVar('apiurl','').trim();
                if(!apiurl.startsWith('http') && !apiurl.startsWith('hiker://') && !apiurl.startsWith('file://')){
                    return "toast://接口地址不正确";
                }
                let apiname = getMyVar('apiname','').trim();
                if(apiname&&apiurl){
                    require(config.聚影.replace(/[^/]*$/,'') + 'SrcJySet.js');
                    let apitype = getMyVar('apitype','');
                    if(apitype.includes('自动')){
                        apitype = getapitype(apiurl);
                    }
                    if(!apitype){
                        return "toast://无法自动识别接口类型，请检查链接";
                    }
                    
                    let urlfile = apiurl;
                    let extfile;
                    if(/XPath|biubiu|XBPQ|XYQ|hipy_t3/.test(apitype) && /^http|^file/.test(apiurl)){
                        extfile = apiurl;
                        urlfile = cachepath+apitype+"_"+extfile.substr(extfile.lastIndexOf('/') + 1);
                    }
                    let arr = {"name": apiname, "type": apitype, "url": urlfile};
                    let apigroup = getMyVar('apigroup');
                    if(apigroup){
                        arr['group'] = apigroup;
                    }
                    let apicate = getMyVar('apicate','');
                    if(apicate){
                        apicate = apicate.replace('，',',');
                        arr['categories'] = apicate.split(',').filter(v=>v);
                    }
                    let ishidecate = getMyVar('ishidecate')=="1"?1:0;
                    if(ishidecate){
                        arr['hidecate'] = 1;
                    }
                    arr['ext'] = extfile;
                    data = arr;
                }else{
                    return "toast://无法测试，检查项目填写完整性";
                }
            }
            clearMyVar('Src_Jy_dianbo$classCache');
            return $("hiker://empty#noRecordHistory##noHistory#").rule((data) => {
                setPageTitle(data.name+"-接口测试");
                require(config.聚影.replace(/[^/]*$/,'') + 'SrcJuying.js');
                dianboyiji(data);
            }, data);
        }, data)
    }); 
    for (let i = 0; i < 10; i++) {
        d.push({
            col_type: "blank_block"
        })
    }
    setResult(d);
}
//解析新增或编辑
function jiexi(data) {
    addListener("onClose", $.toString(() => {
        clearMyVar('parsename');
        clearMyVar('parseurl');
        clearMyVar('parsetype');
        clearMyVar('parseext');
        clearMyVar('isretain');
        clearMyVar('isload');
    }));
    let d = [];
    if(!data){
        setPageTitle("♥解析管理-新增");
    }else{
        if(getMyVar('isload', '0')=="0"){
            setPageTitle("♥解析管理-变更");
            putMyVar('isretain', data.retain||"");
            putMyVar('isload', '1');
        }
    }
    d.push({
        title:'parseurl',
        col_type: 'input',
        desc: "解析名称",
        extra: {
            titleVisible: false,
            defaultValue: getMyVar('parsename', data?data.name:""),
            onChange: 'putMyVar("parsename",input)'
        }
    });
    d.push({
        title:'parseurl',
        col_type: 'input',
        desc: "链接地址",
        extra: {
            highlight: true,
            type: "textarea",
            titleVisible: false,
            defaultValue: getMyVar('parseurl', data?data.url:""),
            onChange: 'putMyVar("parseurl",input)'
        }
    });
    d.push({
        title: '是否为web嗅探解析：' + (getMyVar('parsetype', data?data.type.toString():'0')=="0"?"是":"否"),
        col_type: 'text_1',
        url:$().lazyRule(()=>{
            if(/^function/.test(getMyVar('parseurl',''))){
                putMyVar('parsetype','1');
            }else if(getMyVar('parsetype')=="1"){
                putMyVar('parsetype','0');
            }else{
                putMyVar('parsetype','1');
            }

            refreshPage(false);
            return "toast://是否为web解析，只用于判断进入video播放";
        })
    });
    d.push({
        title: getMyVar('isretain', '')!="1"?'强制保留：否':'强制保留：是',
        desc: getMyVar('isretain', '')!="1"?'':'全量更新时保留此接口',
        col_type:'text_1',
        url:$('#noLoading#').lazyRule(()=>{
            if(getMyVar('isretain', '')!="1"){
                putMyVar('isretain', '1');
            }else{
                clearMyVar('isretain');
            }
            refreshPage(false);
            return 'toast://已切换';
        })
    });
    d.push({
        title: 'ext数据',
        col_type: 'input',
        desc: "ext对象数据{}，如headers、flag, 可以留空",
        extra: {
            defaultValue: storage0.getMyVar('parseext', data?data.ext:"") || "",
            titleVisible: false,
            type: "textarea",
            highlight: true,
            height: 3,
            onChange: $.toString(() => {
                if (/{|}/.test(input)) {
                    try{
                        storage0.putMyVar("parseext", JSON.parse(input));
                    }catch(e){}
                }
            })
        }
    });
    if(data){
        d.push({
            title:'删除',
            col_type:'text_3',
            url: $("确定删除解析："+getMyVar('parsename',data.name)).confirm((data)=>{
                require(config.聚影.replace(/[^/]*$/,'') + 'SrcJyPublic.js');
                deleteData('jx', data);
                back(true);
                return "toast://已删除";
            }, data)
        });    
    }else{
        d.push({
            title:'清空',
            col_type:'text_3',
            url:$("确定要清空上面填写的内容？").confirm(()=>{
                clearMyVar('parsename');
                clearMyVar('parseurl');
                clearMyVar('parseext');
                refreshPage(false);
                return "toast://已清空";
            })
        });
    } 
    d.push({
        title:'保存',
        col_type:'text_3',
        url: $().lazyRule((data)=>{
            if(!/^http|^functio/.test(getMyVar('parseurl',''))){
                return "toast://解析地址不正确"
            }
            let parseext = storage0.getMyVar('parseext');
            if(parseext && $.type(parseext)!="object"){
                return "toast://ext对象数据不正确"
            }
            require(config.聚影.replace(/[^/]*$/,'') + 'SrcJySet.js');
            let urls= [];
            let parseurl = getMyVar('parseurl');
            let parsename = getMyVar('parsename');
            let parsetype = getMyVar('parsetype','0');
            
            if(parseurl&&parsename){
                let arr  = { "name": parsename.trim(), "type": parseInt(parsetype),"url": parseurl.trim()};
                if(parseext){
                    arr['ext']=  parseext;
                }
                let isretain = getMyVar('isretain')=="1"?1:0;
                if(isretain){arr['retain'] = 1;}
                if(data){
                    arr['oldurl'] = data.url;
                }
                urls.push(arr);
                let num = jiexisave(urls);
                if(num==1){
                    back(true);
                    return "toast://已保存";
                }else if(num==0){
                    return "toast://已存在";
                }else{
                    return "toast://保存出错";
                }
            }else{
                return "toast://无法保存，检查项目填写完整性";
            }
                
        },data)
    });
    d.push({
        title:'测试',
        col_type:'text_3',
        url: $().lazyRule(()=>{
            let dataurl = getMyVar('parseurl');
            let dataname = getMyVar('parsename')||'测试';
            let datatype = getMyVar('parsetype','0');
            let dataext = storage0.getMyVar('parseext') || {};
            if(!dataurl||!/^http|^functio/.test(dataurl.trim())){
                return "toast://获取解析地址失败，无法测试";
            }

            addItemAfter('jxline',{
                title: '选择测试片源',
                col_type: "rich_text",
                extra:{
                    id: 'jxfrom',
                    cls: 'jxtest'
                }
            })
            addItemAfter('jxfrom',{
                col_type: "line",
                extra:{
                    id: 'jxline2',
                    cls: 'jxtest'
                }
            })
            let filepath = globalMap0.getVar('Src_Jy_gmParams').libspath + "testurls.json";
            let datafile = fetch(filepath);
            if(datafile != ""){
                eval("var urls=" + datafile+ ";");
            }else{
                var urls = {
                    "1905": "https://vip.1905.com/play/1659382.shtml",
                    "爱奇艺": "https://www.iqiyi.com/v_1e6upn2xiek.html",
                    "优酷": "https://v.youku.com/v_show/id_XNjQwMzkxNzU1Mg==.html",
                    "腾讯": "https://v.qq.com/x/cover/mzc002007n0xa7w/j4100ne9iw8.html",
                    "芒果": "https://www.mgtv.com/b/638338/21190020.html",
                    "哔哩哔哩": "https://www.bilibili.com/bangumi/play/ep828752",
                    "搜狐": "https://tv.sohu.com/v/MjAyMzA5MjEvbjYwMTMzNDI0Ni5zaHRtbA==.html",
                    "西瓜": "https://www.ixigua.com/6915270027096621576",
                    "PPTV": "https://v.pptv.com/show/UKm0M5sBca8SkPg.html",
                    "咪咕": "https://m.miguvideo.com/m/detail/919226692",
                    "乐视": "https://www.le.com/ptv/vplay/24093071.html"
                }
                writeFile(filepath, JSON.stringify(urls));
            }

            let dataObj = {};
            dataObj.parse = {name:dataname,url:dataurl,type:parseInt(datatype),ext:dataext};

            urls['自定义'] = "";
            for(let key in urls){
                addItemBefore('jxline2', {
                    title: key,
                    url: key!="自定义"?$('#noRecordHistory##noHistory#').lazyRule((vipUrl,dataObj)=>{
                        require(config.聚影.replace(/[^/]*$/,'') + 'SrcParseS.js');
                        return SrcParseS.聚影(vipUrl, dataObj);
                    },urls[key],dataObj):$("","输入自定义播放地址").input((dataObj) => {
                        if(input==""){
                            return "toast://未输入自定义地址，无法测试";
                        }else{
                            return $().lazyRule((vipUrl,dataObj)=>{
                                require(config.聚影.replace(/[^/]*$/,'') + 'SrcParseS.js');
                                return SrcParseS.聚影(vipUrl, dataObj);
                            }, input, dataObj)
                        }
                    }, dataObj),
                    col_type: "text_3",
                    extra:{
                        cls: 'jxtest',
                        jsLoadingInject: true,
                        blockRules: ['.m4a','.mp3','.gif','.jpeg','.png','.ico','hm.baidu.com','/ads/*.js'] 
                    }
                })
            }
            addItemBefore('jxline2', {
                title: '编辑测试',
                url: $('#noRecordHistory##noHistory#').lazyRule(()=>{
                    return "editFile://" + globalMap0.getVar('Src_Jy_gmParams').libspath + "testurls.json";
                }),
                col_type: "text_3",
                extra:{
                    cls: 'jxtest'
                }
            })
            updateItem('jxtest', {
                url: "hiker://empty"
            })
            return "hiker://empty";
        }),
        extra:{
            id: 'jxtest'
        }
    });
    
    d.push({
        col_type: "line",
        extra:{id:'jxline'}
    })
    setResult(d);
}

//资源管理
function resource() {
    addListener("onClose", $.toString(() => {
        clearMyVar('importjiekou');
        clearMyVar('importjiexi');
        clearMyVar('importtype');
        clearMyVar('importinput');
    }));
    setPageTitle("资源管理");

    let d = [];
    d.push({
        col_type: "line_blank"
    });
    d.push({
        title: '🎁 选择资源类型',
        col_type: "rich_text"
    });
    let importtype = getMyVar('importtype','1');
    d.push({
        title: (importtype=="1"?"👉":"")+"tvBox接口配置",
        col_type: 'scroll_button',
        url: $('#noLoading#').lazyRule(() => {
            putMyVar('importtype','1');
            refreshPage(false);
            return "toast://支持本地包或在线的tvBox接口配置地址";
        })
    });
    if(getItem("sourceMode","1")=="1"){
        /*
        d.push({
            title: (importtype=="2"?"👉":"")+"道长hipy库导入",
            col_type: 'scroll_button',
            url: $('#noLoading#').lazyRule(() => {
                putMyVar('importtype','2');
                refreshPage(false);
                return "toast://此项仅支github库，hipy项目js文件所在的路径";
            })
        });
        //订阅和导入进行合并,importtype=="3"作废
        d.push({
            title: (importtype=="3"?"👉":"")+"box配置文件订阅",
            col_type: 'scroll_button',
            url: $('#noLoading#').lazyRule(() => {
                putMyVar('importtype','3');
                refreshPage(false);
                return "toast://订阅本地包或在线的配置文件，但无法管理接口";
            })
        });
        */

        d.push({
            title: (importtype=="4"?"👉":"")+"js/py文件夹",
            col_type: 'scroll_button',
            url: $('#noLoading#').lazyRule(() => {
                clearMyVar('importinput');
                putMyVar('importtype','4');
                refreshPage(false);
                return "toast://此项仅支持js/py文件所在目录";
            })
        });
    }

    if(importtype=="1"){
        if(getItem("sourceMode")=="2"){
            d.push({
                title: '当前订阅地址：' + (Juconfig['dySource'] || "无"),
                col_type: "rich_text",
                extra:{textSize:12}
            });
        }else{
            d.push({
                title: '选择需要的导入项目',
                col_type: "rich_text",
                extra:{textSize:12}
            });
            d.push({
                title:(getMyVar('importjiekou','1')=="1"?getide(1):getide(0))+'影视接口',
                col_type:'scroll_button',
                url:$('#noLoading#').lazyRule(() => {
                    if(getMyVar('importjiekou')=="0"){
                        putMyVar('importjiekou','1');
                    }else{
                        putMyVar('importjiekou','0');
                    }
                    refreshPage(false);
                    return "hiker://empty";
                })
            });
            d.push({
                title:(getMyVar('importjiexi','1')=="1"?getide(1):getide(0))+'解析接口',
                col_type:'scroll_button',
                url:$('#noLoading#').lazyRule(() => {
                    if(getMyVar('importjiexi')=="0"){
                        putMyVar('importjiexi','1');
                    }else{
                        putMyVar('importjiexi','0');
                    }
                    refreshPage(false);
                    return "hiker://empty";
                })
            });
        }
    }
    d.push({
        title:'本地',
        col_type: 'input',
        desc: '请输入链接地址',
        url: $.toString(() => {
            return `fileSelect://`+$.toString(()=>{
                if(!MY_PATH){
                    return "toast://获取文件真实路径失败：不支持通过文件管理器获取，可手工填写目录路径";
                }
                if(getMyVar('importtype')=='4'){
                    MY_PATH = MY_PATH.substr(0, MY_PATH.lastIndexOf('/')+1)
                }
                putMyVar("importinput",MY_PATH);
                refreshPage();
                return "hiker://empty";
            })
        }),
        extra: {
            titleVisible: true,
            defaultValue: getMyVar('importinput', ''),
            onChange: 'putMyVar("importinput",input);'
        }
    });

    d.push({
        title: '🆗 '+(importtype=="4"?'确定扫描':getItem("sourceMode")=="2"?'确定订阅':'确定导入(' + (Juconfig["importmode"]?"全量":"增量")+')'),
        url: importtype=="1"&&getItem("sourceMode","1")=="1"&&getMyVar('importjiekou','1')!="1"&&getMyVar('importjiexi','1')!="1"?'toast://请选择导入项目':$('#noLoading#').lazyRule((Juconfig,cfgfile) => {
                let importtype = getMyVar('importtype','1');

                let input = getMyVar('importinput', '').trim();
                // ★ 云口令直接粘贴导入
                //   原校验只放行 / http file hiker 开头的"链接"，
                //   而云口令形如「聚影接口￥xxxx￥xxx」以「聚」开头 -> 被判"非正常链接"拒掉
                //   所以粘贴口令永远导不进来（除非走 .hiker 文件的 @import 通道，
                //   而那个通道又硬编码规则名"聚影"，改名后也失效）
                //   这里在链接校验【之前】先识别口令，直接交给 JYimport 处理
                if(input.indexOf('￥') > -1 || /^云口令：/.test(input)){
                    return JYimport(input);
                }
                if(input=="" || input.endsWith("Juying.js")){
                    return 'toast://输入不能为空、代码库地址';
                }else if(!(input.startsWith('/') || input.startsWith('http') || input.startsWith('file') || input.startsWith('hiker'))){
                    return 'toast://输入不正确，非正常链接';
                }else if(importtype!="4" && input.endsWith('/')){
                    return 'toast://输入不正确，不要以/结尾';
                }else if(importtype=="4" && (!input.endsWith('/') || !input.startsWith('/'))){
                    return 'toast://文件夹路径不正确，以/开头结尾';
                }
                
                let importrecord = Juconfig['importrecord']||[];
                if(importrecord.length>20){//保留20个记录
                    importrecord.shift();
                }
                if(!importrecord.some(item => item.url==input && item.type==importtype)){
                    importrecord.push({type:importtype,url:input});
                    Juconfig['importrecord'] = importrecord;
                    writeFile(cfgfile, JSON.stringify(Juconfig));
                }
                if(input.startsWith('/')){
                    input = "file://" + input;
                }

                require(config.聚影.replace(/[^/]*$/,'') + 'SrcJySet.js');

                if(importtype=="4"){//扫描本地js/py文件夹
                    return scanFolder(input);
                }

                function exeImport(input){
                    let importtype = getMyVar('importtype','1');
                    if(importtype=="1"){
                        if(getItem("sourceMode")=="2"){
                            return "toast://" + getBoxSource(input, 3).message;
                        }else{
                            return Resourceimport(input, '1', Juconfig['importmode']?2:0);
                        }
                    }else if(importtype=="2"){
                        return HipyImport(input, Juconfig['importmode']?2:0);
                    }
                }
                
                let checkUrl = checkBoxUrl(input);
                if(checkUrl.message){
                    return "toast://" + checkUrl.message;
                }else if(checkUrl.urls){
                    let urls = checkUrl.urls;
                    let names = urls.map(v=>v.name);
                    return $(names, 1).select((urls,exeImport) => {
                        let url = urls.filter(v=>v.name==input)[0].url;
                        require(config.聚影.replace(/[^/]*$/,'') + 'SrcJySet.js');
                        return exeImport(url);
                    },urls,exeImport)
                }
                return exeImport(input);
            }, Juconfig, cfgfile),
        col_type: "text_center_1",
        extra: {
            longClick: [{
                title: "导入方式："+(Juconfig["importmode"]?"全量":"增量"),
                js: $.toString((cfgfile, Juconfig) => {
                    if(Juconfig["importmode"]){
                        Juconfig["importmode"] = 0;
                    }else{
                        Juconfig["importmode"] = 1;
                    }
                    writeFile(cfgfile, JSON.stringify(Juconfig));
                    refreshPage(false);
                    return 'toast://导入方式设置为：' + (Juconfig["importmode"]?"全":"增") + "量导入";
                },cfgfile, Juconfig)
            }]
        }
    });

    d.push({
        col_type: "line_blank"
    });
    d.push({
        title: '🆖 历史记录',
        col_type: "rich_text"
    });
    let importrecord = Juconfig['importrecord']||[];
    let lists = importrecord.filter(item => {
        return item.type==getMyVar('importtype','1');
    })
    lists.reverse();
    
    if(lists.length>0){
        if(importtype=="1" || importtype=="2"){
            d.push({
                title: '点此进行检测配置文件有效性👀',
                url: $('#noLoading#').lazyRule((lists) => {
                    require(config.聚影.replace(/[^/]*$/,'') + 'SrcJyPublic.js');
                    lists.forEach(it=>{
                        let checkUrl = checkBoxUrl(it.url);
                        updateItem(it.url, {title: it.url +(checkUrl.message?" ❌":" ✔️")});
                    })
                    return "toast://已检测完成，长按删除坏的";
                }, lists),
                col_type: "text_center_1"
            });
            d.push({
                col_type: "line"
            });
        }
        
        for(let i=0;i<lists.length;i++){
            let long = [{
                title: "删除",
                js: $.toString((cfgfile, Juconfig, url) => {
                    let importrecord = Juconfig['importrecord']||[];
                    for(let j=0;j<importrecord.length;j++){
                        if(importrecord[j].url==url&&importrecord[j].type==getMyVar('importtype','1')){
                            importrecord.splice(j,1);
                            break;
                        }
                    }
                    Juconfig['importrecord'] = importrecord; 
                    writeFile(cfgfile, JSON.stringify(Juconfig));
                    refreshPage(false);
                    return "toast://已删除";
                },cfgfile, Juconfig, lists[i].url)
            },{
                title: "复制",
                js: $.toString((url) => {
                    copy(url);
                    return "hiker://empty";
                }, lists[i].url)
            }]
            if(importtype=="4"){
                long.push({
                    title: "自动",
                    js: $.toString((cfgfile, Juconfig, url) => {
                        let importrecord = Juconfig['importrecord']||[];
                        for(let j=0;j<importrecord.length;j++){
                            if(importrecord[j].url==url&&importrecord[j].type=='4'){
                                if(importrecord[j].scan){
                                    delete importrecord[j].scan;
                                }else{
                                    importrecord[j].scan = 1;
                                }
                                break;
                            }
                        }
                        Juconfig['importrecord'] = importrecord; 
                        writeFile(cfgfile, JSON.stringify(Juconfig));
                        refreshPage(false);
                        return "toast://已设置为自动扫描";
                    },cfgfile, Juconfig, lists[i].url)
                });
            }
            d.push({
                title: lists[i].url + (lists[i].scan?"  [自动扫描]":""),
                url: $('#noLoading#').lazyRule((url) => {
                    putMyVar('importinput', url);
                    refreshPage(true);
                    return "toast://已选择，需确认";
                },lists[i].url),
                col_type: "text_1",
                extra: {
                    id: lists[i].url,
                    longClick: long
                }
            });
        }
    }else{
        d.push({
            title: '↻无记录',
            col_type: "rich_text"
        });
    }
    setResult(d);
}
//hipy库导入
function HipyImport(input, importmode){
    try{
        if(input.startsWith('http') && !input.includes('github.com')){
            return "toast://在线只支持github库";
        }
        if(input.endsWith('/')){
            input = input.substring(0, input.length - 1);
        }
        showLoading('检测地址有效性');
        let html = getContnet(input);
        let json = JSON.parse(html.split(`data-target="react-app.embeddedData">`)[1].split(`</script>`)[0]);
        let list = json.payload.tree.items;
        showLoading('执行多线程导入'+list.length);

        let jiekous = list.filter(v=>v.contentType=="file").map(it=>{
            return {
                name: it.name,
                url: input.replace('github.com','raw.githubusercontent.com').replace('/tree/','/') + it.path.substr(it.path.lastIndexOf('/'))
            }
        });

        let urls= [];
        //多线程处理
        let task = function(obj) {
            let arr = { "name": obj.name.split('.')[0], "type": "hipy_t3", "ext": obj.url}
            if(arr.name.includes('[搜]')){
                arr['onlysearch'] = 1;
            }
            let urlfile;
            try{
                let content = getContnet(obj.url);
                if (content) {
                    urlfile = jkfilespath + arr.type + '_' + obj.name;
                    writeFile(urlfile, content);
                }
            }catch(e){
                log(obj.name + '>hipy库文件缓存失败>' + e.message);
            }
            
            if(urlfile){
                arr['url'] = urlfile;
            }
            
            if(arr.url){
                return {data: arr};
            }
            return {};
        }
        
        let jiekoutask = jiekous.map((list)=>{
            return {
                func: task,
                param: list,
                id: list.name
            }
        });

        be(jiekoutask, {
            func: function(obj, id, error, taskResult) {   
                if(taskResult.data){
                    urls.push(taskResult.data);
                }                  
            },
            param: {
            }
        });
        let jknum = 0;
        try{
            jknum = jiekousave(urls, importmode);
        }catch(e){
            jknum =-1;
            log('TVBox导入接口保存有异常>'+e.message);
        }
        hideLoading();
        return 'toast://hipy库>查询' + jiekous.length + (jknum>-1?' 接口保存'+jknum:' 导入异常');     
    }catch(e){
        toast('链接访问异常，查看网页');
        return input;
    }
}
//资源导入
function Resourceimport(input,importtype,importmode){
    //mode:0增量，1覆盖，2全量
    if(importtype=="1"){//tvbox导入
        let jknum = -1;
        let jxnum = -1;
        let imports = {};

        if(getMyVar('importjiekou','1')=="1"){
            imports.jk = 1;
        }
        if(getMyVar('importjiexi','1')=="1"){
            imports.jx = 1;
        }
        let boxSource = getBoxSource(input, 1, imports);
        if(boxSource.message){
            return "toast://" + boxSource.message;
        }
        showLoading('导入中，请稍后...');
        let jiekous = boxSource.jklist || [];
        try{
            jknum = jiekousave(jiekous, importmode);
        }catch(e){
            jknum =-1;
            log('TVBox导入接口保存有异常>'+e.message);
        } 
        let jiexis = boxSource.jxlist || [];
        try{
            jxnum = jiexisave(jiexis, importmode);
        } catch (e) {
            jxnum = -1;
            log('TVBox导入解析保存失败>'+e.message);
        }
        hideLoading();
        let sm = (jknum>-1?' 接口保存'+jknum:'')+(jxnum>-1?' 解析保存'+jxnum:'');
        if(jknum>0||jxnum>0){back();}
        if(jknum==-1&&jxnum==-1){
            clearMyVar('importinput');
            refreshPage(false);
        }
        return 'toast://TVBox导入：'+(sm?sm:'导入异常，详情查看日志');     
    }
}

//资源分享
function JYshare(lx,input,data) {
    let sharelist, sm, sm2;
    if(lx=="jk"){
        sm = "聚影接口";
    }else if(lx=="jx"){
        sm = "聚影解析";
    }
    if(data){
        sharelist = [];
        sharelist.push(data);
    }else{
        let duoselect = storage0.getMyVar('duoselect') || [];
        if(duoselect.length>0){
            sharelist = duoselect;
        }else{
            sharelist = storage0.getMyVar("jkdatalist", []);
        }
    }

    for(let i=0;i<sharelist.length;i++){
        let it = sharelist[i];
        if(it.url.startsWith(jkfilespath) && (($.type(it.ext)=="string" && it.ext.startsWith("file")) || !it.ext)){
            it.extstr = fetch(it.url) || fetch(it.ext.split("?")[0]);
            if(!it.extstr){
                log(it.name+">未获取到数据文件，剔除分享");
                sharelist.splice(i,1);
                i = i - 1;
            }
        }else if(!it.url.startsWith(jkfilespath) && it.url.startsWith("hiker")){
            log(it.name+">私有路径的数据文件，剔除分享");
            sharelist.splice(i,1);
            i = i - 1;
        }
    }

    if(sharelist.length==0){
        return "toast://有效接口数为0，无法分享";
    }
    let gzip = $.require(codepath + "plugins/gzip.js");
    let sharetxt = gzip.zip(JSON.stringify(sharelist));
    let sharetxtlength = sharetxt.length;
    if(sharetxtlength>200000 && /云剪贴板2|云剪贴板5|云剪贴板9|云剪贴板10/.test(input)){
        return "toast://超出字符最大限制，建议用云6或文件分享";
    }

    if(input=='云口令文件'){
        sm2 = sharelist.length==1?sharelist[0].name:sharelist.length;
        let code = sm + '￥' + aesEncode('Juying2', sharetxt) + '￥云口令文件';
        let sharefile = 'hiker://files/_cache/Juying2_'+sm2+'_'+$.dateFormat(new Date(),"HHmmss")+'.hiker';
        writeFile(sharefile, '云口令：'+code+`@import=js:$.require("hiker://page/import?rule=聚影");`);
        if(fileExist(sharefile)){
            return 'share://'+sharefile;
        }else{
            return 'toast://'+input+'分享生成失败';
        }
    }else{
        showLoading('分享生成中，请稍后...');
        sm2 = sharelist.length==1?sharelist[0].name:'共' + sharelist.length + '条';
        let pasteurl = sharePaste(sharetxt, input);
        hideLoading();
        if(/^http|^云/.test(pasteurl) && pasteurl.includes('/')){
            log('剪贴板地址>'+pasteurl);
            let code = sm+'￥'+aesEncode('Juying2', pasteurl)+'￥' + sm2 + '('+input+')';
            copy('云口令：'+code+`@import=js:$.require("hiker://page/import?rule=聚影");`);
            return "toast://聚影分享口令已生成";
        }else{
            log('分享失败>'+pasteurl);
            return "toast://分享失败，剪粘板或网络异常>"+pasteurl;
        }
    }
}
//资源导入
function JYimport(input) {
    let cloudimport;
    if(/^云口令：/.test(input)){
        input = input.replace('云口令：','').trim();
        cloudimport = 1;
    }
    let pasteurl;
    let inputname;
    let codelx = "share";
    try{
        pasteurl = aesDecode('Juying2', input.split('￥')[1]);
        inputname = input.split('￥')[0];
        if(inputname=="聚影资源码"){
            codelx = "dingyue";
            if(input.split('￥')[2] != "文件分享"){
                pasteurl = '云6oooole/xxxxxx/' + pasteurl;
            }
            if(getMyVar('guanli')=="jk"){
                inputname = "聚影接口";
            }else if(getMyVar('guanli')=="jx"){
                inputname = "聚影解析";
            }
        }
    }catch(e){
        return "toast://聚影：口令有误>"+e.message;
    }
    try{
        if(inputname=="聚影接口"){
            var sm = "聚影：接口";
        }else if(inputname=="聚影解析"){
            var sm = "聚影：解析";
        }else{
            return "toast://聚影：无法识别的口令";
        }
        let text;
        if(/^http|^云/.test(pasteurl)){
            showLoading('获取数据中，请稍后...');
            text = parsePaste(pasteurl);
            hideLoading();
        }else{
            text = pasteurl;
        }
        // ★ 原来取失败时什么都不做（无 toast、页面空白），用户以为"点了没反应"
        if(!pasteurl){
            return "toast://聚影：口令解密为空，口令可能已损坏";
        }
        if(/^error/.test(String(text)) || !text){
            return "toast://聚影：剪贴板取不到内容（多半已过期）；" + String(text||'').substring(0,60);
        }
        if(pasteurl&&!/^error/.test(text)){
            let gzip = $.require(codepath + "plugins/gzip.js");
            let sharetxt = gzip.unzip(text);
            let pastedata = JSON.parse(sharetxt);           
            let urlnum = 0;
            if(inputname=="聚影接口"){
                if(codelx=="share"){
                    var pastedatalist = pastedata;
                }else if(codelx=="dingyue"){
                    var pastedatalist = pastedata.接口;
                }
                urlnum = jiekousave(pastedatalist);
            }else if(inputname=="聚影解析"){
                if(codelx=="share"){
                    var pastedatalist = pastedata;
                }else if(codelx=="dingyue"){
                    var pastedatalist = pastedata.解析;
                }
                urlnum = jiexisave(pastedatalist);
            }
            if(urlnum>0&&cloudimport!=1){
                refreshPage(false);
            }
            return "toast://"+sm+"合计："+pastedatalist.length+"，保存："+urlnum;
        }else{
            return "toast://聚影：口令错误或已失效";
        }
    } catch (e) {
        return "toast://聚影：无法识别的口令>"+e.message;
    }
}
//云盘的接口方法
function yundiskjiekou() {
    setPageTitle('☁️云盘接口 | 聚影');
    clearMyVar('duoselect');
    let filepath = rulepath + "yundisk.json";
    let datalist = [];
    let datafile = fetch(filepath);
    if(datafile != ""){
        try{
            eval("datalist=" + datafile+ ";");
        }catch(e){}
    }

    function yundiskapi(filepath,data){
        addListener("onClose", $.toString(() => {
            clearMyVar('yundiskname');
            clearMyVar('yundiskparse');
            clearMyVar('yundiskerparse');
            clearMyVar('yundiskedit');
        }));
        if(data){
            putMyVar('yundiskedit','1');
            putMyVar('yundiskname',getMyVar('yundiskname',data.name));
            putMyVar('yundiskparse',getMyVar('yundiskparse',data.parse));
            putMyVar('yundiskerparse',getMyVar('yundiskerparse',data.erparse||""));
        }
        let d = [];
        d.push({
            title:'名称',
            col_type: 'input',
            desc: "接口名称",
            extra: {
                defaultValue: getMyVar('yundiskname',''),
                titleVisible: false,
                onChange: $.toString(() => {
                    putMyVar('yundiskname',input);
                })
            }
        });
        d.push({
            title:'一解',
            col_type: 'input',
            desc: "一解函数",
            extra: {
                defaultValue: getMyVar('yundiskparse',''),
                titleVisible: false,
                type: "textarea",
                highlight: true,
                height: 5,
                onChange: $.toString(() => {
                    putMyVar('yundiskparse',input);
                })
            }
        });
        d.push({
            title:'二解',
            col_type: 'input',
            desc: "二解函数, 可以留空",
            extra: {
                defaultValue: getMyVar('yundiskerparse',''),
                titleVisible: false,
                type: "textarea",
                highlight: true,
                height: 5,
                onChange: $.toString(() => {
                    putMyVar('yundiskerparse',input);
                })
            }
        });
        d.push({
            title: '测试',
            col_type: 'text_2',
            url: $().lazyRule(()=>{
                if(!getMyVar('yundiskname')||!getMyVar('yundiskparse')){
                    return "toast://名称和一解函数不能为空";
                }
                try{
                    let name = getMyVar('yundiskname');
                    let parse = getMyVar('yundiskparse');
                    let erparse = getMyVar('yundiskerparse');
                    let newapi = {
                        name: name,
                        parse: parse
                    }
                    if(erparse){
                        newapi['erparse'] = erparse;
                    }
                    
                    return $(getItem('searchtestkey', '斗罗大陆'),"输入测试搜索关键字").input((data)=>{
                        setItem("searchtestkey",input);
                        return $("hiker://empty#noRecordHistory##noHistory#").rule((name,data) => {
                            let d = [];
                            d.push({
                                title: data.name+"-搜索测试",
                                url: 'hiker://empty',
                                col_type: 'text_center_1',
                                extra: {
                                    id: "listloading",
                                    lineVisible: false
                                }
                            });
                            setResult(d);
                            require(config.聚影.replace(/[^/]*$/,'') + 'SrcJyAliDisk.js');
                            aliDiskSearch(name,data);
                        },input,data)
                    },newapi)
                }catch(e){
                    return "toast://接口数据异常，请确认对象格式";
                }
            })
        });
        d.push({
            title: '保存',
            col_type: 'text_2',
            url: $().lazyRule((filepath)=>{
                if(!getMyVar('yundiskname')||!getMyVar('yundiskparse')){
                    return "toast://名称和一解函数不能为空";
                }
                try{
                    let name = getMyVar('yundiskname');
                    let parse = getMyVar('yundiskparse');
                    let erparse = getMyVar('yundiskerparse');
                    let newapi = {
                        name: name,
                        parse: parse
                    }
                    if(erparse){
                        newapi['erparse'] = erparse;
                    }

                    let datafile = fetch(filepath);
                    if(datafile != ""){
                        try{
                            eval("var datalist=" + datafile+ ";");
                        }catch(e){
                            var datalist = [];
                        }
                    }else{
                        var datalist = [];
                    }
                    let index = datalist.indexOf(datalist.filter(d=>d.name == name)[0]);
                    if(index>-1 && getMyVar('yundiskedit')!="1"){
                        return "toast://已存在-"+name;
                    }else{
                        if(getMyVar('yundiskedit')=="1" && index>-1){
                            datalist.splice(index,1);
                        }
                        datalist.push(newapi);
                        writeFile(filepath, JSON.stringify(datalist));
                        back(true);
                        return "toast://已保存";
                    }
                }catch(e){
                    return "toast://接口数据异常，请确认对象格式";
                }
            },filepath)
        });
        setResult(d);
    }
    var d = [];
    d.push({
        title: '增加',
        url: $('hiker://empty#noRecordHistory##noHistory#').rule((filepath,yundiskapi) => {
            yundiskapi(filepath);
        },filepath,yundiskapi),
        img: getIcon("云盘-接口增加.svg"),//"https://hikerfans.com/tubiao/more/25.png",
        col_type: "icon_small_3"
    });
    d.push({
        title: '导入',
        url: $("", "云盘分享口令的云剪贴板").input(() => {
            try {
                input = input.split('@import=js:')[0].replace('云口令：','')
                let inputname = input.split('￥')[0];
                if (inputname == "聚影云盘") {
                    showLoading("正在导入，请稍后...");
                    let parseurl = aesDecode('Juying2', input.split('￥')[1]);
                    let content = parsePaste(parseurl);
                    let gzip = $.require(codepath + "plugins/gzip.js");
                    let datalist2 = JSON.parse(gzip.unzip(content));
                    require(config.聚影.replace(/[^/]*$/,'') + 'SrcJySet.js');
                    let num = yundisksave(datalist2);
                    hideLoading();
                    refreshPage(false);
                    return "toast://合计" + datalist2.length + "个，导入" + num + "个";
                } else {
                    return "toast://聚影：非云盘口令";
                }
            } catch (e) {
                log(e.message);
                return "toast://聚影：口令有误";
            }
        }),
        img: getIcon("云盘-接口导入.svg"),//"https://hikerfans.com/tubiao/more/43.png",
        col_type: "icon_small_3"
    });
    d.push({
        title: '分享',
        url: datalist.length == 0 ? "toast://云盘接口为0，无法分享" : $().lazyRule((datalist) => {
            let gzip = $.require(codepath + "plugins/gzip.js");
            let pasteurl = sharePaste(gzip.zip(JSON.stringify(datalist)), getItem("sharePaste",""));
            if (pasteurl) {
                let code = '聚影云盘￥' + aesEncode('Juying2', pasteurl) + '￥共' + datalist.length + '条';
                copy('云口令：'+code+`@import=js:$.require("hiker://page/import?rule=聚影");`);
                return "toast://(全部)云盘分享口令已生成";
            } else {
                return "toast://分享失败，剪粘板或网络异常";
            }
        }, datalist),
        img: getIcon("云盘-接口分享.svg"),//"https://hikerfans.com/tubiao/more/3.png",
        col_type: "icon_small_3",
        extra: {
            longClick: [{
                title: '分享剪贴板：' + getItem("sharePaste","自动选择"),
                js: $.toString(() => {
                    let pastes = getPastes();
                    pastes.unshift('自动选择');
                    return $(pastes,2,'指定单接口分享时用哪个剪贴板').select(() => {
                        if(input=="自动选择"){
                            clearItem("sharePaste");
                        }else{
                            setItem("sharePaste", input);
                        }
                        refreshPage(false);
                        return 'toast://分享剪贴板已设置为：' + input;
                    })
                })
            }]
        }
    });
    d.push({
        col_type: "line"
    });

    datalist.forEach(item => {
        d.push({
            title: "💽 " + (item.stop?"““"+item.name+"””":item.name) + "   (" + (item.erparse?"二解接口":"一解接口") + ")",
            url: $(["分享", "编辑", "删除", item.stop?"启用":"禁用", "测试"], 1).select((filepath,yundiskapi,data) => {
                if (input == "分享") {
                    showLoading('分享上传中，请稍后...');
                    let oneshare = []
                    oneshare.push(data);
                    let gzip = $.require(codepath + "plugins/gzip.js");
                    let pasteurl = sharePaste(gzip.zip(JSON.stringify(oneshare)), getItem("sharePaste",""));
                    hideLoading();
                    if(pasteurl){
                        let code = '聚影云盘￥'+aesEncode('Juying2', pasteurl)+'￥'+data.name;
                        copy('云口令：'+code+`@import=js:$.require("hiker://page/import?rule=聚影");`);
                        return "toast://(单个)云盘分享口令已生成";
                    }else{
                        return "toast://分享失败，剪粘板或网络异常";
                    }
                } else if (input == "编辑") {
                    return $('hiker://empty#noRecordHistory##noHistory#').rule((filepath,yundiskapi,data) => {
                        yundiskapi(filepath,data);
                    },filepath,yundiskapi,data)
                } else if (input == "删除") {
                    let datafile = fetch(filepath);
                    eval("var datalist=" + datafile+ ";");
                    let index = datalist.indexOf(datalist.filter(d=>d.name == data.name)[0]);
                    datalist.splice(index, 1);
                    writeFile(filepath, JSON.stringify(datalist));
                    refreshPage(false);
                    return 'toast://已删除';
                } else if (input == "禁用" || input == "启用") {
                    let datafile = fetch(filepath);
                    eval("var datalist=" + datafile+ ";");
                    let index = datalist.indexOf(datalist.filter(d=>d.name == data.name)[0]);
                    datalist[index].stop = input=="禁用"?1:0;
                    writeFile(filepath, JSON.stringify(datalist));
                    refreshPage(false);
                    return 'toast://已'+input;
                } else if (input == "测试") {
                    return $(getItem('searchtestkey', '斗罗大陆'),"输入测试搜索关键字").input((data)=>{
                        setItem("searchtestkey",input);
                        return $("hiker://empty#noRecordHistory##noHistory#").rule((name,data) => {
                            let d = [];
                            d.push({
                                title: data.name+"-搜索测试",
                                url: 'hiker://empty',
                                col_type: 'text_center_1',
                                extra: {
                                    id: "listloading",
                                    lineVisible: false
                                }
                            });
                            setResult(d);
                            require(config.聚影.replace(/[^/]*$/,'') + 'SrcJyAliDisk.js');
                            aliDiskSearch(name,data);
                        },input,data)
                    },data)
                } 
            },filepath,yundiskapi,item),
            desc: '',
            col_type: "text_1"
        });
    })

    setResult(d);
}

function yundisksave(datas, mode){
    let filepath = getFile("yp");
    let datalist2 = datas;
    let datafile = fetch(filepath);
    let datalist = [];
    if(datafile != ""){
        try{
            eval("datalist=" + datafile+ ";");
        }catch(e){}
    }
    mode = mode==0?0:1;
    let num = 0;
    for (let i = 0; i < datalist2.length; i++) {
        if (datalist.some(item => item.name == datalist2[i].name)) {
            if(mode){
                let index = datalist.indexOf(datalist.filter(d => d.name==datalist2[i].name)[0]);
                datalist.splice(index, 1);
                datalist.push(datalist2[i]);
                num = num + 1;
            }
        }else{
            datalist.push(datalist2[i]);
            num = num + 1;
        }
    }
    writeFile(filepath, JSON.stringify(datalist));
    return num;
}
// 云口令导入确认页
function importConfirm(jsfile) {
    let importfile = "hiker://files/_cache/Juying2/cloudimport.txt";
    addListener("onClose", $.toString((importfile) => {
        deleteFile(importfile);
        clearMyVar('importConfirm');
    },importfile));
    let code,name,lx,sm,importdatas,datalist;
    let d = [];
    
    if(!jsfile){
        //云口令导入
        let input = fetch(importfile);
        input = input.replace('云口令：','').trim();
        try{
            code = aesDecode('Juying2', input.split('￥')[1]);
            name = input.split('￥')[0];
            if(name=="聚影资源码" && input.split('￥')[2]=="文件分享"){
                let gzip = $.require(codepath + "plugins/gzip.js");
                let textcontent = gzip.unzip(code);
                let pastedata = JSON.parse(textcontent);

                d.push({
                    title: '以增量方式导入，不会清除原有的',
                    desc: "包含资源：" + Object.keys(pastedata).join(','),
                    url: "hiker://empty",
                    col_type: "text_center_1"
                });
                const hikerPop = $.require(config.聚影.replace(/[^/]*$/,'') + 'plugins/hikerPop.js');
                let fruit = Object.keys(pastedata);
                hikerPop.multiChoice({
                    title: "选择要导入本地的项", 
                    options: fruit, 
                    checkedIndexs: Array.from(fruit.keys()), 
                    onChoice(i, isChecked) {
                        //log(i + ":" + isChecked);
                    }, 
                    rightTitle: "确认导入", 
                    rightClick(options, checked) {
                        if(options.filter((v, i) => checked[i]).length==0){
                            return "toast://没有选择导入项";
                        }
                        require(config.聚影.replace(/[^/]*$/,'') + 'SrcJySet.js');
                        let jknum = 0, jxnum = 0, ypnum = 0, tvnum = 0, ghnum = 0;
                        hikerPop.runOnNewThread(() => {
                            options.forEach((option,i)=>{
                                if(checked[i]){
                                    if(option=="ghproxy"){
                                        let ghproxy = pastedata.ghproxy||[];
                                        if(ghproxy.length>0){
                                            oldproxy = Juconfig['ghproxy'] || [];
                                            ghproxy.forEach(gh=>{
                                                if(!oldproxy.some(item => gh.url==item.url)){
                                                    oldproxy.push(gh);
                                                    ghnum++;
                                                }
                                            })
                                            Juconfig['ghproxy'] = oldproxy;
                                        }
                                    }else if(option=="接口"){
                                        let jkdatalist = pastedata.接口||[];
                                        jknum = jiekousave(jkdatalist, 1);
                                    }else if(option=="解析"){
                                        let jxdatalist = pastedata.解析||[];
                                        jxnum = jiexisave(jxdatalist, 1);
                                    }else if(option=="云盘"){
                                        let ypdatalist = pastedata.云盘||[];
                                        ypnum = yundisksave(ypdatalist, 1);
                                    }else if(option=="直播"){
                                        let livefilepath = globalMap0.getVar('Src_Jy_gmParams').rulepath + "liveconfig.json";
                                        let liveconfig = pastedata.直播;
                                        let livefile = fetch(livefilepath);
                                        if(livefile){
                                            try{
                                                let olddata = JSON.parse(livefile).data;
                                                let newdata = liveconfig.data;
                                                newdata.forEach(tv=>{
                                                    if(!olddata.some(item => tv.url==item.url)){
                                                        olddata.push(tv);
                                                        tvnum++;
                                                    }
                                                })
                                                liveconfig.data = olddata;
                                                writeFile(livefilepath, JSON.stringify(liveconfig));
                                            }catch(e){
                                                //log("增量导入直播失败>"+e.message);
                                            }
                                        }
                                    }
                                }
                            })
                            writeFile(cfgfile, JSON.stringify(Juconfig));
                            log("更新同步订阅资源完成；新增接口："+jknum+"，解析："+jxnum+"，直播"+tvnum+"，云盘："+ypnum+"，ghproxy："+ghnum);
                            back(false);
                            return "toast://更新同步文件资源完成；";
                        })
                    }, 
                    leftTitle: "取消",
                    leftClick() {
                        back(false);
                    }
                });
            }else{
                if (name == "聚影云盘") {
                    sm = "云盘";
                    lx = "yp";
                }else if(name=="聚影接口"){
                    sm = "接口";
                    lx = "jk";
                }else if(name=="聚影解析"){
                    sm = "解析";
                    lx = "jx";
                }else{
                    toast("聚影：无法识别的口令");
                }
                importdatas = storage0.getMyVar('importConfirm', []);
                if(importdatas.length==0){
                    try{
                        let text;
                        if(/^http|^云/.test(code)){
                            showLoading('获取数据中，请稍后...');
                            text = parsePaste(code);
                            hideLoading();
                        }else{
                            text = code;
                        }
                        if(text && !/^error/.test(text)){
                            let gzip = $.require(codepath + "plugins/gzip.js");
                            let sharetxt = gzip.unzip(text);
                            importdatas = JSON.parse(sharetxt); 
                            storage0.putMyVar('importConfirm', importdatas);
                        }
                    } catch (e) {
                        toast("聚影：无法识别的口令>"+e.message);
                    }
                }
            }
        }catch(e){
            toast("聚影：口令有误>"+e.message);
        }
    }else{
        //js/py文件导入
        importdatas = storage0.getMyVar('importConfirm', []);
        if(importdatas.length==0){
            let files = [];
            if($.type(jsfile)=="string"){
                if(jsfile.endsWith('.js')){//js单文件导入
                    if(jsfile.startsWith('/')){
                        jsfile = "file://" + jsfile;
                    }
                    files.push(jsfile);
                }else if(jsfile==importfile){//文件夹文件名数组写入文件导入
                    eval("let fileconet = " + fetch(jsfile));
                    if(typeof fileconet == "array"){
                        files = fileconet;
                    }
                }
            }else if($.type(jsfile)=="array"){//文件夹文件名数组传递导入
                files = jsfile;
            }
            importdatas = files.map(extfile=>{
                let name = extfile.substr(extfile.lastIndexOf('/')+1).split(".")[0];
                let arr = { "name": name};
                if(extfile.endsWith(".js")){
                    arr['type'] = "hipy_t3";
                }else if(extfile.endsWith(".py")){
                    arr['type'] = "py";
                }
                if(arr.name.includes('[搜]')){
                    arr['onlysearch'] = 1;
                }
                let filepath = cachepath + arr.type;
                let urlfile = filepath + '_' + extfile.substr(extfile.lastIndexOf('/')+1);
                arr['url'] = urlfile;
                writeFile(urlfile, fetch(extfile));
                if(!extfile.includes('/_cache/')){
                    arr['ext'] = extfile;
                }
                return arr;
            })
            storage0.putMyVar('importConfirm', importdatas);
        }
        sm = "接口";
        lx = "jk";
    }
    if(name!="聚影资源码"){
        //获取现有接口
        datalist = [];
        let sourcefile = getFile(lx);
        let sourcedata = fetch(sourcefile);
        if(sourcedata != ""){
            try{
                eval("datalist = " + sourcedata+ ";");
            }catch(e){}
        }
        let newdatas = [];
        importdatas.forEach(it=>{
            if(!datalist.some(v=>v.url==it.url || v.url==jkfilespath+it.url.substr(it.url.lastIndexOf('/')+1))){
                newdatas.push(it);
            }
        })
        let oldnum = importdatas.length - newdatas.length;
        d.push({
            title: "聚影云口令导入",
            desc: (sm||"") + " 共计" + importdatas.length + "/新增" + newdatas.length + "/存在" + oldnum ,
            url: "hiker://empty",
            col_type: 'text_center_1'
        });
        d.push({
            title: "增量导入",
            url: $("跳过已存在，只导入新增，确认？").confirm((lx)=>{
                require(config.聚影.replace(/[^/]*$/,'') + 'SrcJySet.js');
                let importlist = storage0.getMyVar('importConfirm', []);
                let num;
                if(lx=="jk"){
                    num = jiekousave(importlist, 0);
                }else if(lx=="jx"){
                    num = jiexisave(importlist, 0);
                }else if(lx=="yp"){
                    num = yundisksave(importlist, 0);
                }else{
                    return "toast://类型异常";
                }
                clearMyVar('Src_Jy_searchMark');
                back(false);
                return "toast://增量导入"+(num<0?"失败":num);
            },lx),
            img: getIcon("管理-增量导入.svg"),
            col_type: 'icon_small_3'
        });
        d.push({
            title: "",
            url: "hiker://empty",
            col_type: 'icon_small_3'
        });
        d.push({
            title: "全量导入",
            url: $("覆盖本地已存在重新导入，确认？").confirm((lx)=>{
                require(config.聚影.replace(/[^/]*$/,'') + 'SrcJySet.js');
                let importlist = storage0.getMyVar('importConfirm', []);
                if(lx=="jk"){
                    num = jiekousave(importlist, 1);
                }else if(lx=="jx"){
                    num = jiexisave(importlist, 1);
                }else if(lx=="yp"){
                    num = yundisksave(importlist, 1);
                }else{
                    return "toast://类型异常";
                }
                clearMyVar('Src_Jy_searchMark');
                back(false);
                return "toast://全量导入"+(num<0?"失败":num);
            },lx),
            img: getIcon("管理-全量导入.svg"),
            col_type: 'icon_small_3'
        });

        importdatas.forEach(it=>{
            let isnew = newdatas.some(v=>v.url==it.url);
            let datamenu = ["确定导入", "修改名称"];
            if(lx=="jk"){
                datamenu.push("设定分组");
                datamenu.push("接口测试");
                if(!it.url.startsWith('http')){
                    datamenu.push("查看文件");
                    datamenu.push("删除文件");
                }
            }
            
            d.push({
                title: it.name + (lx=="yp"?"":"   (" + it.type + ")") + (it.group?"  ["+it.group+"]":"") + "  {" + (isnew?"新增加":"已存在") + "}",
                url: $(datamenu, 2).select((lx, data) => {
                    data = JSON.parse(base64Decode(data));

                    if (input == "确定导入") {
                        return $("如本地存在则将覆盖，确认？").confirm((lx,data)=>{
                            let dataurl = data.url;
                            require(config.聚影.replace(/[^/]*$/,'') + 'SrcJySet.js');
                            let datas = [];
                            datas.push(data);
                            let num;
                            if(lx=="jk"){
                                num = jiekousave(datas, 1);
                            }else if(lx=="jx"){
                                num = jiexisave(datas, 1);
                            }else if(lx=="yp"){
                                num = yundisksave(datas, 1);
                            }else{
                                return "toast://类型异常";
                            }
                            clearMyVar('Src_Jy_searchMark');
                            let importlist = storage0.getMyVar('importConfirm', []);
                            if(importlist.length==1){
                                back(false);
                            }else{
                                let index2 = importlist.indexOf(importlist.filter(d => d.url==dataurl)[0]);
                                importlist.splice(index2, 1);
                                storage0.putMyVar('importConfirm', importlist);
                                deleteItem(dataurl);
                            }
                            return "toast://导入"+(num<0?"失败":num);
                        },lx,data);
                    }else if (input == "修改名称") {
                        return $(data.name, "请输入新名称").input((data)=>{
                            if(!input.trim()){
                                return "toast://不能为空";
                            }
                            let dataurl = data.url;
                            let importlist = storage0.getMyVar('importConfirm', []);
                            let index = importlist.indexOf(importlist.filter(d => d.url==dataurl)[0]);
                            importlist[index].name = input;
                            storage0.putMyVar('importConfirm', importlist);
                            refreshPage(false);
                            return "toast://已修改名称";
                        }, data);
                    }else if (input == "设定分组") {
                        let dataurl = data.url;
                        require(config.聚影.replace(/[^/]*$/,'') + 'SrcJySet.js');
                        let groupNames = getGroupNames();
                        groupNames.unshift("清除");
                        return $(groupNames, 2, "选择分组").select((dataurl) => {
                            let importlist = storage0.getMyVar('importConfirm', []);
                            let index = importlist.indexOf(importlist.filter(d => d.url==dataurl)[0]);
                            if(input=="清除"){
                                delete importlist[index].group;
                            }else{
                                importlist[index].group = input;
                            }
                            storage0.putMyVar('importConfirm', importlist);
                            refreshPage(false);
                            return 'toast://已设置分组';
                        },dataurl)
                    }else if (input == "接口测试") {
                        return $("hiker://empty#noRecordHistory##noHistory#").rule((data) => {
                            setPageTitle(data.name+"-接口测试");
                            require(config.聚影.replace(/[^/]*$/,'') + 'SrcJuying.js');
                            dianboyiji(data);
                        },data)
                    }else if (input == "查看文件") {
                        return "editFile://" + data.ext;
                    }else if (input == "删除文件") {
                        return $("删除"+data.ext+"，确认？").confirm((data)=>{
                            deleteFile(data.ext);
                            clearMyVar('Src_Jy_searchMark');
                            let importlist = storage0.getMyVar('importConfirm', []);
                            if(importlist.length==1){
                                back(false);
                            }else{
                                let index2 = importlist.indexOf(importlist.filter(d => d.url==data.url)[0]);
                                importlist.splice(index2, 1);
                                storage0.putMyVar('importConfirm', importlist);
                                deleteItem(data.url);
                            }
                            return "toast://已删除";
                        }, data)
                    }
                }, lx, base64Encode(JSON.stringify(it))),
                img: getIcon("管理-箭头.svg"),
                col_type: "text_icon",
                extra: {
                    id: it.url
                }
            });
        })
    }
    setResult(d);
}