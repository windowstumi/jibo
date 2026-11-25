"""Offline import/resource check for a freshly installed local environment."""
import argparse
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live2d', action='store_true')
    args = parser.parse_args()
    modules = ['fastapi', 'uvicorn', 'httpx', 'multipart', 'PIL', 'numpy', 'PyInstaller']
    if args.live2d:
        modules += ['cv2', 'psd_tools']
    for module in modules:
        importlib.import_module(module)
    for file in ['app.py', 'backend_entry.py', 'static/index.html', 'tts_windows.ps1']:
        if not (ROOT / file).is_file():
            raise RuntimeError(f'Missing project resource: {file}')
    if args.live2d:
        version=json.loads((ROOT/'runtime.versions.json').read_text(encoding='utf-8'))['psd2live']['version']
        home=Path(os.environ.get('PSD2LIVE_HOME', ROOT/'.runtime'/f'psd2live-{version}'))
        java=home/'runtime/bin/java.exe'
        if not java.is_file():
            raise RuntimeError('Missing PSD2Live runtime; run setup.cmd -WithLive2D')
        subprocess.run([str(java), '-version'], check=True)
    print(f'Environment OK: Python {sys.version.split()[0]}, {sys.executable}')

if __name__ == '__main__':
    main()
