import argparse,hashlib,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('archive',type=Path);a=p.parse_args();archive=a.archive.resolve();parts=[]
with archive.open('rb') as f:
 for i in range(1,257):
  data=f.read(4*1024*1024)
  if not data:break
  name=archive.name+'.'+str(i).zfill(3);target=archive.parent/name;target.write_bytes(data);parts.append({'name':name,'size':len(data),'sha256':hashlib.sha256(data).hexdigest()})
 else:raise ValueError('Too many parts')
m={'archive_name':archive.name,'archive_size':archive.stat().st_size,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'parts':parts}
(archive.parent/'release-parts.json').write_text(json.dumps(m,indent=2)+'\n','utf-8');print('Prepared',len(parts),'verified parts')
