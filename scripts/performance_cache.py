"""Project-local, content-bound caches. Never replace human semantic review."""
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from common import ROOT, sha256, ffmpeg, ffprobe, load_json

SCHEMA = 1


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def enabled():
    return os.environ.get('REMIX_DISABLE_CACHE', '').lower() not in ('1', 'true', 'yes')


def implementation(kind):
    """Hash executable bytes, not just a version label or file timestamp."""
    names = ('performance_cache.py', 'common.py', 'render_ops.py')
    if kind == 'validation':
        names += ('filmcraft_ops.py',)
    files = {name: sha256(ROOT/'scripts'/name) for name in names}
    tools = {'ffprobe': sha256(ffprobe())}
    if kind == 'validation':
        tools['ffmpeg'] = sha256(ffmpeg())
    manifest = ROOT/'package-manifest.json'
    version = load_json(manifest).get('version') if manifest.exists() else None
    return dict(schema=SCHEMA, code=files, tools=tools,
                package_version=version, python=list(sys.version_info[:3]))


def _path(project, kind, binding):
    return Path(project).resolve()/'.remix'/'cache'/kind/(digest(binding)+'.json')


def _event(project, kind, status, key):
    try:
        path = Path(project).resolve()/'.remix'/'cache'/'events.jsonl'
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(),
                kind=kind, status=status, key=key))+'\n')
    except OSError:
        pass  # A cache or its observability must not be required for production.


def _read(path, kind, binding):
    try:
        record = load_json(path)
        if (record.get('schema') != SCHEMA or record.get('kind') != kind or
                record.get('binding') != binding or
                record.get('payload_sha256') != digest(record['payload'])):
            return None
        return record['payload']
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return None


def _write(path, kind, binding, payload):
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        record = dict(schema=SCHEMA, kind=kind, binding=binding, payload=payload,
                      payload_sha256=digest(payload))
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                dir=path.parent, prefix=path.name+'.', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(record, stream, ensure_ascii=False, allow_nan=False)
        os.replace(temporary, path)
    except OSError:
        pass
    finally:
        if temporary is not None and temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                pass


def metadata(project, path, compute):
    path = Path(path)
    if project is None or not enabled():
        return compute()
    binding = dict(file_sha256=sha256(path), implementation=implementation('metadata'))
    cache = _path(project, 'metadata', binding)
    payload = _read(cache, 'metadata', binding)
    if payload is not None:
        # Format filename is contextual; identical bytes may be at a new path.
        if 'format' in payload:
            payload['format']['filename'] = str(path)
        _event(project, 'metadata', 'hit', cache.stem)
        return payload
    payload = compute()
    if sha256(path) != binding['file_sha256']:
        raise ValueError('Media changed during metadata probe: '+str(path))
    _write(cache, 'metadata', binding, payload)
    _event(project, 'metadata', 'miss', cache.stem)
    return payload


def revoke_validation(project, output_sha256):
    """Revoke all evidence for this output before any forced validation path."""
    folder = Path(project).resolve()/'.remix'/'cache'/'validation'
    for path in folder.glob('*.json'):
        try:
            record = load_json(path)
            revoke = record.get('binding', {}).get('output_sha256') == output_sha256
        except (ValueError, TypeError, KeyError, AttributeError):
            revoke = True  # Malformed evidence must never survive a forced recheck.
        except OSError as error:
            raise ValueError('Cannot inspect previous validation evidence') from error
        if revoke:
            try:
                path.unlink(missing_ok=True)
            except OSError as error:
                raise ValueError('Cannot revoke previous validation evidence for forced recheck') from error


def validated_report(project, binding_factory, compute, force=False):
    """Only a successful full check can seed reusable technical evidence."""
    forced_binding = None
    if force:
        forced_binding = json.loads(canonical(binding_factory()))
        revoke_validation(project, forced_binding['output_sha256'])
    if not enabled():
        return compute()
    # Freeze a snapshot: callers may hold mutable config/context dictionaries.
    binding = forced_binding if force else json.loads(canonical(binding_factory()))
    cache = _path(project, 'validation', binding)
    if force:
        # A failed/exceptional explicit recheck must never resurrect an old PASS.
        try:
            cache.unlink(missing_ok=True)
        except OSError as error:
            raise ValueError('Cannot revoke previous validation evidence for forced recheck') from error
    report = None if force else _read(cache, 'validation', binding)
    if (isinstance(report, dict) and report.get('passed') is True and
            report.get('video_id') == binding['video']['video_id'] and
            report.get('actual_frames') == report.get('expected_frames') and
            isinstance(report.get('actual_frames'), int) and
            report['actual_frames'] > 0 and
            isinstance(report.get('segments'), list) and report['segments'] and
            all(segment.get('passed') is True for segment in report['segments'])):
        _event(project, 'validation', 'hit', cache.stem)
        return dict(report, validation_cache=dict(status='hit', key=cache.stem,
                    binding=binding, technical_evidence_only=True))
    report = compute()
    if report.get('passed') is True:
        if binding_factory() != binding:
            raise ValueError('Validation inputs changed during full verification')
        _write(cache, 'validation', binding, report)
    status = 'forced' if force else 'miss'
    _event(project, 'validation', status, cache.stem)
    return dict(report, validation_cache=dict(status=status, key=cache.stem,
                binding=binding, technical_evidence_only=True))
