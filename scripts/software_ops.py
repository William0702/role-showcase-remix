"""Detect FilmCraft, install official portable software when absent, self-test."""
import argparse,json,os,re,shutil,subprocess,tempfile,zipfile
from pathlib import Path
from common import ROOT,sha256,save_json,load_json,run_ffmpeg
VERSION='0.7.2'
ASSET='filmcraft-'+VERSION+'-windows-x64-portable.zip'
RELEASE='https://github.com/storytold/filmcraft/releases/download/v'+VERSION+'/'

def run(argv,timeout=90):
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    p=subprocess.run(list(map(str,argv)),capture_output=True,encoding='utf-8',errors='replace',timeout=timeout,creationflags=flags)
    if p.returncode:raise RuntimeError(p.stderr[-2500:]+p.stdout[-1500:])
    return p.stdout

def candidates():
    values=[]
    if os.environ.get('REMIX_FILMCRAFT_HOME'):values.append(Path(os.environ['REMIX_FILMCRAFT_HOME']))
    for var,tail in [('ProgramFiles','FilmCraft'),('ProgramFiles(x86)','FilmCraft'),('LOCALAPPDATA','Programs/FilmCraft'),('LOCALAPPDATA','ArtCraft/FilmCraft/'+VERSION)]:
        if os.environ.get(var):values.append(Path(os.environ[var])/tail)
    found=shutil.which('filmcraft.exe')
    if found:values.append(Path(found).parent)
    if os.name=='nt':
        # Return only FilmCraft paths, no unrelated application or account information.
        ps=r"$p = Get-Process filmcraft -ErrorAction SilentlyContinue; $p | ForEach-Object { $_.Path }; Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\App Paths\filmcraft.exe','HKLM:\Software\Microsoft\Windows\CurrentVersion\App Paths\filmcraft.exe' -ErrorAction SilentlyContinue | ForEach-Object { $_.'(default)' }"
        try:
            for line in run(['powershell.exe','-NoProfile','-Command',ps],15).splitlines():
                if line.strip().lower().endswith('filmcraft.exe'):values.append(Path(line.strip()).parent)
        except (RuntimeError,subprocess.TimeoutExpired):pass
    return list(dict.fromkeys(values))

def gui_version(app):
    if os.name!='nt':return run([app,'--version'],30).strip()
    # The official Windows GUI --version opens a modal message box. Read PE resources instead.
    import ctypes
    from ctypes import wintypes
    dll=ctypes.WinDLL('version',use_last_error=True)
    dll.GetFileVersionInfoSizeW.argtypes=[wintypes.LPCWSTR,ctypes.POINTER(wintypes.DWORD)]
    dll.GetFileVersionInfoSizeW.restype=wintypes.DWORD
    dll.GetFileVersionInfoW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p]
    dll.GetFileVersionInfoW.restype=wintypes.BOOL
    dll.VerQueryValueW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR,ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(wintypes.UINT)]
    dll.VerQueryValueW.restype=wintypes.BOOL
    unused=wintypes.DWORD();size=dll.GetFileVersionInfoSizeW(str(app),ctypes.byref(unused))
    if not size:raise ValueError('GUI version resource missing: '+str(app))
    data=ctypes.create_string_buffer(size)
    if not dll.GetFileVersionInfoW(str(app),0,size,data):raise OSError(ctypes.get_last_error(),'Read GUI version resource failed')
    pointer=ctypes.c_void_p();length=wintypes.UINT()
    if not dll.VerQueryValueW(data,chr(92),ctypes.byref(pointer),ctypes.byref(length)) or length.value<52:raise ValueError('Invalid GUI version resource')
    fields=ctypes.cast(pointer,ctypes.POINTER(wintypes.DWORD))
    if fields[0]!=0xFEEF04BD:raise ValueError('Invalid GUI version signature')
    ms,ls=fields[2],fields[3]
    return 'filmcraft '+'.'.join(map(str,(ms>>16,ms&65535,ls>>16)))

def pair(folder):
    app=folder/'filmcraft.exe';cli=folder/'filmcraft-cli.exe'
    if not app.is_file() or not cli.is_file():return None
    av=gui_version(app);cv=run([cli,'--version'],30).strip()
    a=re.search(r'(\d+)\.(\d+)\.(\d+)',av);c=re.search(r'(\d+)\.(\d+)\.(\d+)',cv)
    if not a or not c or a.groups()!=c.groups() or tuple(map(int,a.groups()))<(0,7,2):return None
    commands=json.loads(run([cli,'commands','--json'],30))
    if not {'file.newSequence','file.import','timeline.place','file.exportMedia'}.issubset({x['id'] for x in commands}):return None
    return {'gui':str(app.resolve()),'cli':str(cli.resolve()),'gui_version':av,'cli_version':cv,'gui_sha256':sha256(app),'cli_sha256':sha256(cli)}

def selftest(record):
    import render_ops as r
    cli=record['cli']
    with tempfile.TemporaryDirectory(prefix='filmcraft-selftest-') as td:
        root=Path(td);assert root.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve());src=root/'source.mov';q=root/'selftest.fcproj';out=root/'selftest.mp4'
        run_ffmpeg(['-y','-f','lavfi','-i','testsrc2=size=160x90:rate=30:duration=1','-f','lavfi','-i','sine=frequency=600:sample_rate=48000:duration=1','-c:v','libx264','-profile:v','baseline','-crf','12','-pix_fmt','yuv420p','-c:a','pcm_s16le','-ar','48000','-ac','2',src])
        run([cli,'exec','file.newSequence','name=selftest','width=160','height=90','fps=30','video=1','audio=1','--save-as',q])
        imported=json.loads(run([cli,'--project',q,'--save','import',src]));assert not imported.get('errors')
        item=imported['items'][0]
        run([cli,'--project',q,'--save','exec','timeline.place',f'item={item}','track=V1','audioTrack=A1','frame=0','duration=254016000000','insert=false'])
        run([cli,'--project',q,'export',out,'--format','h264','--gpu-rendering','off','--settings','{"crf":18,"hardwareEncoding":"off"}'])
        segment={'path':'source.mov','sha256':sha256(src),'frames':30,'segment_id':'selftest'}
        with tempfile.TemporaryDirectory(dir=root) as vd:
            report=r.validate_video(root,{'video_id':'selftest','segments':[segment]},{'output_width':160,'output_height':90,'output_fps':'30/1'},out,Path(vd))
        if not report['passed']:raise RuntimeError('FilmCraft native audio/video self-test failed')
        return {'passed':True,'frames':report['actual_frames'],'operations':['GUI and CLI version','command catalog','create project','import','linked audio/video timeline','native H264/AAC export','independent all-frame and original audio validation']}

def download(url,destination):
    if not url.startswith(RELEASE):raise ValueError('Only the pinned official FilmCraft release is allowed')
    destination.parent.mkdir(parents=True,exist_ok=True)
    run(['curl.exe','--fail','--silent','--show-error','--location','--retry','1','--max-time','120',url,'--output',destination],250)

def checksum(text):
    for line in text.splitlines():
        m=re.match(r'^([0-9a-fA-F]{64})\s+\*?(.+)$',line.strip())
        if m and m.group(2)==ASSET:return m.group(1).lower()
    raise ValueError('Official release checksum for portable package missing')

def software_archive(root):
    root=Path(root).resolve();meta=load_json(root/'tools/software/filmcraft-release.json')
    expected=meta['archive_sha256'];archive=root/'tools/software'/ASSET
    if not archive.is_file():
        cache=Path(tempfile.gettempdir())/'role-showcase-remix-software';archive=cache/ASSET
        if not archive.is_file() or sha256(archive)!=expected:
            sums=cache/'FilmCraft-SHA256SUMS.txt';download(RELEASE+'SHA256SUMS.txt',sums)
            if checksum(sums.read_text(encoding='utf-8'))!=expected:raise ValueError('Official checksum changed from pinned package')
            download(RELEASE+ASSET,archive)
    if sha256(archive)!=expected:raise ValueError('FilmCraft archive checksum mismatch')
    return archive,expected


def ensure_filmcraft(root=ROOT,search=None,target_dir=None,write_state=True):
    root=Path(root).resolve();errors=[];record=None
    for folder in candidates() if search is None else search:
        try:
            candidate=pair(Path(folder))
            if candidate:
                candidate['selftest']=selftest(candidate);candidate['origin']='existing-local';record=candidate;break
        except (OSError,RuntimeError,ValueError,AssertionError,subprocess.TimeoutExpired) as error:errors.append({'path':str(folder),'error':str(error)[-1200:]})
    if not record:
        archive,expected=software_archive(root)
        target=Path(target_dir) if target_dir else Path(os.environ.get('LOCALAPPDATA') or (Path.home()/'AppData/Local'))/'ArtCraft/FilmCraft'/VERSION
        target=target.expanduser().absolute()
        if target.exists():
            record=pair(target)
            if not record:raise ValueError('Existing software directory preserved; it is incomplete: '+str(target))
            record['selftest']=selftest(record);record['origin']='existing-managed-portable'
        else:
            # Stage and validate before promoting the portable install. No system MSI or admin requirement.
            target.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.TemporaryDirectory(dir=target.parent,prefix='filmcraft-stage-') as td:
                stage=Path(td);assert stage.resolve().is_relative_to(target.parent.resolve())
                with zipfile.ZipFile(archive) as package:
                    if package.testzip() is not None:raise ValueError('Damaged FilmCraft archive')
                    for item in package.infolist():
                        final=(stage/item.filename).resolve()
                        if not final.is_relative_to(stage.resolve()) or ((item.external_attr>>16)&0o170000)==0o120000:raise ValueError('Invalid archive path')
                    package.extractall(stage)
                apps=list(stage.rglob('filmcraft.exe'))
                if len(apps)!=1:raise ValueError('Portable software package has ambiguous GUI location')
                software=apps[0].parent;candidate=pair(software)
                if not candidate:raise ValueError('Portable software is missing a compatible GUI/CLI pair')
                tested=selftest(candidate)
                shutil.copytree(software,target)
            record=pair(target);record['selftest']=tested;record['origin']='official-bundled-portable' if archive.is_relative_to(root) else 'official-downloaded-portable'
        record['archive_sha256']=expected
    record['detection_errors']=errors
    if write_state:save_json(root/'.software/filmcraft.json',record)
    print('FilmCraft ready: '+record['gui']+'; native self-test passed',flush=True)
    return record

def setup(args):
    ensure_filmcraft(target_dir=Path(args.software_dir) if args.software_dir else None)

def register(sub):
    p=sub.add_parser('software-setup');p.add_argument('--software-dir');p.set_defaults(func=setup)
