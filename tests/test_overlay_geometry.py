import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'overlay'))
from geometry import window_rect
class GeometryTests(unittest.TestCase):
    def test_lower_monitor_125_percent(self):
        g=dict(x=0,y=1152,width=4096,height=1152,output=dict(x=0,y=1152))
        self.assertEqual(window_rect(g,(0,1440)),(0,1440,4096,1152))
    def test_upper_monitor_and_window_offset(self):
        g=dict(x=772,y=50,width=1200,height=600,output=dict(x=672,y=0))
        self.assertEqual(window_rect(g,(840,0)),(940,50,1200,600))
    def test_negative_origin(self):
        g=dict(x=-1800,y=40,width=1000,height=700,output=dict(x=-1920,y=0))
        self.assertEqual(window_rect(g,(-2400,0)),(-2280,40,1000,700))
