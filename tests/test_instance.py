import unittest
import tempfile
import subprocess
import sys
import queue
from pathlib import Path
from types import SimpleNamespace
from instance import Instance
from app import App

class InstanceTests(unittest.TestCase):
    def test_second_process_exits_and_lock_releases(self):
        with tempfile.TemporaryDirectory() as d:
            first=Instance(d);self.assertTrue(first.acquire())
            code='from instance import Instance; import sys; print(Instance(sys.argv[1]).acquire())'
            self.assertEqual(subprocess.check_output([sys.executable,'-c',code,d],text=True).strip(),'False')
            first.lock.close()
            self.assertEqual(subprocess.check_output([sys.executable,'-c',code,d],text=True).strip(),'True')
    def test_delivery_waits_for_edit_and_latest_replaces(self):
        with tempfile.TemporaryDirectory() as d:
            inbox=Instance(d);loaded=[]
            app=SimpleNamespace(inbox=inbox,busy=False,editing=True,seen_request=None,
                messages=queue.Queue(),root=SimpleNamespace(after=lambda *args:None),
                load=loaded.append,poll=lambda:None)
            inbox.send('/tmp/old.png');App.poll(app);self.assertEqual(loaded,[])
            inbox.send('/tmp/new.png');app.editing=False;App.poll(app)
            self.assertEqual(loaded,['/tmp/new.png']);App.poll(app);self.assertEqual(len(loaded),1)
            app.busy=True;inbox.send('/tmp/next.png');App.poll(app);self.assertEqual(len(loaded),1)
            app.busy=False;App.poll(app);self.assertEqual(loaded[-1],'/tmp/next.png')
