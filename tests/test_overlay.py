import unittest
from PIL import Image
from overlay.worker import recognize_overlay
from recognizer import prepare_image,slots
import tempfile
from pathlib import Path

class OverlayTests(unittest.TestCase):
    def test_menu_has_no_labels(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'menu.png';Image.new('RGB',(5120,1440),'#000000').save(p)
            self.assertEqual(recognize_overlay(p)['labels'],[])
    def test_inverse_crop_coordinates(self):
        im=Image.new('RGB',(5120,1440));normalized=prepare_image(im)
        scale=1440/1018*.95;left=round(2560-1042*scale);top=round(1440*.025)
        x,y,_=slots(*normalized.size)[0]
        # Inverting the crop must reproduce the original source pixel.
        px,py=round(left+x),round(top+y)
        im.putpixel((px,py),(255,0,0))
        self.assertEqual(prepare_image(im).getpixel((px-left,py-top)),(255,0,0))
