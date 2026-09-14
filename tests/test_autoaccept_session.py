"""Run with system Python (PyQt6); no display, captures or real clicks."""
import sys,json,time,unittest
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from autoaccept.runner import Session

class SessionTests(unittest.TestCase):
    def fake(self,result):
        s=Mock();s.current=s.snapshot={'id':'same'};s.target=42;s.input.focused.return_value=42
        s.proc.readAllStandardOutput.return_value=json.dumps(result).encode()
        s.stage='scan';s.started=time.monotonic();s.draft_frames=0;s.clicks=0
        return s
    def test_retry_after_next_match(self):
        s=self.fake({'kind':'accept','button':{'x':1,'y':2},'width':5120,'height':1440})
        Session.finished(s,0);Session.finished(s,0)
        self.assertEqual(s.input.press_enter.call_count,2);self.assertEqual(s.clicks,2)
    def test_no_click_when_focus_changed(self):
        s=self.fake({'kind':'accept'});s.input.focused.return_value=None
        Session.finished(s,0);s.input.press_enter.assert_not_called()
    def test_stale_capture_does_not_click(self):
        s=self.fake({'kind':'accept'});s.started-=10
        Session.finished(s,0);s.input.press_enter.assert_not_called()
    def test_draft_requires_two_frames(self):
        s=self.fake({'kind':'draft'});Session.finished(s,0);s.start_overlay.assert_not_called()
        Session.finished(s,0);s.start_overlay.assert_called_once();s.input.press_enter.assert_not_called()
    def test_error_resets_confirmation(self):
        s=self.fake({'kind':'draft'});Session.finished(s,0);Session.finished(s,1)
        self.assertEqual(s.draft_frames,0);s.start_overlay.assert_not_called()
if __name__=='__main__':unittest.main()
