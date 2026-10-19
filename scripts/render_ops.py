"""Approved, resumable render and independent media verification.

All files are project-relative. The plan is immutable; revisions are overrides
against a specific rendered hash and do not add a use of any segment.
"""
import argparse
import array
import math
import os
import re
import shutil
import tempfile
from collections import Counter
from fractions import Fraction
from pathlib import Path
from common import load_json, save_json, sha256, state_dir, project_path, require_approval, run_ffmpeg, probe


def rounded(value):
    value = Fraction(value)
    return (2 * value.numerator + value.denominator) // (2 * value.denominator)


def stream(info, kind):
    return next((s for s in info['streams'] if s['codec_type'] == kind), None)


def metadata(path):
    info = probe(path, frames=True)
    video = stream(info, 'video')
    frames = [f for f in info.get('frames', []) if f.get('media_type') == 'video']
    if not video or not frames:
        raise ValueError('No decoded video frames: ' + str(path))
    pts = [Fraction(f.get('best_effort_timestamp_time', f.get('pts_time', '0'))) for f in frames]
    gaps = [b-a for a,b in zip(pts,pts[1:])]
    nominal = Fraction(video.get('avg_frame_rate', '0/1'))
    if nominal <= 0:
        raise ValueError('Cannot determine frame timing: ' + str(path))
    tail = Fraction(frames[-1].get('duration_time', frames[-1].get('pkt_duration_time', str(float(1/nominal)))))
    if tail <= 0: tail = gaps[-1] if gaps else 1/nominal
    # Decimal PTS rounded by ffprobe can differ by a microsecond.
    cfr = not gaps or max(gaps)-min(gaps) <= Fraction(2,1000000)
    duration = len(frames)/nominal if cfr else pts[-1]-pts[0]+tail
    return info, video, frames, pts, nominal, cfr, duration


def read_plan(project):
    path = state_dir(project)/'plan.json'
    plan = load_json(path)
    require_approval(project, 'render', path)
    # Approval authenticates the chosen artifact; it cannot replace checking
    # group size, exact usage, source diversity or other configured constraints.
    from planner_ops import audit
    audit(argparse.Namespace(project=str(project)))
    ids = [str(v['video_id']) for v in plan['videos']]
    if len(set(ids)) != len(ids): raise ValueError('Duplicate video IDs')
    usage=Counter()
    for video in plan['videos']:
        segids = [s['segment_id'] for s in video['segments']]
        if len(segids) != len(set(segids)): raise ValueError('Repeated segment within '+str(video['video_id']))
        usage.update(segids)
    if any(n>int(plan['config'].get('max_uses',plan['config'].get('max_uses_per_segment',3))) for n in usage.values()):
        raise ValueError('Approved plan exceeds configured segment use limit')
    if 'asset_manifest_sha256' in plan:
        manifest=state_dir(project)/'segments-cut.json'
        if not manifest.exists() or sha256(manifest)!=plan['asset_manifest_sha256']:
            raise ValueError('Cut manifest changed after planning')
    return plan, sha256(path)


def output_fps(config):
    fps = Fraction(config.get('output_fps','30/1'))
    if fps <= 0: raise ValueError('Invalid output FPS')
    return fps


def source_spec(project, segment, config, trim_tail=0):
    path = project_path(project, segment['path'])
    if sha256(path) != segment['sha256']:
        raise ValueError('Source changed: '+segment['path'])
    info, video, frames, pts, fps, cfr, duration = metadata(path)
    if int(segment['frames']) != len(frames):
        raise ValueError('Source frame count does not match plan: '+segment['path'])
    count = len(frames)-trim_tail
    if count <= 0: raise ValueError('Tail trim removes entire segment')
    if cfr: duration = Fraction(count,1)/fps
    elif trim_tail:
        duration = pts[count]-pts[0]
    target = rounded(duration*output_fps(config))
    if target < 1: raise ValueError('Segment too short for output FPS')
    return dict(path=path, info=info, count=count, source_fps=fps,
                cfr=cfr, duration=duration, target_frames=target,
                target_duration=Fraction(target,1)/output_fps(config),
                has_audio=stream(info,'audio') is not None)


def visual_filter(spec, config, boundary=None):
    w,h = int(config.get('output_width',1280)),int(config.get('output_height',720))
    if w%2 or h%2 or w<=0 or h<=0: raise ValueError('Output dimensions must be positive even integers')
    spatial = f'scale={w}:{h}:force_original_aspect_ratio=decrease:flags=lanczos,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p'
    if boundary is not None:
        n = 0 if boundary=='first' else spec['count']-1
        return f"select=eq(n\\,{n}),setpts=PTS-STARTPTS,{spatial}"
    filters = [f"trim=end_frame={spec['count']}"]
    if spec['cfr']:
        filters += [f"settb=expr={spec['source_fps'].denominator}/{spec['source_fps'].numerator}", 'setpts=N']
    else: filters += ['setpts=PTS-STARTPTS']
    # Extend before fps conversion so fps never discards the last actual frame.
    if not spec['cfr'] or spec['source_fps']!=output_fps(config):
        # Decimation (e.g. 60 -> 30) can still skip the last real source frame.
        # Replace the final resampled frame with the actual source endpoint.
        # Verification independently compares that endpoint, not this graph.
        if spec['target_frames']==1:
            return visual_filter(spec,config,'last')+f',settb=expr={output_fps(config).denominator}/{output_fps(config).numerator},setpts=N'
        temporal=','.join(filters)
        end=spec['count']-1
        return (temporal+',split[seq][last];'+
                f"[seq]tpad=stop_mode=clone:stop_duration=1,fps={output_fps(config)}:round=near,trim=end_frame={spec['target_frames']-1},setpts=PTS-STARTPTS[body];"+
                f"[last]select=eq(n\\,{end}),setpts=PTS-STARTPTS[endpoint];"+
                f"[body][endpoint]concat=n=2:v=1:a=0,settb=expr={output_fps(config).denominator}/{output_fps(config).numerator},setpts=N,{spatial}")
    filters += [f"trim=end_frame={spec['target_frames']}",'setpts=PTS-STARTPTS',spatial]
    return ','.join(filters)


def audio_filter(spec):
    return f"atrim=duration={float(spec['duration']):.12f},asetpts=PTS-STARTPTS,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,apad,atrim=duration={float(spec['target_duration']):.12f}"


def build_parts(project, video, config, temp, overrides=None):
    parts, specs = [],[]
    overrides = overrides or {}
    for i,segment in enumerate(video['segments']):
        spec = source_spec(project,segment,config,int(overrides.get(segment['segment_id'],0)))
        if not spec['has_audio'] and not config.get('allow_missing_audio',False):
            raise ValueError('Missing audio; confirm allow_missing_audio before rendering: '+segment['path'])
        if config.get('preserve_original_audio',True) is not True:
            raise ValueError('This renderer supports original audio only')
        part = temp/f'part-{i}.mkv'
        args = ['-y','-i',spec['path']]
        if not spec['has_audio']: args += ['-f','lavfi','-i','anullsrc=r=48000:cl=stereo']
        audio_input = '0:a:0' if spec['has_audio'] else '1:a:0'
        graph = f"[0:v:0]{visual_filter(spec,config)}[v];[{audio_input}]{audio_filter(spec)}[a]"
        # Lossless parts avoid repeated lossy encoding; final encode happens once.
        run_ffmpeg(args+['-filter_complex',graph,'-map','[v]','-map','[a]',
                         '-c:v','ffv1','-level','3','-c:a','pcm_s16le','-fps_mode','passthrough',part])
        parts.append(part); specs.append(spec)
    return parts,specs


def assemble(parts, config, target, temp):
    # Matroska duration is rounded to milliseconds. Demuxer concatenation
    # accumulates that rounding at joins and shifts audio. Concatenate decoded
    # video and sample-exact PCM separately to preserve both timelines.
    args=['-y']
    for part in parts: args += ['-i',part]
    graph=[]
    for i in range(len(parts)):
        graph += [f'[{i}:v:0]setpts=PTS-STARTPTS[v{i}]',
                  f'[{i}:a:0]asetpts=N/SR/TB[a{i}]']
    graph += [''.join(f'[v{i}]' for i in range(len(parts)))+f'concat=n={len(parts)}:v=1:a=0[v]',
              ''.join(f'[a{i}]' for i in range(len(parts)))+f'concat=n={len(parts)}:v=0:a=1[a]']
    run_ffmpeg(args+['-filter_complex',';'.join(graph),
                '-map','[v]','-map','[a]','-c:v','libx264','-profile:v','high',
                '-pix_fmt','yuv420p','-crf',str(config.get('crf',18)),
                '-preset',config.get('preset','medium'),'-c:a','aac',
                '-b:a',config.get('audio_bitrate','192k'),'-ar','48000','-ac','2',
                '-fps_mode','passthrough','-movflags','+faststart',target])


def ssim_score(left, right, temp, name):
    log=temp/(name+'.ssim.txt')
    # Use relative log basename, including on Windows where drive colons escape badly.
    run_ffmpeg(['-i',left,'-i',right,'-filter_complex',
                f'[0:v]setpts=PTS-STARTPTS[a];[1:v]setpts=PTS-STARTPTS[b];[a][b]ssim=stats_file={log.name}',
                '-an','-f','null','-'],cwd=temp)
    scores=[]
    for line in log.read_text().splitlines():
        match=re.search(r'All:([0-9.]+)',line)
        if match: scores.append(float(match.group(1)))
    if not scores: raise ValueError('SSIM produced no comparisons')
    return scores


def pcm(path, filters):
    values=array.array('f')
    values.frombytes(run_ffmpeg(['-i',path,'-map','0:a:0','-af',filters,
                                 '-ar','8000','-ac','2','-c:a','pcm_f32le','-f','f32le','-']))
    return values


def correlate(left,right):
    # Separate channels; zero-lag only, so a shifted soundtrack cannot pass.
    n=min(len(left),len(right))//2
    if n<1: raise ValueError('Empty audio comparison')
    reports=[]
    for channel in (0,1):
        a=left[channel:2*n:2];b=right[channel:2*n:2]
        ea=sum(x*x for x in a)/n;eb=sum(x*x for x in b)/n
        if ea<1e-10:
            reports.append({'correlation':1.0 if eb<1e-8 else 0.0,'source_rms':math.sqrt(ea),'output_rms':math.sqrt(eb),'silence':True})
            continue
        ma=sum(a)/n;mb=sum(b)/n
        va=sum((x-ma)**2 for x in a);vb=sum((x-mb)**2 for x in b)
        corr=sum((x-ma)*(y-mb) for x,y in zip(a,b))/math.sqrt(va*vb) if va*vb>0 else 0.0
        reports.append({'correlation':corr,'source_rms':math.sqrt(ea),'output_rms':math.sqrt(eb),'silence':False})
    return reports


def validate_video(project,video,config,path,temp,overrides=None):
    info,v,frames,pts,fps,cfr,duration=metadata(path)
    if v.get('codec_name')!='h264' or v.get('pix_fmt')!='yuv420p': raise ValueError('Wrong output codec/pixel format')
    if (v['width'],v['height'])!=(int(config.get('output_width',1280)),int(config.get('output_height',720))): raise ValueError('Wrong output dimensions')
    if fps!=output_fps(config) or not cfr: raise ValueError('Wrong output FPS')
    a=stream(info,'audio')
    if not a or a['codec_name']!='aac' or int(a['channels'])!=2 or int(a['sample_rate'])!=48000: raise ValueError('Wrong output audio format')
    result={'video_id':str(video['video_id']),'segments':[],'passed':False,'checks':'full-frame SSIM; source first/last SSIM; stereo audio correlation at zero lag'}
    offset=0
    overrides=overrides or {}
    for i,segment in enumerate(video['segments']):
        spec=source_spec(project,segment,config,int(overrides.get(segment['segment_id'],0)))
        reference=temp/f'ref-{i}.mkv';actual=temp/f'actual-{i}.mkv'
        run_ffmpeg(['-y','-i',spec['path'],'-vf',visual_filter(spec,config),'-an','-c:v','ffv1','-fps_mode','passthrough',reference])
        run_ffmpeg(['-y','-i',path,'-vf',f"trim=start_frame={offset}:end_frame={offset+spec['target_frames']},setpts=PTS-STARTPTS",'-an','-c:v','ffv1','-fps_mode','passthrough',actual])
        scores=ssim_score(reference,actual,temp,f'segment-{i}')
        if len(scores)!=spec['target_frames']: raise ValueError('Frame comparison count mismatch')
        boundaries={}
        for label,n in [('first',0),('last',spec['target_frames']-1)]:
            source=temp/f'source-{i}-{label}.mkv';edge=temp/f'edge-{i}-{label}.mkv'
            run_ffmpeg(['-y','-i',spec['path'],'-vf',visual_filter(spec,config,label),'-an','-c:v','ffv1','-fps_mode','passthrough',source])
            run_ffmpeg(['-y','-i',actual,'-vf',f"select=eq(n\\,{n}),setpts=PTS-STARTPTS",'-an','-c:v','ffv1','-fps_mode','passthrough',edge])
            boundaries[label]=ssim_score(source,edge,temp,f'boundary-{i}-{label}')[0]
        start=Fraction(offset,1)/output_fps(config)
        output_audio=pcm(path,f'atrim=start={float(start):.12f}:duration={float(spec["target_duration"]):.12f},asetpts=PTS-STARTPTS')
        source_audio=pcm(spec['path'],audio_filter(spec)) if spec['has_audio'] else array.array('f',[0.0])*len(output_audio)
        audio=correlate(source_audio,output_audio)
        audio_length_ok=abs(len(source_audio)-len(output_audio))<=32
        passed=(sum(scores)/len(scores)>=float(config.get('verify_mean_ssim',.98)) and
                min(boundaries.values())>=float(config.get('verify_boundary_ssim',.95)) and audio_length_ok and
                all(x['correlation']>=float(config.get('verify_audio_correlation',.98)) for x in audio))
        result['segments'].append({'segment_id':segment['segment_id'],'frame_start':offset,'frames':spec['target_frames'],
                                  'source_frames':spec['count'],'mean_ssim':sum(scores)/len(scores),'min_frame_ssim':min(scores),
                                  'boundaries':boundaries,'audio':audio,'audio_length_ok':audio_length_ok,'passed':passed})
        offset+=spec['target_frames']
    result['expected_frames']=offset;result['actual_frames']=len(frames)
    result['passed']=len(frames)==offset and all(x['passed'] for x in result['segments'])
    return result


def rendered_state(project):
    path=state_dir(project)/'rendered.json'
    return load_json(path) if path.exists() else {'videos':[]}


def update_usage(project,plan,state):
    plan_by_id={str(v['video_id']):v for v in plan['videos']}
    uses={}
    effective=[]
    for record in state['videos']:
        vid=str(record['video_id'])
        if vid not in plan_by_id or record.get('plan_sha256')!=sha256(state_dir(project)/'plan.json'): continue
        effective.append(vid)
        for s in plan_by_id[vid]['segments']: uses[s['segment_id']]=uses.get(s['segment_id'],0)+1
    limit=int(plan['config'].get('max_uses_per_segment',plan['config'].get('max_uses',3)))
    if any(n>limit for n in uses.values()): raise ValueError('Effective usage exceeds approved limit')
    save_json(state_dir(project)/'usage.json',{'effective_video_ids':effective,'segment_uses':uses,'max_uses_per_segment':limit,
                                             'complete':len(effective)==len(plan['videos'])})


def selection(plan,only):
    requested=set(only.split(',')) if only else None
    result=[v for v in plan['videos'] if requested is None or str(v['video_id']) in requested]
    if requested and requested!={str(v['video_id']) for v in result}: raise ValueError('Unknown --only video ID')
    return result


def render_one(project,plan,plan_hash,video,state,overrides=None,forced=False):
    root=Path(project).resolve();vid=str(video['video_id']);config=plan['config']
    old=next((r for r in state['videos'] if str(r['video_id'])==vid),None)
    target=project_path(root,old['path'] if old else f'混剪/成品/混剪_{vid}.mp4')
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists() and not forced:
        if not old or old.get('plan_sha256')!=plan_hash or sha256(target)!=old.get('sha256'):
            raise ValueError('Existing output cannot be silently overwritten: '+str(target))
        with tempfile.TemporaryDirectory(prefix='.verify-',dir=target.parent) as td:
            report=validate_video(root,video,config,target,Path(td),old.get('tail_trim_overrides'))
        if not report['passed']: raise ValueError('Existing output failed validation')
        return old
    with tempfile.TemporaryDirectory(prefix='.render-',dir=target.parent) as td:
        temp=Path(td);candidate=temp/'candidate.mp4'
        reuse=config.get('reuse_outputs',{}).get(vid) if not forced else None
        if reuse:
            source=project_path(root,reuse);sidecar=source.with_suffix('.remix.json')
            if not sidecar.exists(): raise ValueError('Sample reuse requires .remix.json sidecar')
            record=load_json(sidecar)
            if record.get('plan_sha256')!=plan_hash or record.get('segments')!=[s['segment_id'] for s in video['segments']] or record.get('sha256')!=sha256(source):
                raise ValueError('Sample sidecar does not match approved plan, order or hash')
            shutil.copy2(source,candidate)
        else:
            parts,specs=build_parts(root,video,config,temp,overrides)
            assemble(parts,config,candidate,temp)
        report=validate_video(root,video,config,candidate,temp,overrides)
        if not report['passed']:
            save_json(state_dir(root)/'validation'/f'failed-{vid}.json',report)
            raise ValueError('Validation failed; existing output preserved: '+vid)
        if target.exists():
            backup=state_dir(root)/'backups'/f'{vid}-{sha256(target)[:16]}.mp4'
            backup.parent.mkdir(parents=True,exist_ok=True)
            if not backup.exists(): shutil.copy2(target,backup)
        os.replace(candidate,target)
    reportpath=state_dir(root)/'validation'/f'{vid}.json'
    save_json(reportpath,report)
    record={'video_id':vid,'path':str(target.relative_to(root)),'sha256':sha256(target),'plan_sha256':plan_hash,
            'segments':[s['segment_id'] for s in video['segments']],
            'validation_path':str(reportpath.relative_to(root)),'tail_trim_overrides':overrides or {},'passed':True}
    save_json(target.with_suffix('.remix.json'),record)
    state['videos']=[r for r in state['videos'] if str(r['video_id'])!=vid]+[record]
    save_json(state_dir(root)/'rendered.json',state);update_usage(root,plan,state)
    return record


def render(args):
    plan,ph=read_plan(args.project);state=rendered_state(args.project)
    for video in selection(plan,args.only):
        record=render_one(args.project,plan,ph,video,state)
        print('Validated '+record['video_id']+' -> '+record['path'])
    update_usage(args.project,plan,state)
    print('Complete batch' if load_json(state_dir(args.project)/'usage.json')['complete'] else 'Partial batch; pending video IDs remain')


def verify(args):
    plan,ph=read_plan(args.project);state=rendered_state(args.project);reports=[]
    for video in selection(plan,args.only):
        record=next((r for r in state['videos'] if str(r['video_id'])==str(video['video_id'])),None)
        if not record: raise ValueError('Video not rendered: '+str(video['video_id']))
        path=project_path(args.project,record['path'])
        if record['plan_sha256']!=ph or record['sha256']!=sha256(path): raise ValueError('Output or approved plan changed')
        with tempfile.TemporaryDirectory(prefix='.verify-',dir=path.parent) as td:
            report=validate_video(args.project,video,plan['config'],path,Path(td),record.get('tail_trim_overrides'))
        save_json(project_path(args.project,record['validation_path']),report);reports.append(report)
    destination=state_dir(args.project)/'validation'/'verification-summary.md'
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text('# Independent verification\n\n'+''.join(f"- {r['video_id']}: {'PASS' if r['passed'] else 'FAIL'}, frames {r['actual_frames']}/{r['expected_frames']}\n" for r in reports),encoding='utf-8')
    if not all(r['passed'] for r in reports): raise ValueError('Independent verification failed')
    print(str(destination))


def revise(args):
    plan,ph=read_plan(args.project);state=rendered_state(args.project)
    artifact=state_dir(args.project)/'revision.json'
    require_approval(args.project,'revise',artifact)
    proposal=load_json(artifact)
    record=next((r for r in state['videos'] if str(r['video_id'])==args.video),None)
    if not record: raise ValueError('Unknown rendered video ID')
    if proposal.get('video_id')!=args.video or proposal.get('trim_tail_frames')!=args.trim_tail_frames or proposal.get('reason')!=args.reason:
        raise ValueError('Revision arguments do not match approved artifact')
    if proposal.get('output_sha256')!=record['sha256'] or sha256(project_path(args.project,record['path']))!=record['sha256']:
        raise ValueError('Revision is stale')
    if args.trim_tail_frames<1: raise ValueError('Trim must be positive source-frame count')
    video=next(v for v in plan['videos'] if str(v['video_id'])==args.video)
    overrides=dict(record.get('tail_trim_overrides',{}))
    last=video['segments'][-1]['segment_id'];overrides[last]=overrides.get(last,0)+args.trim_tail_frames
    render_one(args.project,plan,ph,video,state,overrides,forced=True)
    print('Revised '+args.video+' from source; usage unchanged')


def register(subparsers):
    for command,function in [('render',render),('verify',verify)]:
        parser=subparsers.add_parser(command)
        parser.add_argument('--project',required=True)
        parser.add_argument('--only',help='Comma-separated stable video IDs; e.g. 01,07')
        parser.set_defaults(func=function)
    parser=subparsers.add_parser('revise')
    parser.add_argument('--project',required=True);parser.add_argument('--video',required=True)
    parser.add_argument('--trim-tail-frames',required=True,type=int,help='Number of real SOURCE frames removed from final segment')
    parser.add_argument('--reason',required=True);parser.set_defaults(func=revise)
