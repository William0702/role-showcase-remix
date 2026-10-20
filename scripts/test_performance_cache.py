"""Behavioral regression checks for project-local technical evidence reuse.

Run with the bundled Python. Set REMIX_CACHE_TEST_WORK to retain the real
cross-process FFmpeg evidence in a chosen scratch directory.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
import filmcraft_ops as filmcraft
import performance_cache as cache
import render_ops as render


def scratch_temporary(prefix):
    root = Path(os.environ.get('REMIX_CACHE_TEST_SCRATCH', Path.cwd()/'work/cache-tests-scratch'))
    root.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(prefix=prefix, dir=root)


def successful_report(video):
    return {'video_id': video['video_id'], 'passed': True,
            'actual_frames': 8, 'expected_frames': 8,
            'segments': [{'segment_id': s['segment_id'], 'passed': True}
                         for s in video['segments']]}


class CacheBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = scratch_temporary('cache-unit-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root/'source.bin'
        self.source.write_bytes(b'original source bytes')
        self.output = self.root/'output.bin'
        self.output.write_bytes(b'original output bytes')
        self.segment = {'segment_id': 's1', 'path': 'source.bin',
                        'sha256': common.sha256(self.source), 'frames': 8}
        self.video = {'video_id': '01', 'segments': [self.segment]}
        self.config = {'output_fps': '30/1', 'verify_mean_ssim': .98,
                       'verify_boundary_ssim': .95, 'verify_audio_correlation': .98}
        self.context = {'sequence': {'clips': ['s1']}}
        self.compute = self.enterContext(patch.object(render, 'validate_video',
            side_effect=lambda *a, **k: successful_report(a[1])))
        self.enterContext(patch.object(cache, 'implementation',
            return_value={'code': 'code-v1', 'tools': 'tools-v1'}))
        self.enterContext(patch.dict(os.environ, {'REMIX_DISABLE_CACHE': ''}))

    def check(self, **kwargs):
        return render.validate_video_cached(self.root, self.video, self.config,
            self.output, self.root, context=self.context, **kwargs)

    def seed(self):
        self.assertEqual(self.check()['validation_cache']['status'], 'miss')
        self.assertEqual(self.check()['validation_cache']['status'], 'hit')
        self.assertEqual(self.compute.call_count, 1)

    def assert_recomputed(self, **kwargs):
        self.assertEqual(self.check(**kwargs)['validation_cache']['status'], 'miss')
        self.assertEqual(self.compute.call_count, 2)

    def test_identical_inputs_reuse_full_verification(self):
        self.seed()

    def test_same_size_and_mtime_output_content_change_invalidates(self):
        self.seed()
        before = self.output.stat()
        self.output.write_bytes(b'X'*before.st_size)
        os.utime(self.output, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertEqual(self.output.stat().st_size, before.st_size)
        self.assertEqual(self.output.stat().st_mtime_ns, before.st_mtime_ns)
        self.assert_recomputed()

    def test_changed_source_rejected_before_reuse(self):
        self.seed()
        before = self.source.stat()
        self.source.write_bytes(b'X'*before.st_size)
        os.utime(self.source, ns=(before.st_atime_ns, before.st_mtime_ns))
        with self.assertRaisesRegex(ValueError, 'Source changed'):
            self.check()
        self.assertEqual(self.compute.call_count, 1)

    def test_rebound_source_hash_still_requires_verification(self):
        self.seed()
        self.source.write_bytes(b'new approved source')
        self.segment['sha256'] = common.sha256(self.source)
        self.assert_recomputed()

    def test_config_change_invalidates(self):
        self.seed()
        self.config['output_width'] = 1920
        self.assert_recomputed()

    def test_each_acceptance_threshold_invalidates(self):
        self.seed()
        for name in ('verify_mean_ssim', 'verify_boundary_ssim',
                     'verify_audio_correlation'):
            before = self.compute.call_count
            self.config[name] = .999
            self.assertEqual(self.check()['validation_cache']['status'], 'miss')
            self.assertEqual(self.compute.call_count, before+1)

    def test_segment_sequence_change_invalidates(self):
        other = dict(self.segment, segment_id='s2')
        self.video['segments'].append(other)
        self.seed()
        self.video['segments'].reverse()
        self.assert_recomputed()

    def test_trim_change_invalidates(self):
        self.seed()
        self.assert_recomputed(overrides={'s1': 1})

    def test_plan_file_content_change_invalidates(self):
        plan = self.root/'.remix'/'plan.json'
        plan.parent.mkdir()
        plan.write_text('{"revision":1}')
        self.seed()
        plan.write_text('{"revision":2}')
        self.assert_recomputed()

    def test_sequence_context_change_invalidates(self):
        self.seed()
        self.context['sequence']['clips'].append('s2')
        self.assert_recomputed()

    def test_implementation_and_tool_identity_change_invalidates(self):
        self.seed()
        with patch.object(cache, 'implementation',
                          return_value={'code': 'v2', 'tools': 'tools-v1'}):
            self.assert_recomputed()
        with patch.object(cache, 'implementation',
                          return_value={'code': 'v2', 'tools': 'tools-v2'}):
            self.assertEqual(self.check()['validation_cache']['status'], 'miss')
        self.assertEqual(self.compute.call_count, 3)

    def test_force_rechecks_even_after_hit(self):
        self.seed()
        self.assertEqual(self.check(force=True)['validation_cache']['status'], 'forced')
        self.assertEqual(self.compute.call_count, 2)

    def test_environment_disables_existing_cache(self):
        self.seed()
        for value in ('1', 'true', 'YES'):
            with patch.dict(os.environ, {'REMIX_DISABLE_CACHE': value}):
                self.check()
        self.assertEqual(self.compute.call_count, 4)

    def test_failed_report_is_never_reused(self):
        self.compute.side_effect = lambda *a, **k: dict(successful_report(a[1]), passed=False)
        self.assertFalse(self.check()['passed'])
        self.assertFalse(self.check()['passed'])
        self.assertEqual(self.compute.call_count, 2)
        self.assertFalse(list((self.root/'.remix/cache/validation').glob('*.json')))

    def test_failed_forced_recheck_revokes_previous_success(self):
        self.seed()
        self.compute.side_effect = lambda *a, **k: dict(successful_report(a[1]), passed=False)
        self.assertFalse(self.check(force=True)['passed'])
        self.assertFalse(self.check()['passed'], 'A newer failed recheck must not revive old PASS evidence')
        self.assertEqual(self.compute.call_count, 3)

    def test_exception_during_forced_recheck_revokes_previous_success(self):
        self.seed()
        self.compute.side_effect = RuntimeError('decoder failure')
        with self.assertRaisesRegex(RuntimeError, 'decoder failure'):
            self.check(force=True)
        with self.assertRaisesRegex(RuntimeError, 'decoder failure'):
            self.check()
        self.assertEqual(self.compute.call_count, 3)

    def test_disabled_cache_forced_failure_revokes_previous_success(self):
        self.seed()
        self.compute.side_effect = lambda *a, **k: dict(successful_report(a[1]), passed=False)
        with patch.dict(os.environ, {'REMIX_DISABLE_CACHE': '1'}):
            self.assertFalse(self.check(force=True)['passed'])
        self.assertFalse(self.check()['passed'])
        self.assertEqual(self.compute.call_count, 3)

    def test_disabled_cache_forced_exception_revokes_previous_success(self):
        self.seed()
        self.compute.side_effect = RuntimeError('forced decoder failure')
        with patch.dict(os.environ, {'REMIX_DISABLE_CACHE': '1'}):
            with self.assertRaisesRegex(RuntimeError, 'forced decoder failure'):
                self.check(force=True)
        with self.assertRaisesRegex(RuntimeError, 'forced decoder failure'):
            self.check()

    def test_forced_recheck_revokes_all_contexts_for_same_output(self):
        self.seed()
        self.context['sequence'] = {'clips': ['alternate-context']}
        self.check()
        self.compute.side_effect = lambda *a, **k: dict(successful_report(a[1]), passed=False)
        self.assertFalse(self.check(force=True)['passed'])
        self.context['sequence'] = {'clips': ['s1']}
        self.assertFalse(self.check()['passed'])

    def test_delivery_without_cli_forced_failure_revokes_previous_success(self):
        import argparse
        self.seed()
        project_file = self.root/'native.fcproj'
        project_file.write_text('{}')
        ph = '0'*64
        record = dict(video_id='01', plan_sha256=ph, native_passed=True,
            path='native.fcproj', sha256=common.sha256(project_file),
            native_output='output.bin', native_sha256=common.sha256(self.output),
            segments=[dict(segment_id='s1', path='source.bin', sha256=common.sha256(self.source))])
        common.save_json(self.root/'.remix/filmcraft.json', {'videos': [record]})
        self.compute.side_effect = lambda *a, **k: dict(successful_report(a[1]), passed=False)
        with patch.object(render, 'read_plan', return_value=({'videos':[self.video], 'config':self.config}, ph)), patch.object(filmcraft, 'existing_validation_cli', return_value=None):
            with self.assertRaisesRegex(ValueError, 'failed independent verification'):
                filmcraft.deliver(argparse.Namespace(project=str(self.root), only=None, cli=None, force_recheck=True))
        self.assertFalse(self.check()['passed'])

    def test_corrupt_validation_record_recomputes(self):
        self.seed()
        record = next((self.root/'.remix/cache/validation').glob('*.json'))
        record.write_text('{broken json')
        self.assert_recomputed()

    def test_modified_report_payload_without_checksum_recomputes(self):
        self.seed()
        record = next((self.root/'.remix/cache/validation').glob('*.json'))
        payload = json.loads(record.read_text())
        payload['payload']['actual_frames'] = 100
        record.write_text(json.dumps(payload))
        self.assert_recomputed()

    def test_partial_successful_report_is_not_reused(self):
        self.compute.side_effect = lambda *a, **k: dict(successful_report(a[1]), actual_frames=7)
        self.check()
        self.check()
        self.assertEqual(self.compute.call_count, 2)

    def test_input_drift_during_validation_aborts_without_evidence(self):
        def drifting(*args, **kwargs):
            self.output.write_bytes(b'output replaced during decode')
            return successful_report(self.video)
        self.compute.side_effect = drifting
        with self.assertRaisesRegex(ValueError, 'inputs changed'):
            self.check()
        self.assertFalse(list((self.root/'.remix/cache/validation').glob('*.json')))

    def test_mutable_context_drift_during_validation_aborts(self):
        def drifting(*args, **kwargs):
            self.context['sequence']['clips'].append('changed during validation')
            return successful_report(self.video)
        self.compute.side_effect = drifting
        with self.assertRaisesRegex(ValueError, 'inputs changed'):
            self.check()

    def test_metadata_content_change_ignores_size_and_mtime(self):
        def probe():
            return {'streams': [], 'format': {'filename': str(self.source)},
                    'observed_bytes': self.source.read_bytes().decode()}
        with patch.object(render, 'probe', side_effect=lambda *a, **k: probe()) as expensive:
            first = cache.metadata(self.root, self.source, lambda: render.probe(self.source))
            cache.metadata(self.root, self.source, lambda: render.probe(self.source))
            self.assertEqual(expensive.call_count, 1)
            before = self.source.stat()
            self.source.write_bytes(b'X'*before.st_size)
            os.utime(self.source, ns=(before.st_atime_ns, before.st_mtime_ns))
            changed = cache.metadata(self.root, self.source, lambda: render.probe(self.source))
            self.assertNotEqual(first['observed_bytes'], changed['observed_bytes'])
            self.assertEqual(expensive.call_count, 2)

    def test_corrupt_metadata_recomputes(self):
        probe = unittest.mock.Mock(return_value={'streams': []})
        cache.metadata(self.root, self.source, probe)
        record = next((self.root/'.remix/cache/metadata').glob('*.json'))
        record.write_text('[]')
        cache.metadata(self.root, self.source, probe)
        self.assertEqual(probe.call_count, 2)

    def test_metadata_drift_aborts_without_publishing(self):
        def drifting():
            self.source.write_bytes(b'changed during probe')
            return {'streams': []}
        with self.assertRaisesRegex(ValueError, 'changed during metadata probe'):
            cache.metadata(self.root, self.source, drifting)
        self.assertFalse(list((self.root/'.remix/cache/metadata').glob('*.json')))

    def test_environment_disables_metadata_decode_reuse(self):
        probe = unittest.mock.Mock(return_value={'streams': []})
        cache.metadata(self.root, self.source, probe)
        with patch.dict(os.environ, {'REMIX_DISABLE_CACHE': '1'}):
            cache.metadata(self.root, self.source, probe)
            cache.metadata(self.root, self.source, probe)
        self.assertEqual(probe.call_count, 3)

    def test_identical_media_at_new_path_reuses_decode_and_updates_filename(self):
        moved = self.root/'renamed.bin'
        moved.write_bytes(self.source.read_bytes())
        probe = unittest.mock.Mock(return_value={'streams': [], 'format': {'filename': str(self.source)}})
        cache.metadata(self.root, self.source, probe)
        result = cache.metadata(self.root, moved, probe)
        self.assertEqual(result['format']['filename'], str(moved))
        self.assertEqual(probe.call_count, 1)

    def test_filmcraft_context_file_changes_invalidate(self):
        editable, compat, cli = (self.root/name for name in ('project.fcproj', 'compat.mov', 'cli.exe'))
        for file in (editable, compat, cli):
            file.write_bytes(b'initial')
        record = {'path': editable.name, 'segments': [{'segment_id': 's1', 'path': compat.name}]}
        self.context = lambda: filmcraft.validation_context(self.root, record, cli, 'plan-hash')
        self.seed()
        for file in (editable, compat, cli):
            before = self.compute.call_count
            file.write_bytes(b'changed')
            self.assertEqual(self.check()['validation_cache']['status'], 'miss')
            self.assertEqual(self.compute.call_count, before+1)


class ImplementationFingerprintTests(unittest.TestCase):
    def test_real_code_and_tool_bytes_change_identity(self):
        with scratch_temporary('cache-fingerprint-') as td:
            root = Path(td)
            (root/'scripts').mkdir()
            paths = [root/'scripts'/name for name in ('performance_cache.py', 'common.py',
                     'render_ops.py', 'filmcraft_ops.py')]
            tools = [root/'ffmpeg.exe', root/'ffprobe.exe']
            for file in paths+tools:
                file.write_bytes(b'original')
            with patch.object(cache, 'ROOT', root), patch.object(cache, 'ffmpeg', return_value=tools[0]), \
                    patch.object(cache, 'ffprobe', return_value=tools[1]):
                before = cache.implementation('validation')
                for file in paths+tools:
                    stat = file.stat()
                    file.write_bytes(b'modified')  # equal length; timestamps restored
                    os.utime(file, ns=(stat.st_atime_ns, stat.st_mtime_ns))
                    after = cache.implementation('validation')
                    self.assertNotEqual(before, after, file.name)
                    before = after


def real_stage(root, label):
    root = Path(root)
    scenario = common.load_json(root/'scenario.json')
    counters = {'probe': 0, 'ffmpeg': 0, 'full_validation': 0}
    original_probe, original_ffmpeg, original_validate = render.probe, render.run_ffmpeg, render.validate_video
    def observed_probe(*args, **kwargs):
        counters['probe'] += 1
        return original_probe(*args, **kwargs)
    def observed_ffmpeg(*args, **kwargs):
        counters['ffmpeg'] += 1
        return original_ffmpeg(*args, **kwargs)
    def observed_validate(*args, **kwargs):
        counters['full_validation'] += 1
        return original_validate(*args, **kwargs)
    started = time.perf_counter()
    with patch.object(render, 'probe', observed_probe), patch.object(render, 'run_ffmpeg', observed_ffmpeg), \
            patch.object(render, 'validate_video', observed_validate), tempfile.TemporaryDirectory(dir=root) as td:
        report = render.validate_video_cached(root, scenario['video'], scenario['config'],
            root/'output.mp4', Path(td), context={'engine': 'cross-process-test'})
    evidence = dict(label=label, pid=os.getpid(), elapsed_seconds=time.perf_counter()-started,
                    counters=counters, report=report)
    common.save_json(root/(label+'.json'), evidence)


class RealCrossProcessTests(unittest.TestCase):
    def test_ffmpeg_cold_then_new_process_warm_preserves_all_metrics(self):
        requested = os.environ.get('REMIX_CACHE_TEST_WORK')
        if requested:
            root = Path(requested).resolve()
            root.mkdir(parents=True, exist_ok=True)
            self.assertFalse((root/'scenario.json').exists(), 'Use a fresh evidence directory')
        else:
            temp = scratch_temporary('cache-real-')
            self.addCleanup(temp.cleanup)
            root = Path(temp.name)
        source = root/'source.mkv'
        common.run_ffmpeg(['-y', '-f', 'lavfi', '-i', 'testsrc2=size=160x90:rate=30:duration=1',
            '-f', 'lavfi', '-i', 'aevalsrc=0.3*sin(2*PI*440*t)|0.3*sin(2*PI*660*t):s=48000:d=1',
            '-c:v', 'ffv1', '-c:a', 'pcm_s16le', source])
        config = {'output_width': 160, 'output_height': 90, 'output_fps': '30/1',
                  'crf': 12, 'preset': 'fast'}
        video = {'video_id': '01', 'segments': [{'segment_id': 's1', 'path': source.name,
                 'sha256': common.sha256(source), 'frames': 30}]}
        # Render through the shipping graph, but do not seed metadata evidence.
        with patch.dict(os.environ, {'REMIX_DISABLE_CACHE': '1'}), tempfile.TemporaryDirectory(dir=root) as td:
            parts, _ = render.build_parts(root, video, config, Path(td))
            render.assemble(parts, config, root/'output.mp4', Path(td))
        common.save_json(root/'scenario.json', {'video': video, 'config': config})
        env = dict(os.environ, REMIX_DISABLE_CACHE='')
        for label in ('cold', 'warm'):
            done = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                '--real-stage', str(root), label], capture_output=True, text=True, env=env)
            self.assertEqual(done.returncode, 0, done.stderr+done.stdout)
        cold, warm = (common.load_json(root/(label+'.json')) for label in ('cold', 'warm'))
        self.assertNotEqual(cold['pid'], warm['pid'])
        self.assertEqual(cold['report']['validation_cache']['status'], 'miss')
        self.assertEqual(warm['report']['validation_cache']['status'], 'hit')
        self.assertEqual(cold['counters']['full_validation'], 1)
        self.assertGreaterEqual(cold['counters']['probe'], 2)
        self.assertGreater(cold['counters']['ffmpeg'], 0)
        self.assertEqual(warm['counters'], {'probe': 0, 'ffmpeg': 0, 'full_validation': 0})
        cold_report, warm_report = copy.deepcopy(cold['report']), copy.deepcopy(warm['report'])
        cold_report.pop('validation_cache'); warm_report.pop('validation_cache')
        self.assertEqual(cold_report, warm_report)
        self.assertTrue(cold_report['passed'])
        self.assertEqual(cold_report['actual_frames'], 30)
        segment = cold_report['segments'][0]
        self.assertEqual(set(segment['boundaries']), {'first', 'last'})
        self.assertEqual(len(segment['audio']), 2)
        self.assertTrue(segment['audio_length_ok'])
        # An independent process also exercises persisted metadata without decoding.
        code = ('import sys;sys.path.insert(0,sys.argv[1]);import render_ops;'
                'from unittest.mock import patch;from pathlib import Path;'
                'root=Path(sys.argv[2]);'
                '\nwith patch.object(render_ops,"probe",side_effect=AssertionError("decoded again")):'
                '\n assert len(render_ops.metadata(root/"source.mkv",cache_project=root)[2])==30')
        done = subprocess.run([sys.executable, '-c', code, str(Path(__file__).resolve().parent), str(root)],
                              capture_output=True, text=True, env=env)
        self.assertEqual(done.returncode, 0, done.stderr+done.stdout)
        # Distinct left/right source tones expose a real channel swap. The full
        # validator must fail it twice rather than caching a failed report.
        swapped = root/'swapped.mp4'
        common.run_ffmpeg(['-y', '-i', root/'output.mp4', '-c:v', 'copy',
            '-af', 'pan=stereo|c0=c1|c1=c0', '-c:a', 'aac', '-b:a', '192k', swapped])
        os.replace(swapped, root/'output.mp4')
        for label in ('swapped', 'swapped-again'):
            done = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                '--real-stage', str(root), label], capture_output=True, text=True, env=env)
            self.assertEqual(done.returncode, 0, done.stderr+done.stdout)
            failed = common.load_json(root/(label+'.json'))
            self.assertFalse(failed['report']['passed'])
            self.assertEqual(failed['report']['validation_cache']['status'], 'miss')
            self.assertEqual(failed['counters']['full_validation'], 1)
            self.assertGreater(failed['counters']['ffmpeg'], 0)
            self.assertTrue(any(channel['correlation'] < .98
                                for channel in failed['report']['segments'][0]['audio']))


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--real-stage':
        real_stage(sys.argv[2], sys.argv[3])
    else:
        unittest.main()
