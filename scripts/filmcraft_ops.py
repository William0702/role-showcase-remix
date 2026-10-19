"""Convert approved showcase plans into editable FilmCraft projects."""
import argparse,json,os,shutil,subprocess,tempfile
from fractions import Fraction
from pathlib import Path
from common import ROOT,load_json,save_json,sha256,project_path,state_dir,run_ffmpeg
import render_ops as r
TICKS=254016000000

def binary(args):
    explicit=args.cli or os.environ.get('REMIX_FILMCRAFT_CLI')
    if explicit:
        if not Path(explicit).is_file():raise ValueError('Explicit FilmCraft CLI missing')
        return str(Path(explicit).resolve())
    state=ROOT/'.software/filmcraft.json'
    if state.is_file():
        record=load_json(state)
        if record.get('selftest',{}).get('passed') and all(Path(record[key]).is_file() and sha256(record[key])==record[key+'_sha256'] for key in ('gui','cli')):
            return record['cli']
    from software_ops import ensure_filmcraft
    return ensure_filmcraft()['cli']

def call(cli,args,json_result=True):
    done=subprocess.run([cli,*map(str,args)],capture_output=True,encoding='utf-8',errors='replace')
    if done.returncode:raise RuntimeError(done.stderr[-5000:]+done.stdout[-2000:])
    return json.loads(done.stdout) if json_result and done.stdout.strip() else done.stdout

def doctor(args):
    cli=binary(args);version=call(cli,['--version'],False).strip()
    catalog=call(cli,['commands','--json'])
    required={'file.newProject','file.newSequence','file.import','timeline.place','sequence.inspect','file.exportMedia'}
    if not required.issubset({c['id'] for c in catalog}):raise ValueError('Required FilmCraft commands missing')
    print(version+'; approved-plan project adapter available')

def checks(sequence,segments):
    total=sum(s['frames'] for s in segments)
    if sequence['durationFrames']!=total:raise ValueError('FilmCraft sequence frame count mismatch')
    for kind in ['video','audio']:
        tracks=sequence[kind]
        if len(tracks)!=1:raise ValueError('Unexpected '+kind+' track count')
        clips=tracks[0]['items']
        if len(clips)!=len(segments):raise ValueError('Clip count mismatch: '+kind)
        offset=0
        for clip,seg in zip(clips,segments):
            if (clip['startFrame'],clip['durationFrames'],clip['item'])!=(offset,seg['frames'],seg['item']):raise ValueError('Clip order/timing mismatch: '+kind)
            if clip['sourceIn']!=0 or clip['speed']!=1 or clip['reverse'] or not clip['enabled']:raise ValueError('Unexpected source trim or playback transform')
            if clip['gainDb']!=0:raise ValueError('Original audio gain changed')
            offset+=seg['frames']
        if kind=='audio' and tracks[0]['muted']:raise ValueError('Original audio track muted')
    return total

def build(args):
    cli=binary(args);plan,planhash=r.read_plan(args.project);root=Path(args.project).resolve()
    statepath=state_dir(root)/'filmcraft.json';state=load_json(statepath) if statepath.exists() else {'videos':[]}
    for video in plan['videos']:
        vid=str(video['video_id'])
        if args.only and vid!=args.only:continue
        folder=project_path(root,'混剪/FilmCraft/'+vid);folder.mkdir(parents=True,exist_ok=True)
        q=folder/f'混剪_{vid}.fcproj'
        if q.exists():
            previous=next((x for x in state['videos'] if x['video_id']==vid),None)
            if not previous or previous['plan_sha256']!=planhash or sha256(q)!=previous['sha256']:
                raise ValueError('Existing FilmCraft project preserved; it differs from the approved plan: '+str(q))
            for media in previous['segments']:
                if sha256(project_path(root,media['path']))!=media['sha256']:raise ValueError('Existing FilmCraft media changed')
            checks(call(cli,['--project',q,'inspect','sequence']),previous['segments'])
            print('Reused verified FilmCraft project '+vid,flush=True)
            continue
        call(cli,['exec','file.newProject',json.dumps({'name':'混剪_'+vid},ensure_ascii=False),'--save-as',q])
        cfg=plan['config'];fps=r.output_fps(cfg)
        if cfg.get('preserve_original_audio',True) is not True:raise ValueError('FilmCraft adapter supports original audio only')
        call(cli,['--project',q,'--save','exec','file.newSequence',json.dumps({'name':'混剪_'+vid,'width':cfg.get('output_width',1280),'height':cfg.get('output_height',720),'fps':float(fps),'sampleRate':48000,'video':1,'audio':1})])
        rows=[];offset=0
        for i,seg in enumerate(video['segments']):
            spec=r.source_spec(root,seg,cfg)
            if not spec['has_audio']:raise ValueError('FilmCraft showcase adapter currently requires original audio')
            normalized=folder/f'compat_{i+1:02d}.mov'
            if normalized.exists():raise ValueError('Existing compatibility media preserved: '+str(normalized))
            graph=f"[0:v:0]{r.visual_filter(spec,cfg)}[v];[0:a:0]{r.audio_filter(spec)}[a]"
            run_ffmpeg(['-y','-i',spec['path'],'-filter_complex',graph,'-map','[v]','-map','[a]','-c:v','libx264','-profile:v','baseline','-crf','12','-preset','medium','-pix_fmt','yuv420p','-c:a','pcm_s16le','-ar','48000','-ac','2','-fps_mode','passthrough',normalized])
            info=r.metadata(normalized)
            if len(info[2])!=spec['target_frames']:raise ValueError('Compatibility frame count mismatch')
            imported=call(cli,['--project',q,'--save','import',normalized])
            if imported.get('errors') or len(imported['items'])!=1:raise ValueError('FilmCraft import failed')
            item=imported['items'][0];ticks=Fraction(spec['target_frames']*TICKS,1)/fps
            if ticks.denominator!=1:raise ValueError('FilmCraft ticks cannot exactly represent selected frame rate')
            call(cli,['--project',q,'--save','exec','timeline.place',json.dumps({'item':item,'track':'V1','audioTrack':'A1','frame':offset,'sourceIn':0,'duration':int(ticks),'insert':False,'video':True,'audio':True})])
            rows.append({'segment_id':seg['segment_id'],'source_sha256':seg['sha256'],'path':str(normalized.relative_to(root)),'sha256':sha256(normalized),'item':item,'start_frame':offset,'frames':spec['target_frames']})
            offset+=spec['target_frames'];print('FilmCraft placed '+seg['segment_id'],flush=True)
        sequence=call(cli,['--project',q,'inspect','sequence']);checks(sequence,rows)
        save_json(folder/'timeline-inspect.json',sequence)
        # Reject imported-but-unreadable media, which otherwise becomes a placeholder.
        for i,row in enumerate(rows):
            call(cli,['--project',q,'render','--seconds',float(Fraction(row['start_frame'],1)/fps),'--out',folder/f'preview_{i+1:02d}.png','--scale','0.5'],False)
        record={'video_id':vid,'plan_sha256':planhash,'path':str(q.relative_to(root)),'sha256':sha256(q),'cli_version':call(cli,['--version'],False).strip(),'segments':rows,'expected_frames':offset,'status':'project-checked; native export requires independent verification'}
        state['videos']=[x for x in state['videos'] if x['video_id']!=vid]+[record];save_json(statepath,state)
        print('Editable FilmCraft project: '+str(q),flush=True)

def export(args):
    cli=binary(args);root=Path(args.project).resolve();plan,planhash=r.read_plan(root)
    state=load_json(state_dir(root)/'filmcraft.json')
    for video in plan['videos']:
        vid=str(video['video_id'])
        if args.only and vid!=args.only:continue
        rec=next(x for x in state['videos'] if x['video_id']==vid);q=project_path(root,rec['path'])
        if rec['plan_sha256']!=planhash or sha256(q)!=rec['sha256']:raise ValueError('Plan or editable project changed; review before export')
        for seg in rec['segments']:
            if sha256(project_path(root,seg['path']))!=seg['sha256']:raise ValueError('Compatibility media changed')
        sequence=call(cli,['--project',q,'inspect','sequence']);checks(sequence,rec['segments'])
        output=q.parent/f'FilmCraft_混剪_{vid}.mp4'
        if output.exists():
            if not rec.get('native_passed') or rec.get('native_sha256')!=sha256(output):raise ValueError('Existing native export preserved; it is not verified: '+str(output))
            print('Reused native output '+vid,flush=True)
        else:call(cli,['--project',q,'export',output,'--format','h264','--gpu-rendering','off','--settings',json.dumps({'crf':plan['config'].get('crf',18),'hardwareEncoding':'off'})],False)
        with tempfile.TemporaryDirectory(dir=q.parent) as td:
            try:report=r.validate_video(root,video,plan['config'],output,Path(td))
            except (ValueError,RuntimeError) as error:report={'passed':False,'error':str(error)}
        save_json(q.parent/'native-validation.json',report)
        rec['native_output']=str(output.relative_to(root));rec['native_sha256']=sha256(output);rec['native_passed']=report['passed']
        save_json(state_dir(root)/'filmcraft.json',state)
        if not report['passed']:raise ValueError('FilmCraft native export failed independent validation; preserved for diagnosis, not registered as final delivery')
        print('PASS native FilmCraft export: '+str(output))
    # This is an alternate version of an existing plan, not an extra use.
    print('Original delivery and usage ledger preserved')

def deliver(args):
    root=Path(args.project).resolve();plan,ph=r.read_plan(root)
    native=load_json(state_dir(root)/'filmcraft.json');state=r.rendered_state(root)
    for video in r.selection(plan,args.only):
        vid=str(video['video_id']);rec=next(x for x in native['videos'] if x['video_id']==vid)
        if rec['plan_sha256']!=ph or not rec.get('native_passed'):raise ValueError('Native export not approved or verified')
        q=project_path(root,rec['path']);source=project_path(root,rec['native_output'])
        if sha256(q)!=rec['sha256'] or sha256(source)!=rec['native_sha256']:raise ValueError('Native project or output changed')
        for media in rec['segments']:
            if sha256(project_path(root,media['path']))!=media['sha256']:raise ValueError('Native compatibility media changed')
        with tempfile.TemporaryDirectory(dir=q.parent) as td:
            report=r.validate_video(root,video,plan['config'],source,Path(td))
        if not report['passed']:raise ValueError('Native delivery failed independent verification')
        previous=next((x for x in state['videos'] if x['video_id']==vid),None)
        if previous and previous.get('plan_sha256')==ph and previous.get('sha256')==rec['native_sha256'] and project_path(root,previous['path']).is_file() and sha256(project_path(root,previous['path']))==rec['native_sha256']:
            destination=project_path(root,previous['path'])
        else:destination=project_path(root,f'混剪/成品/混剪_{vid}.mp4')
        if destination.exists() and sha256(destination)!=rec['native_sha256']:
            destination=destination.with_name(f'FilmCraft_混剪_{vid}.mp4')
        if destination.exists() and sha256(destination)!=rec['native_sha256']:raise ValueError('Conflicting delivery preserved')
        destination.parent.mkdir(parents=True,exist_ok=True)
        if not destination.exists():shutil.copy2(source,destination)
        validation=state_dir(root)/'validation'/f'filmcraft-{vid}.json';save_json(validation,report)
        record={'video_id':vid,'path':destination.relative_to(root).as_posix(),'sha256':sha256(destination),'plan_sha256':ph,
                'segments':[x['segment_id'] for x in video['segments']],'validation_path':str(validation.relative_to(root)),
                'tail_trim_overrides':{},'passed':True,'engine':'FilmCraft','editable_project':rec['path']}
        old=next((x for x in state['videos'] if x['video_id']==vid),None)
        if old and old!=record:
            history=state_dir(root)/'delivery-history.json';records=load_json(history) if history.exists() else []
            records.append(old);save_json(history,records)
        state['videos']=[x for x in state['videos'] if x['video_id']!=vid]+[record]
        save_json(destination.with_suffix('.remix.json'),record)
        save_json(state_dir(root)/'rendered.json',state);r.update_usage(root,plan,state)
        print('Delivered verified native output: '+str(destination),flush=True)


def register(sub):
    for name,fn in [('filmcraft-doctor',doctor),('filmcraft-project',build),('filmcraft-export',export),('filmcraft-deliver',deliver)]:
        p=sub.add_parser(name);p.add_argument('--cli');p.set_defaults(func=fn)
        if name!='filmcraft-doctor':p.add_argument('--project',required=True);p.add_argument('--only')
