import json,hashlib,os,platform,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha256(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
 return h.hexdigest()
def load_json(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def save_json(path,data):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 temp=path.with_name(path.name+'.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');os.replace(temp,path)
def state_dir(project):
 p=Path(project).resolve()/'.remix';p.mkdir(parents=True,exist_ok=True);return p
def project_path(project,relative):
 root=Path(project).resolve();p=(root/relative).resolve()
 if not p.is_relative_to(root):raise ValueError('Path escapes project: '+str(relative))
 return p
def tool(name):
 override=os.environ.get('REMIX_'+name.upper())
 if override:
  p=Path(override).resolve()
  if not p.is_file():raise RuntimeError('Missing override '+str(p))
  return str(p)
 p=ROOT/'tools'/'windows-x64'/(name+'.exe')
 if platform.system()!='Windows' or not p.is_file():raise RuntimeError('This offline pack ships Windows x64 tools. Configure REMIX_FFMPEG/REMIX_FFPROBE for other systems.')
 return str(p)
def ffmpeg():return tool('ffmpeg')
def ffprobe():return tool('ffprobe')
def run_ffmpeg(args,cwd=None):
 p=subprocess.run([ffmpeg(),'-hide_banner','-v','error',*map(str,args)],cwd=cwd,capture_output=True)
 if p.returncode:raise RuntimeError(p.stderr.decode('utf-8',errors='replace')[-6000:])
 return p.stdout
def probe(path,frames=False):
 args=[ffprobe(),'-v','error','-show_streams','-show_format','-of','json',str(path)]
 if frames:args[3:3]=['-show_frames']
 p=subprocess.run(args,capture_output=True)
 if p.returncode:raise RuntimeError(p.stderr.decode('utf-8',errors='replace'))
 return json.loads(p.stdout)
def approve(project,stage,artifact,note):
 if not note.strip():raise ValueError('Record the human authorization text')
 artifact=project_path(project,artifact);p=state_dir(project)/'approvals.json';d=load_json(p) if p.exists() else {'approvals':[]}
 d['approvals'].append({'stage':stage,'artifact':str(artifact.relative_to(Path(project).resolve())),'sha256':sha256(artifact),'human_authorization':note});save_json(p,d)
def require_approval(project,stage,artifact):
 artifact=Path(artifact).resolve();p=state_dir(project)/'approvals.json'
 if not p.exists():raise ValueError('Human approval required for '+stage)
 records=load_json(p)['approvals'];want=sha256(artifact)
 if not any(x['stage']==stage and x['sha256']==want and x.get('human_authorization') for x in records):raise ValueError('Missing or stale human approval for '+stage+' artifact '+str(artifact))
def frame_hashes(path,filters=None):
 args=['-i',str(path),'-map','0:v:0','-an']
 if filters:args+=['-vf',filters]
 raw=run_ffmpeg(args+['-fps_mode','passthrough','-f','framemd5','-']).decode()
 return [l.split(',')[-1].strip() for l in raw.splitlines() if l and not l.startswith('#')]
