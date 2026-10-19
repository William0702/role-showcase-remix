"""Portable arrangement, constraint audit and reversible naming operations."""
import itertools,random,time,os,re
from collections import Counter
from pathlib import Path
from common import load_json,save_json,sha256,state_dir,project_path,require_approval

def constraints(videos,segments,c):
 ids={s['segment_id']:s for s in segments};use=Counter();positions={k:Counter() for k in ids};sets=set();orders=set();pairs=set();errors=[]
 for row in videos:
  seq=[s['segment_id'] for s in row['segments']];key=tuple(seq);st=tuple(sorted(seq))
  if len(seq)!=int(c.get('segments_per_video',3)):errors.append('Wrong group size: '+row['video_id'])
  if len(set(seq))!=len(seq):errors.append('Repeated segment inside '+row['video_id'])
  if any(x not in ids for x in seq):errors.append('Unknown segment');continue
  if key in orders:errors.append('Duplicate ordered video')
  if c.get('unique_sets',True) and st in sets:errors.append('Duplicate unordered set')
  orders.add(key);sets.add(st)
  if c.get('distinct_sources',False) and len({ids[x]['asset_id'] for x in seq})!=len(seq):errors.append('Repeated source')
  for pair in itertools.combinations(sorted(seq),2):
   if c.get('unique_pairs',False) and pair in pairs:errors.append('Repeated pair')
   pairs.add(pair)
  for pos,x in enumerate(seq):use[x]+=1;positions[x][pos]+=1
 for x in ids:
  if use[x]>int(c.get('max_uses',3)):errors.append('Usage limit: '+x)
  if c.get('exact_uses',False) and use[x]!=int(c.get('max_uses',3)):errors.append('Exact usage: '+x)
  if c.get('balance_positions',False):
   counts=[positions[x][p] for p in range(int(c.get('segments_per_video',3)))]
   if max(counts)-min(counts)>1:errors.append('Unbalanced positions: '+x)
 if c.get('target_count') is not None and len(videos)!=int(c['target_count']):errors.append('Wrong target count')
 return errors,dict(use),{x:dict(v) for x,v in positions.items()}

def plan(args):
 root=Path(args.project).resolve();manifest=project_path(root,'.remix/segments-cut.json');segments=load_json(manifest)['segments'];c=load_json(project_path(root,args.config));n=len(segments);k=int(c.get('segments_per_video',3));limit=int(c.get('max_uses',3))
 if k<1 or limit<1 or n<k:raise ValueError('Insufficient segments or invalid group/usage size')
 ids=[s['segment_id'] for s in segments]
 if len(set(ids))!=n:raise ValueError('Duplicate stable segment IDs')
 byid={s['segment_id']:s for s in segments};target=c.get('target_count');target=int(target) if target is not None else n*limit//k
 if target*k>n*limit:raise ValueError('Requested count exceeds usage capacity')
 if c.get('exact_uses') and target*k!=n*limit:raise ValueError('Exact usage incompatible with target/group size')
 c=dict(c,target_count=target);fixed=c.get('fixed_videos',[])
 if len(fixed)>target:raise ValueError('Too many fixed videos')
 rng=random.Random(c.get('seed',0));deadline=time.monotonic()+args.budget_seconds;attempts=0;best=0;solution=None
 while time.monotonic()<deadline:
  attempts+=1;rows=[];use=Counter();posuse={x:Counter() for x in ids};seen=set();orders=set();pairs=set();failed=False
  for index in range(target):
   choices=[]
   if index<len(fixed):choices=[list(fixed[index])]
   else:
    # Weighted random proposals plus balanced-position ordering; restart on a dead end.
    for _ in range(max(160,n*12)):
     seq=[]
     for p in range(k):
      pool=[x for x in ids if x not in seq and use[x]<limit and (not c.get('distinct_sources') or all(byid[x]['asset_id']!=byid[y]['asset_id'] for y in seq))]
      if not pool:break
      weights=[(limit-use[x])**2/(1+posuse[x][p])**4 for x in pool];seq.append(rng.choices(pool,weights=weights)[0])
     if len(seq)==k:choices.append(seq)
   accepted=None
   for seq in choices:
    if len(seq)!=k or len(set(seq))!=k or any(x not in byid or use[x]>=limit for x in seq):continue
    if c.get('distinct_sources') and len({byid[x]['asset_id'] for x in seq})!=k:continue
    st=tuple(sorted(seq));order=tuple(seq);ps=set(itertools.combinations(sorted(seq),2))
    if order in orders or (c.get('unique_sets',True) and st in seen) or (c.get('unique_pairs') and ps & pairs):continue
    if c.get('balance_positions') and any(posuse[x][p]>= (limit+k-1)//k for p,x in enumerate(seq)):continue
    accepted=seq;seen.add(st);orders.add(order);pairs|=ps;break
   if accepted is None:failed=True;break
   rows.append({'video_id':str(index+1).zfill(2),'segments':[byid[x] for x in accepted],'duration_seconds':sum(float(byid[x]['duration_seconds']) for x in accepted)})
   for p,x in enumerate(accepted):use[x]+=1;posuse[x][p]+=1
  best=max(best,len(rows))
  if not failed and not constraints(rows,segments,c)[0]:solution=rows;break
 if solution is None:raise RuntimeError(f'No valid plan found within search budget; not proof of infeasibility. Attempts={attempts}, best={best}/{target}. No constraints relaxed.')
 errors,usage,positions=constraints(solution,segments,c);out={'config':c,'asset_manifest_sha256':sha256(manifest),'videos':solution,'usage':{x:usage.get(x,0) for x in ids},'positions':positions,'constraints_checked':True,'attempts':attempts};save_json(state_dir(root)/'plan.json',out)
 folder=project_path(root,'混剪/组合方案');folder.mkdir(parents=True,exist_ok=True)
 lines=['# 混剪排列方案','','| 条号 | 片段顺序（角色 / 稳定 ID） | 秒 |','|---|---|---:|']
 for v in solution:lines.append('| '+v['video_id']+' | '+' → '.join(str(s.get('role',''))+' / '+s.get('display_id',s['segment_id']) for s in v['segments'])+' | '+f"{v['duration_seconds']:.3f}"+' |')
 lines+=['','## 使用次数','','| 片段 | 次数 |','|---|---:|']+[f'| {x} | {usage.get(x,0)} |' for x in ids];(folder/'方案.md').write_text('\n'.join(lines),encoding='utf-8');print('Plan drafted:',len(solution),'videos')

def audit(args):
 root=Path(args.project).resolve();mp=project_path(root,'.remix/segments-cut.json');manifest=load_json(mp);p=load_json(project_path(root,'.remix/plan.json'));errors,usage,positions=constraints(p['videos'],manifest['segments'],p['config']);byid={s['segment_id']:s for s in manifest['segments']}
 if sha256(mp)!=p['asset_manifest_sha256']:errors.append('Segment manifest changed')
 for s in manifest['segments']:
  path=project_path(root,s['path'])
  if not path.is_file() or sha256(path)!=s['sha256']:errors.append('Missing/changed segment: '+s['segment_id'])
 for v in p['videos']:
  for s in v['segments']:
   if s!=byid.get(s['segment_id']):errors.append('Plan record differs from manifest: '+s['segment_id'])
 if p.get('usage')!={x:usage.get(x,0) for x in byid}:errors.append('Usage summary differs')
 if errors:raise ValueError('\n'.join(errors))
 print('Plan audit passed:',len(p['videos']),'videos')

def letters(number):
 result=''
 while number:number,rem=divmod(number-1,26);result=chr(65+rem)+result
 return result

def naming(args):
 root=Path(args.project).resolve();p=load_json(project_path(root,'.remix/plan.json'));rendered=load_json(project_path(root,'.remix/rendered.json'));paths={v['video_id']:v['path'] for v in rendered['videos']};authors={}
 ap=project_path(root,'.remix/assets.json')
 if ap.exists():authors={a['asset_id']:a.get('author','') for a in load_json(ap).get('assets',[])}
 if args.author_map:authors.update(load_json(project_path(root,args.author_map)))
 rows=[]
 for i,v in enumerate(p['videos'],1):
  names=[]
  for s in v['segments']:
   author=s.get('author') or authors.get(s['asset_id'])
   if not author:raise ValueError('Missing author for '+s['asset_id']+'; supply --author-map')
   if author not in names:names.append(author)
  parts=[args.id_prefix,args.material_name+'迭'+letters(i),args.category,args.tag,'AI视频','角色展示',*names,args.fixed_suffix,args.size_label];name='-'.join(parts)+'.mp4'
  if any(re.search(r'[<>:"/\\|?*\x00-\x1f]',str(x)) for x in parts):raise ValueError('Unsafe filename component')
  old=paths[v['video_id']];source=project_path(root,old)
  if not source.is_file():raise ValueError('Missing rendered video '+old)
  new=str(Path(old).with_name(name)).replace('\\','/');project_path(root,new);rows.append({'video_id':v['video_id'],'old_path':old,'new_path':new,'sha256':sha256(source)})
 if len({r['new_path'].casefold() for r in rows})!=len(rows):raise ValueError('Naming collisions')
 mapping={'plan_sha256':sha256(project_path(root,'.remix/plan.json')),'rows':rows};save_json(state_dir(root)/'naming.json',mapping);folder=project_path(root,'混剪/命名方案');folder.mkdir(parents=True,exist_ok=True);(folder/'方案.md').write_text('# 命名方案（尚未执行）\n\n| 条号 | 原文件 | 新文件 |\n|---|---|---|\n'+'\n'.join(f"| {r['video_id']} | {r['old_path']} | {r['new_path']} |" for r in rows),encoding='utf-8');print('Naming drafted:',len(rows))

def rename(args):
 root=Path(args.project).resolve();mp=project_path(root,args.mapping);require_approval(root,'rename',mp);mapping=load_json(mp);rows=mapping['rows'];changed=[];sidechanged=[];metadata={}
 if mapping.get('plan_sha256')!=sha256(project_path(root,'.remix/plan.json')):raise ValueError('Plan changed after naming draft')
 planned=load_json(project_path(root,'.remix/plan.json'))['videos']
 if len(rows)!=len(planned) or {r['video_id'] for r in rows}!={v['video_id'] for v in planned}:raise ValueError('Mapping must cover the complete plan exactly once')
 rendered=load_json(project_path(root,'.remix/rendered.json'));actual={v['video_id']:v['path'] for v in rendered['videos']}
 if any(actual.get(r['video_id'])!=r['old_path'] for r in rows):raise ValueError('Mapping source paths do not match rendered records')
 if len({r['old_path'].casefold() for r in rows})!=len(rows):raise ValueError('Duplicate sources')
 if len({r['new_path'].casefold() for r in rows})!=len(rows):raise ValueError('Duplicate destinations')
 for r in rows:
  src=project_path(root,r['old_path']);dst=project_path(root,r['new_path'])
  if not src.is_file() or sha256(src)!=r['sha256']:raise ValueError('Source missing/changed: '+str(src))
  if dst.exists() and src!=dst:raise ValueError('Destination exists: '+str(dst))
  side=src.with_suffix('.remix.json');newside=dst.with_suffix('.remix.json')
  if side.exists():
   record=load_json(side)
   if str(record.get('video_id'))!=str(r['video_id']) or record.get('path')!=r['old_path'] or record.get('sha256')!=r['sha256']:raise ValueError('Sidecar does not match rendered asset: '+str(side))
   if newside.exists() and newside!=side:raise ValueError('Destination sidecar exists: '+str(newside))
 try:
  for r in rows:
   src=project_path(root,r['old_path']);dst=project_path(root,r['new_path']);src.rename(dst);changed.append((src,dst))
  if any(sha256(dst)!=r['sha256'] for r,(_,dst) in zip(rows,changed)):raise RuntimeError('Post-rename hash mismatch')
  replacements={r['old_path']:r['new_path'] for r in rows}
  def update(value):
   if isinstance(value,dict):return {k:update(v) for k,v in value.items()}
   if isinstance(value,list):return [update(v) for v in value]
   if isinstance(value,str):return replacements.get(value,value)
   return value
  for r in rows:
   side=project_path(root,r['old_path']).with_suffix('.remix.json');newside=project_path(root,r['new_path']).with_suffix('.remix.json')
   if side.exists():
    metadata[side]=side.read_bytes();updated=update(load_json(side));side.rename(newside);sidechanged.append((side,newside));save_json(newside,updated)
  files=[state_dir(root)/filename for filename in ['rendered.json','usage.json','validation.json']]
  validation=state_dir(root)/'validation'
  if validation.exists():files+=list(validation.rglob('*.json'))
  for f in files:
   if f.exists():metadata[f]=f.read_bytes();save_json(f,update(load_json(f)))
  save_json(state_dir(root)/'rename-log.json',{'mapping_sha256':sha256(mp),'rows':rows,'content_hashes_verified':True})
 except Exception:
  for src,dst in reversed(sidechanged):
   if dst.exists() and src!=dst and not src.exists():dst.rename(src)
  for src,dst in reversed(changed):
   if dst.exists() and not src.exists():dst.rename(src)
  for f,data in metadata.items():f.write_bytes(data)
  raise
 print('Renamed with unchanged hashes:',len(rows))

def register(subparsers):
 for command,fn in [('plan',plan),('plan-audit',audit),('naming',naming),('rename',rename)]:
  p=subparsers.add_parser(command);p.add_argument('--project',required=True);p.set_defaults(func=fn)
  if command=='plan':p.add_argument('--config',default='.remix/batch.json');p.add_argument('--budget-seconds',type=float,default=30)
  if command=='naming':
   p.add_argument('--id-prefix',required=True);p.add_argument('--material-name',default='角色展示变身');p.add_argument('--category',default='K4');p.add_argument('--tag',default='外扒混剪');p.add_argument('--fixed-suffix',default='sgl');p.add_argument('--size-label',default='720');p.add_argument('--author-map')
  if command=='rename':p.add_argument('--mapping',default='.remix/naming.json')
