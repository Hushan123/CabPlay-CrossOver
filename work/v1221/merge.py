from pathlib import Path
import hashlib, runpy, json, subprocess, tempfile
m=runpy.run_path('outputs/cabplay-local-music.py')
def files(p):
 h,d=m['unpack'](p.read_bytes());out={}
 def walk(t,pre):
  for k,v in t['files'].items():
   n=pre+k
   if 'files' in v: walk(v,n+'/')
   elif 'offset' in v:out[n]=m['get'](h,d,n)
 walk(h,'');return out
def sha(d):return hashlib.sha256(d).hexdigest()
a=m['ASAR']
old=Path('work/v122/full/resources/app.asar')
new=Path('work/v1221/full/resources/app.asar')
base,custom,latest=map(files,(old,a,new))
print('versions', [json.loads(x['package.json'])['version'] for x in (base,custom,latest)])
root=Path('work/v1221/merged')
changes={}
with tempfile.TemporaryDirectory() as td:
 tmp=Path(td)
 for k,v in custom.items():
  if v==base.get(k):continue
  if k not in base:
   if k in latest and latest[k]!=v:raise ValueError(k)
   result=v
  elif latest.get(k)==base[k]: result=v
  else:
   paths=[tmp/n for n in ('latest','base','custom')]
   for p,s in zip(paths,(latest[k],base[k],v)):p.write_bytes(s)
   r=subprocess.run(['git','merge-file','-p',*paths],capture_output=True)
   print(k,r.returncode); result=r.stdout
   if r.returncode>1:raise ValueError(k)
  p=root/k;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(result)
  changes[k]=result
for k,v in latest.items():
 if k.endswith('.js') and (b'install-plugin' in v or b'einspielen' in v):
  p=Path('work/v1221/inspect')/k;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(v)
if __name__=='__main__':
 assert not any(b'<<<<<<<' in v for k,v in changes.items() if k.endswith(('.js','.html')))
 for k in changes:
  if k.endswith('.js'):subprocess.run(['node','--check',root/k],check=True)
 p=Path('work/v1221/patched.asar')
 p.write_bytes(m['archive_with'](new.read_bytes(),changes))
 assert files(p)==dict(latest,**changes)
