#!/usr/bin/env python3
"""Install the CabPlay 1.22.1 CrossOver patch from this checkout."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import runpy
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
MUSIC = runpy.run_path(str(ROOT / "outputs/cabplay-local-music.py"))
SOUND = runpy.run_path(str(ROOT / "outputs/cabplay-soundcheck.py"))
GRAPHICS = runpy.run_path(str(ROOT / "outputs/cabplay-d3dmetal-textures.py"))
STATE = Path.home() / "Library/Application Support/CabPlay-CrossOver"
BOTTLE = Path.home() / "Library/Application Support/CrossOver/Bottles/Steam"
ARCHIVE = MUSIC["ASAR"]
DLL, EXE = GRAPHICS["DLL"], GRAPHICS["EXE"]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def patch_archive(original):
    tree, payload = MUSIC["unpack"](original)
    def read(name):
        return MUSIC["get"](tree, payload, name)

    if json.loads(read("package.json"))["version"] != "1.22.1":
        raise ValueError("请先在 Steam 容器中安装官方 CabPlay 1.22.1。")
    if MUSIC["is_patched"](tree):
        if "soundcheck-v1" not in read("main/local-music.js").decode():
            raise ValueError("检测到其他定制版，请先恢复官方 CabPlay 1.22.1。")
        return original
    delta = json.loads((ROOT / "patch/cabplay-1.22.1.json").read_text())
    changes = {}
    for name, spec in delta.items():
        source = read(name)
        if sha(source) != spec["sha256"]:
            raise ValueError(f"CabPlay 文件版本不匹配：{name}")
        lines = source.decode().splitlines(keepends=True)
        for start, end, text in reversed(spec["edits"]):
            lines[start:end] = [text]
        changes[name] = "".join(lines).encode()
    protocol = MUSIC["replace"](MUSIC["PROTOCOL"], "const type = types[", "let type = types[")
    protocol = MUSIC["replace"](protocol, "size = stat.size;", SOUND["HOOK"])
    changes.update({
        "main/local-music.js": protocol.encode(),
        "ui/local-music.js": MUSIC["PLAYER"].encode(),
        "ui/local-music.css": MUSIC["STYLES"].encode(),
        "ui/local-music-index.js": b"window.CabPlayLocalTracks = [];\n",
        "ui/local-music-index.json": b"[]",
    })
    return MUSIC["archive_with"](original, changes)


def find_game(explicit):
    if explicit:
        folder = explicit.expanduser().resolve()
        return folder if (folder / EXE).is_file() else folder / "bin/win_x64"
    steam = BOTTLE / "drive_c/Program Files (x86)/Steam"
    libraries = [steam]
    vdf = steam / "steamapps/libraryfolders.vdf"
    if vdf.is_file():
        for path in re.findall(r'"path"\s+"([^"]+)"', vdf.read_text(errors="replace")):
            match = re.fullmatch(r"([A-Za-z]):[\\/]+(.*)", path)
            if match:
                drive, rest = match.groups()
                libraries.append(BOTTLE / "dosdevices" / (drive.lower() + ":") / rest.replace("\\", "/"))
    matches = {p.resolve() for library in libraries
               if (p := library / "steamapps/common/Euro Truck Simulator 2/bin/win_x64").joinpath(EXE).is_file()}
    if not matches:
        patterns = (
            "*/steamapps/common/Euro Truck Simulator 2/bin/win_x64/eurotrucks2.exe",
            "*/*/steamapps/common/Euro Truck Simulator 2/bin/win_x64/eurotrucks2.exe",
            "*/*/*/steamapps/common/Euro Truck Simulator 2/bin/win_x64/eurotrucks2.exe",
        )
        for pattern in patterns:
            matches.update(p.parent.resolve() for p in Path("/Volumes").glob(pattern) if p.is_file())
    if len(matches) != 1:
        raise ValueError("无法唯一找到欧卡 2。请加 --game-dir，并把游戏安装文件夹拖进终端。")
    return matches.pop()


def patch_dll(path, installer):
    try:
        return GRAPHICS["plan"](path, DLL, False)[1]
    except (ValueError, FileNotFoundError):
        if installer is None:
            installer = Path.home() / "Downloads/CabPlay-Setup-1.22.0.exe"
        if not installer.is_file():
            raise ValueError("需要官方 CabPlay 1.22.0 安装包来提取兼容 DLL。请将其放在下载目录，或使用 --legacy-installer 指定。")
        dll = subprocess.check_output(["/usr/bin/bsdtar", "-xOf", str(installer), "resources/plugin/cabplay.dll"])
        original_hash, edits = GRAPHICS["FILES"][DLL]
        if sha(dll) != original_hash:
            raise ValueError("安装包里的 DLL 与已验证的 1.22.0 官方版本不符。")
        return GRAPHICS["transform"](dll, edits)


def configure(data):
    text = data.decode("utf-8-sig")
    if not text:
        text = """[hotkeys]
menu=Strg+C
touch=Strg+T

[app]
autostart=1

[screen gps]
original=/vehicle/truck/share/gps.tobj
override=/home/CabPlay-Display/gps.tobj
fingerprint=64x2048
target=1600x900
fps=30
flip=1
source=carplay

[cluster]
flip=1
"""
    newline = "\r\n" if "\r\n" in text else "\n"
    for section, values in {"render": {"mipmaps": 0, "fastupload": 0}, "cluster": {"enabled": 1}}.items():
        header = re.search(rf"(?m)^\[{section}\][ \t]*\r?$", text)
        if header is None:
            text += newline + f"[{section}]" + newline
            header = re.search(rf"(?m)^\[{section}\]", text)
        newline_at = text.find("\n", header.end())
        if newline_at == -1:
            text += newline
            newline_at = len(text) - 1
        start = newline_at + 1
        boundary = re.search(r"(?m)^\[", text[start:])
        end = start + boundary.start() if boundary else len(text)
        body = text[start:end]
        for name, value in values.items():
            body, count = re.subn(rf"(?m)^[ \t]*{name}[ \t]*=[^\r\n]*", f"{name}={value}", body)
            if count == 0:
                body += ("" if not body or body.endswith("\n") else newline) + f"{name}={value}" + newline
        text = text[:start] + body + text[end:]
    return text.encode()


def write(path, data):
    if data is None:
        path.unlink(missing_ok=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        MUSIC["atomic_write"](path, data)


def read(path):
    return path.read_bytes() if path.exists() else None


def change_files(changes):
    before = {p: read(p) for p in changes}
    applied = []
    try:
        for path, data in changes.items():
            if data != before[path]:
                write(path, data)
                applied.append(path)
    except BaseException:
        for path in reversed(applied):
            write(path, before[path])
        raise


def agents(enabled, paths):
    domain = f"gui/{os.getuid()}"
    for path in paths:
        subprocess.run(["launchctl", "bootout", f"{domain}/{path.stem}"], capture_output=True)
        if enabled and path.exists():
            subprocess.run(["launchctl", "bootstrap", domain, str(path)], check=True)


def install(args):
    manifest = STATE / "backup.json"
    usb_agent, sound_agent = MUSIC["USB_AGENT"], SOUND["AGENT"]
    agent_paths = (usb_agent, sound_agent)
    if args.restore:
        rows = json.loads(manifest.read_text())
        previous = {Path(row["path"]): (STATE / row["backup"]).read_bytes() if row["backup"] else None for row in rows}
        for row in rows:
            path = Path(row["path"])
            current = read(path)
            if (path.name in {"app.asar", "cabplay.dll", EXE} and current != previous[path]
                    and (current is None or sha(current) != row["installed"])):
                raise ValueError(f"{path.name} 已被更新，已停止自动回滚。备份见 {STATE}")
        agents(False, agent_paths)
        change_files(previous)
        agents(True, agent_paths)
        manifest.unlink()
        print("已恢复补丁安装前的文件和后台服务。")
        return

    if manifest.exists():
        raise ValueError("此安装器已运行过。可用 --restore 恢复后重新安装。")
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise ValueError("请安装 FFmpeg，并确保 ffmpeg 和 ffprobe 都在 PATH 中。")
    game = find_game(args.game_dir)
    exe, dll, ini = game / EXE, game / DLL, game / "plugins/cabplay.ini"
    if not exe.is_file():
        raise ValueError(f"找不到游戏程序：{exe}")
    MUSIC["verify_executable"](ARCHIVE)
    archive = patch_archive(ARCHIVE.read_bytes())
    exe_data = GRAPHICS["plan"](exe, EXE, False)[1]
    dll_data = patch_dll(dll, args.legacy_installer)
    ini_data = configure(read(ini) or b"")
    print(f"已校验 CabPlay 1.22.1 与游戏目录：{game}")
    if args.check:
        return

    usb_worker = MUSIC["USB_SUPPORT"] / "usb-display.py"
    sound_worker = SOUND["WORKER"]
    launch_path = os.environ.get("PATH", "/usr/bin:/bin")
    changes = {
        ARCHIVE: archive, exe: exe_data, dll: dll_data, ini: ini_data,
        usb_worker: (ROOT / "outputs/cabplay-local-music.py").read_bytes(),
        sound_worker: (ROOT / "outputs/cabplay-soundcheck.py").read_bytes(),
        usb_agent: plistlib.dumps(dict(Label=usb_agent.stem, RunAtLoad=True, KeepAlive=True,
                                      ProgramArguments=[sys.executable, str(usb_worker), "--usb-worker"],
                                      EnvironmentVariables={"PATH": launch_path})),
        sound_agent: plistlib.dumps(dict(Label=sound_agent.stem, RunAtLoad=True, StartInterval=120,
                                        Nice=10, ProcessType="Background",
                                        ProgramArguments=[sys.executable, str(sound_worker), "--scan", ffmpeg])),
    }
    previous = {path: read(path) for path in changes}
    rows = []
    for number, (path, old) in enumerate(previous.items()):
        backup = f"backup-{number}" if old is not None else None
        if backup:
            write(STATE / backup, old)
        rows.append(dict(path=str(path), backup=backup, installed=sha(changes[path])))
    write(manifest, json.dumps(rows, indent=2).encode())
    try:
        MUSIC["DOCS"].joinpath("music").mkdir(parents=True, exist_ok=True)
        change_files(changes)
        agents(True, agent_paths)
    except BaseException:
        agents(False, agent_paths)
        change_files(previous)
        manifest.unlink()
        agents(True, agent_paths)
        raise
    print("已安装 CabPlay 全功能补丁。请用 D3DMetal 和 DX11 启动欧卡 2。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--restore", action="store_true")
    parser.add_argument("--game-dir", type=Path)
    parser.add_argument("--legacy-installer", type=Path)
    args = parser.parse_args()
    try:
        if args.check:
            install(args)
        else:
            STATE.mkdir(parents=True, exist_ok=True)
            with (STATE / "install.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                install(args)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"未完成：{exc}\n")
