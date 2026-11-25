"""Verify a clean source copy with no installed environment or global tools."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent.parent

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--build',action='store_true',help='Also build and smoke-test the portable package')
    parser.add_argument('--cold-cache',action='store_true',help='Do not reuse already downloaded, verified artifact/package caches')
    args=parser.parse_args()
    destination=ROOT/'.runtime/verification'/f'fresh clone 中文 {int(time.time())}'
    destination.mkdir(parents=True)
    files=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).decode('utf-8').split('\0')
    for name in filter(None,files):
        source=ROOT/name
        if source.is_file():
            target=destination/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    if not args.cold_cache:
        for folder in ['downloads','cache']:
            source=ROOT/'.runtime'/folder
            if source.is_dir():shutil.copytree(source,destination/'.runtime'/folder)
    assert not (destination/'.venv').exists()
    assert not (destination/'node_modules').exists()
    assert not (destination/'.runtime/python').exists()
    env=os.environ.copy()
    for name in ['PYTHONHOME','PYTHONPATH','VIRTUAL_ENV','CONDA_PREFIX','YINGBO_PYTHON','NODE_PATH','ELECTRON_RUN_AS_NODE','PSMODULEPATH','PSModulePath']:
        env.pop(name,None)
    windows=Path(env.get('SYSTEMROOT') or env.get('SystemRoot') or env['WINDIR'])
    env['PATH']=os.pathsep.join(str(p) for p in [windows,windows/'System32',windows/'System32/WindowsPowerShell/v1.0'])
    powershell=windows/'System32/WindowsPowerShell/v1.0/powershell.exe'
    def bootstrap(action):
        subprocess.run([str(powershell),'-NoLogo','-NoProfile','-ExecutionPolicy','Bypass','-File',str(destination/'scripts/bootstrap.ps1'),'-Action',action],cwd=destination,env=env,check=True)
    print(f'Clean source verification: {destination}',flush=True)
    bootstrap('check')
    if args.build:
        bootstrap('build')
        moved=destination/'.runtime/moved package 中文'
        shutil.copytree(destination/'release/win-unpacked',moved)
        node=destination/'.runtime'/json.loads((destination/'runtime.versions.json').read_text())['node']['directory']/'node.exe'
        subprocess.run([str(node),str(destination/'scripts/smoke_desktop.cjs'),str(moved/'Yingbo Studio.exe')],cwd=destination,env=env,check=True)
    report={'source':str(destination),'global_python_node_removed_from_path':True,'fresh_virtual_environment':True,
            'reused_download_cache':not args.cold_cache,'source_checks_passed':True,'package_relocation_passed':args.build}
    (ROOT/'.runtime/verification/latest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
