"""Assisted local decomposition: preserves source pixels, with calibrated masks.

Not a general semantic segmentation model. The landmarks below were inspected
for this character; this fallback remains explicitly recorded in the report.
"""
from pathlib import Path
import os
import json
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer

ROOT=Path(os.environ["AVATAR_WORKSPACE"]).resolve()
OUT=ROOT/'layers';OUT.mkdir(exist_ok=True)
im=Image.open(ROOT/'images/neutral.transparent.png').convert('RGBA')
W,H=im.size
PROFILE=json.loads(Path(os.environ["AVATAR_PROFILE"]).read_text(encoding="utf-8"))
if list(im.size)!=PROFILE["canvas"]:raise ValueError("Image dimensions do not match the calibrated profile")
arr=np.asarray(im).copy();rgb=arr[:,:,:3].astype(np.int16)
green=(rgb[:,:,1]>rgb[:,:,0]+12)&(rgb[:,:,1]>rgb[:,:,2]-60)
arr[green,3]=0
im=Image.fromarray(arr)
im.save(ROOT/'images/neutral.clean.png')
alpha=np.array(im.getchannel('A'))

def polygon(points):
    m=Image.new('L',(W,H));ImageDraw.Draw(m).polygon(points,fill=255);return np.array(m)
def rect(box):
    m=Image.new('L',(W,H));ImageDraw.Draw(m).rectangle(box,fill=255);return np.array(m)
def ellipse(box):
    m=Image.new('L',(W,H));ImageDraw.Draw(m).ellipse(box,fill=255);return np.array(m)
def profile_mask(name):
    item=PROFILE["masks"][name]
    return {"polygon":polygon,"rect":rect,"ellipse":ellipse}[item["shape"]](item["points"])

def masked(mask, source=im):
    o=source.copy();o.putalpha(Image.fromarray(np.minimum(np.array(source.getchannel('A')),mask).astype('uint8')));return o

# Whole connected arm meshes are skinned to shoulder, elbow and wrist bones.
# The overlap at the shoulder stays beneath the central blouse.
left=profile_mask("left")
right=profile_mask("right")
arms=np.maximum(left,right)
face=profile_mask("face")
neck=profile_mask("neck")
head=profile_mask("head");head=np.minimum(head,255-np.maximum(face,neck))
top=profile_mask("top")
skirt=profile_mask("skirt")
legL=profile_mask("legL")
legR=profile_mask("legR")
footL=profile_mask("footL"); footR=profile_mask("footR")
legL=np.minimum(legL,255-rect((0,PROFILE["leg_trim_y"],W,H)));legR=np.minimum(legR,255-rect((0,PROFILE["leg_trim_y"],W,H)))

# Remove eyes/brows/mouth from the face base; overlay exact source features later.
eyeR=profile_mask("eyeR");eyeL=profile_mask("eyeL")
browR=profile_mask("browR");browL=profile_mask("browL")
mouth=profile_mask("mouth")
features=np.maximum.reduce([eyeR,eyeL,browR,browL,mouth])
face_rgb=cv2.inpaint(np.asarray(im)[:,:,:3],features,4,cv2.INPAINT_TELEA)
faceim=Image.fromarray(np.dstack((face_rgb,alpha)))

# Remaining pixels form the back-hair layer. Fill narrow holes behind the arms
# locally; no neural reconstruction or unseen-body claims are made.
occupied=np.maximum.reduce([arms,face,neck,head,top,skirt,legL,legR,footL,footR])
back=masked(255-occupied)
ba=np.array(back.getchannel('A'))
close=cv2.morphologyEx(ba,cv2.MORPH_CLOSE,np.ones((31,31),np.uint8))
fill=((close>0)&(ba==0)&(arms>0)).astype('uint8')*255
back_rgb=cv2.inpaint(np.asarray(im)[:,:,:3],fill,5,cv2.INPAINT_TELEA)
back=Image.fromarray(np.dstack((back_rgb,np.maximum(ba,fill))))
hair_alpha=np.array(back.getchannel('A'))
hair_alpha[PROFILE["hair_bottom"]:]=0
skin=(rgb[:,:,0]>rgb[:,:,2]+12)&(rgb[:,:,0]>rgb[:,:,1]+6)
hair_alpha[skin]=0
back.putalpha(Image.fromarray(hair_alpha))

layers=[('back hair',back),('legwear-r',masked(legR)),('legwear-l',masked(legL)),
 ('footwear-r',masked(footR)),('footwear-l',masked(footL)),('neck',masked(neck))]
yy,xx=np.mgrid[:H,:W]
for side,mask,elbow,wrist in [(cfg['side'],right if cfg['side']=='r' else left,cfg['pivots'][1],cfg['pivots'][2]) for cfg in PROFILE['joints'].values()]:
    direction=np.array(wrist,dtype=float)-elbow;direction/=np.linalg.norm(direction)
    at_elbow=(xx-elbow[0])*direction[0]+(yy-elbow[1])*direction[1]
    at_wrist=(xx-wrist[0])*direction[0]+(yy-wrist[1])*direction[1]
    # Overlapping cutouts retain a small skin cap at each joint.
    parts=[('upper',at_elbow<12),('fore',(at_elbow>-12)&(at_wrist<10)),('hand',at_wrist>-10)]
    for part,region in parts:
        art=masked(np.where(region,mask,0).astype('uint8'))
        if part in ('upper','fore'):
            cx,cy=elbow if part=='upper' else wrist
            radius=PROFILE['joint_cap_radius']['elbow' if part=='upper' else 'wrist']
            color=tuple(int(v) for v in np.asarray(im)[cy-2:cy+3,cx-2:cx+3,:3].mean(axis=(0,1)))+(255,)
            cap=Image.new('RGBA',(W,H));ImageDraw.Draw(cap).ellipse((cx-radius,cy-radius,cx+radius,cy+radius),fill=color)
            cap.alpha_composite(art);art=cap
        layers.append((f'handwear-{side}-{part}',art))
layers += [('topwear',masked(top)),('bottomwear',masked(skirt)),('face',masked(face,faceim))]

# Sclera, iris and eyelash supply independent anchors to the standard eye rig.
for eye_config in PROFILE['eyes']:
    side=eye_config['side'];eye=eyeR if side=='r' else eyeL;cx,cy=eye_config['center']
    iris=ellipse((cx-12,cy-14,cx+12,cy+13))
    eye_shape=polygon([(cx-32,cy-5),(cx-23,cy-13),(cx-6,cy-16),
                       (cx+13,cy-12),(cx+24,cy-3),(cx+13,cy+12),
                       (cx-12,cy+12),(cx-25,cy+3)])
    sclera=np.array(im).copy();sclera[eye_shape>0,:3]=[250,247,248]
    dark=np.max(np.asarray(im)[:,:,:3],axis=2)<170
    lash=(dark&(eye>0)&~(iris>0)).astype('uint8')*255
    layers.extend([('eyewhite-'+side,masked(eye_shape,Image.fromarray(sclera))),
                   ('irides-'+side,masked(np.minimum(iris,eye_shape))),
                   ('eyelash-'+side,masked(lash))])
layers += [('eyebrow-r',masked(browR)),('eyebrow-l',masked(browL))]
speaking=Image.open(ROOT/'images/speaking.transparent.png').convert('RGBA')
layers.append(('mouth open',masked(mouth,speaking)))
layers.append(('front hair',masked(head)))

psd=PSDImage.new('RGBA',(W,H))
records=[]
for i,(name,layer) in enumerate(layers):
    box=layer.getbbox()
    if not box:continue
    layer.save(OUT/(name.replace(' ','_')+'.png'))
    PixelLayer.frompil(layer.crop(box),psd,name=name,left=box[0],top=box[1])
    records.append({'name':name,'bbox':list(box),'pixels':int((np.array(layer.getchannel('A'))>0).sum())})
psd.save(ROOT/'character.assisted.psd')
psd.composite().save(ROOT/'layers-composite.png')
(ROOT/'layer-manifest.json').write_text(json.dumps({'method':'local calibrated masks; manually assisted fallback','canvas':[W,H],'layers':records,'limitations':['simple inferred sclera and cropped iris artwork','locally inpainted narrow hair gaps','mask landmarks calibrated for this image']},ensure_ascii=False,indent=2),encoding='utf-8')

board=Image.new('RGB',(1200,960),'#e7edf4');draw=ImageDraw.Draw(board);font=ImageFont.truetype(str(Path(os.environ.get('WINDIR',r'C:\Windows'))/'Fonts/arial.ttf'),19)
for i,(name,layer) in enumerate(layers):
    tile=Image.new('RGBA',layer.size,'#f7f8fa');tile.alpha_composite(layer);tile.thumbnail((190,270))
    x=i%6*200;y=i//6*320;board.paste(tile.convert('RGB'),(x+(200-tile.width)//2,y+5));draw.text((x+5,y+285),name,font=font,fill='#24344a')
board.save(ROOT/'layers-overview.jpg',quality=94)
print('Saved assisted PSD',len(psd),'layers')
