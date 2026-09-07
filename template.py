"""Draw a numbered perspective grid template for manual calibration."""
from pathlib import Path
import argparse
from PIL import Image, ImageDraw, ImageFont
from recognizer import slots

p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('--output',default='outputs/grid-template.png');a=p.parse_args()
im=Image.open(a.input).convert('RGB'); out=im.copy(); d=ImageDraw.Draw(out); w,h=im.size
try: font=ImageFont.truetype('/usr/share/fonts/TTF/DejaVuSans-Bold.ttf',max(12,int(16*min(w/1494,h/1158))))
except OSError: font=ImageFont.load_default()
for r in slots(w,h,'board'):
    x,y,sx,sy=(r[k] for k in ('x','y','sx','sy'))
    # Tile-shaped quadrilateral: slightly narrower at the top, following the board's perspective.
    half={'ultimate':37, 'standard':39, 'hero':37}[r['kind']]
    hw,hh=half*sx,half*sy
    skew=(6*sx if y < h*.45 else 3*sx)
    # Mirror the slant on the right side of the board.
    sign = -1 if x > w*.5 else 1
    poly=[(x-hw+sign*skew,y-hh),(x+hw+sign*skew,y-hh),(x+hw-sign*skew,y+hh),(x-hw-sign*skew,y+hh)]
    color={'ultimate':'#ffd54a','standard':'#43d7ff','hero':'#c0c0c0'}[r['kind']]
    d.line(poly+[poly[0]],fill=color,width=max(2,int(2*sx)))
    label=str(r['slot']+1); bb=d.textbbox((0,0),label,font=font); tw=bb[2]-bb[0];th=bb[3]-bb[1]
    d.rounded_rectangle((x-tw/2-4,y-th/2-3,x+tw/2+4,y+th/2+3),radius=3,fill='#101722',outline=color,width=max(1,int(sx)))
    d.text((x-tw/2,y-th/2-bb[1]),label,font=font,fill=color)
Path(a.output).parent.mkdir(parents=True,exist_ok=True);out.save(a.output)
print(a.output)
