"""Capture a full screenshot for the restored original viewer."""
from pathlib import Path
import subprocess
import tempfile
from recognizer import ROOT

def main():
    state = ROOT / 'state'
    state.mkdir(exist_ok=True)
    output = state / 'full-capture.png'
    subprocess.run(['spectacle', '--background', '--activewindow', '--no-decoration', '--no-shadow', '--nonotify', '--output', str(output)], check=True, timeout=30)
    with (state / 'app.log').open('a') as log:
        subprocess.Popen([str(ROOT / 'start.sh'), str(output)], stdout=log, stderr=log, start_new_session=True)

if __name__ == '__main__':
    main()
