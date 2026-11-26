"""Try uncompressed transparent placeholders for CabPlay on D3DMetal."""
import argparse
import hashlib
import os
from pathlib import Path
import struct
import tempfile

FILES = {
    "gps.dds": (64, 2048, "5be24cc10e34400aa720f4c6145ea458e33295022ec5b1041663971a98191f35"),
    "dashboard.dds": (2048, 64, "6582a73512c4637dc77ccef90c542e5b241dd69daec62b1a0286d96e6b7ab807"),
}


def transparent_bgra(width, height):
    header = [124, 0x100F, height, width, width * 4, 0, 0] + [0] * 11
    pixel_format = [32, 0x41, 0, 32, 0xff0000, 0xff00, 0xff, 0xff000000]
    caps = [0x1000, 0, 0, 0, 0]
    return b'DDS ' + struct.pack('<31I', *(header + pixel_format + caps)) + bytes(width * height * 4)


def replace_file(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as fp:
        temp = Path(fp.name)
        try:
            fp.write(data)
            fp.flush()
            os.fchmod(fp.fileno(), path.stat().st_mode & 0o777)
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)


def main(directory, restore):
    changes = []
    for name, (width, height, digest) in FILES.items():
        path = directory / name
        old = path.read_bytes()
        candidate = transparent_bgra(width, height)
        backup = path.with_suffix(".dds.before-bgra")
        original = old if hashlib.sha256(old).hexdigest() == digest else None
        if original is None and old != candidate:
            raise ValueError(f"文件版本与已核对的版本不同：{name}")
        if backup.exists():
            original = backup.read_bytes()
            if hashlib.sha256(original).hexdigest() != digest:
                raise ValueError(f"备份校验失败：{backup}")
        elif original is None:
            raise ValueError(f"缺少原文件备份：{backup}")
        target = original if restore else candidate
        if old != target:
            changes.append((path, old, target, backup))
    for path, old, target, backup in changes:
        if not backup.exists():
            with backup.open("xb") as fp:
                fp.write(old)
    applied = []
    try:
        for path, old, target, backup in changes:
            replace_file(path, target)
            applied.append((path, old))
    except OSError:
        for path, old in reversed(applied):
            replace_file(path, old)
        raise
    print("已恢复原始纹理。" if restore else "两张 BGRA 测试纹理已就位。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    try:
        main(Path.home() / "Documents/Euro Truck Simulator 2/CabPlay-Display", args.restore)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")
