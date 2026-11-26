import asyncio
import base64
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock,patch

import httpx
from PIL import Image

import character_pipeline as pipeline


def image_bytes():
    output=io.BytesIO();Image.new('RGB',(256,256),'white').save(output,'PNG');return output.getvalue()


class PipelineTests(unittest.TestCase):
    def setUp(self):
        async def convert(source,target):target.write_bytes(source.read_bytes())
        patcher=patch.object(pipeline,'transparent_video',convert);patcher.start();self.addCleanup(patcher.stop)

    def settings(self):
        return {'image':{'key':'image-secret','model':'gpt-image-2'},
            'vision':{'key':'vision-secret'},'video':{'key':'video-secret',
                'references':{kind:{'url':'https://example.com/'+kind+'.mp4','duration':3} for kind in pipeline.PRESETS}}}

    def job(self,folder):
        settings=self.settings();quote=pipeline.quote(settings)
        job={'id':folder.name,'status':'running','steps':{r['kind']:{'status':'waiting','estimated_cny':r['cost_cny'],
            **({'rate_cny':r['rate_cny']} if 'rate_cny' in r else {})} for r in quote['rows']},
            'references':settings['video']['references'],'budget_cny':quote['with_retry_allowance_cny'],'assets':{}}
        (folder/'reference.png').write_bytes(image_bytes());pipeline.persist(folder,job);return job

    def test_quote_covers_all_emotions_and_motions_without_promising_actual_invoice(self):
        settings=self.settings();quote=pipeline.quote(settings)
        self.assertEqual(quote['total_cny'],8.25)
        self.assertEqual(quote['with_retry_allowance_cny'],15.45)
        settings['video']['mode']='wan-pro'
        self.assertEqual(pipeline.quote(settings)['total_cny'],11.85)
        self.assertNotIn('secret',json.dumps(quote))

    def test_paid_submit_is_never_repeated_when_result_is_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);self.job(folder)
            with patch.object(pipeline,'analyze_character',AsyncMock(side_effect=httpx.ReadTimeout('vision-secret'))) as call:
                asyncio.run(pipeline.run_character(folder,self.settings(),lambda *_:None))
                asyncio.run(pipeline.run_character(folder,self.settings(),lambda *_:None))
                self.assertEqual(call.await_count,1)
            result=pipeline.read_job(folder)
            self.assertEqual(result['steps']['analysis']['status'],'unknown')
            self.assertNotIn('vision-secret',json.dumps(result))
            self.assertGreater(result['costs']['uncertain_reserved_cny'],0)

    def test_existing_provider_tasks_are_queried_without_resubmission(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);job=self.job(folder)
            for key in ['analysis','standard']:job['steps'][key]['status']='done'
            job['analysis']={'identity':'角色','clothing':'宽袖','motion_constraints':[],'risks':[]}
            (folder/'standard.png').write_bytes(image_bytes())
            for kind in pipeline.PRESETS:job['steps'][kind].update(task_id=kind,status='pending')
            pipeline.persist(folder,job)
            async def download(url,path,cfg):path.write_bytes(b'video')
            result={'output':{'task_status':'SUCCEEDED','results':{'video_url':'https://cdn.example/video.mp4'}},'usage':{'duration':3}}
            with patch.object(pipeline,'query_video',AsyncMock(return_value=result)),patch.object(pipeline,'submit_video',AsyncMock()) as submit,\
                 patch.object(pipeline,'download_video',download),patch.object(pipeline,'probe_video',return_value={'duration':3,'width':512,'height':512,'fps':'24/1'}):
                asyncio.run(pipeline.run_character(folder,self.settings(),lambda *_:None))
                submit.assert_not_called()
            result=pipeline.read_job(folder)
            self.assertEqual(result['status'],'review');self.assertEqual(len(result['assets']),len(pipeline.PRESETS))
            self.assertEqual(result['costs']['estimated_completed_cny'],8.25)

    def test_optional_emotion_is_not_charged_without_reference(self):
        settings=self.settings();settings['video']['references'].pop('happy')
        settings['video']['references']['thoughtful']={'url':'https://example.com/old.mp4','duration':3}
        quote=pipeline.quote(settings)
        self.assertEqual(quote['total_cny'],7.05);self.assertEqual(quote['with_retry_allowance_cny'],13.05)
        self.assertEqual(quote['fallbacks'],{'happy':'talk'})
        self.assertNotIn('happy',[r['kind'] for r in quote['rows']]);self.assertNotIn('thoughtful',pipeline.pipeline_settings(settings)['video']['references'])

    def test_failed_optional_emotion_does_not_block_core_review(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);job=self.job(folder)
            for kind,step in job['steps'].items():step['status']='done'
            job['steps']['happy'].update(status='pending',task_id='optional-task')
            job['assets']={kind:{'file':kind+'.mp4'} for kind in pipeline.REQUIRED_PRESETS}
            (folder/'standard.png').write_bytes(image_bytes());pipeline.persist(folder,job)
            response={'output':{'task_status':'FAILED','message':'optional unavailable'}}
            with patch.object(pipeline,'query_video',AsyncMock(return_value=response)),patch.object(pipeline,'submit_video',AsyncMock()) as submit:
                asyncio.run(pipeline.run_character(folder,self.settings(),lambda *_:None));submit.assert_not_called()
            result=pipeline.read_job(folder);self.assertEqual(result['status'],'review')
            self.assertIn('使用平静说话',result['error']);self.assertNotIn('happy',result['assets'])

    def test_gpt_vision_uses_multimodal_messages_and_collects_usage(self):
        payload={'choices':[{'message':{'content':json.dumps({'identity':'动漫人物','clothing':'和服宽袖','motion_constraints':['腰带稳定'],'risks':[]})}}],
            'usage':{'prompt_tokens':100,'completion_tokens':80}}
        async def run():
            with patch('httpx.AsyncClient.post',AsyncMock(return_value=httpx.Response(200,json=payload))) as call:
                analysis,usage=await pipeline.analyze_character(image_bytes(),pipeline.pipeline_settings(self.settings())['vision'])
                content=call.call_args.kwargs['json']['messages'][1]['content'][0]
                self.assertEqual(content['type'],'image_url');self.assertIn('data:image/jpeg;base64,',content['image_url']['url'])
                self.assertEqual(analysis['clothing'],'和服宽袖');self.assertEqual(usage['prompt_tokens'],100)
        asyncio.run(run())

    def test_official_video_payload_includes_async_and_temporary_resource_headers(self):
        async def run():
            cfg=pipeline.pipeline_settings(self.settings())['video']
            with patch('httpx.AsyncClient.post',AsyncMock(return_value=httpx.Response(200,json={'output':{'task_id':'task-1'}}))) as call:
                self.assertEqual(await pipeline.submit_video('oss://image','https://example.com/ref.mp4',cfg),'task-1')
                args=call.call_args
                self.assertTrue(args.args[0].endswith('/api/v1/services/aigc/image2video/video-synthesis'))
                self.assertEqual(args.kwargs['headers']['X-DashScope-OssResourceResolve'],'enable')
                self.assertEqual(args.kwargs['json']['parameters']['mode'],'wan-std')
        asyncio.run(run())

    def test_temporary_oss_upload_never_forwards_provider_bearer(self):
        async def run(path):
            policy={'data':{'upload_host':'https://oss.example.com','upload_dir':'temporary',
                'oss_access_key_id':'oss-token','signature':'signature','policy':'policy',
                'x_oss_object_acl':'private','x_oss_forbid_overwrite':'true'}}
            with patch('httpx.AsyncClient.get',AsyncMock(return_value=httpx.Response(200,json=policy))),\
                 patch('httpx.AsyncClient.post',AsyncMock(return_value=httpx.Response(200))) as upload:
                url=await pipeline.upload_temporary(path,pipeline.pipeline_settings(self.settings())['video'])
                self.assertTrue(url.startswith('oss://temporary/'))
                self.assertNotIn('Authorization',upload.call_args.kwargs.get('headers',{}))
                self.assertNotIn('video-secret',repr(upload.call_args.kwargs))
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'image.png';path.write_bytes(image_bytes());asyncio.run(run(path))

    def test_actual_duration_budget_stops_next_new_paid_submission(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);job=self.job(folder);job['budget_cny']=9.45
            for key in ['analysis','standard']:job['steps'][key]['status']='done'
            job['analysis']={'identity':'角色','clothing':'宽袖','motion_constraints':[],'risks':[]}
            (folder/'standard.png').write_bytes(image_bytes());job['steps']['idle'].update(task_id='existing',status='pending')
            pipeline.persist(folder,job)
            async def download(url,path,cfg):path.write_bytes(b'video')
            result={'output':{'task_status':'SUCCEEDED','results':{'video_url':'https://cdn.example/video.mp4'}}}
            with patch.object(pipeline,'query_video',AsyncMock(return_value=result)),patch.object(pipeline,'submit_video',AsyncMock()) as submit,\
                 patch.object(pipeline,'download_video',download),patch.object(pipeline,'probe_video',return_value={'duration':8,'width':512,'height':512,'fps':'24/1'}):
                asyncio.run(pipeline.run_character(folder,self.settings(),lambda *_:None));submit.assert_not_called()
            self.assertIn('预算',pipeline.read_job(folder)['error'])

    def test_new_generation_separates_cutout_before_uploading_video_input(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);self.job(folder)
            img=Image.new('RGB',(256,256),(0,255,0))
            from PIL import ImageDraw
            ImageDraw.Draw(img).rectangle((95,10,160,240),fill='white')
            buf=io.BytesIO();img.save(buf,'PNG')
            async def upload(path,cfg):
                self.assertEqual(path.name,'video-input.png')
                with Image.open(path) as image:self.assertEqual(image.getpixel((0,0)),(0,255,0))
                with Image.open(folder/'standard.png') as image:
                    self.assertEqual(image.mode,'RGBA');self.assertEqual(image.getpixel((0,0))[3],0)
                    self.assertEqual(image.getpixel((120,100)),(255,255,255,255))
                return 'oss://prepared-character'
            async def download(url,path,cfg):path.write_bytes(b'video')
            analysis={'identity':'角色','clothing':'长袖','motion_constraints':[],'risks':[]}
            with patch.object(pipeline,'analyze_character',AsyncMock(return_value=(analysis,{}))),\
                 patch.object(pipeline,'generate_asset',AsyncMock(return_value=buf.getvalue())) as generate,\
                 patch.object(pipeline,'upload_temporary',upload),patch.object(pipeline,'submit_video',AsyncMock(return_value='task-id')),\
                 patch.object(pipeline,'query_video',AsyncMock(return_value={'output':{'task_status':'SUCCEEDED','video_url':'https://cdn.example/video.mp4'}})),\
                 patch.object(pipeline,'download_video',download),patch.object(pipeline,'probe_video',return_value={'duration':3,'width':512,'height':512,'fps':'24/1'}):
                asyncio.run(pipeline.run_character(folder,self.settings(),lambda *_:None))
                self.assertIn('STRICTLY FRONT-FACING',generate.call_args.args[2])
            self.assertEqual(pipeline.read_job(folder)['status'],'review')


if __name__=='__main__':unittest.main()
