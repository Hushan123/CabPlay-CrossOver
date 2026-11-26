"""CabPlay 1.22.1 migration for the Steam CrossOver bottle on macOS."""
import argparse
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path.home() / 'Library/Application Support/CrossOver/Bottles/Steam/drive_c/users/crossover/AppData/Local/Programs/CabPlay'
def digest(path):
    with path.open('rb') as fp:
        h = hashlib.sha256()
        for block in iter(lambda: fp.read(1024 * 1024), b''):
            h.update(block)
        return h.hexdigest()

def swap(a, b):
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.renamex_np(os.fsencode(a), os.fsencode(b), 2):
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))

def check(root, manifest, key):
    for filename, record in manifest.items():
        if digest(root / filename) != record[key]:
            raise ValueError(f'文件版本与预期不符：{filename}')

def verify_game(root, expected):
    for filename, hash_value in expected.items():
        if digest(root / filename) != hash_value:
            raise ValueError(f'外置盘上的 {filename} 已变化，未升级。')


def install(root, undo, game_root):
    backup = root.with_name('CabPlay.before-1221')
    with zipfile.ZipFile(sys.argv[0]) as z:
        manifest = json.loads(z.read('manifest'))
        if not undo:
            verify_game(game_root, json.loads(z.read('game-files')))
        arc = 'resources/app.asar'
        state = digest(root / arc)
        if undo:
            if state == manifest[arc]['old']:
                print('当前已是升级前版本。'); return
            check(root, manifest, 'new')
            check(backup, manifest, 'old')
            swap(root, backup)
            print('已恢复升级前的定制版。'); return
        if state == manifest[arc]['new']:
            check(root, manifest, 'new')
            print('已安装定制版 1.22.1。'); return
        check(root, manifest, 'old')
        if backup.exists():
            check(backup, manifest, 'new')
            swap(root, backup)
        else:
            with tempfile.TemporaryDirectory(dir=root.parent, prefix='.cabplay-stage-') as td:
                staged = Path(td) / root.name
                subprocess.run(['/bin/cp','-pR',str(root),str(staged)],check=True)
                for filename, rec in manifest.items():
                    dest = staged / filename
                    if 'chunks' in rec:
                        with dest.open('r+b') as fp:
                            for offset in rec['chunks']:
                                fp.seek(offset)
                                fp.write(z.read(f'exe/{offset}'))
                    else:
                        dest.write_bytes(z.read('new/' + filename))
                check(staged, manifest, 'new')
                os.rename(staged, backup)
                swap(root, backup)
        print('已升级到 CabPlay 1.22.1 定制版。')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--restore', action='store_true')
    args = parser.parse_args()
    try:
        with (ROOT.parent / '.cabplay-1221.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            game_root = Path('/Volumes/HIKVISION/driver/SteamLibrary/steamapps/common/Euro Truck Simulator 2/bin/win_x64')
            install(ROOT, args.restore, game_root)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        sys.exit(f'未完成：{exc}')
