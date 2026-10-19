"""Source inventory, exhaustive visual review aids, and approved exact-frame cutting."""
import argparse, json, math, os, re, subprocess, tempfile
from pathlib import Path
from fractions import Fraction
from common import (sha256,load_json,save_json,project_path,state_dir,ffmpeg,ffprobe,
                    run_ffmpeg,probe,frame_hashes,require_approval)

EXTENSIONS={'.mp4','.mov','.mkv','.avi','.webm','.m4v','.mts','.m2ts'}

def safe_name(s):
    s=re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_',str(s)).strip(' .')
    if not s: s='unnamed'
    if s.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:s='_'+s
    return s[:160]

def metadata(path):
    cmd=[ffprobe(),'-v','error','-select_streams','v:0','-count_frames','-show_frames','-show_streams','-show_entries','stream=width,height,avg_frame_rate,r_frame_rate,nb_read_frames,time_base:frame=best_effort_timestamp_time,pkt_duration_time,duration_time','-of','json',str(path)]
    p=subprocess.run(cmd,capture_output=True)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace'))
    d=json.loads(p.stdout);v=d['streams'][0];frames=d.get('frames',[])
    pts=[float(f['best_effort_timestamp_time']) for f in frames]
    if not pts or any(b<=a for a,b in zip(pts,pts[1:])):raise ValueError('Missing or nonmonotonic video timestamps: '+str(path))
    rate=v.get('avg_frame_rate','0/0')
    if rate=='0/0':rate=v.get('r_frame_rate','0/0')
    nominal=1/float(Fraction(rate)) if rate!='0/0' else 0
    last=frames[-1];tail=float(last.get('duration_time',last.get('pkt_duration_time',0)) or 0)
    if tail<=0:tail=(pts[-1]-pts[-2]) if len(pts)>1 else nominal
    if tail<=0:raise ValueError('Cannot determine final frame duration')
    full=probe(path);audio=any(s['codec_type']=='audio' for s in full['streams'])
    delta=[b-a for a,b in zip(pts,pts[1:])]
    return {'fps':rate,'frame_count':len(pts),'width':v['width'],'height':v['height'],
            'audio':audio,'variable_frame_rate':bool(delta and max(delta)-min(delta)>0.00001),
            'duration_seconds':pts[-1]+tail-pts[0],'frame_pts_seconds':pts,'end_pts_seconds':pts[-1]+tail}

def inventory(args):
    root=Path(args.project).resolve();source=project_path(root,args.source)
    if not source.is_dir():raise ValueError('Source folder does not exist: '+str(source))
    assets=[];seen={};display_ids={};duplicates=[];discovered_count=0
    for path in sorted(source.rglob('*')):
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS:continue
        path=project_path(root,path.relative_to(root));h=sha256(path)
        discovered_count+=1
        if h in seen:
            duplicates.append({'path':path.relative_to(root).as_posix(),'sha256':h,'asset_id':h[:16],'canonical_path':seen[h]})
            continue
        tokens=path.stem.split('-');display=tokens[0]
        if display.casefold() in display_ids:raise ValueError('Different unique assets share display_id '+display+'; rename source ID to prevent shared cut folders: '+display_ids[display.casefold()]+' / '+str(path))
        seen[h]=path.relative_to(root).as_posix();display_ids[display.casefold()]=str(path)
        assets.append({'asset_id':h[:16],'display_id':tokens[0],'path':path.relative_to(root).as_posix(),
                       'sha256':h,'author':tokens[-2] if len(tokens)>2 else None,**metadata(path)})
    manifest=state_dir(root)/'assets.json'
    if manifest.exists():
        save_json(state_dir(root)/'manifest-history'/(sha256(manifest)+'.json'),load_json(manifest))
    save_json(manifest,{'assets':assets,'discovered_count':discovered_count,'unique_count':len(assets),'duplicates':duplicates})
    save_json(state_dir(root)/'manifest-history'/(sha256(manifest)+'.json'),load_json(manifest))
    print(json.dumps({'assets':len(assets),'manifest':str(state_dir(root)/'assets.json')},ensure_ascii=False))

def get_asset(project,ident):
    matches=[a for a in load_json(state_dir(project)/'assets.json')['assets'] if ident in (a['asset_id'],a['display_id'])]
    if len(matches)!=1:raise ValueError('Asset ID must resolve uniquely: '+ident)
    a=matches[0];p=project_path(project,a['path'])
    if sha256(p)!=a['sha256']:raise ValueError('Source changed; reinventory and review: '+a['path'])
    return a,p

def review(args):
    from PIL import Image,ImageDraw
    a,path=get_asset(args.project,args.asset)
    if args.width<64 or args.page_size<1 or args.page_size>200:raise ValueError('width >=64; page-size 1..200')
    out=project_path(args.project,'拉片审阅')/(safe_name(a['display_id'])+'-'+a['asset_id']);out.mkdir(parents=True,exist_ok=True)
    w=args.width;h=max(1,round(a['height']*w/a['width']));size=w*h*3
    cmd=[ffmpeg(),'-hide_banner','-v','error','-i',str(path),'-map','0:v:0','-vf',f'scale={w}:{h}', '-fps_mode','passthrough','-pix_fmt','rgb24','-f','rawvideo','-']
    count=0;sheets=[];cols=min(5,args.page_size);rows=math.ceil(args.page_size/cols);sheet=None
    with tempfile.TemporaryFile() as err:
        proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=err)
        try:
            while True:
                raw=bytearray()
                while len(raw)<size:
                    part=proc.stdout.read(size-len(raw))
                    if not part:break
                    raw.extend(part)
                if not raw:break
                if len(raw)!=size:raise RuntimeError('Partial decoded frame')
                offset=count%args.page_size
                if offset==0:sheet=Image.new('RGB',(cols*w,rows*(h+28)), '#222222')
                x=(offset%cols)*w;y=(offset//cols)*(h+28)
                sheet.paste(Image.frombytes('RGB',(w,h),bytes(raw)),(x,y))
                ImageDraw.Draw(sheet).text((x+3,y+h+3),f"frame {count} | {a['frame_pts_seconds'][count]:.6f}s",fill='white')
                count+=1
                if count%args.page_size==0:
                    name=f'page_{len(sheets)+1:04d}.jpg';sheet.save(out/name,quality=94);sheets.append(name);sheet=None
            if proc.wait()!=0:
                err.seek(0);raise RuntimeError(err.read().decode(errors='replace'))
        finally:
            if proc.poll() is None:proc.kill();proc.wait()
    if sheet is not None:
        name=f'page_{len(sheets)+1:04d}.jpg';sheet.save(out/name,quality=94);sheets.append(name)
    if count!=a['frame_count']:raise RuntimeError('Review frame count mismatch')
    for boundary in args.boundary or []:
        for n in range(max(0,boundary-2),min(count,boundary+3)):
            run_ffmpeg(['-i',path,'-vf',f'select=eq(n\\,{n})','-frames:v','1','-y',out/f'boundary_{n:06d}.png'])
    save_json(out/'review.json',{'asset_id':a['asset_id'],'source_sha256':a['sha256'],'frames':count,'pages':sheets,'status':'requires_agent_visual_review_of_every_page','note':'All frame indices are zero-based. Tool does not identify characters.'})
    print(str(out))

def waveform(path,start=None,end=None):
    args=['-copyts','-i',path,'-map','0:a:0']
    if start is not None:args+=['-af',f'atrim=start={start:.9f}:end={end:.9f},asetpts=PTS-STARTPTS']
    return run_ffmpeg(args+['-ac','1','-ar','16000','-f','f32le','-'])

def audio_check(source,output,start,end):
    import numpy as np
    x=np.frombuffer(waveform(source,start,end),dtype='<f4');y=np.frombuffer(waveform(output),dtype='<f4')
    # AAC encoder padding may differ; compare centered common decoded samples.
    if not len(x) or not len(y):raise ValueError('Empty audio')
    if abs(len(x)-len(y))>2048:raise ValueError('Audio duration differs by more than codec padding')
    n=min(len(x),len(y));x=x[:n];y=y[:n];rms=float(np.sqrt(np.mean(x*x)))
    error=float(np.sqrt(np.mean((x-y)**2)))
    corr=float(np.corrcoef(x,y)[0,1]) if rms>0.0001 and np.std(y)>0.00001 else None
    if corr is not None and (not math.isfinite(corr) or corr<0.95):raise ValueError(f'Audio correlation failed: {corr}')
    if corr is None and error>max(0.0005,rms*0.3):raise ValueError('Silent audio RMS difference failed')
    return {'correlation':corr,'rms_difference':error,'samples_source':len(x),'samples_output':len(y)}

def cut(args):
    root=Path(args.project).resolve();spec=project_path(root,args.segments);require_approval(root,'cut',spec)
    doc=load_json(spec);segments=doc['segments'];assets=load_json(state_dir(root)/'assets.json')['assets'];amap={a['asset_id']:a for a in assets}
    version=doc.get('source_manifest_sha256')
    if not version:raise ValueError('segments.json requires source_manifest_sha256')
    history=state_dir(root)/'manifest-history'/(version+'.json')
    if version==sha256(state_dir(root)/'assets.json'):original=amap
    elif history.exists():original={a['asset_id']:a for a in load_json(history)['assets']}
    else:raise ValueError('Unknown source manifest version; inventory and review again')
    for s in segments:
        if s['asset_id'] not in amap or original.get(s['asset_id'])!=amap[s['asset_id']]:raise ValueError('Reviewed source metadata changed; review and approve again')
    if len({s['segment_id'] for s in segments})!=len(segments):raise ValueError('Duplicate segment ID')
    for aid in {s['asset_id'] for s in segments}:
        a=amap[aid];get_asset(root,aid);ranges=sorted((s['start_frame'],s['end_frame_exclusive']) for s in segments if s['asset_id']==aid)
        if any(not isinstance(x,int) or not isinstance(y,int) or not 0<=x<y<=a['frame_count'] for x,y in ranges):raise ValueError('Invalid frame range')
        if any(y>u for (x,y),(u,v) in zip(ranges,ranges[1:])):raise ValueError('Overlapping role ranges')
    if any(s.get('exclusions') for s in segments):raise ValueError('Internal exclusions require separate accepted continuous segments; remove exclusions and resubmit approved ranges.')
    record_path=state_dir(root)/'segments-cut.json';previous=load_json(record_path).get('segments',[]) if record_path.exists() else []
    current={s['segment_id']:s for s in segments}
    for old in previous:
        fresh=current.get(old['segment_id'])
        if fresh is None or any(old.get(k)!=fresh.get(k) for k in ('asset_id','role','start_frame','end_frame_exclusive','display_id','exclusions')):
            raise ValueError('Existing cut pool differs from current approved segment specification; preserve this version and create a new project/version for removed or changed roles.')
    results={s['segment_id']:s for s in previous};selected=[s for s in segments if not args.only or args.only in (s['asset_id'],s['segment_id'],amap[s['asset_id']]['display_id'])]
    if not selected:raise ValueError('No selected segments')
    for s in selected:
        a,source=get_asset(root,s['asset_id']);first=s['start_frame'];last=s['end_frame_exclusive'];pts=a['frame_pts_seconds'];start=pts[first];end=pts[last] if last<len(pts) else a['end_pts_seconds']
        old=results.get(s['segment_id']);keys=('asset_id','role','start_frame','end_frame_exclusive')
        if old and all(old.get(k)==s.get(k) for k in keys) and old.get('source_sha256')==a['sha256']:
            existing=project_path(root,old['path'])
            if existing.exists() and sha256(existing)==old['sha256']:continue
        folder=project_path(root,'切分')/safe_name(a['display_id']);folder.mkdir(parents=True,exist_ok=True)
        ordinal=sorted([q for q in segments if q['asset_id']==s['asset_id']],key=lambda q:q['start_frame']).index(s)+1
        target=folder/f"{ordinal:02d}_{safe_name(s['role'])}.mp4"
        if target.exists():raise ValueError('Existing output differs or untracked; preserve it and choose a new project/output: '+str(target))
        temp=folder/(target.stem+'.pending.mp4')
        vf=f'trim=start_frame={first}:end_frame={last},setpts=PTS-STARTPTS'
        command=['-copyts','-i',source,'-map','0:v:0','-vf',vf,'-fps_mode','passthrough','-c:v','libx264','-preset','veryfast','-crf','0']
        if a['audio']:command+=['-map','0:a:0','-af',f'atrim=start={start:.9f}:end={end:.9f},asetpts=PTS-STARTPTS','-c:a','aac','-b:a','192k']
        else:command+=['-an']
        try:
            run_ffmpeg(command+['-movflags','+faststart','-y',temp])
            expected=frame_hashes(source,vf);actual=frame_hashes(temp)
            if len(expected)!=last-first or expected!=actual:raise ValueError('Decoded pixel/frame count verification failed')
            check=audio_check(source,temp,start,end) if a['audio'] else None
            meta=metadata(temp)
            run_ffmpeg(['-i',temp,'-vf','select=eq(n\\,0)','-frames:v','1','-y',folder/(target.stem+'_first.png')])
            run_ffmpeg(['-i',temp,'-vf',f'select=eq(n\\,{last-first-1})','-frames:v','1','-y',folder/(target.stem+'_last.png')])
            os.replace(temp,target)
            results[s['segment_id']]={**s,'path':target.relative_to(root).as_posix(),'sha256':sha256(target),'source_sha256':a['sha256'],'fps':meta['fps'],'frames':last-first,'width':meta['width'],'height':meta['height'],'audio':a['audio'],'duration_seconds':meta['duration_seconds'],'source_start_seconds':start,'source_end_seconds':end,'audio_verification':check,'pixel_verification':'exact_decoded_frame_md5'}
            save_json(record_path,{'segments':list(results.values())})
        finally:
            if temp.exists():temp.unlink()
    print(str(record_path))

def register(subparsers):
    p=subparsers.add_parser('inventory',help='Inventory video sources with exact decoded frame timestamps');p.add_argument('--project',required=True);p.add_argument('--source',default='母片');p.set_defaults(func=inventory)
    p=subparsers.add_parser('review',help='Generate contact sheets containing EVERY source frame');p.add_argument('--project',required=True);p.add_argument('--asset',required=True);p.add_argument('--page-size',type=int,default=80);p.add_argument('--width',type=int,default=240);p.add_argument('--boundary',type=int,nargs='*');p.set_defaults(func=review)
    p=subparsers.add_parser('cut',help='Cut human-approved role ranges with exact decoded verification');p.add_argument('--project',required=True);p.add_argument('--segments',default='.remix/segments.json');p.add_argument('--only');p.set_defaults(func=cut)
