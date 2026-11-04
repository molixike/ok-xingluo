# 更新日志

## v1.0（2026-11-05）

首个融合版发布。基底为 OK影视 5.1.6 魔改版（包名 `com.fongmi.android.tv`，versionCode 516），融合星落 6.0.5 的以下内容：

### 新增

- 内置 `assets/1118.jar`（星落爬虫 jar，518,755 字节，MD5 `a81c03da23212c9ffc8a699465dedc8b`）。可用引擎：`csp_XBPQ`、`csp_AppYs`、`csp_AppYsV2`、`csp_PushAgent`；解析器：`JsonBasic`、`JsonParallel`、`JsonSequence`。注意 jar 只是引擎，星落各站点的 ext 参数在其远程配置里，不在包内。
- 内置 `assets/ysp/ysp-live-v9.5.py`（192,193 字节，MD5 `a4f28ebadef5d52e272d90d5681aa9ba`）。经核查它是独立的央视频全频道直播代理服务（纯标准库，端口 8767，提供 `/all.m3u` 等路由），不是可加载的 PY 爬虫源；需在 Termux 或局域网主机单独运行后，由直播线路消费。
- 内置 `assets/xingluo-config.json` 种子配置：spider 指向 `assets://1118.jar`；parses 含星落聚合/并行/顺序三个解析器；lives 含“央视直播·ysp”（`http://127.0.0.1:8767/all.m3u`）；proxy 含“本地代理”一条（github、githubusercontent、googleapis、youtube、googlevideo、gstatic、ytimg 等域名转发 `127.0.0.1:7890`）。

### 修改

- smali 补丁 `com/fongmi/android/tv/bean/Config` 的 `vod()` 与 `live()`：无已存配置（URL 为空）时自动以种子配置建一条名为“星落内置”的配置并入库，走底包自带的 `assets://` 本地代理机制加载。用户自填接口后不再干预。
- 签名更换为新建的 Xingluo Merge 证书（SHA-256 指纹 `23d22247e13ef41a9808c8e2090576eb7528784f778c30da0e85378ee770177b`）。因此与 OKTV Merge 签名的旧版不能互相覆盖安装，后续本系列更新用同一证书签名可直接覆盖。

### 未移植（及原因）

- mihomo 代理订阅（星落的 `libmihomo.so` 内核加订阅解析、测速、注入配置链）：代码级功能，无法以资源或配置形式移植。替代方案为种子配置里的配置级代理预置。
- 三引擎加载规则：基底已内建 jar 加载器、QuickJS、Chaquopy Python 三引擎，无需移植。

### 校验

- 重打包后 zipalign + 签名校验通过（v1/v2/v3）。
- 与原包结构对比：包名、版本、主 Activity、权限数（19）、Activity 数（19）、dex 数（5）全部一致；条目 1611 → 1614，仅新增上述 3 个 assets，签名文件由 OKMERGE 换为 XINGLUO，其余无删减。
- 未做真机/模拟器运行测试（构建环境无安卓设备），安装与使用问题请结合 docs 里的说明排查。
