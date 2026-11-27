"""Shared image preparation for video characters; no mesh or rig generation."""
import io
import json
import numpy as np
from PIL import Image, ImageFilter
from image_service import image_client, endpoint, image_payload, response_json, download_result


def write_json(path,data):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(path)

STANDARD_PROMPT = 'Create one standardized 2D illustrated character asset based on the reference. Analyze the input pose and change it to a STRICTLY FRONT-FACING, upright neutral full-body standing pose. Preserve the same identity, hairstyle, hair color, eyes, costume, accessories and illustration style. Face forward, no head tilt. Both hands relaxed below the waist, not touching face. Eyes open, mouth closed, neutral friendly expression. Show the ENTIRE character including shoes, with 6% margin top and bottom. Character centered at x=50%; top of head at y=6%, chin at about y=24%, waist y=46%, feet y=94%. Long hair, ribbon and skirt must remain visible. Put character on a perfectly flat solid chroma green background RGB(0,255,0), no shadows on background, no scenery, no floor. Do not add labels, frames, props or additional characters. This is a rigging asset, not a poster.'

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

def video_input_image(character):
    """Keep the cutout separate; APIs without alpha receive a temporary chroma plate."""
    character=character.convert('RGBA');alpha=character.getchannel('A')
    if sum(alpha.histogram()[:20])<character.width*character.height*.08 or not alpha.getbbox():
        raise ValueError('视频输入必须先完成角色与背景分离，不能直接使用带背景原图')
    canvas=Image.new('RGBA',character.size,(0,255,0,255));canvas.alpha_composite(character)
    return canvas.convert('RGB')

async def generate_asset(cfg, source, prompt):
    async with image_client(cfg,timeout=240) as client:
        response=await client.post(endpoint(cfg['base_url'],'/images/edits'),headers={'Authorization':'Bearer '+cfg['key']},
            data={'model':cfg['model'],'prompt':prompt,'size':'1024x1024'},files={'image':('reference.png',source,'image/png')})
    payload=image_payload(response_json(response,cfg))
    return await download_result(payload,cfg) if isinstance(payload,str) else payload
