"""Capture the active game window, keep only the calibrated draft rectangle."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from PIL import Image
from recognizer import ROOT, atomic_json

STATE = ROOT/'state'


def prepare_capture(im, settings):
    rect = settings.get('captureRect')
    ratio = settings.get('sourceAspect', 0)
    if not rect or len(rect) != 4 or not ratio or abs(im.width/im.height-ratio) > .03:
        return im.copy(), 'calibrate'
    if not (0 <= rect[0] < rect[2] <= 1 and 0 <= rect[1] < rect[3] <= 1):
        return im.copy(), 'calibrate'
    box = tuple(round(v*(im.width if i%2==0 else im.height)) for i,v in enumerate(rect))
    return im.crop(box), 'board'


def deliver(im):
    STATE.mkdir(exist_ok=True)
    settings_file=STATE/'settings.json'
    settings=json.loads(settings_file.read_text()) if settings_file.exists() else {}
    cropped,mode=prepare_capture(im,settings)
    stamp=str(time.time_ns())
    # Immutable filename prevents a newer capture from replacing pixels being read.
    name='capture-'+stamp+'.png'
    cropped.save(STATE/name)
    atomic_json(STATE/'incoming.json',{'id':stamp,'file':name,'mode':mode})
    (STATE/'capture-error.json').unlink(missing_ok=True)


def main():
    STATE.mkdir(exist_ok=True)
    with (STATE/'capture.lock').open('w') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: return
        try:
            with tempfile.TemporaryDirectory(prefix='ability-draft-') as temp:
                output=Path(temp)/'window.png'
                subprocess.run(['spectacle','--background','--activewindow','--no-decoration','--no-shadow','--nonotify','--output',str(output)],check=True,timeout=30)
                if not output.exists():
                    raise RuntimeError('Spectacle не сохранил изображение. Повторите захват на экране драфта.')
                with Image.open(output) as im: deliver(im.convert('RGB'))
            # Existing app holds a lock; this invocation exits without raising it.
            with (STATE/'app.log').open('a') as log:
                subprocess.Popen([str(ROOT/'start.sh'),'--inbox'],stdout=log,stderr=log,start_new_session=True)
        except Exception as exc:
            atomic_json(STATE/'capture-error.json',{'id':str(time.time_ns()),'error':str(exc)})
            subprocess.run(['notify-send','Ability Draft','Не удалось захватить драфт: '+str(exc)],check=False)
            raise

if __name__=='__main__': main()
