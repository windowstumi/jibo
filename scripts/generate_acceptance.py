"""Explicit end-to-end acceptance run. Exactly one request per image, no retries."""
import asyncio
import json
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
# Also works with the bundled development runtime while pip prepares the venv.
sys.path.append(str(ROOT/'.venv'/'Lib'/'site-packages'))
from scene_model import build_scene, new_job, public_job, write_json
from image_service import connection_error
import httpx


async def main():
    data=Path(sys.argv[1]).resolve()
    with sqlite3.connect(data/'studio.sqlite3') as c:
        settings=json.loads(c.execute("SELECT value FROM kv WHERE key='settings'").fetchone()[0])
    source=data/'images'/Path(settings['avatar']['original']).name
    scene_root=data/'scenes';scene_root.mkdir(exist_ok=True)
    directory=new_job(scene_root,source.read_bytes())
    print('SCENE_ID='+directory.name,flush=True)
    def progress(job):print(json.dumps({'status':job['status'],'current':job['current'],'steps':job['steps']},ensure_ascii=True),flush=True)
    try:
        model=await build_scene(directory,settings['image'],source.read_bytes(),on_progress=progress)
        print(json.dumps({'completed':model['id'],'quality':model['quality']},ensure_ascii=True),flush=True)
    except Exception as exc:
        error=connection_error(exc,settings['image']) if isinstance(exc,httpx.RequestError) else str(exc)
        job=public_job(directory);job['error']=error;write_json(directory/'job.json',job)
        print(json.dumps({'failed':directory.name,'error':error},ensure_ascii=True),flush=True)
        raise SystemExit(1)


if __name__=='__main__':asyncio.run(main())
