# CabPlay for CrossOver

用于 macOS CrossOver 的 CabPlay 定制补丁。当前适配 CabPlay 1.22.1 和 Euro Truck Simulator 2 1.62.3.3s。

- `outputs/cabplay-local-music.py` 包含本地音乐界面、曲库更新和 iPad 远程显示的原始补丁。
- `outputs/cabplay-soundcheck.py` 实现本地音乐的自动响度均衡。独立安装脚本面向 1.22.0，1.22.1 升级构建会迁移这项功能。
- `outputs/cabplay-d3dmetal-textures.py` 是目前使用的 D3DMetal 双屏补丁。其他 D3DMetal 脚本记录先前的调试方案。
- `work/ipad/` 保存 CabPlayPad 的 Swift 源码和应用配置。
- `work/v1221/` 保存 1.22.1 的合并和升级脚本。构建依赖本机 CrossOver 安装、官方版本文件和已验证的游戏文件，路径与版本校验针对原设备。

上游项目为 [Ku3rb1s/CabPlay](https://github.com/Ku3rb1s/CabPlay)。官方程序和生成的安装包在本机单独保存。
