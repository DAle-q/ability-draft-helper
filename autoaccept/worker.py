import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
from autoaccept.detector import detect_button
from overlay.worker import recognize_overlay

def scan(path):
    image=Image.open(path).convert('RGB')
    # Existing draft recognition remains read-only and unchanged.
    if abs(image.width/image.height-5120/1440)<.03:
        draft=recognize_overlay(path)
        if 'font' in draft:return {'kind':'draft'}
    button=detect_button(image)
    return {'kind':'accept' if button else 'waiting','button':button,
            'width':image.width,'height':image.height}
if __name__=='__main__':
    try:print(json.dumps(scan(sys.argv[1])))
    except Exception as exc:print(str(exc),file=sys.stderr);sys.exit(1)
