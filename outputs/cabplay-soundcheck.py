"""Per-song loudness matching for the CabPlay 1.22.0 local player."""
import argparse
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import plistlib
import shutil
import struct
import subprocess
import sys
import tempfile

MUSIC = Path.home() / "Documents/Euro Truck Simulator 2/music"
ASAR = Path.home() / "Library/Application Support/CrossOver/Bottles/Steam/drive_c/users/crossover/AppData/Local/Programs/CabPlay/resources/app.asar"
SUPPORT = Path.home() / "Library/Application Support/CabPlay-SoundCheck"
LABEL = "local.cabplay.soundcheck"
AGENT = Path.home() / "Library/LaunchAgents" / (LABEL + ".plist")
WORKER = SUPPORT / "scan.py"
EXTS = {".mp3", ".flac", ".m4a", ".ogg", ".wav"}
TARGET = -16
HOOK = """size = stat.size;
      try {
        const dir = path.join(cache, 'soundcheck-v1');
        const manifest = JSON.parse(await fs.promises.readFile(path.join(dir, 'index.json'), 'utf8'));
        const hit = Object.hasOwn(manifest, name) && manifest[name];
        if (hit && hit.size === stat.size && Math.abs(hit.ms - stat.mtimeMs) < 2 && /^[a-f0-9]{64}$/.test(hit.key)) {
          const normalized = path.join(dir, hit.key + '.flac');
          const ns = await fs.promises.stat(normalized);
          if (ns.isFile() && ns.size > 0) {
            file = normalized;
            type = 'audio/flac';
            size = ns.size;
          }
        }
      } catch { /* original track is playable while its cache is built */ }"""


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
        temp = Path(f.name)
    try:
        temp.write_bytes(data)
        if path.exists():
            shutil.copymode(path, temp)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def patch(data):
    _, header, _, length = struct.unpack_from('<4I', data)
    tree = json.loads(data[16:16+length])
    payload = data[8+header:]
    entries = tree['files']
    def read(entry):
        start = int(entry['offset'])
        return payload[start:start+entry['size']]
    if json.loads(read(entries['package.json']))['version'] != '1.22.0':
        raise ValueError("仅适用于 CabPlay 1.22.0 定制版")
    e = entries['main']['files']['local-music.js']
    source = read(e).decode()
    for old, new in [('const type = types[', 'let type = types['), ('size = stat.size;', HOOK)]:
        if source.count(old) != 1:
            raise ValueError('本地音乐模块版本不匹配')
        source = source.replace(old, new)
    content = source.encode()
    digest = hashlib.sha256(content).hexdigest()
    e.update(offset=str(len(payload)), size=len(content), integrity=dict(algorithm='SHA256',hash=digest,blockSize=4194304,blocks=[digest]))
    raw = json.dumps(tree,ensure_ascii=False,separators=(',',':')).encode()
    padded = raw + bytes(-len(raw) % 4)
    return struct.pack('<4I',4,8+len(padded),4+len(padded),len(raw))+padded+payload+content


def convert(ffmpeg, src, dest):
    cmd = [ffmpeg,'-nostdin','-hide_banner','-nostats','-threads','1','-i',str(src),'-map','0:a:0','-vn','-sn','-dn']
    log = subprocess.run(cmd+['-af','loudnorm=print_format=json','-f','null','-'],stderr=subprocess.PIPE,check=True).stderr.decode(errors='replace')
    stats = json.loads(log[log.rindex('{'):log.rindex('}')+1])
    loud, peak = map(float,(stats['input_i'],stats['input_tp']))
    if not all(map(math.isfinite,(loud,peak))):
        return False
    gain = min(TARGET-loud, -1.5-peak, 12.0)
    if abs(gain) < 0.5:
        return False
    subprocess.run(cmd+['-loglevel','error','-af',f'volume={gain:.4f}dB:precision=double','-map_metadata','-1','-c:a','flac','-sample_fmt','s32','-threads','1','-f','flac','-y',str(dest)],check=True)
    return True


def scan(folder, ffmpeg):
    cache = folder/'.cabplay/soundcheck-v1'
    cache.mkdir(parents=True,exist_ok=True)
    with (cache/'scan.lock').open('a') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            return
        index = cache/'index.json'
        rows = json.loads(index.read_bytes()) if index.exists() else {}
        present = set()
        for src in sorted(folder.iterdir()):
            if src.name.startswith('.') or src.is_symlink() or not src.is_file() or src.suffix.lower() not in EXTS:
                continue
            present.add(src.name)
            st = src.stat()
            key = hashlib.sha256(json.dumps([src.name, st.st_size, st.st_mtime_ns]).encode()).hexdigest()
            dst = cache/(key+'.flac')
            row = rows.get(src.name,{})
            if row.get('stamp') == key and (row.get('key') is None or dst.is_file()):
                continue
            tmp = cache/'encoding.tmp'
            try:
                used = convert(ffmpeg,src,tmp)
                now = src.stat()
                if (now.st_size,now.st_mtime_ns)!=(st.st_size,st.st_mtime_ns):
                    continue
                if used:
                    tmp.replace(dst)
                rows[src.name] = dict(stamp=key,key=key if used else None,size=st.st_size,ms=st.st_mtime_ns/1e6)
                atomic(index,json.dumps(rows).encode())
            except (ValueError,OSError,subprocess.SubprocessError) as exc:
                print(f'{src.name}: {exc}',file=sys.stderr)
            finally:
                tmp.unlink(missing_ok=True)
        kept = {k:v for k,v in rows.items() if k in present}
        if kept != rows:
            atomic(index,json.dumps(kept).encode())
        active = {v.get('key') for v in kept.values()}
        for p in cache.glob('*.flac'):
            if p.stem not in active:
                p.unlink(missing_ok=True)


def install(restore):
    domain = 'gui/'+str(os.getuid())
    backup = ASAR.with_name('app.asar.before-soundcheck')
    current = ASAR.read_bytes()
    original = backup.read_bytes() if backup.exists() else current
    updated = patch(original)
    if current not in (updated, original):
        raise ValueError('安装目录已有其他更新，已停止以保护新版本')
    if restore:
        if current == updated:
            atomic(ASAR, original)
        subprocess.run(['launchctl','bootout',domain+'/'+LABEL],capture_output=True)
        AGENT.unlink(missing_ok=True)
        print('已恢复原播放器。')
        return
    ffmpeg = shutil.which('ffmpeg') or next((p for p in ['/opt/homebrew/bin/ffmpeg','/usr/local/bin/ffmpeg'] if os.access(p,os.X_OK)),None)
    if not ffmpeg or not MUSIC.is_dir():
        raise ValueError('请确认已安装 ffmpeg 且欧卡 2 音乐目录存在')
    if not backup.exists():
        atomic(backup,original)
    atomic(WORKER,Path(__file__).read_bytes())
    plist = dict(Label=LABEL, ProgramArguments=[sys.executable,str(WORKER),'--scan',ffmpeg],RunAtLoad=True,StartInterval=120,Nice=10, ProcessType='Background',ThrottleInterval=30)
    subprocess.run(['launchctl','bootout',domain+'/'+LABEL],capture_output=True)
    atomic(AGENT,plistlib.dumps(plist))
    subprocess.run(['launchctl','bootstrap',domain,str(AGENT)],check=True)
    if current != updated:
        atomic(ASAR,updated)
    print('已开启自动响度均衡。资料库正在后台逐首处理。')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restore',action='store_true')
    parser.add_argument('--scan',metavar='FFMPEG',help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.scan:
            scan(MUSIC,args.scan)
        else:
            install(args.restore)
    except (KeyError,ValueError,OSError,subprocess.SubprocessError) as exc:
        sys.exit(f'未完成：{exc}')
