"""Offline icon matching for the full, uncropped Ability Draft screen layout."""
from pathlib import Path
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parent

def feature(im):
    a=np.asarray(im.resize((16,16),Image.Resampling.BILINEAR).convert('RGB'),dtype=np.float32)/255
    a=a.reshape(-1)
    return (a-a.mean())/(a.std()+.10)

def slots(w,h):
    # Reference coordinates describe UI geometry only, never ability identities.
    coords=[]
    for y in [166,263]:
        for x in [807,900,995,1090,1184,1278]: coords.append((x,y,False))
    for y,xs in [(338,[738,834,912,993,1095,1173,1250,1344]),(403,[727,829,909,992,1096,1175,1253,1353]),(472,[717,824,905,990,1098,1178,1258,1363]),(584,[703,815,901,987,1100,1184,1267,1378]),(667,[691,809,899,986,1102,1188,1274,1391]),(754,[678,804,897,985,1105,1193,1282,1405])]:
        for j,x in enumerate(xs): coords.append((x,y,j in (0,7)))
    return [(x*w/2048,y*h/1018,hero) for x,y,hero in coords]

class Recognizer:
    def __init__(self):
        data=json.loads((ROOT/'data/windrun-7.41d.json').read_text())
        manifest=json.loads((ROOT/'data/icon-manifest.json').read_text())
        rows={r['abilityId']:r for r in data['abilityStats']}
        self.groups={}
        for hero in [False,True]:
            entries=[m for m in manifest if m['status']=='ok' and (m['abilityId']<0)==hero]
            self.groups[hero]=([rows[m['abilityId']] for m in entries],np.stack([feature(Image.open(ROOT/m['path'])) for m in entries]))
    def recognize(self,im):
        im=im.convert('RGB'); w,h=im.size
        if abs(w/h-2048/1018)>.08: raise ValueError('Нужен полный скриншот драфта с соотношением сторон около 2:1. Обрезанные изображения пока не поддерживаются.')
        result=[]; scale=w/2048
        for x,y,hero in slots(w,h):
            rows,templates=self.groups[hero]
            crops=[]; boxes=[]
            for size in [42,48,54,60]:
                for dx,dy in [(0,0),(-3,0),(3,0),(0,-3),(0,3)]:
                    box=(x+(dx-size/2)*scale,y+(dy-size/2)*scale,x+(dx+size/2)*scale,y+(dy+size/2)*scale)
                    crops.append(feature(im.crop(box)));boxes.append(box)
            samples=np.stack(crops)
            distances=((samples[:,None,:]-templates[None,:,:])**2).mean(axis=2)
            best=distances.min(axis=0); order=np.argsort(best); idx=int(order[0]); score=float(best[idx]);margin=float(best[order[1]]-score)
            row=rows[idx]
            brightness=np.asarray(im.crop((x-18*scale,y-18*scale,x+18*scale,y+18*scale))).mean()/255
            accepted=score<(.22 if hero else .30) and margin>.065 and brightness>.07
            result.append({'x':x,'y':y,'hero':hero,'accepted':bool(accepted),'score':round(score,4),'margin':round(margin,4),'abilityId':row['abilityId'],'name':row['name'],'winrate':row['winrate'],'candidates':[{'name':rows[int(k)]['name'],'winrate':rows[int(k)]['winrate'],'score':round(float(best[k]),4)} for k in order[:3]]})
        return result

def annotate(im,results):
    out=im.convert('RGB').copy();d=ImageDraw.Draw(out);scale=im.width/2048
    try: font=ImageFont.truetype('/usr/share/fonts/TTF/DejaVuSans-Bold.ttf',max(12,int(15*scale)))
    except OSError: font=ImageFont.load_default(size=max(12,int(15*scale)))
    for r in results:
        text=f"{r['winrate']*100:.1f}%" if r['accepted'] else '?'
        color=('#8bf0b0' if r['winrate']>=.5 else '#ffbd83') if r['accepted'] else '#d5d9df'
        x=r['x'];y=r['y']+22*scale
        box=d.textbbox((0,0),text,font=font);tw=box[2];th=box[3]-box[1]
        d.rounded_rectangle((x-tw/2-5*scale,y,x+tw/2+5*scale,y+th+8*scale),radius=3*scale,fill='#121a24',outline=color)
        d.text((x-tw/2,y+3*scale-box[1]),text,font=font,fill=color)
    return out

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('--output',default='outputs/annotated.png');a=p.parse_args()
    im=Image.open(a.input);results=Recognizer().recognize(im);out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);annotate(im,results).save(out);out.with_suffix('.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    print(f'{sum(r["accepted"] for r in results)}/{len(results)} confident matches; output: {out}')
