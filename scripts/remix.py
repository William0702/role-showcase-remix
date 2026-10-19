"""Offline entry point. Invoke with the Python runtime shipped in this package."""
import argparse, platform, subprocess, sys
from pathlib import Path
from common import ROOT, ffmpeg, ffprobe, approve, save_json, state_dir, sha256, load_json
import asset_ops, planner_ops, render_ops, filmcraft_ops, automation_ops, software_ops, audio_review_ops

def initialize(args):
    root=Path(args.project).resolve(); root.mkdir(parents=True,exist_ok=True)
    (root/'母片').mkdir(exist_ok=True)
    path=state_dir(root)/'batch.json'
    if path.exists(): raise ValueError('Existing configuration preserved: '+str(path))
    save_json(path,{'segments_per_video':3,'max_uses':3,'exact_uses':False,
      'target_count':None,'unique_sets':True,'unique_pairs':False,
      'distinct_sources':False,'balance_positions':False,'fixed_videos':[],
      'seed':0,'output_width':1280,'output_height':720,'output_fps':'30/1',
      'crf':18,'preset':'medium','audio_bitrate':'192k','allow_missing_audio':False})
    print(path)

def doctor(args):
    import numpy, PIL
    if args.full:
        manifest=ROOT/'package-manifest.json'
        if not manifest.exists(): raise ValueError('Package checksum manifest missing')
        for item in load_json(manifest)['files']:
            path=(ROOT/item['path']).resolve()
            if not path.is_relative_to(ROOT) or not path.is_file() or sha256(path)!=item['sha256']:
                raise ValueError('Package file missing or changed: '+item['path'])
    print('Python',sys.version.split()[0],platform.machine(),'NumPy',numpy.__version__,'Pillow',PIL.__version__)
    for binary in (ffmpeg(),ffprobe()):
        result=subprocess.run([binary,'-version'],capture_output=True,text=True,check=True)
        print(result.stdout.splitlines()[0])
    print('PASS: runtime available'+('; package hashes verified' if args.full else ''))

def startup(args):
    print((ROOT/'references/startup-guide.md').read_text(encoding='utf-8').replace('{SKILL_DIR}',str(ROOT)))


def record_approval(args):
    approve(args.project,args.stage,args.artifact,args.human_text)
    print('Recorded approval of current artifact hash')

def main():
    for output in (sys.stdout,sys.stderr):
        if hasattr(output,'reconfigure'): output.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description='角色展示逐帧切分与批量混剪 — Windows x64 offline skill')
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('doctor');p.add_argument('--full',action='store_true');p.set_defaults(func=doctor)
    p=sub.add_parser('start',help='Show first-use path and material setup steps');p.set_defaults(func=startup)
    p=sub.add_parser('init');p.add_argument('--project',required=True);p.set_defaults(func=initialize)
    p=sub.add_parser('approve',help='Only record an actual direct human authorization')
    p.add_argument('--project',required=True);p.add_argument('--stage',required=True,choices=['cut','render','rename','revise'])
    p.add_argument('--artifact',required=True);p.add_argument('--human-text',required=True);p.set_defaults(func=record_approval)
    for module in (asset_ops,planner_ops,render_ops,filmcraft_ops,automation_ops,software_ops,audio_review_ops): module.register(sub)
    args=parser.parse_args()
    try: args.func(args)
    except (ValueError,RuntimeError,FileNotFoundError,KeyError) as error:
        parser.exit(2,'ERROR: '+str(error)+'\n')

if __name__=='__main__': main()
