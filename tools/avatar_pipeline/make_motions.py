from pathlib import Path
import os
import math,json
from mcp_proxy import Client

ROOT=Path(os.environ["AVATAR_WORKSPACE"]).resolve()
def smooth(x):
    x=max(0,min(1,x));return x*x*(3-2*x)
def envelope(t,start=.15,rise=.75,fall=3.2,end=4.1):
    return smooth((t-start)/rise)*(1-smooth((t-fall)/(end-fall)))
def values(name,t):
    e=envelope(t)
    if name=='Wave':
        wiggle=math.sin((t-.9)*math.pi*4.2)*16*smooth((t-.7)/.4)
        return {'ParamGestureLShoulder':-35*e,'ParamGestureLElbow':-110*e,
                'ParamGestureLWrist':wiggle*e,'ParamAngleZ':-3*e,'ParamMouthForm':.35*e}
    if name=='Present':
        return {'ParamGestureLShoulder':-7*e,'ParamGestureLElbow':-62*e,
                'ParamGestureLWrist':25*e,'ParamAngleZ':2*e,'ParamMouthForm':.25*e}
    if name=='Thanks':
        return {'ParamAngleY':-9*e,'ParamBodyAngleY':2.5*e,'ParamAngleZ':1.5*e,
                'ParamMouthForm':.3*e,'ParamGestureLShoulder':7*e,'ParamGestureRShoulder':-7*e}

with Client() as c:
    manifest={}
    for name in ['Wave','Present','Thanks']:
        duration=4.4;times=[round(i/30,5) for i in range(133)]
        poses=[values(name,t) for t in times]
        curves=[{'parameter':pid,'keys':[{'time':t,'value':v[pid],'interpolation':'LINEAR'} for t,v in zip(times,poses)]} for pid in poses[0]]
        clip={'id':name,'name':name,'duration':duration,'fps':30,'loop':False,'fade_in':.2,'fade_out':.3,'enabled':True,'curves':curves}
        c.edit('motion_put',clip=clip)
        manifest[name]={'duration':duration,'frames':len(times),'parameters':list(poses[0]),'samples':poses}
        print('MOTION',name,flush=True)
    (ROOT/'motion-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    c.edit('project_save_as',path=str(ROOT/'character-final.psd2live'))
    d=c.edit('project_export_model',output_directory=str(ROOT/'live2d-final'))
    (ROOT/'model-export.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    print('MODEL EXPORTED',flush=True)
    preview_poses=[{},values('Wave',1.15),values('Wave',1.42),values('Present',1.5),values('Thanks',1.5),{'ParamEyeLOpen':0,'ParamEyeROpen':0,'ParamMouthOpenY':.5}]
    d,images=c.call('view_render_poses',{'viewport':{'mode':'canvas_rect','left':40,'top':0,'width':940,'height':1536},'poses':preview_poses,'columns':3,'target_long_edge':1600})
    for i,img in enumerate(images):(ROOT/f'motion-contact-{i}.png').write_bytes(img)
    (ROOT/'pose-render.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    overview=c.call('workspace_overview')[0];(ROOT/'final-overview.json').write_text(json.dumps(overview,ensure_ascii=False,indent=2),encoding='utf-8')
    print('POSES RENDERED',len(images),flush=True)
