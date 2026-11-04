# 聚影 py 蜘蛛 · 口令交付规范

> 基准样本：用户 2026-11-04 提供的 `云帧享-py聚影口令.txt`（已反解成功，密文可逐字节复现）。
> 以后的源一律按本规范交付：**一条口令整行**，源码自包含，不走 URL、不裸传 .py。

---

## 一、交付物

- 位置：`/workspace/outputs/<源名>-聚影口令.txt`
- 内容：**只有一行**，无换行、无空行、无 BOM、不夹任何说明文字
- 形如：

```
云口令：聚影接口￥<密文>￥<源名>()@import=js:$.require("hiker://page/import?rule=聚影");
```

分三段，`￥` 是全角，段数必须 3。

## 二、密文算法（已实测可逆）

```
明文   = base64( gzip( JSON数组, mtime=0 ) )        # ASCII 文本
密文   = base64( AES-256-ECB / PKCS7( key, 明文 ) )
key    = b"Juying2" + b"0"*25                       # 7 + 25 = 32 字节
```

JSON 数组：

```json
[{
  "name": "源名",
  "type": "py",
  "url": "hiker://files/rules/Src/Juying2/jiekou/py_<落地名>.py",
  "oldurl": "",
  "ext": "",
  "extstr": "<py 源码全文>",
  "searchable": 1, "quickSearch": 1, "filterable": 1
}]
```

- `url` 是导入时聚影 `writeFile(url, extstr)` 的落地路径，必须写
  `hiker://files/rules/Src/Juying2/jiekou/py_xxx.py`；
  历史坑：`hiker://files/data/...` 能导入但打不开。
- **明文里绝对不能出现 http(s) 链接**：一旦出现，App 判定为云剪贴板口令 → 解析出 0 条 → 导入空白。
- 生成脚本：`/workspace/juying_kouling.py`
  `python3 juying_kouling.py 蜘蛛.py 源名 落地名` → 写出单行 TXT + 反解自检 PASS/FAIL
  `python3 juying_kouling.py --unpack 口令.txt` → 反解出源码，用来核对

## 三、py 源码规范（T3 风格，照 云帧享 的写法）

1. `class Spider(_Dummy)`，**不继承 `base.spider.Spider`** —— 父类的 setCache/getCache 会抢占 pyDriver 注入的 MyVar。
2. 依赖**全部软导入**（requests / Crypto 都可缺），缺任何一个都不许让模块加载失败。
3. 网络层自控：`_http()` 返回 `(code, text)`，**永不抛异常**；不调父类 fetch（签名不一致会 TypeError）。
4. **跨实例状态一律用 `self.getCache / self.setCache`**（pyDriver 写 MyVar）。
   聚影每次 runPy 都建新实例，`self.xxx`、模块级变量都不共享 —— 任何"缓存/换线"逻辑都必须落在 getCache 上。
5. 五个入口与调用点：

| 方法 | 签名 | 返回 |
|---|---|---|
| 首页 | `homeContent(filter)` | `{'class':[{type_name,type_id}], 'filters':{}, 'list':[卡片]}` |
| 分类 | `categoryContent(tid, pg, filter, extend)` | `{'list':[卡片]}` |
| 详情 | `detailContent([erurl])` | `{'list':[vod_*]}`，`vod_play_from/url` 用 `$$$`、`#`、`$` 三层分隔 |
| 搜索 | `searchContent(key, quick, pg='1')` | `{'list':[卡片]}` |
| 播放 | `playerContent(flag, id, vipFlags)` | `{'parse':0,'url':<直链>,'jx':0}` |

6. 卡片字段只要 `vod_id / vod_name / vod_pic / vod_remarks`；详情 `vod_*` 按 TVBox 契约。
7. 播放 id 建议把参数编码进字符串（如 `http://xxx.local/p/<vid>~<idx>~<ji>`），
   playerContent 里用正则取出，不依赖 detailContent 留下的状态。
8. 代码里不留 Python 2 的异常属性写法（`.message` 之类），异常处理器二次崩溃会整源空白。
9. 体积控制：15–25 KB 最稳；几十 KB 以上每次切站都要重新解析。

## 四、导入与排错

1. 先删掉同名旧接口（否则两个同名源，旧的还在走老代码）。
2. 复制整行 → 聚影剪贴板自动弹窗；没弹就 设置 → 接口 → 导入 → 云口令 → 粘贴。
   成功提示：`聚影：接口合计：1，保存：1`。
3. **导入后强制停止 App 再打开**（pyDriver 缓存 py 模块，不重启还跑旧代码）。
4. 仍然空白，按序查：
   - 设置 → 安全及隐私 → 打开「忽略 https 安全警告」
   - 该源关掉「自动换源」（探活失败会被切到广告线路）
   - 接口 → 编辑：类型是 py，路径是 `hiker://files/rules/Src/Juying2/jiekou/py_xxx.py`
   - 再强制停止一次
