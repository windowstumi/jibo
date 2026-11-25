import asyncio
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,AsyncMock

import numpy as np
from PIL import Image,ImageDraw

from scene_model import remove_chroma,derive_rig,compile_model,build_scene,new_job,public_job,write_cloth_mask,ensure_cloth_model,validate_cloth_polygon


def test_image(kind='neutral'):
    im=Image.new('RGBA',(256,256),(0,255,0,255));d=ImageDraw.Draw(im)
    d.ellipse((100,10,156,67),fill='#edc4b3')
    d.rectangle((110,62,145,125),fill='#ffffff')
    d.polygon([(107,112),(149,112),(178,190),(79,190)],fill='#55445b')
    d.rectangle((112,185,124,246),fill='#eeeefa');d.rectangle((135,185,147,246),fill='#eeeefa')
    d.line((113,36,120,36),fill='#222222',width=2);d.line((137,36,144,36),fill='#222222',width=2)
    d.line((123,54,134,54),fill='#763a40',width=2)
    if kind=='speaking':d.ellipse((120,50,137,61),fill='#713545')
    if kind=='blink':d.line((113,39,120,39),fill='#222222',width=3);d.line((137,39,144,39),fill='#222222',width=3)
    return im


class SceneModelTests(unittest.TestCase):
    def test_chroma_removes_background_and_preserves_white(self):
        im,report=remove_chroma(test_image())
        self.assertTrue(report['background_removed'])
        self.assertEqual(im.getpixel((0,0))[3],0)
        white=im.getpixel((120,80))
        self.assertEqual(white,(255,255,255,255))
        self.assertGreater(im.getpixel((126,40))[3],240)

    def test_non_keyed_image_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'绿幕'):
            remove_chroma(Image.new('RGB',(256,256),'blue'))

    def test_transparent_input_is_accepted(self):
        im=Image.new('RGBA',(256,256));ImageDraw.Draw(im).rectangle((80,20,170,240),fill='white')
        result,report=remove_chroma(im)
        self.assertEqual(report['matting'],'alpha')
        self.assertEqual(result.getpixel((0,0))[3],0)

    def test_compiler_exports_real_texture_mesh_and_layers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ('neutral','speaking','blink'):test_image(name).save(root/(name+'.raw.png'))
            Image.new('RGB',(256,256),'#83a9e4').save(root/'background.raw.png')
            model=compile_model(root)
            self.assertEqual(model['format'],'yingbo-scene')
            self.assertGreater(model['mesh']['rows'],20)
            for asset in [*model['textures'].values(),*model['layers'].values()]:self.assertTrue((root/asset).exists())
            self.assertTrue(model['rig']['eye_y']<model['rig']['mouth_y']<model['rig']['neck_y'])
            self.assertTrue(model['rig']['skirt_y']<model['rig']['skirt_end'])
            self.assertEqual(Image.open(root/'neutral.png').getpixel((0,0))[3],0)

    def test_four_calls_and_never_retries_submitted_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            im=test_image();buf=io.BytesIO();im.save(buf,'PNG');raw=buf.getvalue()
            directory=new_job(Path(tmp),raw)
            async def run():
                with patch('scene_model.generate_asset',AsyncMock(return_value=raw)) as call:
                    await build_scene(directory,{},raw)
                    self.assertEqual(call.await_count,4)
                    await build_scene(directory,{},raw)
                    self.assertEqual(call.await_count,4)
                failed=new_job(Path(tmp),raw)
                with patch('scene_model.generate_asset',AsyncMock(side_effect=ValueError('upstream failed'))) as call:
                    with self.assertRaises(ValueError):await build_scene(failed,{},raw)
                    with self.assertRaisesRegex(ValueError,'先前已提交'):await build_scene(failed,{},raw)
                    self.assertEqual(call.await_count,1)
            asyncio.run(run())

    def test_cloth_mask_excludes_legs_and_feathers_inward_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            neutral,_=remove_chroma(test_image());neutral.save(root/'neutral.png')
            model={'textures':{},'rig':derive_rig(neutral),'cloth':{'polygon':[[.40,.46],[.60,.46],[.67,.70],[.33,.70]]}}
            write_cloth_mask(root,model)
            mask=np.asarray(Image.open(root/'cloth-mask.png'))
            self.assertGreater(mask[150,128],100)
            self.assertEqual(int(mask[181:,:].max()),0)
            self.assertEqual(int(mask[:115,:].max()),0)
            self.assertEqual(int(mask[:,0:70].max()),0)

    def test_old_scene_gets_mask_without_cloud_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);neutral,_=remove_chroma(test_image());neutral.save(root/'neutral.png')
            rig=derive_rig(neutral);rig.update(skirt_y=.46,skirt_end=.70)
            old={'textures':{'neutral':'neutral.png'},'rig':rig}
            (root/'model.json').write_text(json.dumps(old))
            with patch('scene_model.generate_asset',AsyncMock()) as cloud:
                model=ensure_cloth_model(root)
                cloud.assert_not_called()
            self.assertTrue((root/'cloth-mask.png').exists())
            self.assertEqual(model['cloth']['method'],'masked-texture-flow')
            self.assertEqual(ensure_cloth_model(root)['revision'],model['revision'])

    def test_invalid_polygon_rejected(self):
        for points in ([],[[0,0],[1,1],[2,0]],[[0,0],[0,0],[0,0]]):
            with self.assertRaises(ValueError):validate_cloth_polygon(points)


if __name__=='__main__':unittest.main()
