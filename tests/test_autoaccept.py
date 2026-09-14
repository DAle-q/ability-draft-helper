import unittest
from PIL import Image,ImageDraw,ImageFont
from autoaccept.detector import button_from_words,detect_button

class AcceptDetectionTests(unittest.TestCase):
    def fixture(self,text='ACCEPT GAME',color='#407a22',center=True):
        image=Image.new('RGB',(1920,1080),'#111822');d=ImageDraw.Draw(image)
        x,y=(790,520) if center else (80,60)
        d.rectangle((x-35,y-30,x+350,y+65),fill=color)
        font=ImageFont.truetype('/usr/share/fonts/TTF/DejaVuSans.ttf',32)
        d.text((x,y),text,font=font,fill='white')
        d.text((x-10,y-120),'YOUR GAME IS READY',font=ImageFont.truetype('/usr/share/fonts/TTF/DejaVuSans.ttf',22),fill='white')
        d.text((x+20,y-80),'ABILITY DRAFT',font=font,fill='white')
        return image
    def test_ocr_accept(self):
        b=detect_button(self.fixture())
        self.assertIsNotNone(b);self.assertEqual(b['text'],'ACCEPT GAME')
    def test_green_other_button(self):
        self.assertIsNone(detect_button(self.fixture('FIND MATCH')))
    def test_already_accepted(self):
        self.assertIsNone(detect_button(self.fixture('ACCEPTED')))
    def test_no_green_background(self):
        self.assertIsNone(detect_button(self.fixture(color='#555555')))
    def test_outside_center(self):
        self.assertIsNone(detect_button(self.fixture(center=False)))
    def test_negative_text(self):
        self.assertIsNone(detect_button(self.fixture('DO NOT ACCEPT')))

    def test_missing_draft_header(self):
        im=self.fixture();ImageDraw.Draw(im).rectangle((0,0,1920,480),fill='#111822')
        self.assertIsNone(detect_button(im))
