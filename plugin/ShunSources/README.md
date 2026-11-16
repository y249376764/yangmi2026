# 随身听书（ssts）插件：新增 番茄听书 / 七猫听书

在仓库自带的 `ShunSources` 听书插件上加了两个源，版本 5.6 → **5.8**。成品 `ShunSources.zip` 结构跟官方 `plugins/dist/ShunSources.zip` 一致（manifest + 脚本都在根目录），App 里「插件 → + → 从文件导入 zip」直接试。

| 文件 | 源 | 分组 | 说明 |
|---|---|---|---|
| `fanqie.js` | 番茄听书 | 听书 | 真人演播，音频直链 |
| `qimao.js` | 七猫听书 | 听书 | 真人 + 官方 AI 多音色（可切） |

来源是记忆库里的 `番茄听书.txt`（海阔规则）和 `小七听书-海阔规则-v1`。
（「歌词适配」音乐源按你的要求去掉了，`kwmusic.js` 不在包里，manifest 也没列。）

## 一、番茄听书（`fanqie.js`）

原规则走番茄官方接口（`reading.snssdk.com` 等），每条请求都要 `fanqieSignHeaders()` 签名（自定义时间戳 + HMAC），插件端只有 `md5/sha256`，手搓既重又容易随版本失效。改成免签名的聚合接口 `fq.neeao.dpdns.org`（就是当初那套阅读 NG 源用的站）：

| 用途 | 接口 |
|---|---|
| 搜索 | `/api/search?key=&tab_type=2&offset=&search_id=&passback=&next_offset=`（每页 10 本） |
| 分类导航 | `/api/discover/style?tab=听书&source_type=0`（带 url 的是按钮，空 url 的是分组标题） |
| 分类列表 | `/api/discover?tab=听书&type=&gender=&genre_type=1&page=1`（100 本） |
| 详情 / 目录 | `/api/detail?book_id=`、`/api/book?book_id=`（卷 → 章，一次给全） |
| 音频 | `/api/content?item_id=&book_id=&tab=听书` |

处理掉的坑：

1. `discover` 不认 `page/offset`，翻页永远同一批 100 本 → 分类只做单页，`nextUrl` 给 `null`。
2. 搜索翻页必须回传上一页的 `search_id`，只改 offset 会被当成新搜索 → 按关键词缓存。
3. `/api/content` 少 `tab=听书` 直接 400；`content_type` 不是 `audio` 就是没音频的书。
4. 作者字段混着「（主播：索尔配音）」→ 拆成 author + artist。
5. 两个聚合站都偶发 TLS 断连 → 每请求重试一次，`e.cancelled` 不重试。
6. **音频 CDN 不能带 Referer**：`fqnovelvod.com` 的防盗链规则是「带 Referer 就 403 deny by referer access rule」，只带 UA 或裸请求才 206。之前 `audio()` 回了 `headers:{UA, Referer}`，播放器直接吃 403，表现就是“点了没声音”，而海阔那边用裸地址所以能放 —— 这是 5.7 听不了的根因。

## 二、七猫听书（`qimao.js`）

接口站 `qm.neeao.dpdns.org`（原规则同源）：

| 用途 | 接口 |
|---|---|
| 首页 / 分类 | `/api/audio/home`、`/api/audio/categories` |
| 分类列表 | `/api/audio/category-list?categoryId=&categoryType=2&page=` |
| 榜单 | `/api/audio/rank?rankType=rec_list\|hot\|new\|over&categoryType=2`（固定 30 本） |
| 搜索 | `/api/audio/search?keyword=&page=` |
| 详情 | `/api/audio/info?id=`（mode / defaultVoice / aiVoices / realVoices / chapters） |
| 音频 | `/api/audio/chapter?id=&cid=&voice=` |

处理掉的坑：

1. **AI 书不带 voice 会返回「该章节暂无可播放音频」**（书 1851388 实测），真人书传 voice 又被忽略 → 详情时缓存 `mode/defaultVoice/aiVoices`，播放按「设置 → 原站默认 → 该书其它音色」最多试 5 次。
2. 音色 ID 跨书稳定：10 多角色对话 / 8 明朗青年 / 4 武侠男声 / 6 古风御姐 / 5 相声阿龙 / 7 温柔淑女 / 9 儒雅青叔；每本书只开一部分，所以做成了插件设置项（`config` → select），选到不支持的回退。
3. 榜单不认 page（固定 30 本）；搜索 `total` 不可信（第 11 页还有数据）→ 按「本页满 10 条」判断 + 20 页上限。
4. 章节直链带 `expire` 签名 → 章节 URL 只存稳定 ID，播放时现取。

## 三、自测结果（2026-11-16，node 桩模拟宿主 + 真接口）

| 源 | 方法 | 耗时 | 结果 |
|---|---|---|---|
| 番茄 | categoryMenus | 0.9 s | 12 组 / 181 按钮 |
| 番茄 | categoryPage | 1.8 s | 100 本（服务端固定一页） |
| 番茄 | search「剑来」1/2 页 | 1.6 / 1.2 s | 10 + 10 本，0 重复 |
| 番茄 | bookDetail | 2.0 s | 1316 集，主播=索尔配音 |
| 番茄 | audio（5.8 修复后） | 1.1 s | 206 audio/mpeg，前 3 集全 206；带 Referer 时是 403 |
| 七猫 | categoryMenus | 0.9 s | 3 组 / 31 按钮 |
| 七猫 | categoryPage | 1.1 / 0.8 s | 首页 52 本；分类 10 本 / 195 页 |
| 七猫 | bookDetail | 1.4 s | 《剑来》1279 集，7 种 AI 音色 |
| 七猫 | audio 默认/古风御姐/相声阿龙 | 0.9 s | 三次 206，三个文件互不相同（音色真生效） |
| 整包 | 12 脚本同作用域加载 | — | 39 个源全部注册，无加载期异常 |

> 5.8 改动：只改了 `fanqie.js` 的 `audio()` —— 去掉 Referer 头。其余逻辑与 5.7 相同。

两个新脚本都扫过 `=>`、`const`、`let`、反引号、`class`、展开符、可选链、async：纯 ES5，Rhino 可跑。

## 四、装进仓库

```bash
cp fanqie.js qimao.js plugins/ShunSources/
# manifest.json 的 scripts 末尾加两行，version 改 5.7（本目录已改好）
cd plugins/ShunSources && zip -r ../dist/ShunSources.zip . -x '.*'
```

## 五、已知限制

- 番茄分类固定 100 本（接口不认翻页），找书用搜索；搜索最多 20 页。
- 七猫榜单固定 30 本；AI 音色是整源设置，不按书记住。
- 两个站都是第三方接口，挂了改脚本顶部的 `SITE` 常量即可。
