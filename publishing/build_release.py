"""Build a manifest-only release; never walk the user's project or installed extras."""
import argparse,hashlib,json,re,shutil,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPO='William0702/role-showcase-remix'
def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def get_json(url):
 req=urllib.request.Request(url,headers={'User-Agent':'role-showcase-remix-release'})
 with urllib.request.urlopen(req,timeout=60) as response:return json.load(response)
def runtime_from_release():
 release=get_json('https://api.github.com/repos/'+REPO+'/releases/latest');tag=release['tag_name']
 if not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+',tag):raise ValueError('Invalid stable runtime release')
 assets={a['name']:a for a in release['assets']};name='role-showcase-remix-'+tag+'-windows-x64.zip'
 prefix='https://github.com/'+REPO+'/releases/download/'+tag+'/'
 for key in (name,'SHA256SUMS.txt'):
  if not assets[key]['browser_download_url'].startswith(prefix):raise ValueError('Unexpected download origin')
 cache=ROOT/'.release-cache'/tag;cache.mkdir(parents=True,exist_ok=True)
 req=urllib.request.Request(assets['SHA256SUMS.txt']['browser_download_url'],headers={'User-Agent':'role-showcase-remix-release'})
 with urllib.request.urlopen(req,timeout=60) as response:sums=response.read().decode('utf-8')
 expected=next(line.split()[0] for line in sums.splitlines() if line.split()[-1].lstrip('*')==name)
 archive=cache/name
 if not archive.is_file() or digest(archive)!=expected:
  req=urllib.request.Request(assets[name]['browser_download_url'],headers={'User-Agent':'role-showcase-remix-release'})
  with urllib.request.urlopen(req,timeout=600) as response,archive.open('wb') as out:shutil.copyfileobj(response,out)
 if digest(archive)!=expected:raise ValueError('Runtime release checksum mismatch')
 unpack=cache/'unpack'
 if not (unpack/'role-showcase-remix/package-manifest.json').is_file():
  with zipfile.ZipFile(archive) as z:
   for member in z.infolist():
    target=(unpack/member.filename).resolve()
    if not target.is_relative_to(unpack.resolve()):raise ValueError('Unsafe archive member')
   z.extractall(unpack)
 return unpack/'role-showcase-remix'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--runtime-from',type=Path);ap.add_argument('--output',type=Path);args=ap.parse_args()
 manifest=json.loads((ROOT/'package-manifest.json').read_text('utf-8'));version=manifest['version']
 if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+',version):raise ValueError('Invalid version')
 runtime=args.runtime_from;files=[]
 for entry in manifest['files']:
  rel=Path(entry['path']);local=(ROOT/rel).resolve()
  if not local.is_relative_to(ROOT) or rel.parts[0] in ('.git','.software','_tests','dist'):raise ValueError('Unsafe manifest member')
  if not local.is_file():
   if not str(rel).replace(chr(92),'/').startswith(('tools/windows-x64/','tools/sources/','tools/software/')):raise FileNotFoundError(local)
   if runtime is None:runtime=runtime_from_release()
   local=runtime/rel
  if not local.is_file() or local.stat().st_size!=entry['size'] or digest(local)!=entry['sha256']:raise ValueError('Hash/size mismatch: '+str(rel))
  files.append((local,rel))
 out=(args.output or ROOT/'dist').resolve();out.mkdir(parents=True,exist_ok=True);name='role-showcase-remix-v'+version+'-windows-x64.zip';archive=out/name
 if archive.exists():raise FileExistsError('Published archives are immutable; use a fresh dist directory or a new version: '+str(archive))
 stage=out/'stage'/'role-showcase-remix';stage.mkdir(parents=True,exist_ok=False)
 for local,rel in files:
  target=stage/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(local,target)
 shutil.copy2(ROOT/'package-manifest.json',stage/'package-manifest.json')
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for local,rel in files:z.write(stage/rel,'role-showcase-remix/'+rel.as_posix())
  z.write(stage/'package-manifest.json','role-showcase-remix/package-manifest.json')
 with zipfile.ZipFile(archive) as z:
  if z.testzip():raise ValueError('Archive CRC failure')
 checksum=digest(archive);(out/'SHA256SUMS.txt').write_text(checksum+'  '+name+'\n','utf-8')
 print(json.dumps({'version':version,'files':len(files),'archive':str(archive),'bytes':archive.stat().st_size,'sha256':checksum},indent=2),flush=True)
if __name__=='__main__':main()
