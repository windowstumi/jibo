import asyncio
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import AsyncMock,patch

import httpx
from PIL import Image,ImageDraw
from scripts import generate_reference_samples as samples


class ReferenceSampleTests(unittest.TestCase):
    def test_prompt_i2v_protocol_and_ambiguous_submit_never_repeats(self):
        async def protocol():
            cfg={'base_url':'https://dashscope.aliyuncs.com','key':'not-a-real-key','proxy_mode':'direct'}
            response=httpx.Response(200,json={'output':{'task_id':'reference-1'}})
            with patch('httpx.AsyncClient.post',AsyncMock(return_value=response)) as post:
                self.assertEqual(await samples.submit('data:image/png;base64,AA==','talk',cfg),'reference-1')
                body=post.call_args.kwargs['json']
                self.assertIn('/video-generation/video-synthesis',post.call_args.args[0])
                self.assertEqual(body['parameters']['resolution'],'480P')
                self.assertEqual(body['parameters']['duration'],5)
                self.assertIn('prompt',body['input']);self.assertNotIn('video_url',body['input'])
            with patch('httpx.AsyncClient.post',AsyncMock(return_value=httpx.Response(400,json={'code':'Arrearage','message':'Account rejected'}))):
                with self.assertRaises(samples.SubmissionRejected):await samples.submit('data:image/png;base64,AA==','idle',cfg)
        asyncio.run(protocol())
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'images').mkdir()
            Image.new('RGB',(256,256),'white').save(root/'images'/'reference.png')
            ident='a'*32;scene=root/'scenes'/ident;scene.mkdir(parents=True)
            image=Image.new('RGBA',(256,256));ImageDraw.Draw(image).rectangle((80,10,175,240),fill='blue');image.save(scene/'neutral.png')
            cfg={'avatar':{'original':'/media/images/reference.png','scene_id':ident},'video':{'key':'not-a-real-key'}}
            source,transparent,encoded=samples.prepared_image(root,cfg)
            self.assertEqual(source,scene/'neutral.png')
            import io
            with Image.open(io.BytesIO(transparent)) as png:self.assertEqual(png.getpixel((0,0))[3],0)
            with Image.open(io.BytesIO(encoded)) as png:self.assertEqual(png.getpixel((0,0)),(0,255,0))
            # Existing cutouts are available even when the old scene is no longer active.
            self.assertEqual(samples.prepared_image(root,{'avatar':{'original':'/media/images/reference.png'}})[0],source)
            with tempfile.TemporaryDirectory() as empty:
                with self.assertRaises(ValueError):samples.prepared_image(Path(empty),{'avatar':{}})
            with self.assertRaises(ValueError):samples.video_input_image(Image.new('RGB',(256,256),'white'))
            with closing(sqlite3.connect(root/'studio.sqlite3')) as db, db:
                db.execute('CREATE TABLE kv (key TEXT,value TEXT)');db.execute('INSERT INTO kv VALUES (?,?)',('settings',json.dumps(cfg)))
            with patch.object(samples,'ffprobe_binary',return_value='available'),\
                 patch.object(samples,'submit',AsyncMock(side_effect=ValueError('simulated interruption'))) as submit:
                for _ in range(2):
                    with self.assertRaises(ValueError):asyncio.run(samples.run(root,3,True))
                self.assertEqual(submit.await_count,1)
            job=json.loads(next(root.glob('reference-samples/*/manifest.json')).read_text(encoding='utf-8'))
            self.assertEqual(job['steps']['idle']['status'],'unknown')
            self.assertNotIn('not-a-real-key',json.dumps(job))


if __name__=='__main__':unittest.main()
