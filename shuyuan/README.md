# 阅读NG 分组书源

## 关键事实（从 legado_NG 源码确认）

- 分组字段：**`bookSourceGroup`**，逗号分隔，一个源可同时属于多个分组
- 类型 `bookSourceType`：**0 文本 / 1 音频 / 2 图片 / 3 文件 / 4 视频**（纯枚举，不是位掩码）
- 导入必填五字段（缺任一会被静默跳过）：
  `bookSourceUrl` / `bookSourceName` / `bookSourceGroup` / `enabled` / `customOrder`
  ⚠️ `enabled`、`customOrder` 必须**显式写进 JSON**，靠默认值兜底会被判空跳过
- 导入入口：书源管理 → 网络导入（URL）/ 本地导入（文件）/ 粘贴 JSON 文本
- 导入对话框里有「保留分组」开关，勾上才会把 JSON 里的分组原样带入
- 分组里会混入系统标签（失效/规则为空/校验超时/已阻止弹窗），自定义分组名别撞这些

## 用法

1. 改 `shuyuan_group_template.json` 里的站点和分组
2. 上传到 GitHub / 任意静态托管
3. 阅读NG：书源管理 → 网络导入 → 粘贴链接
4. 导入时勾选「保留分组」
5. 书源管理页用「列表 / 分组」切换查看

## 注意

JSON 务必存成 **UTF-8 无 BOM**，BOM 会让第一条字段匹配失败被跳过。
