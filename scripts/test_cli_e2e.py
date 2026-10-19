"""Exercise the actual CLI end to end on isolated synthetic assets only."""
import subprocess,sys,time,json
from pathlib import Path
from collections import Counter
from common import ROOT,run_ffmpeg,save_json,load_json,sha256

def main():
    project=ROOT.parent/'_tests'/'cli-e2e'/('run-'+str(time.time_ns()))
    cli=ROOT/'scripts/remix.py'
    def call(command,*options,blocked=False):
        result=subprocess.run([sys.executable,str(cli),command,'--project',str(project),*map(str,options)],capture_output=True,encoding='utf-8',errors='replace')
        if blocked:
            assert result.returncode!=0 and 'approval' in result.stderr.lower(),(command,result.stdout,result.stderr)
        else:
            assert result.returncode==0,(command,result.stdout,result.stderr)
        print(command+(': expected approval block' if blocked else ': PASS'))
    def approve(stage,artifact):call('approve','--stage',stage,'--artifact',artifact,'--human-text','Synthetic test authorization only; not production approval')
    call('init')
    for i,color in enumerate(('red','green','blue'),1):
        path=project/'母片'/f'idTEST{i}-demo-author{i}-720.mp4'
        run_ffmpeg(['-f','lavfi','-i',f'color=c={color}:s=160x90:r=25:d=1','-f','lavfi','-i',f'sine=frequency={300+i*100}:sample_rate=48000:duration=1',
                    '-vf','drawbox=x=0:y=0:w=iw:h=ih:color=white:t=fill:enable=eq(n\\,24)', '-c:v','libx264','-crf','0','-c:a','aac','-y',path])
    call('inventory');assets=load_json(project/'.remix/assets.json')['assets'];assert len(assets)==3
    segments=[]
    for a in assets:
        call('review','--asset',a['asset_id'],'--page-size','10','--width','160','--boundary','12','24')
        for n,(first,last) in enumerate(((0,12),(12,25)),1):
            segments.append({'segment_id':a['asset_id']+f'-{n:02d}','asset_id':a['asset_id'],'display_id':a['display_id']+f'-{n:02d}','role':f'Role{a["display_id"]}-{n}','start_frame':first,'end_frame_exclusive':last})
    save_json(project/'.remix/segments.json',{'source_manifest_sha256':sha256(project/'.remix/assets.json'),'segments':segments})
    call('cut',blocked=True);assert not(project/'切分').exists()
    approve('cut','.remix/segments.json');call('cut')
    cut=load_json(project/'.remix/segments-cut.json')['segments'];assert len(cut)==6 and sum(x['frames'] for x in cut)==75
    config=load_json(project/'.remix/batch.json');config.update({'segments_per_video':3,'max_uses':3,'exact_uses':True,'target_count':6,'distinct_sources':True,'balance_positions':True,'unique_sets':True,'output_width':160,'output_height':90,'output_fps':'25/1','preset':'ultrafast','crf':18})
    save_json(project/'.remix/batch.json',config)
    call('plan','--budget-seconds','20');call('plan-audit')
    plan=load_json(project/'.remix/plan.json');uses=Counter(s['segment_id'] for v in plan['videos'] for s in v['segments']);assert len(plan['videos'])==6 and set(uses.values())=={3}
    call('render',blocked=True);assert not(project/'.remix/rendered.json').exists()
    approve('render','.remix/plan.json');call('render');call('verify')
    original=load_json(project/'.remix/rendered.json')['videos'];assert len(original)==6
    for v in original:
        path=project/v['path'];side=load_json(path.with_suffix('.remix.json'));assert side['path']==v['path'] and side['sha256']==sha256(path)
    usage=load_json(project/'.remix/usage.json');assert usage['complete'] and set(usage['segment_uses'].values())=={3}
    call('naming','--id-prefix','idTESTOUT','--size-label','90')
    mapping=load_json(project/'.remix/naming.json');call('rename',blocked=True)
    assert all((project/r['old_path']).exists() for r in mapping['rows'])
    approve('rename','.remix/naming.json');call('rename');call('verify')
    renamed=load_json(project/'.remix/rendered.json')['videos'];assert len(renamed)==6
    for r in mapping['rows']:
        path=project/r['new_path'];assert path.exists() and sha256(path)==r['sha256'] and not(project/r['old_path']).exists()
        side=load_json(path.with_suffix('.remix.json'));assert side['path']==r['new_path'] and side['sha256']==r['sha256']
    usage=load_json(project/'.remix/usage.json');assert usage['complete'] and set(usage['segment_uses'].values())=={3}
    save_json(project/'test-result.json',{'status':'PASS','assets':3,'segments':6,'videos':6,'uses_per_segment':3,'approval_blocks':['cut','render','rename'],'sidecars_verified':True,'renamed_video_hashes_unchanged':True})
    print('PASS complete CLI end-to-end; isolated project: '+str(project))

if __name__=='__main__':main()
