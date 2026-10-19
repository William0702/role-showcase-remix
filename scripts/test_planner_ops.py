"""Isolated tests: synthetic empty assets, never production videos."""
import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from common import save_json,sha256,load_json,approve
import planner_ops as m

class PlannerTest(unittest.TestCase):
 def test_full_pipeline(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);segments=[]
   for i in range(33):
    p=root/f'segments/{i}.mp4';p.parent.mkdir(exist_ok=True);p.write_bytes(str(i).encode());segments.append({'segment_id':str(i),'display_id':str(i),'asset_id':'id'+str(i//4),'role':'role'+str(i),'path':str(p.relative_to(root)),'fps':'30/1','frames':30,'duration_seconds':1,'sha256':sha256(p),'source_sha256':'source','author':'author'+str(i%2)})
   save_json(root/'.remix/segments-cut.json',{'segments':segments});save_json(root/'.remix/batch.json',{'segments_per_video':3,'max_uses':3,'exact_uses':True,'balance_positions':True,'unique_sets':True,'unique_pairs':True,'seed':15,'fixed_videos':[['0','4','8']]})
   a=SimpleNamespace(project=td,config='.remix/batch.json',budget_seconds=30);m.plan(a);m.audit(a);plan=load_json(root/'.remix/plan.json');self.assertEqual(len(plan['videos']),33);self.assertTrue(all(v==3 for v in plan['usage'].values()))
   rendered=[]
   for v in plan['videos']:
    p=root/('output/'+v['video_id']+'.mp4');p.parent.mkdir(exist_ok=True);p.write_bytes(v['video_id'].encode());record={'video_id':v['video_id'],'path':str(p.relative_to(root)),'sha256':sha256(p)};rendered.append(record);save_json(p.with_suffix('.remix.json'),record);save_json(root/('.remix/validation/'+v['video_id']+'.json'),{'video_id':v['video_id'],'nested':{'output_path':record['path']}})
   save_json(root/'.remix/rendered.json',{'videos':rendered});a=SimpleNamespace(project=td,id_prefix='id999',material_name='角色展示变身',category='K4',tag='外扒混剪',fixed_suffix='sgl',size_label='720',author_map=None);m.naming(a)
   a=SimpleNamespace(project=td,mapping='.remix/naming.json')
   with self.assertRaises(ValueError):m.rename(a)
   approve(root,'rename','.remix/naming.json','Test-only authorization');m.rename(a)
   for row in load_json(root/'.remix/naming.json')['rows']:
    self.assertEqual(sha256(root/row['new_path']),row['sha256']);self.assertFalse((root/row['old_path']).with_suffix('.remix.json').exists());self.assertEqual(load_json((root/row['new_path']).with_suffix('.remix.json'))['path'],row['new_path']);self.assertEqual(load_json(root/('.remix/validation/'+row['video_id']+'.json'))['nested']['output_path'],row['new_path'])
 def test_letters(self):self.assertEqual([m.letters(n) for n in [1,26,27,33]],['A','Z','AA','AG'])
 def test_infeasible_capacity(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);save_json(root/'.remix/segments-cut.json',{'segments':[{'segment_id':str(i)} for i in range(3)]});save_json(root/'.remix/batch.json',{'segments_per_video':3,'max_uses':1,'target_count':2})
   with self.assertRaisesRegex(ValueError,'capacity'):m.plan(SimpleNamespace(project=td,config='.remix/batch.json',budget_seconds=1))
   self.assertFalse((root/'.remix/plan.json').exists())

if __name__=='__main__':unittest.main()
