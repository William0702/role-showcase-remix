"""Check source package hashes, Python syntax, links and accidental private artifacts."""
import ast,hashlib,json,re
from pathlib import Path
root=Path(__file__).resolve().parents[1];m=json.loads((root/'package-manifest.json').read_text('utf-8'));seen=set()
for e in m['files']:
 p=(root/e['path']).resolve()
 if not p.is_relative_to(root) or e['path'] in seen:raise ValueError('Unsafe/duplicate path')
 seen.add(e['path'])
 if not p.is_file():
  if not e['path'].startswith(('tools/windows-x64/','tools/sources/','tools/software/')):raise FileNotFoundError(p)
  continue
 if p.stat().st_size!=e['size'] or hashlib.sha256(p.read_bytes()).hexdigest()!=e['sha256']:raise ValueError('Manifest mismatch '+e['path'])
for folder in ('scripts','publishing'):
 for p in (root/folder).glob('*.py'):ast.parse(p.read_text('utf-8-sig'))
for p in [root/'SKILL.md',root/'README.md',root/'TESTING.md',*(root/'references').glob('*.md'),*(root/'docs').rglob('*.md')]:
 for ref in re.findall(r'\]\(([^)]+)\)',p.read_text('utf-8-sig')):
  if '://' in ref or ref.startswith('#') or chr(92) in ref or '{' in ref:continue
  target=ref.split('#')[0]
  if target and not (p.parent/target).is_file():raise FileNotFoundError(str(p)+': '+ref)
for p in root.rglob('*'):
 if not p.is_file() or any(x in p.parts for x in ('.git','dist','.release-cache')):continue
 if p.suffix.lower() in ('.mp4','.mov','.wav','.fcproj'):raise ValueError('Production media/project in repository: '+str(p))
 if p.stat().st_size>100*1024*1024:raise ValueError('GitHub source file too large')
 if p.suffix.lower() in ('.md','.py','.ps1','.json','.yml'):
  s=p.read_text('utf-8-sig')
  if re.search(r'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})',s):raise ValueError('Possible secret; inspect locally without printing it')
print('PASS source manifest, syntax, local links and release boundary; version',m['version'])
