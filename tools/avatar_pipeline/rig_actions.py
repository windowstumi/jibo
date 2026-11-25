"""Create native Cubism shoulder/elbow/wrist chains through PSD2Live's API.

Run after importing segmented-base/character.assisted.cmo3. Changes are saved
in the local project history; API credentials are read by the official proxy.
"""
from pathlib import Path
import os
import json
from mcp_proxy import Client

ROOT=Path(os.environ["AVATAR_WORKSPACE"]).resolve()
with Client() as c:
    objects=[]
    offset=0
    while True:
        page=c.call('workspace_inspect',{'scope':'objects','offset':offset})[0]
        objects.extend(page['items'])
        if 'next' not in page:break
        offset=page['next']
    meshes={x['name']:x['target'].split(':',1)[1] for x in objects if x['target'].startswith('mesh:')}
    chains=json.loads(Path(os.environ["AVATAR_PROFILE"]).read_text(encoding="utf-8"))["joints"]
    for side,cfg in chains.items():
        for i,(joint,suffixes) in enumerate([('Shoulder',['upper','fore','hand']),('Elbow',['fore','hand']),('Wrist',['hand'])]):
            rid=f'Gesture{side}{joint}'
            mids=[meshes[f'handwear-{cfg["side"]}-{s}'] for s in suffixes]
            c.edit('canvas_rotation',id=rid,name=f'{side} {joint}',meshes=mids,
                   origin=list(cfg['pivots'][i]),angle=0,handle_length=60,preservePose=True)
            pid=f'ParamGesture{side}{joint}'
            c.edit('parameter_create',parameter_id=pid,name=f'{side} {joint}',min=-170,max=170,default=0)
            c.edit('keyform_apply',changes=[
                {'op':'seed','target':'rotation:'+rid,'key':{pid:0}},
                {'op':'set','target':'rotation:'+rid,'key':{pid:-170},'geometry':{'angle':-170}},
                {'op':'set','target':'rotation:'+rid,'key':{pid:170},'geometry':{'angle':170}},
            ])
            print('RIGGED',rid,flush=True)
    c.edit('project_save_as',path=str(ROOT/'character-rigged.psd2live'))
    poses=[{}, {'ParamGestureLShoulder':35,'ParamGestureLElbow':110},
              {'ParamGestureLShoulder':-35,'ParamGestureLElbow':-110},
              {'ParamGestureLShoulder':15,'ParamGestureLElbow':75,'ParamGestureLWrist':10}]
    d,imgs=c.call('view_render_poses',{'viewport':{'mode':'canvas_rect','left':0,'top':0,'width':1024,'height':1536},
                                    'poses':poses,'columns':2,'target_long_edge':1500})
    for i,img in enumerate(imgs):(ROOT/f'joint-test-{i}.png').write_bytes(img)
    (ROOT/'joint-test.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Joint test rendered',len(imgs),'images',flush=True)
