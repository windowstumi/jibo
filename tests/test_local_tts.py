import hashlib
import io
import json
from pathlib import Path
import tempfile
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
