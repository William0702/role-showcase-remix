"""Isolated synthetic integration test; never reads production assets."""
import argparse,sys
from pathlib import Path
from common import ROOT,run_ffmpeg,save_json,load_json,sha256,approve,frame_hashes
from asset_ops import inventory,review,cut

def main():
    project=ROOT.parent/'_tests'/'assets'
    if project.exists():
        # New isolated run rather than deleting or touching earlier test outputs.
        import time
        project=project/('run-'+str(time.time_ns()))
    source=project/'母片';source.mkdir(parents=True)
    path=source/'idTEST-demo-author-720.mp4'
    run_ffmpeg(['-f','lavfi','-i','color=c=red:s=160x90:r=25:d=1','-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=1',
                '-vf','drawbox=x=0:y=0:w=iw:h=ih:color=blue:t=fill:enable=eq(n\\,24)','-c:v','libx264','-crf','0','-c:a','aac','-y',path])
    inventory(argparse.Namespace(project=project,source='母片'))
    assets=load_json(project/'.remix/assets.json')['assets'];assert len(assets)==1
    a=assets[0];assert a['frame_count']==25 and a['audio'] and a['author']=='author'
    hashes=frame_hashes(path);assert hashes[-1]!=hashes[-2]
    review(argparse.Namespace(project=project,asset=a['asset_id'],width=160,page_size=10,boundary=[24]))
    review_files=list((project/'拉片审阅').glob('*/review.json'));r=load_json(review_files[0]);assert r['frames']==25 and len(r['pages'])==3
    spec=project/'.remix/segments.json';save_json(spec,{'source_manifest_sha256':sha256(project/'.remix/assets.json'),'segments':[{'segment_id':a['asset_id']+'-01','asset_id':a['asset_id'],'role':'TestRole','start_frame':5,'end_frame_exclusive':25,'display_id':'idTEST-01'}]})
    ns=argparse.Namespace(project=project,segments='.remix/segments.json',only=None)
    try:cut(ns)
    except ValueError as e:assert 'approval' in str(e).lower()
    else:raise AssertionError('Unapproved cut was permitted')
    assert not (project/'切分').exists()
    approve(project,'cut','.remix/segments.json','Synthetic automated test authorization only')
    cut(ns);record=load_json(project/'.remix/segments-cut.json')['segments'][0]
    assert record['frames']==20 and record['audio']
    result=project/record['path'];actual=frame_hashes(result);assert actual==hashes[5:25] and actual[-1]!=actual[-2]
    before=sha256(result);cut(ns);assert before==sha256(result)
    vfr=source/'idVFR-demo-author-720.mp4'
    run_ffmpeg(['-i',path,'-vf','select=not(eq(n\\,10))','-fps_mode','vfr','-c:v','libx264','-crf','0','-c:a','aac','-y',vfr])
    inventory(argparse.Namespace(project=project,source='母片'))
    cut(ns)  # Unrelated source addition must not invalidate already reviewed asset.
    av=[x for x in load_json(project/'.remix/assets.json')['assets'] if x['display_id']=='idVFR'][0]
    assert av['frame_count']==24 and av['variable_frame_rate']
    original_segments=load_json(spec)['segments']
    save_json(spec,{'source_manifest_sha256':sha256(project/'.remix/assets.json'),'segments':original_segments+[{'segment_id':av['asset_id']+'-01','asset_id':av['asset_id'],'role':'VFRRole','start_frame':8,'end_frame_exclusive':24,'display_id':'idVFR-01'}]})
    approve(project,'cut','.remix/segments.json','Synthetic VFR test authorization only');cut(ns)
    rv=[x for x in load_json(project/'.remix/segments-cut.json')['segments'] if x['asset_id']==av['asset_id']][0]
    assert frame_hashes(project/rv['path'])==frame_hashes(vfr)[8:24]
    pool_hash=sha256(project/'.remix/segments-cut.json');fullspec=load_json(spec)
    save_json(spec,{**fullspec,'segments':fullspec['segments'][1:]});approve(project,'cut','.remix/segments.json','Synthetic deleted-role rejection test')
    try:cut(ns)
    except ValueError as e:assert 'cut pool differs' in str(e)
    else:raise AssertionError('Deleted-role stale pool was accepted')
    assert pool_hash==sha256(project/'.remix/segments-cut.json')
    save_json(spec,fullspec)
    import shutil
    shutil.copyfile(path,source/'zzz-copy.mp4');inventory(argparse.Namespace(project=project,source='母片'))
    inventory_record=load_json(project/'.remix/assets.json');assert inventory_record['discovered_count']==3 and inventory_record['unique_count']==2 and len(inventory_record['duplicates'])==1
    manifest_hash=sha256(project/'.remix/assets.json')
    shutil.copyfile(vfr,source/'idTEST-other-author-720.mp4')
    try:inventory(argparse.Namespace(project=project,source='母片'))
    except ValueError as e:assert 'share display_id' in str(e)
    else:raise AssertionError('Distinct source ID collision was accepted')
    assert manifest_hash==sha256(project/'.remix/assets.json')
    print('PASS inventory / full review / approval block / exact final frame / audio / resume / VFR / incremental sources / stale pool rejection / duplicate counting / source ID collision')
    print(project)

if __name__=='__main__':main()
