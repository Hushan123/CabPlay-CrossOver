# CabPlay for CrossOver

这个项目维护一套在 **macOS + CrossOver + Steam 版《欧洲卡车模拟 2》** 上使用 [CabPlay](https://github.com/Ku3rb1s/CabPlay) 的定制补丁。它覆盖驾驶室中控和 Ultra 仪表、iPad 副屏，以及带封面、播放列表和自动响度均衡的本地音乐播放器。

当前维护的是 **CabPlay 1.22.1 的定制迁移**。本仓库提供补丁、迁移脚本和 iPad 客户端源码。安装和构建需要自行准备对应版本的官方程序。

## 功能

| 功能 | 用法与行为 |
| --- | --- |
| **GPS 中控和 Ultra 仪表** | 针对 CrossOver D3DMetal 下加载驾驶室时的纹理上传问题，调整游戏和 CabPlay 插件之间的上传路径。Ultra 可从启动时保持开启。 |
| **本地音乐** | 从欧卡 2 的 `music` 目录读取 MP3、FLAC、M4A、OGG 和 WAV。播放页读取曲目信息和内嵌封面，并按封面取色。 |
| **播放控制** | 支持选歌、播放列表、上一曲和下一曲、进度拖动、顺序和随机模式，以及独立的音乐音量。CabPlay 的「正在播放」可打开本地音乐播放页。 |
| **响度均衡** | 后台逐首测量响度，以约 **−16 LUFS** 为目标并限制峰值和最大增益。补偿结果存入播放缓存，音量滑块继续控制整体播放音量。 |
| **iPad 无线副屏** | 在同一局域网内扫码或输入配对网址。客户端显示 CabPlay 画面并回传触控。适配版服务器将无线帧流设为约 **30 FPS**，编码宽度上限为 **1920 px**。 |
| **iPad USB 副屏** | 在 iPad 打开 CabPlayPad 后，用数据线连接 Mac。Mac 后台进程通过 usbmux 转发画面和触控。USB 模式目标约 **60 FPS**，编码宽度上限为 **2560 px**。 |

帧率和画质取决于 CabPlay 提供的原始画面、编码速度、设备和连接。iPad 客户端使用横屏全屏显示，连接期间保持屏幕唤醒。

## 版本与环境

| 组件 | 当前适用范围 |
| --- | --- |
| CabPlay 桌面端 | 1.22.1 定制迁移的输入是已经应用本仓库补丁和响度均衡的 1.22.0。 |
| 游戏端纹理补丁 | 欧卡 2 **1.62.3.3s** 与 CabPlay 原版插件 DLL **1.12.15**。脚本会核对文件哈希。 |
| CrossOver | 现有脚本以名为 `Steam` 的容器和 Windows 用户 `crossover` 为默认路径。D3DMetal 方案对应游戏的 DX11 模式。 |
| iPad | 客户端配置要求 iPadOS 16.0 或更新版本。二维码扫描还需要设备支持 VisionKit 扫描并授予相机权限。 |
| Mac 工具 | Python 3.9+。音乐扫描需要 PATH 中的 `ffmpeg` 和 `ffprobe`。构建迁移包还需要 Git、Node.js 和 macOS 的 `bsdtar`。 |

## 安装与更新

### 已有 1.22.0 定制版，升级到 1.22.1

1. 退出欧卡 2 和 CabPlay，保持游戏所在外置盘已挂载。
2. 下载官方 CabPlay **1.22.1** 安装包。构建脚本会在 CrossOver 容器内的 `AppData/Roaming/CabPlay/update` 查找 `CabPlay-Setup-1.22.1.exe`。安装包用于提取原版资源。
3. 将官方 **1.22.0** 的 `app.asar` 和 `cabplay.dll` 分别放到 `work/v122/full/resources/app.asar` 和 `work/v122/full/resources/plugin/cabplay.dll`。保留现有定制版的 `app.asar.before-soundcheck` 和已安装的响度扫描脚本。
4. 从仓库根目录构建并安装。

   ```bash
   python3 work/v1221/build.py
   python3 outputs/CabPlay-1.22.1-HIKVISION.pyz
   ```

构建脚本以原版 1.22.0、当前定制版和原版 1.22.1 做三方合并。升级包校验当前安装和游戏端文件，保留外置盘上的定制 DLL 和游戏程序，并备份升级前的 CabPlay 目录。生成的安装包按本机文件哈希校验，其他机器上的安装或文件有变动时需要重新核对。

### 本地音乐与响度均衡

Mac 上的默认曲库目录：

```text
~/Documents/Euro Truck Simulator 2/music
```

把歌曲放进去后，从 CabPlay 主屏打开「本地音乐」。背景扫描会更新曲库和封面缓存，播放列表以及音量偏好存放在 CabPlay 的本地数据中。响度均衡会逐首生成 FLAC 缓存，在该歌曲下次播放时生效。原始音频文件可继续用于其他播放器。

`cabplay-local-music.py` 的独立安装入口面向 **原版 1.20.2**。其中 `--check` 可试运行构建并检查版本、曲库和封面。`cabplay-soundcheck.py` 的独立安装入口面向 **1.22.0 定制版**。1.22.1 通过迁移流程合并两项功能。

### D3DMetal 双屏补丁

`outputs/cabplay-d3dmetal-textures.py` 会同时校验并修改 `eurotrucks2.exe` 和 `plugins/cabplay.dll`。运行前先退出游戏，并核对脚本顶部的 `BIN` 与实际 Steam 游戏目录。仓库的默认值指向名为 `HIKVISION` 的外置盘。

```bash
python3 outputs/cabplay-d3dmetal-textures.py
```

当前组合使用 **原版 DDS 占位纹理**，游戏插件配置为 `mipmaps=0`、`fastupload=0`、`[cluster] enabled=1`。启动后进驾驶室，实际观察 GPS 和 Ultra 是否随车辆移动持续刷新。Steam 更新游戏程序或 CabPlay 更新 DLL 后，需要重新核对版本与哈希。

### 连接 iPad

- **无线**：Mac 和 iPad 连接同一个局域网，在 CabPlay 打开远程显示，使用 CabPlayPad 扫描配对二维码或手动输入完整配对网址。客户端首次连接时可能请求本地网络权限。
- **USB**：在 iPad 上打开 CabPlayPad，然后用支持数据传输的线连接 Mac。首次连接按设备提示完成信任。Mac 端需要已运行本地音乐与 USB 转发后台进程。
- **自行构建**：`work/ipad/` 提供 Swift 源码和 `Info.plist`。可在 Xcode 创建 iPad App 目标，加入两个 Swift 文件并应用该配置，按自己的 Apple 开发签名安装到设备。仓库提供源码，签名安装包需自行构建。

## 回滚

| 要恢复的部分 | 操作 |
| --- | --- |
| **1.22.1 应用升级** | 退出游戏和 CabPlay，运行 `python3 outputs/CabPlay-1.22.1-HIKVISION.pyz --restore`。它使用 `CabPlay.before-1221` 备份交换应用目录。 |
| **D3DMetal 游戏纹理补丁** | 退出游戏，运行 `python3 outputs/cabplay-d3dmetal-textures.py --restore`。它恢复该脚本识别的游戏程序和插件 DLL。 |
| **1.22.0 独立响度补丁** | 退出 CabPlay，运行 `python3 outputs/cabplay-soundcheck.py --restore`。它使用安装时保存的 ASAR 备份恢复播放器。 |

## 排查问题

| 现象 | 优先检查 |
| --- | --- |
| 载入生涯时崩溃 | 查看欧卡 2 文档目录的 `game.crash.txt`，以及游戏 `bin/win_x64/plugins/cabplay.log`。记录崩溃时间、CrossOver 图形后端、游戏版本和插件版本。 |
| 中控黑屏，或 Ultra 回到原车仪表 | 检查 `cabplay.ini` 的 `[cluster]` 开关和 `CabPlay-Display` 下的占位纹理。日志出现 `Placeholder-like texture ... not used` 时，先检查是否误用了早期 BGRA 纹理试验。 |
| 本地音乐无曲目或封面 | 检查歌曲是否位于上述 `music` 目录、扩展名是否受支持，以及 `ffmpeg`、`ffprobe` 和扫描后台进程是否可用。 |
| 有的歌仍明显偏轻 | 等待初次扫描完成，重新播放该曲。高峰值或特别安静的曲目会受峰值保护与最大增益限制。 |
| iPad 无法连接 | 无线先检查局域网和配对网址。USB 先检查数据线、设备信任状态、客户端是否打开，以及 Mac 转发后台进程是否运行。 |

## 源码目录

| 路径 | 用途 |
| --- | --- |
| [`outputs/cabplay-local-music.py`](outputs/cabplay-local-music.py) | 本地音乐界面、曲库扫描、播放控制和 USB 转发。 |
| [`outputs/cabplay-soundcheck.py`](outputs/cabplay-soundcheck.py) | 逐曲测量响度、管理播放缓存并接入播放器。 |
| [`outputs/cabplay-d3dmetal-textures.py`](outputs/cabplay-d3dmetal-textures.py) | 当前使用的双屏兼容补丁。其余 D3DMetal 脚本保留了早期排查方案。 |
| [`work/ipad/`](work/ipad/) | CabPlayPad 客户端源码与配置。 |
| [`work/v1221/`](work/v1221/) | 1.22.1 迁移构建、合并、安装和回滚逻辑。 |

提交问题时，附上相关版本、复现步骤和崩溃前后的少量日志。配对网址中可能含有令牌，分享前请删去令牌和个人路径。
