import unittest
from PIL import Image,ImageDraw
from character_images import remove_chroma

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

class CharacterImageTests(unittest.TestCase):

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
