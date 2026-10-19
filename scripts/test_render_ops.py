"""Offline end-to-end tests in an isolated folder; no original project assets."""
import argparse
import tempfile
from pathlib import Path
from common import ROOT, run_ffmpeg, sha256, save_json, load_json, approve
import render_ops as r
from planner_ops import constraints

def write_plan(root,segments,config,video_id):
    manifest=root/'.remix/segments-cut.json'
    save_json(manifest,{'segments':segments})
    videos=[dict(video_id=video_id,segments=segments)]
    errors,usage,positions=constraints(videos,segments,config)
    assert not errors,errors
    plan=dict(config=config,videos=videos,asset_manifest_sha256=sha256(manifest),usage=usage,positions=positions)
    save_json(root/'.remix/plan.json',plan)
    return plan

def main():
    base=ROOT/'_tests'/'render';base.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=base) as td:
        root=Path(td);segments=[]
        # Sharp distinct endpoint frames catch a dropped/repeated incorrect tail.
        for i,fps in enumerate((25,30,60)):
            path=root/f'source{i}.mp4'
            run_ffmpeg(['-y','-f','lavfi','-i',f'testsrc2=size=160x90:rate={fps}:duration=1',
                        '-f','lavfi','-i',f'sine=frequency={440+i*110}:sample_rate=48000:duration=1',
                        '-vf',f"drawbox=x=0:y=0:w=160:h=90:color=red:t=fill:enable=eq(n\\,{fps-1})",
                        '-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-c:a','aac',path])
            segments.append(dict(segment_id=f's{i}',asset_id=f'a{i}',path=path.name,
                                 sha256=sha256(path),frames=fps,fps=f'{fps}/1',duration_seconds=1,
                                 role=f'role{i}',author='test',audio=True,width=160,height=90))
        config=dict(output_width=160,output_height=90,output_fps='30/1',crf=18,preset='ultrafast',max_uses=3,segments_per_video=3,target_count=1,distinct_sources=True)
        plan=write_plan(root,segments,config,'01');approve(root,'render','.remix/plan.json','test explicit approval')
        args=argparse.Namespace(project=str(root),only=None)
        r.render(args);r.verify(args)
        state=load_json(root/'.remix/rendered.json');record=state['videos'][0]
        original=root/record['path'];renamed=original.with_name('renamed.mp4');original.rename(renamed)
        record['path']=str(renamed.relative_to(root));save_json(root/'.remix/rendered.json',state)
        r.verify(args)
        proposal=dict(video_id='01',trim_tail_frames=1,reason='test remove title tail',output_sha256=record['sha256'])
        save_json(root/'.remix/revision.json',proposal);approve(root,'revise','.remix/revision.json','test explicit trim approval')
        r.revise(argparse.Namespace(project=str(root),video='01',trim_tail_frames=1,reason=proposal['reason']))
        r.verify(args)
        assert load_json(root/'.remix/usage.json')['segment_uses']=={'s0':1,'s1':1,'s2':1}
        assert not original.exists()
        print('PASS mixed 25/30/60 FPS, distinct endpoint, audio, rename, revision and unchanged usage')
        # VFR holds source timing, rather than reassigning N/source_fps.
        vfr=root/'vfr.mp4'
        run_ffmpeg(['-y','-i',root/'source0.mp4','-vf','setpts=if(lt(N\\,10)\\,N/(25*TB)\\,(0.4+(N-10)/20)/TB)',
                    '-an','-c:v','libx264','-crf','18','-fps_mode','vfr',vfr])
        assert not r.metadata(vfr)[5]
        silence=dict(segments[0],segment_id='vfr',path=vfr.name,sha256=sha256(vfr),audio=False)
        silence['frames']=len(r.metadata(vfr)[2])
        config=dict(config,segments_per_video=1,allow_missing_audio=True)
        plan=write_plan(root,[silence],config,'02');approve(root,'render','.remix/plan.json','test VFR silence approval')
        r.render(args);r.verify(args)
        print('PASS VFR timing and explicitly permitted missing-audio silence')
        plan['config']['segments_per_video']=3
        save_json(root/'.remix/plan.json',plan);approve(root,'render','.remix/plan.json','test approved invalid grouping')
        try:r.read_plan(root)
        except ValueError as exc:assert 'Wrong group size' in str(exc),str(exc)
        else:raise AssertionError('Approved invalid grouping bypassed render audit')
        plan['config']['segments_per_video']=1;plan['config']['exact_uses']=True
        save_json(root/'.remix/plan.json',plan);approve(root,'render','.remix/plan.json','test approved invalid exact usage')
        try:r.read_plan(root)
        except ValueError as exc:assert 'Exact usage' in str(exc),str(exc)
        else:raise AssertionError('Approved invalid exact usage bypassed render audit')
        print('PASS approved-but-invalid grouping and exact-usage plans rejected')

def test_fractional_join_audio():
    base=ROOT/'_tests'/'render';base.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=base) as td:
        root=Path(td);segments=[]
        for i,count in enumerate((32,32,37)):
            path=root/f'fractional{i}.mp4';duration=count/30
            run_ffmpeg(['-y','-f','lavfi','-i',f'testsrc2=size=160x90:rate=30:duration={duration:.12f}',
                        '-f','lavfi','-i',f'sine=frequency={1700+i*100}:sample_rate=48000:duration={duration:.12f}',
                        '-frames:v',str(count),'-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-c:a','aac',path])
            segments.append(dict(segment_id=f'f{i}',asset_id=f'a{i}',path=path.name,sha256=sha256(path),
                                 frames=count,fps='30/1',duration_seconds=duration,role=f'role{i}',author='test',audio=True,width=160,height=90))
        config=dict(output_width=160,output_height=90,output_fps='30/1',crf=18,preset='ultrafast',max_uses=3,segments_per_video=3,target_count=1)
        write_plan(root,segments,config,'fractional');approve(root,'render','.remix/plan.json','test fractional duration audio regression')
        args=argparse.Namespace(project=str(root),only=None)
        r.render(args);r.verify(args)
        report=load_json(root/'.remix/validation/fractional.json')
        assert report['actual_frames']==101 and report['passed']
        print('PASS non-millisecond segment durations preserve original audio across both joins')

if __name__=='__main__':
    main()
    test_fractional_join_audio()

