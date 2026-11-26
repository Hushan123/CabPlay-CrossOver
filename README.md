# CabPlay for CrossOver

## 这个项目做什么？

CabPlay 可以把导航、仪表和媒体界面放进《欧洲卡车模拟 2》的驾驶室。本项目为 **macOS + CrossOver + Steam 版欧卡 2** 提供一套配套补丁，解决 D3DMetal 下的双屏兼容问题，并加入本地音乐和 iPad 副屏。Mac 端功能通过同一个安装器配置。

| 功能 | 装好后能做什么 |
| --- | --- |
| **驾驶室中控与 Ultra** | 用 D3DMetal 和 DirectX 11 开车时，在驾驶室查看 GPS 中控和 Ultra 数字仪表。补丁针对加载驾驶室时的纹理上传问题。 |
| **本地音乐** | 把歌放进欧卡 2 的音乐目录，在 CabPlay 里选歌、建播放列表、切歌、调整音量和切换顺序或随机播放。支持内嵌封面、封面取色和「正在播放」联动。 |
| **自动响度均衡** | 后台分析歌曲并生成播放缓存，让切歌时的听感音量更接近。仍可用音量滑块调节整体音量。 |
| **iPad 副屏** | 通过无线扫码、手动输入网址或 USB 数据线连接，在 iPad 上查看 CabPlay 并回传触控。无线目标约 30 FPS，USB 约 60 FPS。iPad 端需单独签名安装一次。 |

## 三步安装

**新用户可以直接安装官方 CabPlay 1.22.1。** 1.22.0 安装包在全新安装时只用来提取游戏内兼容 DLL，下载后放着即可。桌面端全程使用 1.22.1。

1. **准备游戏和 CabPlay。** 在 CrossOver 中用同一个容器运行 Steam 和官方 **CabPlay 1.22.1**，并确认游戏版本为 **欧卡 2 1.62.3.3s**。安装器当前读取名为 `Steam` 的容器。Mac 需要 Python 3.9+、Git、`ffmpeg` 和 `ffprobe`。已有 Homebrew 的用户可用 `brew install ffmpeg` 安装音乐工具。运行补丁前，先退出游戏和 CabPlay。
2. **下载兼容 DLL 的来源包。** 把官方 **1.22.0** 安装包 `CabPlay-Setup-1.22.0.exe` 放进 Mac 的「下载」文件夹，保持文件名原样，无需双击运行。如果游戏目录里已经有脚本可识别的兼容 DLL，可以跳过这一步。[官方 CabPlay 发布页](https://github.com/Ku3rb1s/CabPlay/releases)
3. **复制到 Mac 终端执行。**

   ```bash
   git clone https://github.com/Hushan123/CabPlay-CrossOver.git
   cd CabPlay-CrossOver
   python3 install.py
   ```

看到「已安装 CabPlay 全功能补丁」后，在 CrossOver 的 Steam 容器选 **D3DMetal**，用 **DirectX 11** 启动欧卡 2。进入驾驶室后，中控和 Ultra 应随车辆移动刷新。

### 安装目录与检查

安装器会尝试从 Steam 游戏库定位欧卡 2。游戏可以放在默认库或自定义库。找不到游戏时，手动指定安装目录：

```bash
python3 install.py --game-dir "/你的 Steam 游戏库/steamapps/common/Euro Truck Simulator 2"
```

如果旧版安装包放在其他目录，可以用 `--legacy-installer` 指定文件。运行 `python3 install.py --check` 可以先校验安装环境。正式安装会备份程序、插件和配置。

### 手头只有 1.22.1 安装包怎么办？

全新安装且游戏目录里只有 1.22.1 自带的 DLL 时，还需要下载一次 1.22.0 安装包来完成全功能安装。当前 D3DMetal 补丁针对经过验证的 **游戏内插件 1.12.15**，因此安装器会从 1.22.0 安装包提取这个 DLL，再与 1.22.1 桌面端配套使用。可以用 `python3 install.py --check` 先确认你的机器是否已经具备兼容 DLL。

## 装好后怎么用

### 本地音乐

把 MP3、FLAC、M4A、OGG 或 WAV 放进 Mac 的 `~/Documents/Euro Truck Simulator 2/music`，再打开 CabPlay 主屏的「本地音乐」。可以选歌、建播放列表、切换顺序或随机播放，也能调整音乐音量。播放器读取内嵌封面，并按封面取色。

响度均衡默认开启。第一次处理曲库需要一点时间，处理好的歌曲从下次播放起会使用均衡缓存。缓存放在音乐目录的 `.cabplay` 中，原始音频仍可直接播放。

### iPad 副屏

Mac 端已经安装好。iPad 需要额外安装一次 **CabPlayPad**，要求 **iPadOS 16 或更新版本**。如果你还没有客户端，在装有完整 Xcode 的 Mac 上从仓库根目录运行：

```bash
./build-ipad.sh
```

脚本会生成 `outputs/CabPlayPad-unsigned.ipa`。用你自己的签名流程（如 AltStore 或 SideStore）签名并安装到 iPad。已经装好 CabPlayPad 的用户可以直接连接。

- **无线**：让 Mac 和 iPad 连同一局域网，打开 CabPlay 的远程显示，用 CabPlayPad 扫描二维码或输入完整配对网址。无线目标约 30 FPS。
- **USB**：打开 iPad 上的 CabPlayPad，用支持数据传输的线连接 Mac。首次连接按系统提示完成信任。USB 目标约 60 FPS。

两种方式都支持触控回传。实际帧率取决于 CabPlay 的画面刷新和设备性能。

## 恢复与排查

退出欧卡 2 和 CabPlay，在仓库目录运行 `python3 install.py --restore`。脚本会恢复安装前的应用、游戏文件、插件配置和后台服务。备份保存在 `~/Library/Application Support/CabPlay-CrossOver`。

- **版本校验失败**：确认欧卡 2 是 1.62.3.3s、桌面端是官方 1.22.1。Steam 或 CabPlay 更新后二进制可能变化，需要相应版本的补丁。
- **游戏报错或双屏黑屏**：核对 CrossOver 的 D3DMetal 和游戏 DX11 设置。游戏文档目录的 `game.crash.txt` 和游戏目录的 `bin/win_x64/plugins/cabplay.log` 可以帮助定位。
- **歌曲没出现**：核对 `music` 目录，等后台扫描结束再打开播放器。
- **iPad 连不上**：无线检查局域网权限和完整配对地址。USB 检查设备信任、数据线和客户端是否在前台。

本项目基于 [Ku3rb1s/CabPlay](https://github.com/Ku3rb1s/CabPlay)。[`install.py`](install.py) 是安装入口。早期的单项补丁留在 [`outputs/`](outputs/)，适合维护和排查。
