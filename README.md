# CabPlay for CrossOver

给 macOS 上的《欧洲卡车模拟 2》装一套 CabPlay 补丁。**Mac 上运行一次安装脚本**，就能装好 D3DMetal 驾驶室中控和 Ultra 仪表、本地音乐和响度均衡，以及 iPad 无线和 USB 副屏所需的 Mac 端服务。

## 三步安装

1. **准备游戏和 CabPlay。** 在 CrossOver 的 `Steam` 容器中安装 **欧卡 2 1.62.3.3s** 和官方 **CabPlay 1.22.1**。退出游戏和 CabPlay，外置游戏盘保持连接。Mac 需要 Python 3.9+、Git 和 FFmpeg。使用 Homebrew 的话，运行 `brew install ffmpeg` 即可补齐音乐工具。
2. **准备兼容插件。** 把官方 **1.22.0** 安装包 `CabPlay-Setup-1.22.0.exe` 放进 Mac 的「下载」文件夹。脚本会从里面提取经过验证的游戏 DLL，桌面端仍用 1.22.1。如果游戏目录已经有兼容 DLL，可以跳过这一步。[官方 CabPlay 发布页](https://github.com/Ku3rb1s/CabPlay/releases)
3. **复制到 Mac 终端执行。**

   ```bash
   git clone https://github.com/Hushan123/CabPlay-CrossOver.git
   cd CabPlay-CrossOver
   python3 install.py
   ```

看到「已安装 CabPlay 全功能补丁」后，在 CrossOver 的 Steam 容器选 **D3DMetal**，用 **DirectX 11** 启动欧卡 2。进入驾驶室后，中控和 Ultra 应随车辆移动刷新。

脚本会在写入前校验版本并备份程序、插件和配置。如果想先检查环境，运行 `python3 install.py --check`。如果脚本找不到游戏，在命令末尾加 `--game-dir `，再把游戏安装文件夹拖进终端。如果旧版安装包放在别处，可以用 `--legacy-installer` 指定该文件。

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
