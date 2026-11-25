"""Build on the target OS/CPU using the selected Python interpreter."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--clean', action='store_true')
    args = parser.parse_args()
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--noupx', '--onedir', '--console', '--name', 'yingbo-backend',
               '--distpath', str(ROOT/'build'/'sidecar'), '--workpath', str(ROOT/'build'/'pyinstaller'), '--specpath', str(ROOT/'build'),
               '--add-data', f'{ROOT / "static"}:static', '--add-data', f'{ROOT / "tts_windows.ps1"}:.',
               '--collect-all', 'uvicorn', '--collect-all', 'certifi', '--hidden-import', 'multipart']
    if args.clean:
        command.append('--clean')
    command.append(str(ROOT/'backend_entry.py'))
    subprocess.run(command, cwd=ROOT, env={**os.environ, 'PYINSTALLER_CONFIG_DIR':str(ROOT/'.runtime/cache/pyinstaller')}, check=True)
    # Keep PyInstaller's entire onedir layout. DLLs/resources are required.
    import shutil
    source = ROOT/'build'/'sidecar'/'yingbo-backend'
    destination = ROOT/'build'/'backend'
    # A rebuild must not retain DLLs from a different dependency lock.
    build_root = (ROOT/'build').resolve()
    if not build_root.is_relative_to(ROOT.resolve()) or destination.is_symlink() or destination.resolve() != build_root/'backend':
        raise RuntimeError('Refusing to replace a backend directory outside this build folder')
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    print(f'Backend ready: {destination}')


if __name__ == '__main__':
    main()
