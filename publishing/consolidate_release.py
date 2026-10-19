"""Replace transport parts with the exact original verified ZIP; never rebuild a release."""
import argparse,concurrent.futures,hashlib,json,re,subprocess,time,urllib.request,zipfile
from pathlib import Path
REPO='William0702/role-showcase-remix'
def gh(*args):return subprocess.check_output(['gh',*args],text=True)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def download(url,p):
 for attempt in range(3):
  try:
   with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'remix-release-maintenance'}),timeout=180) as f,p.open('wb') as out:
    while block:=f.read(1024*1024):out.write(block)
   return
  except Exception:
   if attempt==2:raise
   time.sleep(2)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('tag');a=ap.parse_args()
 if not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+',a.tag):raise ValueError('Invalid tag')
 release=json.loads(gh('api',f'repos/{REPO}/releases/tags/{a.tag}'));assets={x['name']:x for x in release['assets']}
 name=f'role-showcase-remix-{a.tag}-windows-x64.zip';base=f'https://github.com/{REPO}/releases/download/{a.tag}/'
 work=Path('dist/consolidate')/a.tag;work.mkdir(parents=True,exist_ok=True)
 sums=work/'SHA256SUMS.txt';download(assets['SHA256SUMS.txt']['browser_download_url'],sums)
 expected=next(x.split()[0] for x in sums.read_text().splitlines() if x.split()[-1].lstrip('*')==name)
 archive=work/name
 if name not in assets:
  info_path=work/'release-parts.json';download(assets['release-parts.json']['browser_download_url'],info_path);info=json.loads(info_path.read_text())
  if info['archive_name']!=name or info['archive_sha256']!=expected:raise ValueError('Archive mismatch')
  parts=info['parts'];names=[p['name'] for p in parts]
  if not 1<=len(parts)<=256 or len(set(names))!=len(names):raise ValueError('Invalid parts')
  def one(part):
   n=part['name']
   if not re.fullmatch(re.escape(name)+r'\.\d{3}',n):raise ValueError('Invalid part name')
   url=assets[n]['browser_download_url']
   if url!=base+n:raise ValueError('Unexpected origin')
   p=work/n;download(url,p)
   if p.stat().st_size!=part['size'] or sha(p)!=part['sha256']:raise ValueError('Part verification failed')
  with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(one,parts))
  with archive.open('wb') as out:
   for part in parts:
    with (work/part['name']).open('rb') as f:
     while block:=f.read(1024*1024):out.write(block)
  if archive.stat().st_size!=info['archive_size'] or sha(archive)!=expected:raise ValueError('ZIP checksum failed')
  with zipfile.ZipFile(archive) as z:
   if z.testzip():raise ValueError('ZIP CRC failed')
   m=json.loads(z.read('role-showcase-remix/package-manifest.json'))
   if 'v'+m['version']!=a.tag:raise ValueError('Version mismatch')
   for entry in m['files']:
    data=z.read('role-showcase-remix/'+entry['path'])
    if len(data)!=entry['size'] or hashlib.sha256(data).hexdigest()!=entry['sha256']:raise ValueError('Package manifest failed')
  print('Verified exact original archive and all package members',flush=True)
  subprocess.run(['gh','release','upload',a.tag,str(archive),'--repo',REPO],check=True)
 # Public redownload must pass before any old transport assets are removed.
 verify=work/'public-download.zip';download(base+name,verify)
 if sha(verify)!=expected:raise ValueError('Public ZIP verification failed; parts preserved')
 fresh=json.loads(gh('api',f'repos/{REPO}/releases/tags/{a.tag}'))
 obsolete=[x for x in fresh['assets'] if re.fullmatch(re.escape(name)+r'\.\d{3}',x['name']) or x['name'] in ('release-parts.json','assemble-offline.ps1')]
 for asset in obsolete:gh('api','--method','DELETE',f"repos/{REPO}/releases/assets/{asset['id']}")
 notes=work/'notes.md';notes.write_text(f"# 展示混剪技能 {a.tag} · Windows x64\n\n## 下载与安装\n\n只需下载 **{name}**，解压后双击 **install.cmd**。这是包含运行时、工具和 FilmCraft 的完整技能包，无需手动拼接。安装时检查依赖并执行自检。\n\n- `{name}`：完整离线技能包，普通用户下载这个。\n- `SHA256SUMS.txt`：完整包校验值。\n- `install-role-showcase-remix.ps1`：可选联网安装入口，不必与 ZIP 一起下载。\n\nGitHub 自动生成的 Source code 是开发源码，不是完整安装包。\n\n## 更新\n\n在安装目录运行 `update.cmd`；保留项目并保护本地修改。\n\n## 版本说明\n\n本次只将旧传输分片还原为同一 ZIP，SHA256 保持不变，不改变本版本技能内容。main 上的剧情共创改造为开发中功能，不在此稳定包内。历史 BGM 分离样段未获用户认可，不承诺自动去除音乐。\n",encoding='utf-8')
 subprocess.run(['gh','release','edit',a.tag,'--repo',REPO,'--title',f'展示混剪技能 {a.tag} · Windows x64 完整包','--notes-file',str(notes)],check=True)
 print('PASS public complete ZIP; obsolete transport assets removed',flush=True)
if __name__=='__main__':main()
