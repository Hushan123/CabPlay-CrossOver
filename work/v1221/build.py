from pathlib import Path
import subprocess
import zipfile

full = Path('work/v1221/full')
if not (full / 'CabPlay.exe').is_file():
    installer = (
        Path.home() / 'Library/Application Support/CrossOver/Bottles/Steam/drive_c/users/'
        'crossover/AppData/Roaming/CabPlay/update/CabPlay-Setup-1.22.1.exe'
    )
    if not installer.is_file():
        raise SystemExit(f'构建 1.22.1 需要官方安装包：{installer}')
    subprocess.run(['/usr/bin/bsdtar', '-xf', str(installer), '-C', str(full)], check=True)

from merge import *
app=a.parent.parent
game_js=latest['main/game.js'].decode()
script=runpy.run_path('outputs/cabplay-d3dmetal-textures.py')
dll=Path('work/v122/full/resources/plugin/cabplay.dll').read_bytes()
edits=script['FILES'][script['DLL']][1]
digests=[sha(script['transform'](dll,e)) for e in (edits[:1],edits)]
game_bin=Path('/Volumes/HIKVISION/driver/SteamLibrary/steamapps/common/Euro Truck Simulator 2/bin/win_x64')
game_files = {}
for name in (script['DLL'], script['EXE']):
 installed = game_bin / name
 current, expected = script['plan'](installed, name, False)
 if current != expected:
  raise ValueError(f'外置盘上的 {name} 与当前双屏补丁版本不同')
 game_files[name] = sha(current)
assert game_files[script['DLL']] in digests
anchor="  function pluginStatusFor(id, dir) {"
guard="""  // Recognize the two installed D3DMetal compatibility variants.
  const protectedPluginHashes = new Set(%s);
  function preservePlugin(target) {
    if (!fs.existsSync(target)) return false;
    const digest = require('node:crypto').createHash('sha256').update(fs.readFileSync(target)).digest('hex');
    return protectedPluginHashes.has(digest);
  }

"""%json.dumps(digests)
game_js=game_js.replace(anchor,guard+anchor)
x="    if (!fs.existsSync(bundledPlugin))"
game_js=game_js.replace(x,"    if (preservePlugin(target)) return { ...base, state: 'installed', bundled: true };\n"+x,1)
x="    fs.mkdirSync(plugins, { recursive: true });"
assert game_js.count(x)==1
game_js=game_js.replace(x,"    if (preservePlugin(path.join(plugins, PLUGIN))) return;\n"+x,1)
subprocess.run(['node','--check'],input=game_js.encode(),check=True)
changes['main/game.js']=game_js.encode()
prior=files(a.with_name('app.asar.before-soundcheck'))
assert [k for k in custom if custom[k]!=prior[k]]==['main/local-music.js']
changes['main/local-music.js']=prior['main/local-music.js']
unbalanced=m['archive_with'](new.read_bytes(),changes)
worker=Path.home()/'Library/Application Support/CabPlay-SoundCheck/scan.py'
source=worker.read_text().replace("!= '1.22.0':","not in ('1.22.0', '1.22.1'):")
namespace={'__name__':'soundcheck'}
exec(compile(source,str(worker),'exec'),namespace)
patch=namespace['patch']
balanced=patch(unbalanced)
test=Path('work/v1221/patched.asar');test.write_bytes(balanced)
assert files(test)['main/local-music.js']==custom['main/local-music.js']
out=Path('outputs/CabPlay-1.22.1-HIKVISION.pyz')
manifest={}
with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as z:
 z.write('work/v1221/upgrade_main.py','__main__.py')
 for p in list(full.rglob('*'))+[a.with_name('app.asar.before-soundcheck')]:
  if not p.is_file():continue
  name=(p.relative_to(full) if p.is_relative_to(full) else p.relative_to(app)).as_posix()
  old_data=(app/name).read_bytes()
  updated={'resources/app.asar':balanced,'resources/app.asar.before-soundcheck':unbalanced}.get(name)
  if updated is None: updated=p.read_bytes()
  if updated==old_data:continue
  rec=manifest[name]={'old':sha(old_data),'new':sha(updated)}
  if name=='CabPlay.exe' and len(updated)==len(old_data):
   rec['chunks']=[]
   for i in range(0,len(updated),65536):
    chunk=updated[i:i+65536]
    if chunk!=old_data[i:i+65536]:rec['chunks'].append(i);z.writestr(f'exe/{i}',chunk)
  else:z.writestr('new/'+name,updated)
 z.writestr('manifest',json.dumps(manifest))
 z.writestr('game-files',json.dumps(game_files))
print(out.stat().st_size,list(manifest))
