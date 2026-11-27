import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from character_routes import register_characters
from character_pipeline import PIPELINE_DEFAULTS,PRESETS,REQUIRED_PRESETS,persist,provider_binding


class CharacterRouteTests(unittest.TestCase):
    def test_local_inputs_replace_scene_workshop_without_changing_active_card(self):
        from character_cards import create_local_card
        cutout=Image.new('RGBA',(128,192));cutout.paste('white',(40,10,90,180))
        raw=io.BytesIO();cutout.save(raw,'PNG')
        old_avatar=copy.deepcopy(self.cfg['avatar'])
        result=self.client.post('/api/characters/inputs/standard',files={'file':('front.png',raw.getvalue(),'image/png')})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['selected'],'uploaded')
        self.assertEqual(self.cfg['avatar'],old_avatar)
        raw=io.BytesIO();Image.new('RGB',(128,192),'blue').save(raw,'PNG')
        self.assertEqual(self.client.post('/api/characters/inputs/background',files={'file':('bg.png',raw.getvalue(),'image/png')}).status_code,200)
        self.assertEqual(self.client.post('/api/characters/inputs/standard',files={'file':('opaque.png',raw.getvalue(),'image/png')}).status_code,422)
        for kind in REQUIRED_PRESETS:
            name=('%032x'%len(kind))+'.mp4';(self.root/'references'/name).write_bytes(b'local-source-snapshot')
            self.cfg['video']['references'][kind]={'file':name,'duration':5}
        self.cfg['video']['references'].pop('happy',None)
        with patch('character_cards.media_binary',return_value='ffmpeg'):
            folder,job=create_local_card(self.root,self.cfg,'新卡','uploaded')
        with Image.open(folder/'standard.png') as image:self.assertEqual(image.getpixel((0,0))[3],0)
        self.assertTrue((folder/'background.jpg').is_file())
        self.assertEqual(set(job['steps']),REQUIRED_PRESETS)
        self.assertEqual(job['budget_cny'],0)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.cfg=copy.deepcopy(PIPELINE_DEFAULTS)
        self.cfg['image']={'key':'private-image'}
        self.cfg['vision']['key']='private-vision';self.cfg['video']['key']='private-video'
        self.cfg['obs']['password']='private-obs'
        self.cfg['avatar']={'name':'原角色','mode':'scene','scene_id':'b'*32}
        self.cfg['video']['references']={kind:{'url':'https://example.com/'+kind+'.mp4','duration':3} for kind in PRESETS}
        self.app=FastAPI()
        def put(value):self.cfg=value
        self.startup,self.shutdown=register_characters(self.app,self.root,lambda:self.cfg,put,lambda *_:None)
        self.client=TestClient(self.app)

    def job(self):
        folder=self.root/'characters'/('a'*32);folder.mkdir(exist_ok=True)
        Image.new('RGB',(256,256),'white').save(folder/'standard.png')
        assets={}
        for kind,preset in PRESETS.items():
            (folder/(kind+'.mp4')).write_bytes(b'fake-media')
            assets[kind]=preset|{'file':kind+'.mp4','duration':3,'width':512,'height':512}
        job={'format':'jibo-character','version':1,'id':folder.name,'name':'测试主播','created':1,
             'assets':assets,'providers':{},'costs':{},'status':'review','accepted':False,'steps':{}}
        persist(folder,job);return folder,job

    def test_config_state_is_redacted_and_blank_keys_are_preserved(self):
        text=self.client.get('/api/characters/config').text
        self.assertNotIn('private-',text);self.assertTrue(json.loads(text)['vision']['has_key'])
        self.assertEqual(self.client.put('/api/characters/config',json={'vision':{'key':''}}).status_code,200)
        self.assertEqual(self.cfg['vision']['key'],'private-vision')
        self.assertEqual(self.client.put('/api/characters/config',json={'video':{'mode':'invalid'}}).status_code,422)
        self.assertEqual(self.client.put('/api/characters/config',json={'obs':{'url':'ws://other-host:4455'}}).status_code,422)

    def test_missing_probe_prevents_paid_build(self):
        with patch('character_routes.ffprobe_binary',return_value=None):
            estimate=self.client.get('/api/characters/quote').json()
            self.assertTrue(any('ffprobe' in item for item in estimate['missing']))
            response=self.client.post('/api/characters/build',json={'quote_fingerprint':estimate['fingerprint'],'budget_cny':20,'confirmed':True})
            self.assertEqual(response.status_code,409)

    def test_account_change_and_ambiguous_submit_cannot_resume(self):
        folder,job=self.job();job['status']='interrupted';job['providers']={'mode':'wan-std','video':'wan2.2-animate-move'}
        job['provider_binding']=provider_binding(self.cfg);job['steps']={'analysis':{'status':'unknown'}};persist(folder,job)
        self.assertEqual(self.client.post('/api/characters/'+folder.name+'/continue').status_code,409)
        job['steps']={};persist(folder,job);self.cfg['video']['key']='new-account'
        self.assertEqual(self.client.post('/api/characters/'+folder.name+'/continue').status_code,409)

    def test_role_package_roundtrip_resets_review_and_excludes_credentials(self):
        folder,_=self.job()
        self.assertEqual(self.client.post('/api/characters/'+folder.name+'/review',json={'accepted':True}).status_code,200)
        response=self.client.get('/api/characters/'+folder.name+'/package');self.assertEqual(response.status_code,200)
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            self.assertEqual(len(archive.namelist()),2+len(PRESETS));self.assertNotIn(b'private-',archive.read('character.json'))
        with patch('character_cards.probe_video',return_value={'duration':3,'width':512,'height':512,'fps':'24/1'}):
            imported=self.client.post('/api/characters/import',files={'file':('character.zip',response.content,'application/zip')})
        self.assertEqual(imported.status_code,200,imported.text)
        job=imported.json();self.assertNotEqual(job['id'],folder.name);self.assertFalse(job['accepted'])
        self.assertEqual(job['costs']['estimated_completed_cny'],0);self.assertEqual(len(job['assets']),len(PRESETS))

    def test_core_only_role_can_review_export_and_import_legacy_package(self):
        folder,job=self.job();job['assets'].pop('happy');persist(folder,job)
        self.cfg['video']['references'].pop('happy')
        quote=self.client.get('/api/characters/quote').json()
        self.assertFalse(any('开心' in item or '思考' in item for item in quote['missing']))
        self.assertEqual(quote['total_cny'],7.05)
        self.assertEqual(self.client.post('/api/characters/'+folder.name+'/review',json={'accepted':True}).status_code,200)
        response=self.client.get('/api/characters/'+folder.name+'/package');self.assertEqual(response.status_code,200)
        output=io.BytesIO(response.content)
        with zipfile.ZipFile(output,'a') as z:z.writestr('thoughtful.mp4',b'legacy media')
        with patch('character_cards.probe_video',return_value={'duration':3,'width':512,'height':512,'fps':'24/1'}):
            imported=self.client.post('/api/characters/import',files={'file':('old.zip',output.getvalue(),'application/zip')})
        self.assertEqual(imported.status_code,200,imported.text)
        self.assertEqual(set(imported.json()['assets']),REQUIRED_PRESETS)
        exported=self.client.get('/api/characters/'+imported.json()['id']+'/package')
        with zipfile.ZipFile(io.BytesIO(exported.content)) as z:
            self.assertNotIn('thoughtful.mp4',z.namelist());self.assertNotIn('happy.mp4',z.namelist())

    def test_character_import_rejects_extra_paths_before_writing(self):
        output=io.BytesIO()
        with zipfile.ZipFile(output,'w') as archive:archive.writestr('../outside.mp4',b'bad')
        response=self.client.post('/api/characters/import',files={'file':('bad.zip',output.getvalue(),'application/zip')})
        self.assertEqual(response.status_code,422);self.assertEqual(list((self.root/'characters').iterdir()),[])

    def test_card_persona_validation_and_no_imported_chat_permission(self):
        folder,job=self.job();job['persona']='性格温和';persist(folder,job)
        raw=self.client.get('/api/characters/'+folder.name+'/package').content
        for persona in (None,{},'x'*2001):
            output=io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(raw)) as source,zipfile.ZipFile(output,'w') as target:
                for name in source.namelist():
                    value=source.read(name)
                    if name=='character.json':
                        manifest=json.loads(value);manifest['persona']=persona;value=json.dumps(manifest).encode()
                    target.writestr(name,value)
            response=self.client.post('/api/characters/import',files={'file':('bad-persona.zip',output.getvalue())})
            self.assertEqual(response.status_code,422)
            self.assertEqual(len(list((self.root/'characters').iterdir())),1)
        self.assertNotIn('interaction',self.cfg)

    def test_transparent_card_roundtrip_apply_and_rename_without_emotion(self):
        folder,job=self.job();job['version']=2;job['assets'].pop('happy')
        for kind,asset in job['assets'].items():
            (folder/asset['file']).rename(folder/(kind+'.webm'));asset.update(file=kind+'.webm',background='transparent')
        Image.new('RGB',(256,256),'blue').save(folder/'background.jpg');job['background']='background.jpg';persist(folder,job)
        self.assertEqual(self.client.post('/api/characters/'+folder.name+'/activate').status_code,409)
        self.client.post('/api/characters/'+folder.name+'/review',json={'accepted':True})
        self.assertEqual(self.client.post('/api/characters/'+folder.name+'/activate').status_code,200)
        self.assertEqual(self.cfg['avatar']['character_id'],folder.name)
        self.client.patch('/api/characters/'+folder.name,json={'name':'新角色卡','persona':'温和，喜欢读书。','background_visible':False})
        self.assertEqual(self.cfg['avatar']['name'],'新角色卡')
        self.assertEqual(self.cfg['avatar']['persona'],'温和，喜欢读书。')
        archive=self.client.get('/api/characters/'+folder.name+'/package')
        with zipfile.ZipFile(io.BytesIO(archive.content)) as z:
            self.assertIn('idle.webm',z.namelist());self.assertIn('background.jpg',z.namelist())
            self.assertNotIn('private-',z.read('character.json').decode())
        with patch('character_cards.probe_video',return_value={'duration':5,'width':624,'height':624,'fps':'30/1'}):
            response=self.client.post('/api/characters/import',files={'file':('card.zip',archive.content,'application/zip')})
        self.assertEqual(response.status_code,200,response.text);imported=response.json()
        self.assertNotEqual(imported['id'],folder.name);self.assertFalse(imported['accepted'])
        self.assertEqual(imported['assets']['idle']['file'],'idle.webm');self.assertFalse(imported['background_visible'])
        self.assertEqual(imported['persona'],'温和，喜欢读书。')
        for invalid in (3,'x'*2001):
            self.assertEqual(self.client.patch('/api/characters/'+folder.name,json={'persona':invalid}).status_code,422)


if __name__=='__main__':unittest.main()
