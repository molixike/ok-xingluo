# 阅读书源：导入与使用说明（v2 新增）

## 它是怎么工作的

v2 内置了一个 **Legado 书源兼容引擎**（`assets/legado.py`，PY 爬虫）。每个 Legado 书源在配置里对应一个站点：

- 站点 `api` 指向引擎：`assets://legado.py`
- 站点 `ext` 指向该书源的 JSON：`assets://legado/src-N.json`
- 站名带 `[小说]` 标记，App 内置阅读器会自动接管（搜索出书 → 详情出目录 → 点章节读正文，排版/书签/听书用阅读器自带功能）

种子配置 v2 已预置 7 个实测可用的源（梧桐中文、夜天连看、穿越小说、快眼看书、86读书、芙蓉小说、笔趣阁），装好后在搜索里搜书名即可读。

## 自己加书源（导入）

1. 准备书源 JSON：Legado 书源包（如 XIU2/Yuedu、aoaostar 的书源合集）里挑一个源，单独存成一个 `.json` 文件（内容是一个书源对象，或只含一个源的数组）。
2. 把文件放到手机存储，例如 `/storage/emulated/0/Download/legado/我的源.json`。
3. 在你自己的接口配置里加一个站点（或用配置编辑工具加）：

```json
{"key": "legado_my", "name": "[小说] 我的源", "type": 3,
 "api": "file:///storage/emulated/0/Download/legado/legado.py",
 "ext": "file:///storage/emulated/0/Download/legado/我的源.json",
 "searchable": 1, "quickSearch": 1}
```

注意：引擎文件也要拷一份到手机（就是包里的 `assets/legado.py`，仓库 `source/legado.py` 同一份），`api` 指过去；或者把 `api`/`ext` 写成任何能直达的 http(s) 地址（比如你自己仓库的 raw 链接）也行。

## 引擎支持范围（重要）

支持的 Legado 规则子集：

- CSS/JSoup 选择器：普通 CSS、`class.x` / `id.x` / `tag.x` 链式写法、`.N` 索引、`[n:m]` 切片、`!N` 排除
- `@XPath:` 规则、`@Json:` / `$.` 路径规则
- `##正则##替换##` 后处理（含 `$1` 反向引用）
- 搜索 GET/POST（含单引号选项格式、`charset: gbk` 编码）
- 目录分页 `nextTocUrl`、正文分页 `nextContentUrl`、正文 `replaceRegex` 净化
- 目录顺序自检：首章序号大于尾章时自动正序

**不支持**：带 `@js:`、`<js>`、`java.*` 的规则（需要 Legado 的 JS 运行时）。这类源加进来会搜不到书或正文为空，换纯规则的源即可。构建时统计过：主流书源包里约四成是纯规则源，够挑。

## 配套文件

- v2.0 Release 附带 `legado-clean-pool.json`：594 个纯规则书源（已去重），是从大书源包里筛出来的，未逐一实测，按上面方法挑着加。
- 引擎源码在仓库 `source/legado.py`，预置的 7 个源在 `source/legado/`。

## 已知限制

- 书源站点本身经常换域名/挂站，某个源失效是常态，换同书名的其他源即可，这也是做成可导入的原因。
- 换源（同书多源自动匹配）是 Legado 本体的功能，未移植；多源搜同名书手动切换站点是等效做法。
- 本包未经真机运行测试（构建环境无安卓设备）；引擎已在电脑上对 7 个预置源做过搜索→目录→正文全链路实测（2026-11-05）。
