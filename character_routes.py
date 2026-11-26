"""Character workshop endpoints, isolated from the existing on-air renderer."""
import asyncio
import json
from pathlib import Path
import re
import time
import uuid
import zipfile

from fastapi import File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from PIL import Image, ImageOps

from character_pipeline import (PRESETS, REQUIRED_PRESETS, PIPELINE_DEFAULTS, charges, pipeline_settings, quote,
    persist, read_job, run_character, probe_video, valid_url, provider_binding, ffprobe_binary,media_binary)
from character_cards import create_local_card,assemble_local_card,validate_card,export_card,import_card,MAX_CHARACTER_BYTES



def register_characters(app,data,get_settings,put_settings,emit,on_apply=None):
    root=data/'characters';root.mkdir(exist_ok=True)
    refs=data/'references';refs.mkdir(exist_ok=True)
    tasks={}

    def directory(ident):
        if not re.fullmatch('[a-f0-9]{32}',ident):raise HTTPException(404,'角色编号无效')
        folder=root/ident
        if not (folder/'job.json').is_file():raise HTTPException(404,'角色不存在')
        return folder

    def start(folder,local=False):
        ident=folder.name
        if ident in tasks:raise HTTPException(409,'角色正在处理中')
        task=asyncio.create_task(assemble_local_card(folder,emit) if local else run_character(folder,get_settings(),emit));tasks[ident]=task
        task.add_done_callback(lambda _:tasks.pop(ident,None))

    async def mark_interrupted():
        for path in root.glob('*/job.json'):
            job=read_job(path.parent)
            if job.get('status') in ('running','assembling'):
                job.update(status='interrupted',error='程序已重启，继续时查询原任务编号。')
                persist(path.parent,job)

    # Registered as an explicit shutdown hook by the main lifespan.
    async def shutdown():
        running=list(tasks.values())
        for task in running:task.cancel()
        if running:await asyncio.gather(*running,return_exceptions=True)

    @app.get('/api/characters/config')
    async def config():
        cfg=pipeline_settings(get_settings())
        for section in ['vision','video']:
            cfg[section]['has_key']=bool(cfg[section].pop('key',''))
        cfg['obs']['has_password']=bool(cfg['obs'].pop('password',''))
        return cfg

    @app.get('/api/obs/private-config')
    async def obs_config():
        # Protected by the desktop local-auth middleware; do not include in public state/export.
        return pipeline_settings(get_settings())['obs']

    @app.put('/api/characters/config')
    async def set_config(request:Request):
        body=await request.json();settings=get_settings();cfg=pipeline_settings(settings)
        if not isinstance(body,dict):raise HTTPException(422,'配置必须为对象')
        try:
            for section in ['vision','video','pricing','obs']:
                incoming=body.get(section,{})
                if not isinstance(incoming,dict):raise ValueError('配置字段格式错误')
                for key,value in incoming.items():
                    if key not in PIPELINE_DEFAULTS[section]:continue
                    if key in ('key','password') and not value:continue
                    if key=='references':
                        if not isinstance(value,dict) or set(value)-set(PRESETS)-{'thoughtful'}:raise ValueError('参考动作类型无效')
                        clean={}
                        for kind,item in value.items():
                            if kind=='thoughtful':continue  # Retired; accept old settings without restoring its slot.
                            if not isinstance(item,dict):raise ValueError('参考素材配置无效')
                            duration=float(item.get('duration',0))
                            if not 2<=duration<=8:raise ValueError('参考短片须为2至8秒')
                            if item.get('file'):
                                name=item['file']
                                if not re.fullmatch(r'[a-f0-9]{32}\.mp4',name) or not (refs/name).is_file():raise ValueError('参考文件不存在')
                                duration=probe_video(refs/name)['duration']
                                clean[kind]={'file':name,'duration':duration}
                            else:clean[kind]={'url':valid_url(item.get('url','')),'duration':duration}
                        value=clean
                    elif section=='pricing':
                        value=float(value)
                        if not 0<=value<=100:raise ValueError('费率或预留次数超出范围')
                    elif not isinstance(value,str) or len(value)>2000:raise ValueError('配置内容无效')
                    elif key=='base_url':valid_url(value)
                    elif key=='url':
                        valid_url(value,('ws','wss'))
                        if value.split('://',1)[1].split(':',1)[0] not in ('localhost','127.0.0.1'):
                            raise ValueError('OBS目前仅连接本机127.0.0.1/localhost')
                    cfg[section][key]=value
                if incoming.get('clear_key'):cfg[section]['key']=''
                if incoming.get('clear_password'):cfg[section]['password']=''
            for section in ['vision','video']:
                if cfg[section]['proxy_mode'] not in ('system','manual','direct'):raise ValueError('代理模式无效')
                if cfg[section]['proxy_mode']=='manual':valid_url(cfg[section]['proxy_url'])
            if cfg['video']['mode'] not in ('wan-std','wan-pro'):raise ValueError('视频模式无效')
            if cfg['video']['model']!='wan2.2-animate-move':raise ValueError('此适配器只支持wan2.2-animate-move')
        except (ValueError,TypeError,KeyError) as exc:raise HTTPException(422,str(exc))
        settings.update(cfg);put_settings(settings)
        return {'ok':True}

    @app.post('/api/characters/references/{kind}')
    async def upload_reference(kind:str,file:UploadFile=File(...)):
        if kind not in PRESETS:raise HTTPException(422,'动作类型无效')
        raw=await file.read(20_000_001)
        if len(raw)>20_000_000 or raw[4:8]!=b'ftyp':raise HTTPException(422,'仅支持20MB以内的MP4参考片')
        path=refs/(uuid.uuid4().hex+'.mp4');path.write_bytes(raw)
        try:
            info=await asyncio.to_thread(probe_video,path)
            if not 2<=info['duration']<=8:raise ValueError('参考片须为2至8秒')
        except (ValueError,OSError) as exc:path.unlink(missing_ok=True);raise HTTPException(422,str(exc))
        settings=get_settings();cfg=pipeline_settings(settings)
        cfg['video']['references']=dict(cfg['video']['references'])|{kind:{'file':path.name,'duration':info['duration']}}
        settings.update(cfg);put_settings(settings)
        return {'reference':cfg['video']['references'][kind]}

    @app.get('/api/characters/quote')
    async def estimate():
        settings=get_settings();cfg=pipeline_settings(settings);missing=[]
        for section in ['vision','image','video']:
            if not settings.get(section,{}).get('key'):missing.append({'vision':'GPT视觉密钥','image':'图片服务密钥','video':'万相视频密钥'}[section])
        missing.extend(PRESETS[k]['label']+'参考视频' for k in PRESETS if k in REQUIRED_PRESETS and k not in cfg['video']['references'])
        if not ffprobe_binary():missing.append('FFmpeg/ffprobe视频检查工具（加入PATH后重启客户端）')
        if not media_binary('ffmpeg'):missing.append('FFmpeg透明视频整理工具（加入PATH后重启客户端）')
        return quote(settings)|{'missing':missing,'presets':PRESETS}

    @app.get('/api/characters')
    async def list_characters():
        jobs=[read_job(p.parent) for p in root.glob('*/job.json')]
        return {'jobs':sorted(jobs,key=lambda j:j['created'],reverse=True)[:40]}

    class CardName(BaseModel):
        name:str=Field(min_length=1,max_length=60)

    class CardEdit(BaseModel):
        name:str|None=Field(default=None,min_length=1,max_length=60)
        background_visible:bool|None=None

    @app.post('/api/characters/from-existing')
    async def from_existing(body:CardName):
        if tasks:raise HTTPException(409,'已有角色任务正在处理中')
        if not body.name.strip():raise HTTPException(422,'角色名称不能为空')
        try:folder,job=await asyncio.to_thread(create_local_card,data,get_settings(),body.name.strip())
        except (ValueError,OSError) as exc:raise HTTPException(422,str(exc))
        start(folder,local=True);return job

    @app.post('/api/characters/import')
    async def import_character(file:UploadFile=File(...)):
        raw=await file.read(MAX_CHARACTER_BYTES+1)
        if len(raw)>MAX_CHARACTER_BYTES:raise HTTPException(422,'角色包不能超过300MB')
        try:
            job=await asyncio.to_thread(import_card,raw,root);emit('character_job',job);return job
        except (ValueError,KeyError,TypeError,OSError,zipfile.BadZipFile,RuntimeError) as exc:
            raise HTTPException(422,'角色包校验失败：'+str(exc)[:160])

    class Build(BaseModel):
        name:str=Field(default='我的主播',min_length=1,max_length=60)
        quote_fingerprint:str
        budget_cny:float=Field(gt=0,le=1000)
        confirmed:bool=False

    @app.post('/api/characters/build')
    async def build(body:Build):
        settings=get_settings();cfg=pipeline_settings(settings);estimate=await estimate_impl()
        if not body.confirmed:raise HTTPException(422,'请确认预计费用后再生成')
        if estimate['fingerprint']!=body.quote_fingerprint or body.budget_cny<estimate['total_cny']:
            raise HTTPException(409,'报价已变化或预算不足，请重新核对')
        if estimate['missing']:raise HTTPException(409,'首次配置未完成：'+'、'.join(estimate['missing']))
        if tasks:raise HTTPException(409,'已有角色任务正在制作，请等待完成')
        source=data/'images'/Path(settings['avatar'].get('original','')).name
        if not source.is_file():raise HTTPException(422,'请先上传角色图片')
        ident=uuid.uuid4().hex;folder=root/ident;folder.mkdir()
        with Image.open(source) as im:ImageOps.exif_transpose(im).convert('RGB').save(folder/'reference.png')
        steps={r['kind']:{'status':'waiting','estimated_cny':r['cost_cny'],**({'rate_cny':r['rate_cny']} if 'rate_cny' in r else {})} for r in estimate['rows']}
        job={'format':'jibo-character','version':1,'id':ident,'name':body.name,'created':time.time(),'status':'running',
             'steps':steps,'quote':estimate,'budget_cny':body.budget_cny,'assets':{},'references':cfg['video']['references'],
             'providers':{'vision':cfg['vision']['model'],'video':cfg['video']['model'],'mode':cfg['video']['mode']},
             'provider_binding':provider_binding(settings),'accepted':False}
        job['costs']=charges(job);persist(folder,job);start(folder)
        return job

    # Keep the callable name distinct from the request parameter named body/quote.
    estimate_impl=estimate

    @app.get('/api/characters/{ident}')
    async def get_character(ident:str):return read_job(directory(ident))

    @app.patch('/api/characters/{ident}')
    async def rename_character(ident:str,body:CardEdit):
        folder=directory(ident);job=read_job(folder)
        if body.name is not None:job['name']=body.name.strip()
        if body.background_visible is not None:job['background_visible']=body.background_visible
        if not job['name']:raise HTTPException(422,'角色名称不能为空')
        persist(folder,job);emit('character_job',job)
        settings=get_settings()
        if settings['avatar'].get('character_id')==ident and settings['avatar'].get('mode')=='character':
            settings['avatar']['name']=job['name'];put_settings(settings);emit('settings',{'avatar':settings['avatar'],'title':settings.get('title','')})
        return job

    @app.post('/api/characters/{ident}/activate')
    async def activate_character(ident:str):
        folder=directory(ident);job=read_job(folder)
        try:validate_card(folder,job,accepted=True)
        except ValueError as exc:raise HTTPException(409,str(exc))
        if on_apply:await on_apply()
        settings=get_settings();settings['avatar'].update(mode='character',character_id=ident,name=job['name'],image=f'/media/characters/{ident}/standard.png')
        put_settings(settings);emit('settings',{'avatar':settings['avatar'],'title':settings.get('title','')})
        return {'ok':True,'avatar':settings['avatar']}

    @app.post('/api/characters/{ident}/continue')
    async def resume(ident:str):
        folder=directory(ident);job=read_job(folder);cfg=pipeline_settings(get_settings())
        if job.get('status') in ('review','accepted'):return job
        if job.get('local'):start(folder,local=True);return read_job(folder)
        if job.get('imported'):raise HTTPException(409,'导入素材不能继续云端制作')
        if job.get('provider_binding')!=provider_binding(get_settings()):
            raise HTTPException(409,'账户、接口或模型已变化，请恢复原任务配置后继续')
        if cfg['video']['mode']!=job['providers']['mode'] or cfg['video']['model']!=job['providers']['video']:
            raise HTTPException(409,'模型或模式已变化，不能继续原报价任务')
        if any(s['status']=='unknown' and not s.get('task_id') for s in job['steps'].values()):
            raise HTTPException(409,'有结果不明的提交，请先查供应商后台；禁止自动重复收费请求')
        start(folder);return read_job(folder)

    class Review(BaseModel):
        accepted:bool

    @app.post('/api/characters/{ident}/review')
    async def review(ident:str,body:Review):
        folder=directory(ident);job=read_job(folder)
        if not REQUIRED_PRESETS<=set(job['assets']):raise HTTPException(409,'请先完成基础动作，再人工检查动作、衣物、表情和切换；情绪说话可选')
        try:validate_card(folder,job)
        except ValueError as exc:raise HTTPException(409,str(exc))
        job.update(accepted=body.accepted,status='accepted' if body.accepted else 'review');persist(folder,job);emit('character_job',job)
        return job

    @app.get('/api/characters/{ident}/package')
    async def export_character(ident:str):
        folder=directory(ident);job=read_job(folder)
        try:raw=await asyncio.to_thread(export_card,folder,job)
        except ValueError as exc:raise HTTPException(409,str(exc))
        return Response(raw,media_type='application/zip',headers={'Content-Disposition':'attachment; filename="jibo-character.zip"'})

    return mark_interrupted,shutdown
