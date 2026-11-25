"""Generate and bind a portable 2.5D character scene, without a GPU runtime."""
import asyncio
import io
import json
import math
from pathlib import Path
import time
import uuid

import numpy as np
from PIL import Image, ImageFilter, ImageDraw, ImageChops

from image_service import image_client, endpoint, image_payload, response_json, download_result

STEPS = ('neutral', 'speaking', 'blink', 'background')
LABELS = {'neutral':'标准正面角色', 'speaking':'同角色说话表情', 'blink':'同角色闭眼表情', 'background':'独立完整背景'}
PROMPTS = {
    'neutral': '''Create one standardized 2D illustrated character asset based on the reference. Analyze the input pose and change it to a STRICTLY FRONT-FACING, upright neutral full-body standing pose. Preserve the same identity, hairstyle, hair color, eyes, costume, accessories and illustration style. Face forward, no head tilt. Both hands relaxed below the waist, not touching face. Eyes open, mouth closed, neutral friendly expression. Show the ENTIRE character including shoes, with 6% margin top and bottom. Character centered at x=50%; top of head at y=6%, chin at about y=24%, waist y=46%, feet y=94%. Long hair, ribbon and skirt must remain visible. Put character on a perfectly flat solid chroma green background RGB(0,255,0), no shadows on background, no scenery, no floor. Do not add labels, frames, props or additional characters. This is a rigging asset, not a poster.''',
    'speaking': '''Edit this exact character rig asset. Keep the entire image, pixel framing, head location, hairstyle, eye position, body, costume, hands, pose, background and image dimensions IDENTICAL. Change ONLY the existing mouth and immediately surrounding cheeks to a naturally open speaking mouth, showing dark mouth interior and a small amount of upper teeth. Do not move or enlarge the head. Eyes remain open. No new body pose. Preserve the flat RGB(0,255,0) background. Output one full image, not a collage.''',
    'blink': '''Edit this exact character rig asset. Keep the entire image, pixel framing, head location, hairstyle, mouth, body, costume, hands, pose, background and image dimensions IDENTICAL. Change ONLY both eyes to naturally closed relaxed eyelids (a blink). Mouth stays closed. Do not move or enlarge the head. Preserve the flat RGB(0,255,0) background. Output one full image, not a collage.''',
    'background': '''Create only the background scenery suggested by this reference image, preserving its illustration style, palette and atmosphere. REMOVE ALL characters, people, faces, hands, costumes and their shadows. Reconstruct and paint the full scenery behind the removed character: natural depth, soft atmospheric light, gentle clouds or foliage where appropriate. An empty clean illustration background suitable for a virtual presenter. No people, no text, no logos, no foreground character silhouettes. Fill the entire canvas with scenery.''',
}


def write_json(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2),encoding='utf-8')
    temp.replace(path)


def load_image(raw):
    if len(raw)>15_000_000:
        raise ValueError('生成图超过15MB')
    with Image.open(io.BytesIO(raw)) as image:
        if image.width*image.height>24_000_000:
            raise ValueError('生成图像素过大')
        return image.convert('RGBA')


def remove_chroma(image):
    """Only remove green connected to the outside, preserving green eye/costume detail."""
    from collections import deque
    image = image.convert('RGBA')
    pixels = np.asarray(image).copy()
    if np.mean(pixels[:,:,3]<20) > .08:
        return image, {'matting':'alpha', 'background_removed':True}
    small = np.asarray(image.resize((256,256),Image.Resampling.BILINEAR)).astype(np.int16)
    r,g,b=small[:,:,0],small[:,:,1],small[:,:,2]
    candidates = (g>105)&(g-r>38)&(g-b>28)
    outside=np.zeros((256,256),dtype=bool)
    queue=deque()
    for i in range(256):
        for y,x in ((0,i),(255,i),(i,0),(i,255)):
            if candidates[y,x] and not outside[y,x]:outside[y,x]=True;queue.append((y,x))
    while queue:
        y,x=queue.popleft()
        for yy,xx in ((y-1,x),(y+1,x),(y,x-1),(y,x+1)):
            if 0<=yy<256 and 0<=xx<256 and candidates[yy,xx] and not outside[yy,xx]:
                outside[yy,xx]=True;queue.append((yy,xx))
    if outside.mean()<.08:
        raise ValueError('角色图没有透明背景或可识别的纯绿幕。此步保留原结果，请人工检查后再决定是否重新生成。')
    bg=Image.fromarray((outside*255).astype(np.uint8)).resize(image.size,Image.Resampling.BILINEAR)
    rgb=pixels[:,:,:3].astype(np.int16)
    red,green,blue=rgb[:,:,0],rgb[:,:,1],rgb[:,:,2]
    strong=(green>145)&(green-np.maximum(red,blue)>65)
    # Include enclosed key-colored holes between arms and torso. White clothing must stay white.
    expanded=np.asarray(bg.filter(ImageFilter.MaxFilter(7)))>0
    key_region=expanded|strong
    strength=np.clip((green-np.maximum(red,blue)-15)/75,0,1)
    alpha=np.where(key_region,255*(1-strength),255).astype(np.uint8)
    pixels[:,:,3]=np.minimum(pixels[:,:,3],alpha)
    # Remove green spill only along semi-transparent matte boundaries.
    edge=key_region&(green>np.maximum(red,blue)+12)
    pixels[:,:,1][edge]=np.minimum(green[edge],np.maximum(red[edge],blue[edge])+8).astype(np.uint8)
    pixels[pixels[:,:,3]==0,:3]=0
    return Image.fromarray(pixels),{'matting':'connected-green-screen','background_removed':True,'removed_ratio':round(float(outside.mean()),3)}


def derive_rig(image):
    alpha=np.asarray(image)[:,:,3]
    ys,xs=np.nonzero(alpha>80)
    if len(xs)<image.width*image.height*.04:
        raise ValueError('角色有效面积过小，无法绑定')
    w,h=image.size
    left,right=float(xs.min()/w),float((xs.max()+1)/w)
    top,bottom=float(ys.min()/h),float((ys.max()+1)/h)
    height=bottom-top
    cx=(left+right)/2
    # Standard pose placement is part of the generation contract; coordinates remain editable.
    return {'head_x':cx,'head_y':top+height*.14,'neck_y':top+height*.235,
            'eye_y':top+height*.125,'mouth_y':top+height*.185,'face_width':min(.26,(right-left)*.45),
            'waist_y':top+height*.46,'skirt_y':top+height*.53,'skirt_end':top+height*.68,
            'wind':.5,'breath':.5,'motion':.5,'background_motion':.35,'particles':.35,
            'bounds':[left,top,right,bottom]}


def register_expression(neutral, expression, rig):
    """Translate the generated head back to the neutral head; no detached mouth overlay."""
    expression=expression.resize(neutral.size,Image.Resampling.LANCZOS)
    size=256
    a=np.asarray(neutral.resize((size,size))).astype(np.float32)
    b=np.asarray(expression.resize((size,size))).astype(np.float32)
    yy,xx=np.mgrid[:size,:size]
    head=((xx/size-rig['head_x'])/(rig['face_width']*.9))**2+((yy/size-rig['head_y'])/.14)**2<1
    # Hair boundary anchors alignment; exclude feature interiors that intentionally change.
    mask=head&(a[:,:,3]>180)&((yy/size<rig['eye_y']-.025)|(abs(xx/size-rig['head_x'])>rig['face_width']*.3))
    best=(float('inf'),0,0)
    for dy in range(-10,11):
        for dx in range(-10,11):
            shifted=np.roll(b,(dy,dx),(0,1))
            valid=mask&(shifted[:,:,3]>180)
            if valid.sum()<20:continue
            score=float(np.mean(abs(a[:,:,:3][valid]-shifted[:,:,:3][valid])))
            if score<best[0]:best=(score,dx,dy)
    score,dx,dy=best
    aligned=Image.new('RGBA',neutral.size)
    aligned.alpha_composite(expression,(round(dx*neutral.width/size),round(dy*neutral.height/size)))
    return aligned,{'offset':[dx/size,dy/size],'alignment_error':round(score,2),'review_required':score>35}


def expression_center(neutral,variant,kind):
    """Infer feature positions from the AI edit itself; no extra paid vision request."""
    size=256
    a=np.asarray(neutral.resize((size,size))).astype(np.float32)
    b=np.asarray(variant.resize((size,size))).astype(np.float32)
    diff=np.maximum(np.mean(abs(a[:,:,:3]-b[:,:,:3]),axis=2)-12,0)
    yy,xx=np.mgrid[:size,:size]
    diff*=((a[:,:,3]>160)&(b[:,:,3]>160)&(yy>size*.025)&(yy<size*.30)&(xx>size*.33)&(xx<size*.67))
    # Find the most changed compact facial area, rather than averaging image-wide noise.
    heat=np.asarray(Image.fromarray(np.clip(diff*3,0,255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3)))
    peak_y,peak_x=np.unravel_index(np.argmax(heat),heat.shape)
    if heat[peak_y,peak_x]<8:return None
    window=(abs(xx-peak_x)<(24 if kind=='blink' else 14))&(abs(yy-peak_y)<9)
    weights=diff*window
    if weights.sum()<1:return None
    return [float((weights*xx).sum()/weights.sum()/size),float((weights*yy).sum()/weights.sum()/size)]


def validate_cloth_polygon(points):
    if not isinstance(points, list) or not 3 <= len(points) <= 16:
        raise ValueError('衣料范围需要3至16个边界点')
    clean=[]
    for point in points:
        if not isinstance(point,(list,tuple)) or len(point)!=2:
            raise ValueError('衣料范围坐标无效')
        x,y=point
        if isinstance(x,bool) or isinstance(y,bool) or not isinstance(x,(int,float)) or not isinstance(y,(int,float)) or not math.isfinite(x) or not math.isfinite(y) or not 0<=x<=1 or not 0<=y<=1:
            raise ValueError('衣料范围坐标必须在0到1之间')
        clean.append([float(x),float(y)])
    area=abs(sum(clean[i][0]*clean[(i+1)%len(clean)][1]-clean[(i+1)%len(clean)][0]*clean[i][1] for i in range(len(clean))))/2
    if area<.001 or area>.7:
        raise ValueError('衣料范围面积无效')
    return clean


def default_cloth_polygon(image, rig):
    """Conservative central dress area. Never extend below the estimated hem."""
    alpha=np.asarray(image)[:,:,3]>80
    h,w=alpha.shape
    top=rig['skirt_y'];bottom=rig['skirt_end']
    if bottom<=top+.015:
        bottom=min(.95,top+.08)
    cx=rig['head_x']
    samples=[]
    for y in np.linspace(top,bottom,5):
        row=alpha[min(h-1,round(y*h))]
        xs=np.nonzero(row)[0]
        runs=np.split(xs,np.where(np.diff(xs)>1)[0]+1) if len(xs) else []
        runs=[run for run in runs if len(run)>3]
        # Arms/hands often sit at the same height as the skirt but form separate silhouettes.
        center_run=min(runs,key=lambda run:min(abs(run/w-cx))) if runs else np.array([])
        half=min(.24,max(.04,min(cx-center_run.min()/w,center_run.max()/w-cx)-.012)) if len(center_run) else .1
        samples.append((float(y),float(half)))
    return [[cx-half,y] for y,half in samples]+[[cx+half,y] for y,half in reversed(samples)]


def write_cloth_mask(directory, model):
    image=Image.open(directory/'neutral.png').convert('RGBA')
    polygon=validate_cloth_polygon(model['cloth']['polygon'])
    hard=Image.new('L',image.size)
    ImageDraw.Draw(hard).polygon([(round(x*(image.width-1)),round(y*(image.height-1))) for x,y in polygon],fill=255)
    hard=ImageChops.multiply(hard,image.getchannel('A'))
    # Inward-only feather: outside the selected fabric is exactly zero, including exposed legs.
    inset=hard.filter(ImageFilter.MinFilter(7))
    soft=ImageChops.darker(hard,inset.filter(ImageFilter.GaussianBlur(3)))
    soft.save(directory/'cloth-mask.png')
    make_layers(image, model['rig'], directory, soft)
    model['textures']['cloth_mask']='cloth-mask.png'
    model['cloth']['method']='masked-texture-flow'
    return model


def ensure_cloth_model(directory, model=None):
    path=directory/'model.json'
    model=model or json.loads(path.read_text(encoding='utf-8'))
    if model.get('cloth',{}).get('method')!='masked-texture-flow' or not (directory/'cloth-mask.png').exists():
        with Image.open(directory/'neutral.png') as image:
            polygon=model.get('cloth',{}).get('polygon') or default_cloth_polygon(image.convert('RGBA'),model['rig'])
        model['cloth']={'polygon':polygon,'method':'masked-texture-flow'}
        write_cloth_mask(directory,model)
        model['revision']=uuid.uuid4().hex[:12]
        write_json(path,model)
    return model


def make_layers(neutral, rig, directory, cloth_mask=None):
    """Overlapping feathered regions preserve the complete silhouette when deformed."""
    arr=np.asarray(neutral).copy();w,h=neutral.size
    yy,xx=np.mgrid[:h,:w];y=yy/h;x=xx/w
    head=1-np.clip((y-(rig['neck_y']-.04))/.10,0,1)
    skirt=np.asarray(cloth_mask)/255 if cloth_mask is not None else np.zeros((h,w))
    body=np.clip(1-head-skirt,0,1)
    for name,mask in [('head',head),('body',body),('skirt',skirt)]:
        layer=arr.copy();layer[:,:,3]=(arr[:,:,3]*mask).astype(np.uint8)
        Image.fromarray(layer).save(directory/(name+'.png'))


def compile_model(directory):
    neutral,quality=remove_chroma(load_image((directory/'neutral.raw.png').read_bytes()))
    neutral.thumbnail((768,1024),Image.Resampling.LANCZOS)
    rig=derive_rig(neutral)
    neutral.save(directory/'neutral.png')
    checks={'neutral':quality,'warnings':[]}
    variants={}
    for name in ('speaking','blink'):
        variant,q=remove_chroma(load_image((directory/(name+'.raw.png')).read_bytes()))
        aligned,alignment=register_expression(neutral,variant,rig)
        aligned.save(directory/(name+'.png'))
        variants[name]=aligned
        checks[name]=q|alignment
        if alignment['review_required']:checks['warnings'].append(LABELS[name]+'与标准脸对齐误差较高，请预览并调整面部范围。')
    mouth=expression_center(neutral,variants['speaking'],'speaking')
    eyes=expression_center(neutral,variants['blink'],'blink')
    if mouth and eyes and mouth[1]>eyes[1]:
        rig.update(head_x=mouth[0],mouth_y=mouth[1],eye_y=eyes[1],head_y=(mouth[1]+eyes[1])/2,
                   neck_y=min(mouth[1]+max(.035,(mouth[1]-eyes[1])*.8),.4))
        checks['feature_detection']={'method':'expression-difference','mouth':mouth,'eyes':eyes}
    else:
        checks['warnings'].append('面部自动定位置信度不足，请调整眼睛、嘴巴和颈部高度。')
    # Locate a likely waist in the standardized silhouette, above the skirt's widest section.
    alpha=np.asarray(neutral)[:,:,3]>80
    start=int(neutral.height*.28);end=int(neutral.height*.50)
    widths=np.sum(alpha[start:end,:],axis=1)
    if len(widths):
        waist=(start+int(np.argmin(widths)))/neutral.height
        rig['waist_y']=max(rig['neck_y']+.10,waist)
        rig['skirt_y']=min(.70,rig['waist_y']+.08)
        lo=int((rig['waist_y']+.12)*neutral.height);hi=int(.8*neutral.height)
        profile=np.sum(alpha,axis=1).astype(float)
        drops=profile[lo:hi]-profile[min(lo+12,len(profile)):min(hi+12,len(profile))]
        if len(drops):rig['skirt_end']=(lo+int(np.argmax(drops)))/neutral.height
    background=load_image((directory/'background.raw.png').read_bytes())
    background.thumbnail((1536,1536),Image.Resampling.LANCZOS)
    background.convert('RGB').save(directory/'background.jpg',quality=93)
    cloth={'polygon':default_cloth_polygon(neutral,rig),'method':'masked-texture-flow'}
    # Full textures plus a deformable mesh are the authoritative model. Region layers are inspectable exports.
    model={'format':'yingbo-scene','version':1,'id':directory.name,'width':neutral.width,'height':neutral.height,
           'textures':{'neutral':'neutral.png','speaking':'speaking.png','blink':'blink.png','background':'background.jpg'},
           'layers':{'head':'head.png','body':'body.png','skirt':'skirt.png'},
           'mesh':{'columns':28,'rows':40},'rig':rig,'cloth':cloth,'quality':checks,'revision':uuid.uuid4().hex[:12],
           'limitations':['模板自动绑定，可在客户端调整关键点','表情为AI生成的全脸纹理混合，非音素级口型','衣料流动限制在显式遮罩内，保持轮廓固定以保护肢体']}
    write_cloth_mask(directory,model)
    write_json(directory/'model.json',model)
    return model


def public_job(directory):
    path=directory/'job.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


async def generate_asset(cfg, source, prompt):
    async with image_client(cfg,timeout=240) as client:
        response=await client.post(endpoint(cfg['base_url'],'/images/edits'),headers={'Authorization':'Bearer '+cfg['key']},
            data={'model':cfg['model'],'prompt':prompt,'size':'1024x1024'},files={'image':('reference.png',source,'image/png')})
    payload=image_payload(response_json(response,cfg))
    return await download_result(payload,cfg) if isinstance(payload,str) else payload


async def build_scene(directory, cfg, original, description='', on_progress=None):
    """One call per missing step. Never silently repeat a submitted generation."""
    job=public_job(directory)
    try:
        for step in STEPS:
            if (directory/(step+'.raw.png')).exists():continue
            if job['steps'][step]['status']=='submitted':
                raise ValueError(f'{LABELS[step]}先前已提交但未取得结果。为避免重复扣费，请先查询服务商后台。')
            job['status']='running';job['current']=step;job['steps'][step]={'status':'submitted','started':time.time()}
            write_json(directory/'job.json',job)
            if on_progress:on_progress(job)
            source=original if step in ('neutral','background') else (directory/'neutral.raw.png').read_bytes()
            extra=(' User style preferences: '+description[:600]) if step in ('neutral','background') else ''
            raw=await generate_asset(cfg,source,PROMPTS[step]+extra)
            image=load_image(raw)
            image.save(directory/(step+'.raw.png'))
            job['steps'][step]={'status':'done','finished':time.time()}
            write_json(directory/'job.json',job)
            if on_progress:on_progress(job)
        job['current']='compile';write_json(directory/'job.json',job)
        if on_progress:on_progress(job)
        model=await asyncio.to_thread(compile_model,directory)
        job.update(status='review',current='done',model_id=model['id'],error=None)
        write_json(directory/'job.json',job)
        if on_progress:on_progress(job)
        return model
    except asyncio.CancelledError:
        job.update(status='interrupted',error='任务中断，已提交的生成不会自动重试。')
        write_json(directory/'job.json',job)
        raise
    except Exception:
        # Caller records a user-safe provider/network error, without credentials.
        job.update(status='failed');write_json(directory/'job.json',job)
        raise


def new_job(root, original):
    directory=root/uuid.uuid4().hex
    directory.mkdir(parents=True)
    (directory/'source.png').write_bytes(original)
    write_json(directory/'job.json',{'id':directory.name,'status':'pending','current':'neutral','created':time.time(),
        'steps':{step:{'status':'pending'} for step in STEPS},'error':None})
    return directory
