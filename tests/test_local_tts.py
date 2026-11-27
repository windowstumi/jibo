import hashlib
import io
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
import wave
import zipfile

from local_tts import LocalTTS, DEFAULT_LOCAL, inspect_voice, safe_extract


def voice_zip(change=None, extra=None):
    buffer = io.BytesIO()
    wav = io.BytesIO()
    with wave.open(wav, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b'\0\0' * 64000)
    files = {'gpt.ckpt': b'test-weight', 'sovits.pth': b'test-weight-2', 'reference.wav': wav.getvalue()}
    meta = {'schema': 1, 'version': 'v2', 'name': '测试音色', 'prompt_text': '测试参考文字。'}
    for key, name in [('gpt', 'gpt.ckpt'), ('sovits', 'sovits.pth'), ('reference', 'reference.wav')]:
        meta[key] = {'file': name, 'sha256': hashlib.sha256(files[name]).hexdigest()}
    if change:
        change(meta)
    with zipfile.ZipFile(buffer, 'w') as bundle:
        for name, raw in files.items():
            bundle.writestr(name, raw)
        bundle.writestr('voice.json', json.dumps(meta))
        bundle.writestr('VOICE-LICENSE.txt', 'test-only')
        if extra:
            bundle.writestr(extra, 'not allowed')
    return buffer.getvalue()


class LocalTTSTests(unittest.TestCase):
    def test_github_source_download_uses_archive_api_accept_and_validates_cache(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as folder:
            manager=LocalTTS(Path(folder),lambda:{'local_tts':DEFAULT_LOCAL})
            archive=b'checked-source-archive'
            spec={**manager.manifest['engine'],'size':len(archive),'sha256':hashlib.sha256(archive).hexdigest()}
            response=io.BytesIO(archive);response.status=200;response.headers={}
            target=manager.root/'downloads/engine.zip'
            with patch('local_tts.urllib.request.urlopen',return_value=response) as fetch:
                self.assertEqual(manager._download(spec,target,'下载推理代码'),target)
                self.assertEqual(fetch.call_args.args[0].get_header('Accept'),'application/vnd.github+json')
                self.assertEqual(target.read_bytes(),archive)
                manager._download(spec,target,'下载推理代码')
                self.assertEqual(fetch.call_count,1)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows venv stdin inheritance')
    def test_python_probe_does_not_inherit_watched_parent_pipe(self):
        # Recreate Electron -> backend stdin ownership with a real Python child.
        # Without DEVNULL the venv launcher hangs although the same -c works in a terminal.
        script = '''import sys, threading, time, os
from pathlib import Path
from unittest.mock import patch, PropertyMock
from local_tts import LocalTTS, DEFAULT_LOCAL
threading.Thread(target=lambda:sys.stdin.buffer.read(),daemon=True).start()
time.sleep(.2)
manager=LocalTTS(Path(sys.argv[1]),lambda:{'local_tts':DEFAULT_LOCAL})
with patch.object(LocalTTS,'python',new_callable=PropertyMock,return_value=Path(sys.executable)):
    manager._valid_python({})
print('probe-completed',flush=True)
os._exit(0)
'''
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'check.py';path.write_text(script,encoding='utf-8')
            import os
            env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1])}
            process=subprocess.Popen([sys.executable,str(path),folder],env=env,stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                import time
                deadline=time.monotonic()+22
                while process.poll() is None and time.monotonic()<deadline:time.sleep(.05)
                if process.poll() is None:process.kill();self.fail('Python probe inherited the watched stdin pipe')
                out,err=process.communicate(timeout=3)
                self.assertEqual(process.returncode,0,err.decode(errors='replace'))
                self.assertIn(b'probe-completed',out)
            finally:
                if process.poll() is None:process.kill();process.wait()
                if process.stdin and not process.stdin.closed:process.stdin.close()

    def test_voice_package_hash_and_path_checked_before_install(self):
        for raw in [voice_zip(lambda m: m['gpt'].update(sha256='0'*64)),
                    voice_zip(lambda m: m['reference'].update(file='../reference.wav')),
                    voice_zip(extra='run.py')]:
            with self.subTest(size=len(raw)), self.assertRaises(ValueError):
                inspect_voice(raw)

    def test_import_assigns_distinct_ids_and_never_overwrites_a_voice(self):
        with tempfile.TemporaryDirectory() as folder:
            manager = LocalTTS(Path(folder), lambda: {'local_tts': DEFAULT_LOCAL})
            first = manager.import_voice(voice_zip())
            second = manager.import_voice(voice_zip())
            self.assertNotEqual(first['id'], second['id'])
            self.assertEqual(len(manager.voices()), 2)
            self.assertTrue((manager.root/'voices'/first['id']/'reference.wav').is_file())

    def test_component_archive_cannot_traverse_or_write_drive_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ['../escape', 'C:/escape', 'x/../../escape', '\\outside\\file']:
                archive = io.BytesIO()
                with zipfile.ZipFile(archive, 'w') as bundle:
                    bundle.writestr(name, 'bad')
                with self.subTest(name=name), self.assertRaises(ValueError):
                    safe_extract(io.BytesIO(archive.getvalue()), Path(folder)/'target')

    def test_default_and_status_do_not_load_cuda_or_start_installation(self):
        with tempfile.TemporaryDirectory() as folder:
            manager = LocalTTS(Path(folder), lambda: {'local_tts': DEFAULT_LOCAL})
            state = manager.snapshot()
            self.assertEqual(state['phase'], 'idle')
            self.assertFalse(state['installed'])
            self.assertIsNone(manager.process)
            self.assertFalse(manager.root.exists())


if __name__ == '__main__':
    unittest.main()
