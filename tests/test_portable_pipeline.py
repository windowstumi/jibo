import importlib.util
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('avatar_cli',ROOT/'tools/avatar_pipeline/cli.py')
cli=importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)

class PortablePipelineTests(unittest.TestCase):
    def test_profile_rejects_wrong_canvas_before_build_or_network(self):
        with tempfile.TemporaryDirectory(prefix='avatar profile ') as folder:
            workspace=Path(folder);(workspace/'images').mkdir()
            Image.new('RGBA',(64,96)).save(workspace/'images/neutral.raw.png')
            with self.assertRaisesRegex(ValueError,'canvas'):
                cli.validate_profile(ROOT/'tools/avatar_pipeline/profiles/silver-hair.json',workspace)

    def test_runtime_paths_follow_repository_instead_of_machine_install(self):
        version=json.loads((ROOT/'runtime.versions.json').read_text())['psd2live']['version']
        import os
        from unittest.mock import patch
        with patch.dict(os.environ,{},clear=True):
            self.assertEqual(cli.tool_home(),ROOT/'.runtime'/f'psd2live-{version}')

    def test_source_modules_do_not_reference_experiment_install_paths(self):
        for source in (ROOT/'tools/avatar_pipeline').glob('*.py'):
            text=source.read_text(encoding='utf-8')
            self.assertNotIn('D:\\AI-Live-Demos',text,source.name)
            self.assertNotIn('C:\\Users\\90824',text,source.name)

    def test_unknown_image_request_is_not_resubmitted(self):
        import os
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'reference.png'
            Image.new('RGB',(8,8)).save(source)
            workspace=root/'output';workspace.mkdir()
            (workspace/'generation.json').write_text(json.dumps({
                'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                'steps':{'neutral':{'status':'unknown'}}}),encoding='utf-8')
            args=argparse.Namespace(source=source,workspace=workspace,api_base='https://example.invalid/v1',
                model='test',proxy_mode='direct',prompt=None)
            with patch.dict(os.environ,{'IMAGE_API_KEY':'test-key'}),patch.object(cli,'image_client') as request:
                with self.assertRaisesRegex(ValueError,'outcome unknown'):
                    asyncio.run(cli.generate(args))
                request.assert_not_called()

if __name__=='__main__':unittest.main()
