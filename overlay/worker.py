"""Screenshot-only recognition worker using the existing Python runtime."""
import sys
import json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from recognizer import prepare_image, Recognizer, winrate_color
from PIL import Image
import numpy as np

def recognize_overlay(path):
    with Image.open(path) as source:
        raw=source.convert('RGB')
    w,h=raw.size
    if abs(w/h - 5120/1440) > .03:
        raise ValueError('Overlay currently calibrated for a 32:9 Dota window.')
    scale=h/1018*.95
    left=round(w/2-1042*scale);top=round(h*.025)
    board=prepare_image(raw)
    # Draft brackets: guard against drawing guesses over actual gameplay/menu.
    a=np.asarray(board.resize((2048,1018)))
    hits=0
    for x1,y1,x2,y2 in [(750,112,785,140),(1295,110,1340,142),
                           (750,275,790,312),(1295,275,1340,312)]:
        rgb=a[y1:y2,x1:x2].astype(float)
        hits+=int(((rgb[:,:,1]>rgb[:,:,0]*1.25)&(rgb[:,:,1]>rgb[:,:,2]*1.08)&(rgb[:,:,1]>65)).sum()>12)
    if hits<2:return {'width':w,'height':h,'labels':[],'status':'Waiting for draft board'}
    results=Recognizer().recognize(board)
    labels=[{'x':left+r['x'],'y':top+r['y']+22*board.width/2048,
             'text':f"{r['winrate']*100:.1f}%",'color':winrate_color(r['winrate'])}
            for r in results if r['accepted']]
    return {'width':w,'height':h,'font':15*board.width/2048,'labels':labels,
            'status':f'{len(labels)} percentages'}

if __name__=='__main__':
    try:print(json.dumps(recognize_overlay(sys.argv[1])))
    except Exception as exc:
        print(str(exc),file=sys.stderr);sys.exit(1)
