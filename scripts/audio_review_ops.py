"""Prepare post-export audio choices; optional PCM extraction for real listening."""
import argparse,math,array
from pathlib import Path
from common import load_json,save_json,state_dir,project_path,sha256,probe,run_ffmpeg

QUESTION='成片已完成。音频保持原样，还是去除BGM并保留环境音效、人物念白？也可以先分析音频组成，再选择处理方式。'
OPTIONS=['保持原声，不处理','去除BGM，尽量保留环境音效和人物念白','先分析音频组成，再给我处理建议']

def prepare(args):
    root=Path(args.project).resolve();rendered=load_json(state_dir(root)/'rendered.json')
    if args.only and not any(str(v['video_id'])==args.only for v in rendered['videos']):
        raise ValueError('Unknown final video ID: '+str(args.only))
    path=state_dir(root)/'audio-review.json';previous=load_json(path) if path.exists() else {'videos':[]};old={v['video_id']:v for v in previous['videos']}
    rows=[]
    for record in rendered['videos']:
        vid=str(record['video_id'])
        if args.only and vid!=args.only:continue
        media=project_path(root,record['path'])
        if not record.get('passed') or sha256(media)!=record['sha256']:raise ValueError('Review only an unchanged verified final video')
        prior=old.get(vid)
        row=prior if prior and prior['video_sha256']==record['sha256'] else {'video_id':vid,'video_sha256':record['sha256'],'status':'awaiting_user_audio_choice','composition':{'BGM':'not_semantically_reviewed','environment_and_effects':'not_semantically_reviewed','character_dialogue':'not_semantically_reviewed'}}
        row['video_path']=record['path'];info=probe(media)
        streams=[s for s in info['streams'] if s['codec_type']=='audio']
        row['audio_streams']=[{k:s.get(k) for k in ('index','codec_name','sample_rate','channels','channel_layout','duration')} for s in streams]
        row['separation_status']='no semantic stem separation performed'
        if args.extract and streams:
            folder=project_path(root,'音频复核')/(vid+'-'+record['sha256'][:12]);folder.mkdir(parents=True,exist_ok=True)
            wav=folder/'原始混合音轨.wav'
            if not wav.exists():run_ffmpeg(['-i',media,'-map','0:a:0','-vn','-c:a','pcm_s16le',wav])
            row['listening_audio']=str(wav.relative_to(root))
            pcm=array.array('f');pcm.frombytes(run_ffmpeg(['-i',media,'-map','0:a:0','-vn','-ar','16000','-ac','1','-c:a','pcm_f32le','-f','f32le','-']))
            windows=[]
            for start in range(0,len(pcm),16000):
                samples=pcm[start:start+16000]
                power=sum(x*x for x in samples)/len(samples);peak=max(abs(x) for x in samples)
                windows.append({'start_seconds':start/16000,'end_seconds':(start+len(samples))/16000,'rms_dbfs':10*math.log10(max(power,1e-12)),'peak_dbfs':20*math.log10(max(peak,1e-6))})
            save_json(folder/'技术音频时间表.json',{'windows':windows,'meaning':'Levels and timing only; not evidence of speech/music/effects identity'})
            row['technical_timeline']=str((folder/'技术音频时间表.json').relative_to(root))
        rows.append(row)
    selected={x['video_id'] for x in rows}
    result={'question':QUESTION,'options':OPTIONS,'original_audio_preserved':True,'videos':[v for v in previous['videos'] if v['video_id'] not in selected]+rows,
            'capability':'Metadata and optional decoded audio/timing extraction implemented. Semantic listening is agent work; BGM/dialogue/effects separation is not implemented by this command.'}
    save_json(path,result);print(QUESTION)
    print('Audio confirmation record: '+str(path))

def register(sub):
    p=sub.add_parser('audio-review');p.add_argument('--project',required=True);p.add_argument('--only');p.add_argument('--extract',action='store_true');p.set_defaults(func=prepare)
