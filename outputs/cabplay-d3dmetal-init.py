"""Start CabPlay's existing helper swap chain on its first check in D3DMetal."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import tempfile

BIN = Path("/Volumes/HIKVISION/driver/SteamLibrary/steamapps/common/Euro Truck Simulator 2/bin/win_x64")
DLL = BIN / "plugins/cabplay.dll"
ORIGINAL = "7469d1ed28956d818afb7f59c229f79237d140982043da449359cae084dd92ba"
OFFSET = 0x2E1BD - 0xC00


def digest(data):
    return hashlib.sha256(data).hexdigest()


def update(path, restore):
    data = path.read_bytes()
    origin = bytearray(data)
    origin[OFFSET:OFFSET + 4] = (599).to_bytes(4, "little")
    if len(origin) != len(data) or digest(origin) != ORIGINAL:
        raise ValueError("DLL 与已验证的 CabPlay 原版不符。")
    candidate = bytearray(origin)
    candidate[OFFSET:OFFSET + 4] = bytes(4)
    if data != origin and data != candidate:
        raise ValueError("初始化参数已有其他修改。")
    target = origin if restore else candidate
    if data == target:
        print("已处于目标状态。")
        return
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as fp:
        stage = Path(fp.name)
    try:
        shutil.copy2(path, stage)
        with stage.open("r+b") as fp:
            fp.seek(OFFSET)
            fp.write(target[OFFSET:OFFSET + 4])
            fp.flush()
            os.fsync(fp.fileno())
        if stage.read_bytes() != target or path.read_bytes() != data:
            raise ValueError("文件已变化，未安装。")
        stage.replace(path)
    finally:
        stage.unlink(missing_ok=True)
    print("已恢复原版 DLL。" if restore else "已启用 D3DMetal 提前初始化。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    try:
        if not args.restore and digest((BIN / "eurotrucks2.exe").read_bytes()) != "055ec5343d53bd427de54b06eca74937f0d348dbb0c5d71862edddcf45e2db66":
            raise ValueError("本测试需要已核对的原版欧卡 2 1.62.3.3s。")
        update(DLL, args.restore)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"未完成：{exc}\n")
