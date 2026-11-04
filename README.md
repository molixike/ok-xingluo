# OK影视 · 星落融合版

在 OK影视 5.1.6 魔改版（插件中心 / 音乐舞台 / 漫画 / 阅读器 / 内置浏览器）基础上，融入星落 6.0.5 的内置资源与配置，做成的融合安装包。

## 下载

- 最新版在 [Releases](https://github.com/molixike/ok-xingluo/releases) 里，附件 `OKTV-Xingluo-v1.0.apk`（82.2 MB）
- 直下载：https://github.com/molixike/ok-xingluo/releases/download/v1.0/OKTV-Xingluo-v1.0.apk
- 加速下载：https://ghfast.top/https://github.com/molixike/ok-xingluo/releases/download/v1.0/OKTV-Xingluo-v1.0.apk

## 安装须知（务必先看）

1. 本版签名与 OKTV Merge 原版不同，**不能覆盖安装**：先在旧版里把配置备份好，卸载旧版，装融合版，再恢复备份。
2. 央视直播（ysp）是独立服务脚本：脚本已内置在包里（assets/ysp/），但需要在手机 Termux 或局域网主机上单独运行，种子配置里的直播线路指向 `http://127.0.0.1:8767/all.m3u`。用法见 [docs/port-pack-import.md](docs/port-pack-import.md)。
3. 本包在构建环境里通过了签名校验（v1/v2/v3）和与原包的结构对比；构建环境没有安卓真机/模拟器，未做真机运行测试。

## 更新日志

### v1.0（2026-11-05）

基底：OK影视 5.1.6 魔改版（原有插件中心、音乐舞台含桌面歌词、漫画、阅读器、内置浏览器全部保留）。

融合新增：

- **内置星落爬虫 jar**：`assets/1118.jar`（MD5 `a81c03da23212c9ffc8a699465dedc8b`），含 `csp_XBPQ`、`csp_AppYs`、`csp_AppYsV2`、`csp_PushAgent` 引擎与 `JsonBasic` / `JsonParallel` / `JsonSequence` 三个解析器。
- **内置央视频直播脚本**：`assets/ysp/ysp-live-v9.5.py`（央视频全频道直播代理，独立服务，端口 8767）。
- **首启自动播种配置**：给 `Config.vod()` / `Config.live()` 打了 smali 补丁，没配过接口时自动加载包内种子配置 `assets/xingluo-config.json`（名称“星落内置”）；自己填了接口后以自己的为准。
- **种子配置内容**：spider 指向包内 1118.jar（走底包自带的 `assets://` 机制加载）；三个星落解析器；一条 ysp 央视直播线路；一条配置级代理预置（github / google / youtube 系域名走 `127.0.0.1:7890`，本机没跑代理服务时只影响这些域名，国内源不受影响）。

已知未移植：

- 星落的 mihomo 代理订阅是代码级功能（内核 + 订阅解析 + 测速），无法随包移植；本版用上面的配置级代理预置替代，本机另跑 Clash 等服务监听 7890 即可生效。
- 三引擎（jar / QuickJS / Python）加载规则无需移植：基底 OK 本身三引擎齐全。

完整记录见 [CHANGELOG.md](CHANGELOG.md)。

## 源码与构建

本仓库的“源码”是这次融合改造的全部材料，照着能从原版 OK 魔改包完整重现这个融合版：

- [source/xingluo-config.json](source/xingluo-config.json)：种子配置原文
- [source/Config.smali](source/Config.smali)：打完补丁的 Config 类全文
- [source/Config-seed.patch](source/Config-seed.patch)：播种补丁的 unified diff（相对原包）
- [assets/1118.jar](assets/1118.jar)、[assets/ysp-live-v9.5.py](assets/ysp-live-v9.5.py)：内置的两个星落资源原文
- [BUILD.md](BUILD.md)：工具、步骤、签名与校验说明（签名私钥不在仓库里）
- [docs/install-guide.md](docs/install-guide.md)：安装说明
- [docs/port-pack-import.md](docs/port-pack-import.md)：移植包逐项说明与手动导入方法
