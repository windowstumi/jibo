"""Local character cards: package existing finished clips with FFmpeg, without AI calls."""
import asyncio
import io
import json
from pathlib import Path
import re
import shutil
import time
import uuid
import zipfile

from PIL import Image
from character_pipeline import PRESETS,REQUIRED_PRESETS,media_binary,probe_video,persist,read_job,transparent_video
from character_images import video_input_image,load_image,remove_chroma

MAX_CHARACTER_BYTES=300_000_000
MAX_PROJECT_BYTES=100_000_000


def character_persona(value):
    if not isinstance(value,str) or len(value)>2000:raise ValueError('角色设定须为不超过2000字的文字')
    return value.strip()


def save_input(data,kind,raw):
    if kind not in ('standard','background'):raise ValueError('未知素材类型')
    if len(raw)>10_000_000:raise ValueError('图片不能超过10MB')
    image=load_image(raw)
    if kind=='standard':image,_=remove_chroma(image)
    else:image=image.convert('RGB')
    path=data/'images'/(uuid.uuid4().hex+('.png' if kind=='standard' else '.jpg'))
    path.parent.mkdir(exist_ok=True);image.save(path)
    return '/media/images/'+path.name


def image_sources(data,settings):
    """Offer existing cutouts as inputs, including images from retired scene data."""
    sources=[]
    for folder in sorted((data/'characters').glob('*')):
        if re.fullmatch(r'[a-f0-9]{32}',folder.name) and (folder/'standard.png').is_file():
            job=read_job(folder)
            sources.append({'id':'character:'+folder.name,'name':job['name'],'image':f'/media/characters/{folder.name}/standard.png',
                            'background':f'/media/characters/{folder.name}/background.jpg' if (folder/'background.jpg').is_file() else None})
    for folder in sorted((data/'scenes').glob('*')):
        if re.fullmatch(r'[a-f0-9]{32}',folder.name) and (folder/'neutral.png').is_file():
            sources.append({'id':'scene:'+folder.name,'name':'历史人物图 · '+folder.name[:8],
                            'image':f'/media/scenes/{folder.name}/neutral.png',
                            'background':f'/media/scenes/{folder.name}/background.jpg' if (folder/'background.jpg').is_file() else None})
    inputs=settings.get('character_inputs',{})
    standard=inputs.get('standard','')
    if re.fullmatch(r'/media/images/[a-f0-9]{32}\.png',standard) and (data/'images'/Path(standard).name).is_file():
        sources.insert(0,{'id':'uploaded','name':'已上传的透明人物图','image':standard,'background':None})
    preferred=inputs.get('source_id') or ('character:'+settings['avatar'].get('character_id','') if settings['avatar'].get('mode')=='character' else 'scene:'+settings['avatar'].get('scene_id',''))
    selected=preferred if any(s['id']==preferred for s in sources) else sources[0]['id'] if sources else ''
    return {'sources':sources,'selected':selected,'background':inputs.get('background')}


def local_source(data,settings,source_id=''):
    available=image_sources(data,settings)
    source=next((s for s in available['sources'] if s['id']==(source_id or available['selected'])),None)
    if not source:raise ValueError('请先在角色制作上传透明正面人物图或选择历史人物图')
    background=available['background'] or source['background']
    return data/source['image'].removeprefix('/media/'), data/background.removeprefix('/media/') if background else None


def asset_filename(kind,asset):
    name=asset.get('file','')
    if kind not in PRESETS or name not in (kind+'.mp4',kind+'.webm'):
        raise ValueError('角色素材路径或格式无效')
    return name


def validate_card(folder,job,accepted=False):
    if not REQUIRED_PRESETS<=set(job.get('assets',{})):raise ValueError('五项基础动作尚未完成')
    if accepted and not job.get('accepted'):raise ValueError('请先预览并确认角色卡')
    if not (folder/'standard.png').is_file():raise ValueError('角色标准图缺失')
    for kind,asset in job['assets'].items():
        if kind not in PRESETS:continue
        name=asset_filename(kind,asset)
        if kind in REQUIRED_PRESETS and not (folder/name).is_file():raise ValueError('基础动作文件缺失：'+PRESETS[kind]['label'])


def export_card(folder,job):
    validate_card(folder,job)
    assets={kind:asset for kind,asset in job['assets'].items() if kind in PRESETS and (folder/asset_filename(kind,asset)).is_file()}
    files=['standard.png']+[asset['file'] for asset in assets.values()]
    if (folder/'background.jpg').is_file():files.append('background.jpg')
    if sum((folder/name).stat().st_size for name in files)>MAX_CHARACTER_BYTES-100_000:raise ValueError('角色卡超过300MB，请复制完整数据目录迁移')
    manifest={k:job[k] for k in ('format','version','id','name')}
    manifest['persona']=character_persona(job.get('persona',''))
    manifest.update(assets=assets,providers={k:v for k,v in job.get('providers',{}).items() if k in ('vision','video','mode')},
                    costs=job.get('costs',{}),background='background.jpg' if 'background.jpg' in files else None,
                    background_visible=job.get('background_visible',True))
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_STORED) as archive:
        archive.writestr('character.json',json.dumps(manifest,ensure_ascii=False,indent=2))
        for name in files:archive.write(folder/name,name)
    return output.getvalue()


def import_card(raw,root):
    if len(raw)>MAX_CHARACTER_BYTES:raise ValueError('角色卡不能超过300MB')
    folder=None
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries=archive.infolist();names=[e.filename for e in entries]
            allowed={'character.json','standard.png','background.jpg','thoughtful.mp4'}|{kind+ext for kind in PRESETS for ext in ('.mp4','.webm')}
            if len(names)!=len(set(names)) or not {'character.json','standard.png'}<=set(names) or set(names)-allowed or sum(e.file_size for e in entries)>MAX_CHARACTER_BYTES:
                raise ValueError('角色包内容或大小不符合要求')
            if archive.getinfo('character.json').file_size>100_000:raise ValueError('角色清单过大')
            manifest=json.loads(archive.read('character.json'))
            if not isinstance(manifest,dict) or manifest.get('format')!='jibo-character' or manifest.get('version') not in (1,2):raise ValueError('不支持的角色包版本')
            name=manifest.get('name')
            if not isinstance(name,str) or not 1<=len(name.strip())<=60:raise ValueError('角色名称无效')
            persona=character_persona(manifest.get('persona',''))
            folder=root/uuid.uuid4().hex;folder.mkdir(parents=True)
            with Image.open(io.BytesIO(archive.read('standard.png'))) as image:image.convert('RGBA').save(folder/'standard.png')
            assets={}
            for kind,preset in PRESETS.items():
                choices=[kind+ext for ext in ('.mp4','.webm') if kind+ext in names]
                if len(choices)>1:raise ValueError('同一动作不能重复提供两种视频')
                if not choices:
                    if kind in REQUIRED_PRESETS:raise ValueError('缺少基础动作：'+preset['label'])
                    continue
                path=folder/choices[0];path.write_bytes(archive.read(path.name))
                assets[kind]=preset|probe_video(path)|{'file':path.name,'background':'transparent' if path.suffix=='.webm' else 'opaque'}
            if 'background.jpg' in names:
                with Image.open(io.BytesIO(archive.read('background.jpg'))) as image:image.convert('RGB').save(folder/'background.jpg')
        job={'format':'jibo-character','version':manifest['version'],'id':folder.name,'name':name.strip(),'persona':persona,'created':time.time(),
             'status':'review','accepted':False,'imported':True,'assets':assets,'steps':{},'budget_cny':0,'providers':{},
             'background':'background.jpg' if (folder/'background.jpg').is_file() else None,'background_visible':manifest.get('background_visible',True) is not False,
             'costs':{'estimated_completed_cny':0,'uncertain_reserved_cny':0,'note':'导入已有素材，本次不调用生成服务。'}}
        persist(folder,job);return job
    except BaseException:
        if folder:shutil.rmtree(folder)
        raise


def create_local_card(data,settings,name,source_id='',persona=''):
    """Snapshot local finished clips. Reference actors/public URLs must not be packaged as a new character."""
    standard,background=local_source(data,settings,source_id)
    with Image.open(standard) as image:
        image=image.convert('RGBA');video_input_image(image)  # Reject opaque original posters.
    refs=settings.get('video',{}).get('references',{});inputs={}
    for kind in PRESETS:
        ref=refs.get(kind)
        if not ref:
            if kind in REQUIRED_PRESETS:raise ValueError('缺少成品视频：'+PRESETS[kind]['label'])
            continue
        filename=ref.get('file','')
        if not re.fullmatch(r'[a-f0-9]{32}\.mp4',filename) or not (data/'references'/filename).is_file():
            raise ValueError('请上传本地成品视频再创建角色卡：'+PRESETS[kind]['label'])
        inputs[kind]=data/'references'/filename
    if not media_binary('ffmpeg') or not media_binary('ffprobe'):raise ValueError('本地整理角色需要FFmpeg和ffprobe，请安装并加入PATH后重启')
    folder=data/'characters'/uuid.uuid4().hex;folder.mkdir(parents=True)
    try:
        image.save(folder/'standard.png')
        for kind,source in inputs.items():shutil.copy2(source,folder/('input-'+kind+'.mp4'))
        if background and background.is_file():shutil.copy2(background,folder/'background.jpg')
        job={'format':'jibo-character','version':2,'id':folder.name,'name':name,'persona':character_persona(persona),'created':time.time(),
             'status':'assembling','local':True,'accepted':False,'assets':{},'budget_cny':0,'providers':{},
             'background':'background.jpg' if (folder/'background.jpg').is_file() else None,
             'steps':{kind:{'status':'waiting','estimated_cny':0} for kind in inputs},
             'costs':{'estimated_completed_cny':0,'uncertain_reserved_cny':0,'note':'本地整理已有视频，不调用生成服务。'}}
        persist(folder,job);return folder,job
    except BaseException:
        shutil.rmtree(folder);raise


async def assemble_local_card(folder,emit):
    job=read_job(folder);job.update(status='assembling',error=None)
    def save():persist(folder,job);emit('character_job',job)
    try:
        save()
        for kind,step in job['steps'].items():
            if step['status']=='done':continue
            if kind not in PRESETS:continue
            step['status']='running';save()
            target=folder/(kind+'.webm')
            await transparent_video(folder/('input-'+kind+'.mp4'),target)
            info=await asyncio.to_thread(probe_video,target)
            job['assets'][kind]=PRESETS[kind]|info|{'file':target.name,'background':'transparent'}
            step.update(status='done',media=info);save()
        validate_card(folder,job);job.update(status='review');save()
    except asyncio.CancelledError:
        job.update(status='interrupted',error='本地整理已暂停，可继续，无生成费用。');save();raise
    except Exception as exc:
        job.update(status='interrupted',error=str(exc)[:250]);save()
    finally:
        for path in folder.glob('*.tmp.webm'):path.unlink(missing_ok=True)
