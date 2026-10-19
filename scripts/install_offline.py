"""Install the complete offline skill, then show first-use instructions."""
import argparse, hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path

def main():
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'): stream.reconfigure(encoding='utf-8')
    source=Path(__file__).resolve().parent.parent
    default=Path(os.environ.get('CODEX_HOME') or (Path.home()/'.codex'))/'skills'/'role-showcase-remix'
    parser=argparse.ArgumentParser(description='Install offline skill and display startup guide')
    parser.add_argument('--dest',type=Path,default=default)
    parser.add_argument('--upgrade',action='store_true',help='Backup and update an unmodified installed skill')
    args=parser.parse_args();destination=args.dest.expanduser().absolute()
    if destination.is_symlink():parser.exit(2,'Symlink destination preserved\n')
    if destination.exists() and not args.upgrade:
        parser.exit(2,'Existing destination preserved; use --upgrade for a verified backed-up update: '+str(destination)+'\n')
    if destination.resolve()==source:parser.exit(2,'Source and installation directory must differ\n')
    if destination.exists():
        previous=destination/'package-manifest.json'
        if not previous.is_file():parser.exit(2,'Unknown existing directory preserved\n')
        for item in json.loads(previous.read_text(encoding='utf-8'))['files']:
            file=(destination/item['path']).resolve()
            if not file.is_relative_to(destination.resolve()) or not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest()!=item['sha256']:
                parser.exit(2,'Modified existing skill preserved: '+item['path']+'\n')
    manifest=json.loads((source/'package-manifest.json').read_text(encoding='utf-8'))
    entries=[]
    for item in manifest['files']:
        relative=Path(item['path']);file=(source/relative).resolve()
        from software_ops import ASSET,software_archive
        if item['path']=='tools/software/'+ASSET and not file.is_file():
            archive,expected=software_archive(source)
            file.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(archive,file)
        if relative.is_absolute() or not file.is_relative_to(source) or not file.is_file():
            parser.exit(2,'Invalid or missing package file: '+item['path']+'\n')
        if hashlib.sha256(file.read_bytes()).hexdigest()!=item['sha256']:
            parser.exit(2,'Package hash mismatch: '+item['path']+'\n')
        entries.append((file,relative))
    # Detect/install the GUI + CLI pair and complete native self-test BEFORE skill installation.
    from software_ops import ensure_filmcraft
    software=ensure_filmcraft(source,write_state=False)
    if destination.exists():
        backup=destination.parent.parent/'skill-backups'/(destination.name+'-'+str(time.time_ns()))
        backup.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(destination,backup,symlinks=True)
        print('旧技能已备份：'+str(backup),flush=True)
    else:destination.mkdir(parents=True,exist_ok=False)
    for file,relative in entries:
        target=destination/relative
        if not target.resolve().is_relative_to(destination.resolve()):parser.exit(2,'Installation path escapes destination\n')
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest()==hashlib.sha256(file.read_bytes()).hexdigest():continue
        try:shutil.copy2(file,target)
        except OSError as error:
            parser.exit(2,'Installation file unavailable; backup preserved: '+str(target)+'; '+str(error)+'\n')
    shutil.copy2(source/'package-manifest.json',destination/'package-manifest.json')
    check=subprocess.run([str(destination/'tools/windows-x64/python/python.exe'),str(destination/'scripts/remix.py'),'doctor','--full'],capture_output=True,encoding='utf-8',errors='replace')
    if check.returncode:
        parser.exit(2,'Installation runtime check failed; files preserved at '+str(destination)+'\n'+check.stdout+check.stderr)
    from common import save_json
    save_json(destination/'.software/filmcraft.json',software)
    print('技能安装成功：'+str(destination))
    print('安装在agent支持的技能目录后，下一轮对话可使用 $role-showcase-remix。')
    print('指定其他目录时，可将这里的SKILL.md完整路径交给执行agent。')
    print((destination/'references/startup-guide.md').read_text(encoding='utf-8').replace('{SKILL_DIR}',str(destination)))
    return 0

if __name__=='__main__':sys.exit(main())
