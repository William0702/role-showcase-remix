"""Isolated actual CLI integration, known synthetic boundaries, no user media."""
import json,subprocess,time
from pathlib import Path
from common import ROOT,save_json,load_json,sha256,run_ffmpeg
from automation_ops import normalize

def main():
    base=ROOT.parent/'_技能测试'/('自动FilmCraft-'+str(time.time_ns()));root=base/'project';root.mkdir(parents=True)
    py=ROOT/'tools/windows-x64/python/python.exe';cli=ROOT/'scripts/remix.py'
    def run(args,ok=True):
        p=subprocess.run([str(py),str(cli),args[0],'--project',str(root),*args[1:]],capture_output=True,encoding='utf-8',errors='replace')
        if ok:assert p.returncode==0,p.stdout+p.stderr
        else:assert p.returncode!=0,p.stdout
        print(p.stdout[-1800:],flush=True);return p
    run(['init'])
    # This is a technical test fixture, not a user's confirmed production batch.
    raw='Synthetic test authorization: cut, arrange, export and name generated fixture media only.'
    answers={'mode':'showcase','group_size':3,'target_count':'capacity','max_uses':3,'quota_scope':'batch','distinct_sources':True,'unique_pairs':True,'output_width':160,'output_height':90,'output_fps':'30/1','preserve_original_audio':True,'naming':'custom','id_prefix':'idTEST','material_name':'角色展示变身','category':'K4','tag':'外扒混剪','fixed_suffix':'sgl','size_label':'90','authorization_text':raw}
    save_json(root/'.remix/intake-answers.json',{'mode':'showcase'})
    run(['auto-intake']);assert load_json(root/'.remix/intake.json')['status']=='questions_pending'
    run(['auto-produce'],False);assert not (root/'.remix/segments-cut.json').exists()
    save_json(root/'.remix/intake-answers.json',answers);run(['auto-intake'])
    run(['auto-produce'],False) # no actual-review checkpoint yet
    for i,(fps,count) in enumerate([(25,27),(30,34),(25,31)]):
        output=root/'母片'/f'idT{i}-展示-test{i}-90.mp4';duration=count/fps
        run_ffmpeg(['-y','-f','lavfi','-i',f'testsrc2=size=160x90:rate={fps}:duration={duration:.12f}','-f','lavfi','-i',f'sine=frequency={600+i*120}:sample_rate=48000:duration={duration:.12f}','-frames:v',str(count),'-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-c:a','aac',output])
    run(['inventory'])
    assets=load_json(root/'.remix/assets.json')['assets'];segments=[]
    for a in assets:segments.append({'segment_id':a['asset_id']+'-01','asset_id':a['asset_id'],'display_id':a['display_id']+'-01','role':'fixture-'+a['display_id'],'start_frame':0,'end_frame_exclusive':a['frame_count']})
    save_json(root/'.remix/segments.json',{'source_manifest_sha256':sha256(root/'.remix/assets.json'),'segments':segments})
    # The fixture generator defines the exact full-source boundaries; no semantic review is claimed.
    save_json(root/'.remix/automation.json',{'intake_sha256':sha256(root/'.remix/intake.json'),'segments_sha256':sha256(root/'.remix/segments.json'),'visual_review_complete':True,'unresolved':[],'review_type':'known generated fixture'})
    run(['auto-produce'])
    before=load_json(root/'.remix/usage.json');assert before['complete'] and all(v==1 for v in before['segment_uses'].values())
    state=load_json(root/'.remix/rendered.json');assert len(state['videos'])==1 and state['videos'][0]['engine']=='FilmCraft'
    assert Path(state['videos'][0]['path']).name.startswith('idTEST-角色展示变身迭A-')
    beforehash=sha256(root/state['videos'][0]['path'])
    run(['auto-produce'])
    assert before==load_json(root/'.remix/usage.json')
    state2=load_json(root/'.remix/rendered.json');assert state2['videos'][0]['path']==state['videos'][0]['path'] and sha256(root/state2['videos'][0]['path'])==beforehash
    answers['max_uses']=2;save_json(root/'.remix/intake-answers.json',answers);run(['auto-intake']);run(['auto-produce'],False)
    results={'passed':True,'tests':['missing answers blocked','missing review blocked','capacity bounded by unique role sets','mixed FPS native production','custom naming and final delivery','resume keeps file and usage','changed completed-batch rules blocked'],'fixture_dir':str(root),'scope':'synthetic technical integration; real source semantic review is agent work'}
    save_json(ROOT.parent/'自动化FilmCraft测试报告.json',results);print(json.dumps(results,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
