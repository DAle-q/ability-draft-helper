"""Capture a full screenshot for the restored original viewer."""
from pathlib import Path
import subprocess
import tempfile
import fcntl
import os
from recognizer import ROOT

def main():
    state = ROOT / 'state'
    state.mkdir(exist_ok=True)
    lock=(state/'capture.lock').open('a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:return
    output = state / 'full-capture-pending.png'
    subprocess.run(['spectacle', '--background', '--activewindow', '--no-decoration', '--no-shadow', '--nonotify', '--output', str(output)], check=True, timeout=30)
    os.replace(output,state/'full-capture.png')
    output=state/'full-capture.png'
    with (state / 'app.log').open('a') as log:
        subprocess.Popen([str(ROOT / 'start.sh'), str(output)], stdout=log, stderr=log, start_new_session=True)

if __name__ == '__main__':
    main()
