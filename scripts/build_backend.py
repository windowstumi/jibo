"""Build on the target OS/CPU using the selected Python interpreter."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--clean', action='store_true')
    args = parser.parse_args()
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onedir', '--console', '--name', 'yingbo-backend',
               '--distpath', str(ROOT/'build'/'sidecar'), '--workpath', str(ROOT/'build'/'pyinstaller'), '--specpath', str(ROOT/'build'),
               '--add-data', f'{ROOT / "static"}:static', '--add-data', f'{ROOT / "tts_windows.ps1"}:.',
               '--collect-all', 'uvicorn', '--collect-all', 'certifi', '--hidden-import', 'multipart']
    if args.clean:
        command.append('--clean')
    command.append(str(ROOT/'backend_entry.py'))
    subprocess.run(command, cwd=ROOT, check=True)
    # Keep PyInstaller's entire onedir layout. DLLs/resources are required.
    import shutil
    source = ROOT/'build'/'sidecar'/'yingbo-backend'
    destination = ROOT/'build'/'backend'
    shutil.copytree(source, destination, dirs_exist_ok=True)
    print(f'Backend ready: {destination}')


if __name__ == '__main__':
    main()
