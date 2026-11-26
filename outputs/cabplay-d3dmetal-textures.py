"""CabPlay 1.12.15 / ETS2 1.62.3.3s upload compatibility experiment."""
import argparse
import fcntl
import hashlib
import os
from pathlib import Path
import shutil
import tempfile

BIN = Path("/Volumes/HIKVISION/driver/SteamLibrary/steamapps/common/Euro Truck Simulator 2/bin/win_x64")
# Offset in file, original, replacement. Only accept known full file hashes.
DLL = "plugins/cabplay.dll"
EXE = "eurotrucks2.exe"
FILES = {
    DLL: ("7469d1ed28956d818afb7f59c229f79237d140982043da449359cae084dd92ba", [
        (0x2d5bd, "57020000", "00000000"),
        # Register both dynamic and GPU live targets. The legacy GPU-only marker
        # call retains its condition in the old alignment slot.
        (0x2dac0, "4584ff7474488bcf0f1f840000000000",
         "488bcfeb0b4584ff7405e9d1a5fdffc3"),
        (0x2dae9, "e8b2a5fdff", "e8d7ffffff"),
    ]),
    EXE: ("055ec5343d53bd427de54b06eca74937f0d348dbb0c5d71862edddcf45e2db66", [
        (0x2bc5b2, "742b", "eb2b"),
    ]),
}

def transform(data, edits, reverse=False):
    output = bytearray(data)
    for offset, orig, patched in edits:
        before, after = (patched, orig) if reverse else (orig, patched)
        before, after = bytes.fromhex(before), bytes.fromhex(after)
        if output[offset:offset+len(before)] != before or len(before) != len(after):
            raise ValueError("版本检查失败")
        output[offset:offset+len(before)] = after
    return bytes(output)

def plan(path, name, restore):
    digest, edits = FILES[name]
    current = path.read_bytes()
    variants = [[], edits]
    if name == DLL:
        variants.append(edits[:1])
    for subset in variants:
        try:
            original = transform(current, subset, True)
        except ValueError:
            continue
        if hashlib.sha256(original).hexdigest() == digest:
            return current, original if restore else transform(original, edits)
    raise ValueError(f"文件与已验证版本不符：{path.name}")

def stage(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
        temp = Path(f.name)
    try:
        shutil.copy2(path, temp)
        with temp.open('wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        if temp.read_bytes() != data:
            raise OSError("写入校验失败")
        return temp
    except BaseException:
        temp.unlink(missing_ok=True)
        raise

def apply(root, restore):
    pending, applied, temps = [], [], []
    try:
        for name in FILES:
            p = root / name
            old, new = plan(p, name, restore)
            if old == new:
                continue
            newfile = stage(p, new)
            temps.append(newfile)
            oldfile = stage(p, old)
            temps.append(oldfile)
            pending.append((p, old, oldfile, newfile))
        for p, old, oldfile, newfile in pending:
            if p.read_bytes() != old:
                raise OSError("安装时文件发生变化")
            newfile.replace(p)
            applied.append((p, oldfile))
    except BaseException:
        for p, oldfile in reversed(applied):
            oldfile.replace(p)
        raise
    finally:
        for f in temps:
            f.unlink(missing_ok=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restore', action='store_true')
    args = parser.parse_args()
    try:
        with (BIN / '.cabplay-texture-update.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            apply(BIN, args.restore)
        print("已恢复原版游戏程序和原版插件 DLL。" if args.restore else "已启用动态纹理上传保护测试。")
    except (ValueError, OSError) as err:
        parser.exit(1, f"未完成：{err}\n")
