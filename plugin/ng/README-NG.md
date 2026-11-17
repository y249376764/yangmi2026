# 番茄/七猫 听书源 → 阅读 NG（legado_NG）音频书源

从 `ssts 随身听书插件 5.8` 的 `fanqie.js`、`qimao.js` 迁移而来，接口同一套（`fq.neeao.dpdns.org`、`qm.neeao.dpdns.org`），**不是** TVBox py、也不是海阔规则。

## 导入

阅读 NG → 书源管理 → 右上角 ＋ → 网络导入，粘贴：

```
https://gh-proxy.org/https://raw.githubusercontent.com/y249376764/yangmi2026/main/plugin/ng/fanqie-qimao-ng.json
```

单个导入（失败时分开试）：

```
https://gh-proxy.org/https://raw.githubusercontent.com/y249376764/yangmi2026/main/plugin/ng/番茄听书-ng.json
https://gh-proxy.org/https://raw.githubusercontent.com/y249376764/yangmi2026/main/plugin/ng/七猫听书-ng.json
```

jsDelivr 备用（中文文件名可能 301，用合并包最稳）：

```
https://cdn.jsdelivr.net/gh/y249376764/yangmi2026@main/plugin/ng/fanqie-qimao-ng.json
```

## 结构（都是 bookSourceType=1 音频源）

| 环节 | 番茄 | 七猫 |
|---|---|---|
| 搜索 | `/api/search?key={{key}}&tab_type=2&offset=0` → `data.list[*]` | `/api/audio/search?keyword={{key}}&page=1` → `data.items[*]` |
| 详情 | `/api/detail?book_id=` → `data` | `/api/audio/info?id=` → `data`（自带全部章节） |
| 目录 | `/api/book?book_id=` → `data.volumes[*].chapters[*]` | 复用详情 `data.chapters[*]` |
| 播放 | `/api/content?item_id=&book_id=&tab=听书` → `data.content` | `/api/audio/chapter?id=&cid=&voice=` → `data.url` |
| 发现 | `/api/discover?tab=听书&type=899&gender=2&genre_type=1` → `data.books[*]`（字段是 `book_name`/`thumb_url`/`abstract`） | `/api/audio/home` → `data.sections[*].items[*]` |

## 三个必须记住的坑

1. **header 里不能放 Referer**。番茄音频在 `fqnovelvod.com` CDN，规则是「带 Referer 就 403 `deny by referer access rule`」，只带 UA 才 206。所以两个源的 `header` 都只有 User-Agent。
2. **七猫 AI 书必须带 `voice`**，否则「该章节暂无可播放音频」；`voice` 取详情里的 `defaultVoice`，在 `ruleToc.chapterList` 阶段就拼进 `chapterUrl`（每本书只开一部分音色，不能写死）。真人书传 voice 会被忽略，不影响。
3. **番茄搜索与发现字段名不同**：搜索是 `name/cover/intro`，发现是 `book_name/thumb_url/abstract`，混用会得到空列表。

## 自测（2026-11-16，真接口）

| 项 | 番茄 | 七猫 |
|---|---|---|
| 搜索“剑来” | 10 本 | 10 本 |
| 详情 | 《开局剑落南海…》1316 集 | 《剑来》1279 集 / AI 演播 |
| 目录→首集播放 | `206 audio/mpeg` | `206 audio/mpeg`（voice=10） |
| 发现页 | 100 本 | 52 本 |
| 真人书 | — | 《剑来-第七季广播剧》179 集，voice 空也 206 |

> 番茄 `/api/discover` 是 70KB 大包，偶尔 TLS 断连返回空，重试即可（NG 里重进发现页会重拉）。
