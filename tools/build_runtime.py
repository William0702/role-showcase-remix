import urllib.request,json,hashlib,zipfile,io,shutil,concurrent.futures
from pathlib import Path
root=Path(__file__).resolve().parent.parent;cache=root.parent/'_downloads';cache.mkdir(exist_ok=True)
def fetch(url,name,expected=None):
 p=cache/name
 if not p.exists():
  with urllib.request.urlopen(url,timeout=120) as r,p.open('wb') as f:shutil.copyfileobj(r,f)
 sha=hashlib.sha256(p.read_bytes()).hexdigest()
 if expected and expected.lower()!=sha:raise RuntimeError('SHA mismatch '+name)
 print(name,p.stat().st_size,sha,flush=True)
 return {'name':name,'url':url,'sha256':sha,'size':p.stat().st_size,'path':p}
packages=[]
for package,version in [('numpy','2.3.5'),('pillow','11.3.0'),('pyyaml','6.0.3')]:
 with urllib.request.urlopen(f'https://pypi.org/pypi/{package}/{version}/json',timeout=60) as r:d=json.load(r)
 candidates=[x for x in d['urls'] if x['filename'].endswith('cp312-cp312-win_amd64.whl')]
 assert candidates,package
 x=candidates[0];packages.append((x['url'],x['filename'],x['digests']['sha256']))
jobs=[('https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip','python-3.12.10-embed-amd64.zip',None),('https://github.com/GyanD/codexffmpeg/releases/download/9.0.2/ffmpeg-9.0.2-essentials_build.zip','ffmpeg-essentials.zip',None),('https://codeload.github.com/FFmpeg/FFmpeg/tar.gz/946fcce07b','ffmpeg-9.0.2-source.tar.gz',None),*packages]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:downloads=list(pool.map(lambda t:fetch(*t),jobs))
py=root/'tools'/'windows-x64'/'python';py.mkdir(parents=True,exist_ok=True);site=py/'Lib'/'site-packages';site.mkdir(parents=True,exist_ok=True)
for item in downloads:
 p=item['path']
 if p.name.startswith('python-'):
  with zipfile.ZipFile(p) as z:z.extractall(py)
 elif p.name.endswith('.whl'):
  with zipfile.ZipFile(p) as z:z.extractall(site)
 elif p.name=='ffmpeg-essentials.zip':
  with zipfile.ZipFile(p) as z:
   for entry in z.namelist():
    if entry.endswith('/bin/ffmpeg.exe') or entry.endswith('/bin/ffprobe.exe'):
     target=root/'tools'/'windows-x64'/Path(entry).name;target.write_bytes(z.read(entry))
    elif entry.endswith('/LICENSE') or entry.endswith('/LICENSE.txt') or entry.endswith('/README.txt'):
     (root/'licenses'/('FFmpeg-'+Path(entry).name)).write_bytes(z.read(entry))
 elif p.name.endswith('.tar.gz'):
  dest=root/'tools'/'sources';dest.mkdir(exist_ok=True);shutil.copy2(p,dest/p.name)
(py/'python312._pth').write_text('python312.zip\n.\nLib/site-packages\n../../../scripts\nimport site\n',encoding='utf-8')
shutil.copy2(py/'LICENSE.txt',root/'licenses'/'Python-LICENSE.txt')
for d in downloads:d.pop('path')
(root/'tools'/'download-provenance.json').write_text(json.dumps({'downloads':downloads,'python':'3.12.10','numpy':'2.3.5','pillow':'11.3.0','platform':'Windows x64'},ensure_ascii=False,indent=2),encoding='utf-8')
print('RUNTIME READY',flush=True)


