import json
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from recognizer import Recognizer, slots, recommendations, annotate
from capture import prepare_capture

class CoreTests(unittest.TestCase):
    def test_layout_and_ranking(self):
        rows=slots(800,699,'board')
        self.assertEqual([sum(r['kind']==k for r in rows) for k in ['ultimate','standard','hero']],[12,36,12])
        for r in rows:r.update(accepted=True,available=True,winrate=.5,abilityId=r['slot'])
        rows[0]['winrate']=.75;rows[1]['winrate']=.99;rows[1]['available']=False
        rows[12]['winrate']=1 # hero must never rank
        rows[13]['winrate']=.95;rows[13]['accepted']=False
        rows[14]['winrate']=.7;rows[15]['winrate']=.8;rows[16]['winrate']=.9
        self.assertEqual(recommendations(rows),{0:1,16:1,15:2,14:3})
        out=annotate(Image.new('RGB',(800,699)),rows)
        self.assertEqual(out.size,(800,699))

    def test_learning_survives_restart_and_moves_with_icon(self):
        with tempfile.TemporaryDirectory() as d:
            e=Recognizer(d);board=Image.new('RGB',(800,699),'#303030');positions=slots(800,699,'board')
            rng=np.random.default_rng(17)
            icon=Image.fromarray(rng.integers(40,230,(48,48,3),dtype=np.uint8))
            a=positions[0];b=positions[7]
            for p in [a,b]:board.paste(icon,(int(p['x']-24),int(p['y']-24)))
            choices=e.choices('ultimate');identity=choices[0]['abilityId']
            digest=e.learn(board,a,identity)
            e=Recognizer(d);results=e.recognize(board,'board')
            for i in [0,7]:
                self.assertTrue(results[i]['accepted']);self.assertEqual(results[i]['abilityId'],identity);self.assertEqual(results[i]['source'],'learned')
            self.assertEqual(len(e.examples),1)
            # Reassigning the same picture replaces its old label, rather than creating contradictory examples.
            replacement=choices[1]['abilityId'];self.assertEqual(e.learn(board,a,replacement),digest)
            self.assertEqual(len(e.examples),1)
            self.assertEqual(Recognizer(d).recognize(board,'board')[7]['abilityId'],replacement)
            self.assertTrue(e.forget(board,a));self.assertEqual(len(Recognizer(d).examples),0)
            with self.assertRaises(ValueError):e.learn(board,{**a,'available':False},identity)

    def test_capture_calibration(self):
        image=Image.new('RGB',(2000,1000))
        crop,mode=prepare_capture(image,{})
        self.assertEqual(mode,'calibrate')
        settings={'captureRect':[.25,.1,.75,.9],'sourceAspect':2}
        crop,mode=prepare_capture(image,settings)
        self.assertEqual((crop.size,mode),((1000,800),'board'))
        self.assertEqual(prepare_capture(Image.new('RGB',(1000,1000)),settings)[1],'calibrate')
        self.assertEqual(prepare_capture(image,{**settings,'captureRect':[-1,0,1,1]})[1],'calibrate')

if __name__=='__main__':unittest.main()
