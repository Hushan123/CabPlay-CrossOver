"""Select ETS2's existing D3D11 texture upload fallback at the observed crash site."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import tempfile

GAME = Path("/Volumes/HIKVISION/driver/SteamLibrary/steamapps/common/Euro Truck Simulator 2/bin/win_x64/eurotrucks2.exe")
ORIGINAL = "055ec5343d53bd427de54b06eca74937f0d348dbb0c5d71862edddcf45e2db66"
CHANGED = "21ba9879dcd1ef780033d0a8139d9c9d142e8bf10967c92df8aed042b8f6ffa1"
BRANCH = 0x2BC5B2


def apply(path, restore=False):
    data = path.read_bytes()
    current = hashlib.sha256(data).hexdigest()
    expected, target = (CHANGED, ORIGINAL) if restore else (ORIGINAL, CHANGED)
    if current == target:
        print("当前已经是目标状态。")
        return
    if current != expected:
        raise ValueError("游戏版本或文件已变化，未写入任何内容。")
    output = bytearray(data)
    output[BRANCH] = 0x74 if restore else 0xEB
    if hashlib.sha256(output).hexdigest() != target:
        raise ValueError("输出校验失败。")
    backup = path.with_name("eurotrucks2.before-d3dmetal-upload.bak")
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as fp:
        stage = Path(fp.name)
    try:
        shutil.copy2(path, stage)
        with stage.open("r+b") as fp:
            fp.seek(BRANCH)
            fp.write(output[BRANCH:BRANCH+1])
            fp.flush()
            os.fsync(fp.fileno())
        if hashlib.sha256(stage.read_bytes()).hexdigest() != target:
            raise ValueError("临时文件校验失败。")
        if not restore and not backup.exists():
            with backup.open("xb") as saved:
                saved.write(data)
                saved.flush()
                os.fsync(saved.fileno())
        if not restore and hashlib.sha256(backup.read_bytes()).hexdigest() != ORIGINAL:
            raise ValueError("已有备份与当前原版不一致。")
        if path.read_bytes() != data:
            raise ValueError("游戏文件在操作期间发生变化。")
        stage.replace(path)
    finally:
        stage.unlink(missing_ok=True)
    print("已恢复原版游戏程序。" if restore else "已启用 D3DMetal 纹理上传测试补丁。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    try:
        apply(GAME, args.restore)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"未完成：{exc}\n")
