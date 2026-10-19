"""Upload verified chunks to an existing draft; credentials stay in memory/stdin."""
import argparse,concurrent.futures,hashlib,json,subprocess,time,urllib.parse
from pathlib import Path
REPO='William0702/role-showcase-remix'
def gh(*args):return subprocess.run(['gh',*args],capture_output=True,text=True,check=True).stdout
p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--workers',type=int,default=16);args=p.parse_args();directory=args.directory.resolve()
manifest=json.loads((directory/'release-parts.json').read_text('utf-8'));tag='v'+manifest['archive_name'].split('-v')[1].split('-windows')[0]
release=next(x for x in json.loads(gh('api','repos/'+REPO+'/releases')) if x['tag_name']==tag)
if not release['draft']:raise ValueError('Published release preserved; use a new version')
rid=release['id'];endpoint='repos/'+REPO+'/releases/'+str(rid)
assets=json.loads(gh('api',endpoint+'/assets?per_page=100'))
for a in assets:
 if a['name'].startswith('transport-probe') or a['name'] in ('SHA256SUMS.txt',manifest['archive_name']):gh('api','--method','DELETE','repos/'+REPO+'/releases/assets/'+str(a['id']))
assets=json.loads(gh('api',endpoint+'/assets?per_page=100'));existing={a['name']:a for a in assets}
token=gh('auth','token').strip();config='header = "Authorization: Bearer '+token+'"\nheader = "Accept: application/vnd.github+json"\nheader = "Content-Type: application/octet-stream"\n'
def upload(path):
 data=path.read_bytes();sha=hashlib.sha256(data).hexdigest();size=len(data);old=existing.get(path.name)
 if old and old['size']==size and old.get('digest')=='sha256:'+sha:return {'name':path.name,'reused':True,'bytes':size}
 if old:gh('api','--method','DELETE','repos/'+REPO+'/releases/assets/'+str(old['id']))
 url='https://uploads.github.com/'+endpoint+'/assets?name='+urllib.parse.quote(path.name)
 for attempt in range(3):
  start=time.monotonic();result=subprocess.run(['curl.exe','--config','-','--http1.1','--silent','--show-error','--fail-with-body','--connect-timeout','20','--max-time','600','--request','POST','--data-binary','@'+str(path),url],input=config,capture_output=True,text=True)
  if result.returncode==0:
   response=json.loads(result.stdout)
   if response['size']!=size or response.get('digest')!='sha256:'+sha:raise ValueError('Uploaded checksum differs: '+path.name)
   return {'name':path.name,'bytes':size,'seconds':round(time.monotonic()-start,1)}
  current=json.loads(gh('api',endpoint+'/assets?per_page=100'));same=next((a for a in current if a['name']==path.name),None)
  if same and same['size']==size and same.get('digest')=='sha256:'+sha:return {'name':path.name,'reused_after_retry':True,'bytes':size}
  if same:gh('api','--method','DELETE','repos/'+REPO+'/releases/assets/'+str(same['id']))
 raise RuntimeError('Upload failed: '+path.name+'; '+result.stderr[-180:])
paths=[directory/x['name'] for x in manifest['parts']]+[directory/'release-parts.json',directory/'SHA256SUMS.txt',directory/'assemble-offline.ps1',directory/'install-role-showcase-remix.ps1']
results=[];print('Uploading',len(paths),'assets to draft',tag,flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
 futures={pool.submit(upload,path):path for path in paths}
 for future in concurrent.futures.as_completed(futures):
  results.append(future.result());(directory/'upload-progress.json').write_text(json.dumps(results,indent=2),'utf-8')
  if len(results)%5==0 or len(results)==len(paths):print('Verified uploaded:',len(results),'/',len(paths),flush=True)
print('COMPLETE: all draft assets uploaded and GitHub digest matched',flush=True)
