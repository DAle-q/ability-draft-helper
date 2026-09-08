"""Single-instance lock and atomic local image requests."""
import fcntl
import json
import os
from pathlib import Path
import tempfile
import uuid

class Instance:
    def __init__(self, state):
        self.state=Path(state);self.state.mkdir(parents=True,exist_ok=True)
        self.lock=None
    def acquire(self):
        self.lock=(self.state/'viewer.lock').open('a')
        try:fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            self.lock.close();self.lock=None;return False
        return True
    def send(self, path):
        request={'id':uuid.uuid4().hex,'path':str(Path(path).resolve())}
        fd,name=tempfile.mkstemp(dir=self.state,suffix='.tmp')
        try:
            with os.fdopen(fd,'w') as out:json.dump(request,out)
            os.replace(name,self.state/'viewer-request.json')
        finally:
            if os.path.exists(name):os.unlink(name)
    def read(self):
        try:return json.loads((self.state/'viewer-request.json').read_text())
        except FileNotFoundError:return None
