import json,tempfile,unittest
from pathlib import Path
from PIL import Image
from recognizer import Recognizer,slots,ROOT

NAMES=['lone_druid','venomancer','magnataur','tidehunter','shredder','dark_willow',
       'sven','bristleback','rubick','furion','lion','slardar']
class HeroPortraitTests(unittest.TestCase):
    def test_real_draft_crops_without_manual_learning(self):
        board=Image.new('RGB',(2048,1018))
        for name,(x,y,_) in zip(NAMES,[p for p in slots(2048,1018) if p[2]]):
            with Image.open(ROOT/'tests/fixtures/hero-draft'/f'{name}.png') as crop:
                board.paste(crop,(int(x)-36,int(y)-36))
        with tempfile.TemporaryDirectory() as d:
            recognizer=Recognizer(learned_dir=d)
            results=[r for r in recognizer.recognize(board) if r['hero']]
        ids={r['shortName']:r['abilityId'] for r in json.loads((ROOT/'data/icon-manifest.json').read_text())}
        self.assertGreaterEqual(sum(r['accepted'] for r in results),9)
        for name,result in zip(NAMES,results):
            self.assertEqual(result['abilityId'],ids[name],name)
    def test_extra_portraits_are_unique_known_heroes(self):
        entries=json.loads((ROOT/'data/hero-portraits.json').read_text())
        ids=[e['abilityId'] for e in entries]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertTrue(all(i<0 for i in ids))
