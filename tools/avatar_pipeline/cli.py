"""Portable entry point for the experimental, calibrated Live2D workflow."""
import argparse
import asyncio
import functools
import getpass
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from PIL import Image
from image_service import image_client, endpoint, image_payload, response_json, download_result, safe_detail
from scene_model import load_image, remove_chroma, write_json

IDENTITY = '''Create one front-facing full-body adult anime character asset from this reference.
Preserve the recognizable face, hairstyle, hair color, costume, ornaments and illustration style.
Use an upright relaxed A pose, separate both arms from the torso, show both open hands and both shoes.
Keep long hair behind the arms. Use a level camera, centered character, generous clean margins,
solid RGB(0,255,0) background, no scenery, shadows, text, labels, props or extra limbs.'''
SAME = 'Keep this exact character, canvas, framing, proportions, costume and green background. '
VARIANTS = [
    ('speaking', SAME+'Change only the mouth to an open speaking mouth with a visible interior.'),
    ('blink', SAME+'Change only both eyes to naturally closed eyelids.'),
    ('smile', SAME+'Change only the face to a gentle friendly smile.'),
    ('wave', SAME+'Raise the viewer-right arm in a greeting, elbow bent, open palm beside the head. Five fingers. Other arm stays down.'),
    ('present', SAME+'Bend the viewer-right elbow and extend the forearm outward with the empty palm up. Other arm stays down.'),
]

def tool_home():
    version=json.loads((ROOT/'runtime.versions.json').read_text(encoding='utf-8'))['psd2live']['version']
    return Path(os.environ.get('PSD2LIVE_HOME', ROOT/'.runtime'/f'psd2live-{version}')).resolve()

def validate_profile(profile, workspace):
    data=json.loads(profile.read_text(encoding='utf-8'))
    if not data.get('masks') or set(data.get('joints',{}))!={'L','R'}:
        raise ValueError('A calibrated masks/joints profile is required; see tools/avatar_pipeline/README.md')
    with Image.open(workspace/'images/neutral.raw.png') as image:
        if list(image.size)!=data['canvas']:
            raise ValueError('Profile canvas does not match the generated image; recalibrate it first.')
    return data

async def generate(args):
    source=args.source.resolve()
    if not source.is_file():raise ValueError(f'Source does not exist: {source}')
    workspace=args.workspace.resolve();images=workspace/'images';images.mkdir(parents=True,exist_ok=True)
    manifest_path=workspace/'generation.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {'provider':args.api_base,'model':args.model,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'steps':{}}
    if manifest.get('source_sha256') != hashlib.sha256(source.read_bytes()).hexdigest():
        raise ValueError('Workspace belongs to another reference. Use a new workspace directory.')
    key=os.environ.get('IMAGE_API_KEY') or getpass.getpass('Image API key (not saved): ')
    if not key:raise ValueError('Missing image API key')
    cfg={'base_url':args.api_base,'model':args.model,'key':key,'proxy_mode':args.proxy_mode,'proxy_url':''}
    with Image.open(source) as im:im.convert('RGBA').save(images/'source.png')
    prompt=args.prompt.read_text(encoding='utf-8') if args.prompt else IDENTITY
    steps=[('neutral',prompt),*VARIANTS]
    for name,text in steps:
        path=images/f'{name}.raw.png';record=manifest['steps'].get(name,{})
        if record.get('status')=='saved' and path.is_file():
            if hashlib.sha256(path.read_bytes()).hexdigest()!=record.get('sha256'):
                raise ValueError(f'{name}: saved image checksum changed. Use a new workspace or inspect it before retrying.')
            continue
        if record.get('status') in ('submitted','unknown'):
            raise ValueError(f'{name}: previous request outcome unknown. Check provider history before retrying.')
        source_path=images/('source.png' if name=='neutral' else 'neutral.raw.png')
        record={'status':'submitted','started':time.time(),'prompt':text,'source':source_path.name}
        manifest['steps'][name]=record;write_json(manifest_path,manifest)
        print(f'Generating {name} (one paid request, no automatic retry)...',flush=True)
        try:
            async with image_client(cfg,timeout=360) as client:
                response=await client.post(endpoint(cfg['base_url'],'/images/edits'),headers={'Authorization':'Bearer '+key},
                    data={'model':cfg['model'],'prompt':text,'size':'1024x1536'},files={'image':('reference.png',source_path.read_bytes(),'image/png')})
            raw=image_payload(response_json(response,cfg))
            image=load_image(await download_result(raw,cfg) if isinstance(raw,str) else raw)
            image.save(path);record.update(status='saved',finished=time.time(),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            write_json(manifest_path,manifest)
        except Exception as exc:
            record.update(status='unknown',error=safe_detail(str(exc),cfg));write_json(manifest_path,manifest)
            raise RuntimeError(record['error']) from None
    matte(workspace)
    print(f'Saved six images: {workspace}. Calibrate a profile before building Live2D.')

def matte(workspace):
    for name in ['neutral','speaking','blink','smile','wave','present']:
        path=workspace/'images'/f'{name}.raw.png'
        if path.is_file():
            with Image.open(path) as image:result,_=remove_chroma(image.convert('RGBA'))
            result.save(workspace/'images'/f'{name}.transparent.png')

def ensure_editor():
    home=tool_home();java=home/'runtime/bin/java.exe'
    if not java.is_file():raise ValueError('Run setup.cmd -WithLive2D first.')
    from mcp_proxy import Client
    try:
        with Client() as client:client.project()
        return
    except Exception:
        pass
    # Start the official project-local editor; its MCP endpoint is loopback only.
    flags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0
    subprocess.Popen([str(home/'PSD2Live.exe')],cwd=home,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags)
    for _ in range(60):
        time.sleep(.5)
        try:
            with Client() as client:client.project()
            return
        except Exception:pass
    raise RuntimeError('PSD2Live did not expose its local MCP service. Open its Settings > MCP and check the port/token.')

def build(args):
    workspace=args.workspace.resolve();profile=args.profile.resolve()
    validate_profile(profile,workspace)
    matte(workspace)
    os.environ['AVATAR_WORKSPACE']=str(workspace);os.environ['AVATAR_PROFILE']=str(profile)
    runpy.run_path(str(HERE/'build_local_layers.py'),run_name='__main__')
    home=tool_home();base=workspace/'segmented-base'
    subprocess.run([str(home/'runtime/bin/java.exe'),'-Dfile.encoding=UTF-8',f'-Dcompose.application.resources.dir={home / "app/resources"}',
                    '-cp',str(home/'app/*'),'io.github.psd2live.MainKt','--input',str(workspace/'character.assisted.psd'),
                    '--output',str(base),'--head-strength','0.4','--body-strength','0.35','--mesh-spacing','40','--no-see-through'],check=True)
    ensure_editor()
    from mcp_proxy import Client
    with Client() as client:
        # No discard_unsaved: never discard another open project's edits.
        client.edit('project_import_cmo3',path=str(base/'character.assisted.cmo3'),mode='new')
    runpy.run_path(str(HERE/'rig_actions.py'),run_name='__main__')
    runpy.run_path(str(HERE/'make_motions.py'),run_name='__main__')
    out=workspace/'live2d-final';name='character.assisted'
    model=json.loads((out/f'{name}.model3.json').read_text(encoding='utf-8'))
    original=json.loads((base/f'{name}.model3.json').read_text(encoding='utf-8'))
    for group,files in original['FileReferences']['Motions'].items():
        model['FileReferences']['Motions'].setdefault(group,files)
        for file in files:shutil.copy2(base/file['File'],out/file['File'])
    model['FileReferences']['Expressions']=original['FileReferences'].get('Expressions',[])
    for file in model['FileReferences']['Expressions']:shutil.copy2(base/file['File'],out/file['File'])
    model['Groups']=original.get('Groups',[]);write_json(out/f'{name}.model3.json',model)
    with Client() as client:
        for motion in ['Wave','Present']:
            directory=workspace/'renders'/motion.lower()
            client.edit('project_export_target',target='gif',output_directory=str(directory),settings={'clip':motion,'fps':'15','size':'800','background':'FFF1F4F9','dither':'false'})
            shutil.copy2(next(directory.glob('*.gif')),workspace/f'{motion.lower()}-demo.gif')
    (workspace/'index.html').write_text('<meta charset="utf-8"><title>Live2D build preview</title><h1>Actual model animation exports</h1><p>Calibrated, assisted pipeline; not an automatic rig for arbitrary images.</p><img width="400" src="wave-demo.gif"><img width="400" src="present-demo.gif"><p><a href="live2d-final/character.assisted.model3.json">Model files</a></p>',encoding='utf-8')
    print(f'Build complete: {out}')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    g=commands.add_parser('generate');g.add_argument('--source',type=Path,required=True);g.add_argument('--workspace',type=Path,required=True)
    g.add_argument('--api-base',default='https://api.openai.com/v1');g.add_argument('--model',default='gpt-image-2');g.add_argument('--prompt',type=Path)
    g.add_argument('--proxy-mode',choices=['system','direct'],default='system')
    b=commands.add_parser('build');b.add_argument('--workspace',type=Path,required=True);b.add_argument('--profile',type=Path,required=True)
    p=commands.add_parser('preview');p.add_argument('--workspace',type=Path,required=True);p.add_argument('--port',type=int,default=8768)
    commands.add_parser('doctor')
    args=parser.parse_args()
    if args.command=='generate':asyncio.run(generate(args))
    elif args.command=='build':build(args)
    elif args.command=='doctor':
        subprocess.run([sys.executable,str(ROOT/'scripts/doctor.py'),'--live2d'],check=True)
    else:
        if not (args.workspace/'index.html').is_file():raise ValueError('No built preview. Run build or select an existing output workspace.')
        handler=functools.partial(SimpleHTTPRequestHandler,directory=str(args.workspace.resolve()))
        with ThreadingHTTPServer(('127.0.0.1',args.port),handler) as server:
            print(f'Preview: http://127.0.0.1:{args.port}/',flush=True);server.serve_forever()

if __name__=='__main__':
    try:main()
    except (ValueError,RuntimeError) as error:print(str(error),file=sys.stderr);raise SystemExit(1)
