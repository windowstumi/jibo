"""Opt-in real cloud + installed voice acceptance; runs against an isolated role copy."""
import argparse
import copy
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer

import httpx

ROOT=Path(__file__).resolve().parent.parent

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',type=Path,required=True)
    parser.add_argument('--target',type=Path)
    parser.add_argument('--report-dir',type=Path,default=ROOT/'test-output/interaction-live')
    args=parser.parse_args();out=args.report_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    data=args.data.resolve()
    with sqlite3.connect('file:'+(data/'studio.sqlite3').as_posix()+'?mode=ro',uri=True) as conn:
        saved=json.loads(conn.execute("SELECT value FROM kv WHERE key='settings'").fetchone()[0])
    assert saved['llm'].get('key'),'A configured real cloud model is required'
    with httpx.Client(headers={'X-Yingbo-Token':(data/'.local-access-token').read_text().strip()},trust_env=False,timeout=5) as client:
        state=client.get('http://127.0.0.1:8765/api/state').json()
        status=client.get('http://127.0.0.1:8765/api/local-tts/status').json()
    assert not state['runtime']['active'],'Stop live playback before running this opt-in acceptance'
    assert status['phase']=='ready',status['message']
    ident=saved['avatar']['character_id'];assert re.fullmatch('[a-f0-9]{32}',ident)
    voice=data/'local-tts/voices'/status['loaded_voice'];meta=json.loads((voice/'voice.json').read_text(encoding='utf8'))
    log=(data/'local-tts/service.log').read_text(encoding='utf8',errors='replace')
    port=int(re.findall(r'Uvicorn running on http://127.0.0.1:(\d+)',log)[-1])
    sys.path.insert(0,str(ROOT))
    from tools.local_tts.gpt_sovits_bridge import make_handler
    config={'upstream':f'http://127.0.0.1:{port}','voices':{'test':{'ref_audio_path':str(voice/meta['reference']['file']),'prompt_text':meta['prompt_text']}}}
    bridge=ThreadingHTTPServer(('127.0.0.1',0),make_handler(config));thread=threading.Thread(target=bridge.serve_forever,daemon=True);thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix='private-',dir=out) as temporary:
            isolated=Path(temporary).resolve();assert isolated.parent==out
            os.environ['VTUBER_DATA_DIR']=str(isolated)
            import app
            app.init_db();cfg=copy.deepcopy(app.DEFAULTS)
            cfg['llm']=saved['llm'];cfg['interaction']={'allow_chat':True}
            cfg['tts'].update(provider='compatible',base_url=f'http://127.0.0.1:{bridge.server_port}/v1',model='gpt-sovits',voice='test',key='')
            cfg['local_tts']['auto_load']=False;cfg['gift_template']='谢谢{username}！'
            role=json.loads((data/'characters'/ident/'job.json').read_text(encoding='utf8'))
            cfg['avatar']={'mode':'character','character_id':ident,'name':role['name'],'persona':role.get('persona',''),'image':f'/media/characters/{ident}/standard.png'}
            shutil.copytree(data/'characters'/ident,isolated/'characters'/ident)
            app.put_value('settings',cfg)
            report=out/'report.json'
            if report.exists():raise RuntimeError('Use a fresh report directory to avoid accepting stale results')
            env={**os.environ,'YINGBO_SMOKE_REPORT':str(report),'YINGBO_DATA_DIR':str(isolated),'JIBO_DATA_DIR':str(isolated),'YINGBO_PORT':'0','JIBO_SMOKE_INTERACTION':'1'}
            env.pop('ELECTRON_RUN_AS_NODE',None)
            command=[str(args.target.resolve())] if args.target else [str(ROOT/'node_modules/electron/dist/electron.exe'),str(ROOT)]
            with (out/'desktop.log').open('wb') as output:
                process=subprocess.Popen(command,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
                try:process.wait(timeout=190)
                finally:
                    if process.poll() is None:process.terminate();process.wait(timeout=10)
            if not report.exists():raise RuntimeError('Missing desktop acceptance report; inspect desktop.log')
            result=json.loads(report.read_text(encoding='utf8'))
            for file in (isolated/'audio').glob('*.wav'):shutil.copy2(file,out/file.name)
            assert not result.get('error'),result.get('error')
            assert result['interaction']['motionFence'] and result['interaction']['captionAndSpeech'],result
            print(json.dumps(result['interaction'],ensure_ascii=False,indent=2))
    finally:
        bridge.shutdown();bridge.server_close();thread.join(timeout=3)

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf8');main()
