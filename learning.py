"""Durable user corrections, independent of board geometry."""
import json
import hashlib
import os
import tempfile
import fcntl
from pathlib import Path
import numpy as np
from PIL import Image

class Learning:
    def __init__(self, directory):
        self.directory=Path(directory)
        self.path=self.directory/'corrections.json'

    def read(self):
        if not self.path.exists(): return {}
        data=json.loads(self.path.read_text())
        if not isinstance(data,dict): raise ValueError('Invalid corrections file')
        return data

    def save(self, image, ident, hero):
        image=image.resize((64,64),Image.Resampling.LANCZOS).convert('RGB')
        key=hashlib.sha256(image.tobytes()).hexdigest()
        self.directory.mkdir(parents=True,exist_ok=True)
        with (self.directory/'corrections.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            data=self.read()
            data[key]={'abilityId':ident,'hero':hero,'pixels':list(image.resize((16,16),Image.Resampling.BILINEAR).tobytes())}
            fd,name=tempfile.mkstemp(dir=self.directory,suffix='.tmp')
            try:
                with os.fdopen(fd,'w') as out:
                    json.dump(data,out);out.flush();os.fsync(out.fileno())
                os.replace(name,self.path)
            finally:
                if os.path.exists(name):os.unlink(name)

    def match(self, samples, hero):
        scores={}
        for v in self.read().values():
            if v['hero']!=hero:continue
            a=np.asarray(v['pixels'],dtype=np.float32)/255
            a=(a-a.mean())/(a.std()+.10)
            score=float(((samples-a)**2).mean(axis=1).min())
            ident=v['abilityId'];scores[ident]=min(score,scores.get(ident,float('inf')))
        order=sorted(scores,key=scores.get)
        if order and scores[order[0]]<.10 and (len(order)==1 or scores[order[1]]-scores[order[0]]>.04):
            return order[0]
        return None
