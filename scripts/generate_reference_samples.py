"""Make three isolated I2V samples, reusing the project's HTTP and download helpers.

Default is a local preparation only. --submit authorizes at most three initial
requests; interrupted submissions are never repeated, known task IDs only polled.
"""
import argparse
import asyncio
import base64
from contextlib import closing
import hashlib
import io
import json
from pathlib import Path
import re
import sqlite3
import sys
import time

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from PIL import Image,ImageOps
from character_pipeline import (pipeline_settings,video_base,provider_json,query_video,
                                download_video,probe_video,ffprobe_binary)
from image_service import image_client,safe_detail
from scene_model import video_input_image

MODEL='wan2.2-i2v-flash'
DEFAULT_KINDS=('idle','talk','thanks')
RATE_CNY_SECOND=.10  # Beijing official 480P price, checked 2026-11-26.
COMMON=('二维动漫插画人物动画，严格保持参考图片中同一个角色的脸、蓝色短发、发饰、服装结构、配色和插画画风。'
        '正面全身角色，镜头固定，构图、视角和人物比例不变，始终完整保留头顶、双手和鞋子，不运镜，不切镜。'
        '背景始终为完全均匀的纯绿色RGB(0,255,0)，无场景、地面、阴影、文字和新道具。'
        '保持正面站姿与手的位置，不转身，不改变原有服装覆盖范围。'
        '头发、袖口、裙边只有轻柔自然的微动，躯干、腿部和服装结构稳定，不让衣服拖动肢体。'
        '开头约0.5秒保持参考姿态，结尾约0.5秒回到参考姿态并自然闭嘴。')
PROMPTS={
    'idle':COMMON+'这5秒中角色安静待机，嘴唇自然闭合，有轻微呼吸、一次自然眨眼和极小幅身体晃动，表情温和。动作克制，不说话，不招手，不鞠躬。',
    'talk':COMMON+'这5秒中角色像在友好介绍商品，中间3秒嘴唇自然、清晰、反复小幅张开闭合，不能只保持静态微笑；眼神温和，有自然眨眼和轻微点头。不要求匹配具体文字，不做大幅手势。',
    'thanks':COMMON+'这5秒中角色完成一次温柔答谢：先展露开心微笑，在中间缓慢轻轻低头点头致谢，再自然抬头回到原姿态。嘴唇中间有小幅开合，表现短句感谢。不深鞠躬，不弯腰，不移动双手，不改变身体和腿部结构。',
}
ACTION_COMMON=COMMON.replace('保持正面站姿与手的位置','保持正面站姿')
PROMPTS.update({
    'present':ACTION_COMMON+'这5秒中角色完成一次介绍手势：先保持原站姿约0.5秒，然后只把一只手从身侧缓缓抬到腰胸之间，向身体侧方小幅展开前臂，手掌自然摊开、掌心朝上，像向观众展示旁边的一件商品；另一只手放松停留身侧。温和微笑，不拿任何物品，不指向自己脸部，不合掌，不鞠躬。动作后平缓放下手，最后约1秒双手回到与首帧完全一致的身侧位置，嘴唇闭合，正面站定。',
    'greeting':ACTION_COMMON+'这5秒中角色完成一次微笑招手：先保持原站姿约0.5秒，露出友好微笑，只将一只手抬到肩部高度，手掌朝向镜头，轻柔地左右挥手两次。另一只手始终放松停留身侧，身体保持正面直立，不转身，不合掌，不鞠躬。随后自然放下手，最后约1秒双手回到与首帧完全一致的身侧位置，嘴唇闭合，正面站定。',
})
NEGATIVE='镜头移动，推拉摇移，切镜，背景场景，地面，阴影，背景变动，变脸，真人写实，3D风格，服装改变，肢体扭曲，腿部变形，多余手指，多余肢体，手遮挡嘴，夸张张嘴，文字，字幕，水印，新增道具'


def prepared_image(data,settings):
    """Use the accepted front cutout; never fall back to the original poster."""
    ident=settings.get('avatar',{}).get('scene_id','')
    if not isinstance(ident,str) or not re.fullmatch(r'[a-f0-9]{32}',ident):raise ValueError('请先制作并选择透明正面角色，不能直接使用带背景原图')
    source=data/'scenes'/ident/'neutral.png'
    with Image.open(source) as im:character=ImageOps.exif_transpose(im).convert('RGBA')
    original=io.BytesIO();character.save(original,'PNG')
    encoded=io.BytesIO();video_input_image(character).save(encoded,'PNG')
    return source,original.getvalue(),encoded.getvalue()


class SubmissionRejected(ValueError):
    """Explicit provider rejection without a task, distinct from an ambiguous timeout."""


def payload(image_url,kind):
    return {'model':MODEL,'input':{'img_url':image_url,'prompt':PROMPTS[kind],'negative_prompt':NEGATIVE},
            'parameters':{'resolution':'480P','duration':5,'prompt_extend':False,'watermark':False}}


def save(folder,job):
    path=folder/'manifest.json';temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)


async def submit(image_url,kind,cfg):
    async with image_client(cfg,timeout=90) as client:
        response=await client.post(video_base(cfg)+'/services/aigc/video-generation/video-synthesis',
            headers={'Authorization':'Bearer '+cfg['key'],'X-DashScope-Async':'enable'},json=payload(image_url,kind))
    if 400<=response.status_code<500:
        try:provider_json(response,cfg)
        except ValueError as exc:raise SubmissionRejected(str(exc)) from None
    output=provider_json(response,cfg).get('output',{})
    ident=output.get('task_id')
    if not isinstance(ident,str) or not re.fullmatch(r'[\w-]{1,100}',ident):raise ValueError('没有可靠任务编号，禁止重复提交')
    return ident


async def run(data,budget,paid,kinds=DEFAULT_KINDS,batch=None):
    if not kinds or len(set(kinds))!=len(kinds) or set(kinds)-set(PROMPTS):raise ValueError('动作选择无效')
    if batch and not re.fullmatch(r'[a-z0-9-]{1,50}',batch):raise ValueError('批次名称无效')
    with closing(sqlite3.connect('file:'+str((data/'studio.sqlite3').resolve()).replace('\\','/')+'?mode=ro',uri=True)) as db:
        settings=json.loads(db.execute("SELECT value FROM kv WHERE key='settings'").fetchone()[0])
    cfg=pipeline_settings(settings)['video'];cfg['model']=MODEL
    if not cfg['key']:raise ValueError('没有万相密钥')
    if cfg['base_url'].rstrip('/')!='https://dashscope.aliyuncs.com':
        raise ValueError('此报价仅适用于已配置的北京地域dashscope接口，其他渠道需重新核价')
    if not ffprobe_binary():raise ValueError('缺少ffprobe，停止付费请求')
    source,character_raw,raw=prepared_image(data,settings)
    source_hash=hashlib.sha256(raw).hexdigest()
    folder=data/'reference-samples'/('20261126-'+source_hash[:12]+('-'+batch if batch else ''));folder.mkdir(parents=True,exist_ok=True)
    binding=hashlib.sha256((cfg['base_url']+cfg['key']+MODEL).encode()).hexdigest()
    path=folder/'manifest.json'
    if path.exists():
        job=json.loads(path.read_text(encoding='utf-8'))
        if job['provider_binding']!=binding:raise ValueError('账户变化，禁止继续原任务')
        if set(job['steps'])!=set(kinds):raise ValueError('本批动作清单已固定，不能追加收费任务')
    else:
        job={'model':MODEL,'source_sha256':source_hash,'provider_binding':binding,'budget_cny':budget,
             'source_asset':str(source.relative_to(data)),'source_kind':'front-transparent-character','input_background':'temporary-chroma-green',
             'price_source':'https://help.aliyun.com/zh/model-studio/model-pricing','rate_cny_second':RATE_CNY_SECOND,
             'estimated_total_cny':round(len(kinds)*.5,2),'resolution':'480P','seconds_each':5,'accepted':False,
             'budget_group':batch or 'initial-reference-samples',
             'steps':{kind:{'status':'waiting','estimated_cny':.5,'prompt':PROMPTS[kind]} for kind in kinds}}
        (folder/'source.png').write_bytes(character_raw);(folder/'input.png').write_bytes(raw);save(folder,job)
    if budget<job['estimated_total_cny'] or budget>3 or budget!=job['budget_cny']:raise ValueError('预算必须与原批准一致，且不超过3元')
    previous_reserved=0
    for other in (data/'reference-samples').glob('*/manifest.json'):
        if other==path:continue
        previous=json.loads(other.read_text(encoding='utf-8'))
        if previous.get('budget_group','initial-reference-samples')!=(batch or 'initial-reference-samples'):continue
        previous_reserved+=sum(step.get('estimated_cny',0) for step in previous['steps'].values() if step['status']!='waiting')
    if previous_reserved+job['estimated_total_cny']>budget+.0001:raise ValueError('本预算组累计保守预留超出批准金额，停止新增收费请求')
    job['previous_reserved_cny']=previous_reserved;save(folder,job)
    print('Samples: '+str(folder),flush=True)
    print('New estimate CNY '+str(job['estimated_total_cny'])+'; prior reserved CNY '+str(previous_reserved)+'; group maximum CNY '+str(budget)+'; no paid retries.',flush=True)
    if not paid:return
    image_url='data:image/png;base64,'+base64.b64encode(raw).decode()
    for kind,step in job['steps'].items():
        if step['status']=='done' or (step['status']=='failed' and step.get('task_id')):continue
        if not step.get('task_id'):
            if step['status']!='waiting':raise ValueError(kind+'结果不明或已失败，禁止重复付费')
            step.update(status='submitted',submitted_at=time.time());save(folder,job)
            try:step['task_id']=await submit(image_url,kind,cfg)
            except BaseException as exc:
                step.update(status='rejected' if isinstance(exc,SubmissionRejected) else 'unknown',error=safe_detail(str(exc),cfg))
                save(folder,job);raise
            step['status']='pending';save(folder,job)
        print(kind+': original task '+step['task_id'],flush=True)
        deadline=time.monotonic()+1200;previous=None
        while True:
            try:
                response=await query_video(step['task_id'],cfg);out=response.get('output',{});status=out.get('task_status')
                if status!=previous:print(kind+': '+str(status),flush=True);previous=status
                if status=='SUCCEEDED':
                    results=out.get('results',{});url=out.get('video_url') or (results.get('video_url') if isinstance(results,dict) else None)
                    if not url:raise ValueError('成功但缺少下载地址，仅能查询原任务')
                    media=folder/(kind+'.mp4')
                    if not media.exists():await download_video(url,media,cfg)
                    info=await asyncio.to_thread(probe_video,media)
                    step.update(status='done',media=info,usage=response.get('usage',{}),file=media.name)
                    save(folder,job);break
                if status in ('FAILED','CANCELED','UNKNOWN'):
                    step.update(status='failed',error=safe_detail(out.get('message') or out.get('code') or status,cfg),provider_code=out.get('code'))
                    save(folder,job);print(kind+' failed; no retry: '+step['error'],flush=True);break
                if status not in ('PENDING','RUNNING'):raise ValueError('任务状态不兼容，只查询原任务')
                step['status']=status.lower();save(folder,job)
                if time.monotonic()>deadline:raise ValueError('等待超过20分钟，已保存任务编号，不重复提交')
                await asyncio.sleep(8)
            except BaseException as exc:
                step['error']=safe_detail(str(exc),cfg);save(folder,job);raise
    completed=sum(step['status']=='done' for step in job['steps'].values())
    print(str(completed)+'/'+str(len(kinds))+' samples downloaded. Manual review required; existing reference library unchanged.',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',type=Path,required=True)
    parser.add_argument('--budget',type=float,default=3)
    parser.add_argument('--submit',action='store_true')
    parser.add_argument('--kinds',nargs='+',choices=list(PROMPTS),default=list(DEFAULT_KINDS))
    parser.add_argument('--batch',help='Explicit new request and independent budget group; never change an existing batch')
    args=parser.parse_args()
    try:asyncio.run(run(args.data_dir.resolve(),args.budget,args.submit,args.kinds,args.batch))
    except Exception as exc:
        # Provider errors were already sanitized where they entered the ledger.
        print('Stopped: '+str(exc)[:300],file=sys.stderr);sys.exit(1)
