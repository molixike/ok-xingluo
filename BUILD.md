# 构建说明：如何从原版 OK 魔改包重现融合版

## 原料

- 原版包：OK影视魔改版 `merged-signed-v8.apk`（`com.fongmi.android.tv` 5.1.6 / 516，OKTV Merge 签名）
- 星落资源：`assets/1118.jar`、`assets/ysp-live-v9.5.py`（本仓库 assets 目录即是原文）
- 种子配置：`source/xingluo-config.json`

## 工具

- JDK 17
- apktool 2.12.1
- uber-apk-signer 1.3.0（zipalign + 签名 + 校验一条龙）

## 步骤

1. 反编译原包：`apktool d merged-signed-v8.apk -o ok-src`
2. 放入资源：
   - `ok-src/assets/1118.jar`
   - `ok-src/assets/ysp/ysp-live-v9.5.py`
   - `ok-src/assets/xingluo-config.json`
3. 打播种补丁：对 `ok-src/smali/com/fongmi/android/tv/bean/Config.smali` 应用 `source/Config-seed.patch`（给 `vod()`、`live()` 在 URL 为空时写入 `assets://xingluo-config.json`、名称“星落内置”并 `insert()`；打完的全文见 `source/Config.smali`，可直接覆盖同名文件代替打补丁）。
4. 回编译：`apktool b ok-src -o ok-xingluo-unsigned.apk`
5. 对齐加签：`java -jar uber-apk-signer.jar -a ok-xingluo-unsigned.apk --ks xingluo-merge.keystore --ksAlias xingluo`，产物约 82,211,508 字节。
6. 校验：签名验证 v1/v2/v3 通过；再与原包做结构对比（包名/版本/权限/Activity/dex 数一致，仅多 3 个 assets）。

## 签名

- 证书：CN=Xingluo Merge，SHA-256 指纹 `23d22247e13ef41a9808c8e2090576eb7528784f778c30da0e85378ee770177b`，有效期至 2054-03-22。
- 私钥（keystore）**不在本仓库**，由作者单独保管。本系列后续更新必须用同一 keystore 签名才能覆盖安装。
- 因为签名与原 OKTV Merge 版不同，从原版换到融合版必须先卸载再安装（应用内备份配置后恢复）。

## 已知限制

- 构建环境无安卓真机/模拟器，成品只做静态与结构校验，未做运行测试。
- ysp 脚本是独立服务，内置只是把文件放进包里，运行时仍需 Termux 或局域网主机执行。
- 配置级代理依赖本机 7890 端口有代理服务在跑；没有时仅种子配置里列出的境外域名受影响。

## v2.0 增量（在 v1 产物工程上继续）

1. 放入 `assets/legado.py`、`assets/legado/src-1.json` 至 `src-7.json`、`assets/xingluo-config-v2.json`。
2. Config 播种补丁改版：空配置播种 v2；URL 等于 v1 种子时刷新为 v2（diff 见仓库 git 历史与 v2 种子逻辑说明）。
3. apktool.yml 的 versionCode 改 517，回编译、同 keystore 签名、结构对比（相对 v1 仅多 9 条目）。
4. 书源筛选方法：从书源大包过滤无 JS 规则源，引擎本地全链路实测（搜索/详情/目录/正文）后入选。
