"""Update release version and source hashes without touching unchanged runtime pins."""
import argparse,hashlib,json,re
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('version');args=p.parse_args()
if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+',args.version):raise ValueError('Expected major.minor.patch')
manifest=json.loads((root/'package-manifest.json').read_text('utf-8'));manifest['version']=args.version
for entry in manifest['files']:
 path=(root/entry['path']).resolve()
 if not path.is_relative_to(root):raise ValueError('Unsafe manifest path')
 if path.is_file():entry.update(size=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
(root/'package-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n','utf-8')
print('Prepared',args.version,'; review diff and commit before publishing')
