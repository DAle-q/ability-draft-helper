"""Offline icon matching for the full, uncropped Ability Draft screen layout."""
from pathlib import Path
import json
import numpy as np
from learning import Learning
from PIL import Image, ImageDraw, ImageFont
ROOT=Path(__file__).resolve().parent

def prepare_image(im):
    """Normalize the centered ultrawide draft UI to the original reference."""
    if im.width / im.height > 3:
        scale = im.height / 1018 * .95
        left = im.width / 2 - 1042 * scale
        top = im.height * .025
        return im.crop((round(left), round(top), round(left + 2048*scale), round(top + 1018*scale)))
    # A cropped board-and-players screenshot supplied for build review.
    if abs(im.width/im.height - 2458/1355) < .005:
        unit = im.width/2048
        scale = 1.135*unit
        canvas = Image.new('RGB', (round(2048*scale), round(1018*scale)), '#121923')
        canvas.paste(im, (round(181*unit), round(42*unit)))
        return canvas
    return im

def side_slots(w,h):
    return [(x*w/2048, y*h/1018, False, team*5+row)
            for team, xs in enumerate(([338,398,458,518], [1564,1624,1684,1744]))
            for row,y in enumerate([235,400,565,730,895]) for x in xs]

def build_averages(results):
    groups = {}
    for r in results:
        if 'player' in r:
            groups.setdefault(r['player'], []).append(r)
    return {player: (sum(r['winrate'] for r in items if r['accepted']) / n if n else None, n)
            for player,items in groups.items()
            for n in [sum(bool(r['accepted']) for r in items)]}

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
    def __init__(self, learned_dir=None):
        self.learning=Learning(learned_dir or ROOT/'data/learned-icons')
        data=json.loads((ROOT/'data/windrun-7.41d.json').read_text())
        manifest=json.loads((ROOT/'data/icon-manifest.json').read_text())
        rows={r['abilityId']:r for r in data['abilityStats']}
        self.rows=rows
        self.groups={}
        for hero in [False,True]:
            entries=[m for m in manifest if m['status']=='ok' and (m['abilityId']<0)==hero]
            self.groups[hero]=([rows[m['abilityId']] for m in entries],np.stack([feature(Image.open(ROOT/m['path'])) for m in entries]))
    def learn(self, im, result, ident):
        scale=im.width/2048
        x,y=result['x'],result['y']
        crop=im.crop((x-24*scale,y-24*scale,x+24*scale,y+24*scale))
        if np.asarray(crop).mean()/255 < .07:
            raise ValueError('Cannot learn an empty or dark icon.')
        self.learning.save(crop,ident,result['hero'])

    def recognize(self,im):
        im=im.convert('RGB'); w,h=im.size
        if abs(w/h-2048/1018)>.08: raise ValueError('Нужен полный скриншот драфта с соотношением сторон около 2:1. Обрезанные изображения пока не поддерживаются.')
        result=[]; scale=w/2048
        for x,y,hero,player in [(*v,None) for v in slots(w,h)] + side_slots(w,h):
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
            learned=self.learning.match(samples,hero) if brightness>.07 else None
            if learned is not None and learned in self.rows:
                row=self.rows[learned];accepted=True
            result.append({'x':x,'y':y,'hero':hero,'accepted':bool(accepted),'score':round(score,4),'margin':round(margin,4),'abilityId':row['abilityId'],'name':row['name'],'winrate':row['winrate'],'candidates':[{'name':rows[int(k)]['name'],'winrate':rows[int(k)]['winrate'],'score':round(float(best[k]),4)} for k in order[:3]]})
            if player is not None:
                result[-1]['player']=player
        return result

def winrate_color(rate):
    """Continuous color scale: <=45 red, 48 orange, 50 yellow, >=55 green."""
    stops = [(0.45, (255, 148, 148)), (0.48, (255, 179, 71)),
             (0.50, (255, 232, 92)), (0.55, (71, 255, 117))]
    if rate <= stops[0][0]:
        rgb = stops[0][1]
    elif rate >= stops[-1][0]:
        rgb = stops[-1][1]
    else:
        for (lo, a), (hi, b) in zip(stops, stops[1:]):
            if lo <= rate <= hi:
                t = (rate - lo) / (hi - lo)
                rgb = tuple(round(x + (y-x)*t) for x, y in zip(a, b))
                break
    return '#%02x%02x%02x' % rgb

def annotate(im,results):
    out=im.convert('RGB').copy();d=ImageDraw.Draw(out);scale=im.width/2048
    try: font=ImageFont.truetype('/usr/share/fonts/TTF/DejaVuSans-Bold.ttf',max(12,int(15*scale)))
    except OSError: font=ImageFont.load_default(size=max(12,int(15*scale)))
    for r in results:
        text=f"{r['winrate']*100:.1f}%" if r['accepted'] else '?'
        color=winrate_color(r['winrate']) if r['accepted'] else '#d5d9df'
        x=r['x'];y=r['y']+22*scale
        box=d.textbbox((0,0),text,font=font);tw=box[2];th=box[3]-box[1]
        d.rounded_rectangle((x-tw/2-5*scale,y,x+tw/2+5*scale,y+th+8*scale),radius=3*scale,fill='#121a24',outline=color)
        d.text((x-tw/2,y+3*scale-box[1]),text,font=font,fill=color)
    for player,(average,count) in build_averages(results).items():
        members=[r for r in results if r.get('player')==player]
        x=min(r['x'] for r in members)-27*scale
        y=members[0]['y']-58*scale
        text=(f"AVG {average*100:.1f}%" if average is not None else 'AVG --')+f"  {count}/4"
        color=winrate_color(average) if average is not None else '#d5d9df'
        box=d.textbbox((0,0),text,font=font);tw=box[2];th=box[3]-box[1]
        d.rounded_rectangle((x-5*scale,y,x+tw+5*scale,y+th+8*scale),radius=3*scale,fill='#121a24',outline=color)
        d.text((x,y+3*scale-box[1]),text,font=font,fill=color)
    return out

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('--output',default='outputs/annotated.png');a=p.parse_args()
    im=Image.open(a.input);results=Recognizer().recognize(im);out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);annotate(im,results).save(out);out.with_suffix('.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    print(f'{sum(r["accepted"] for r in results)}/{len(results)} confident matches; output: {out}')
