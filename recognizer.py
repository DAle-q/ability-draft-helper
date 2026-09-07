"""Offline matching, persistent user examples, and draft recommendations."""
from pathlib import Path
import hashlib
import json
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
REFERENCE = (2048, 1018)
BOARD = (640, 115, 1440, 814)


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    os.replace(temp, path)


def feature(im):
    a = np.asarray(im.resize((16, 16), Image.Resampling.BILINEAR).convert('RGB'), dtype=np.float32).reshape(-1) / 255
    return (a - a.mean()) / (a.std() + .10)


def board_box(size):
    w, h = size
    return tuple(round(v * (w / REFERENCE[0] if i % 2 == 0 else h / REFERENCE[1])) for i, v in enumerate(BOARD))


def crop_board(im):
    return im.crop(board_box(im.size))


def slots(w, h, mode='full'):
    coords = []
    for y in [166, 263]:
        for x in [807, 900, 995, 1090, 1184, 1278]:
            coords.append((x, y, 'ultimate'))
    for y, xs in [(338, [738,834,912,993,1095,1173,1250,1344]), (403, [727,829,909,992,1096,1175,1253,1353]), (472, [717,824,905,990,1098,1178,1258,1363]), (584, [703,815,901,987,1100,1184,1267,1378]), (667, [691,809,899,986,1102,1188,1274,1391]), (754, [678,804,897,985,1105,1193,1282,1405])]:
        for j, x in enumerate(xs):
            coords.append((x, y, 'hero' if j in (0, 7) else 'standard'))
    # Board screenshots are cropped with side margins; use a compact horizontal calibration.
    ox, oy, bw, bh = (0, 0, *REFERENCE) if mode == 'full' else (520, BOARD[1], 1050, BOARD[3]-BOARD[1])
    return [{'slot': i, 'x': (x-ox)*w/bw, 'y': (y-oy)*h/bh, 'kind': kind, 'hero': kind == 'hero', 'sx': w/bw, 'sy': h/bh} for i, (x, y, kind) in enumerate(coords)]


def icon_crop(im, slot, size=48):
    x, y, sx, sy = (slot[k] for k in ('x', 'y', 'sx', 'sy'))
    return im.crop((x-size/2*sx, y-size/2*sy, x+size/2*sx, y+size/2*sy)).convert('RGB')


class Recognizer:
    def __init__(self, learned_dir=None):
        data = json.loads((ROOT/'data/windrun-7.41d.json').read_text())
        self.rows = {r['abilityId']: r for r in data['abilityStats'] if 'name' in r}
        manifest = json.loads((ROOT/'data/icon-manifest.json').read_text())
        self.learned_dir = Path(learned_dir) if learned_dir else ROOT/'data/learned-icons'
        self.entries = [m for m in manifest if m['status'] == 'ok']
        self.vendor_features = {m['abilityId']: feature(Image.open(ROOT/m['path'])) for m in self.entries}
        self.reload_examples()

    def choices(self, kind):
        return [r for r in self.rows.values() if (r['abilityId'] < 0 if kind == 'hero' else r['abilityId'] > 0 and (r.get('isUltimate') is True if kind == 'ultimate' else r.get('isUltimate') is not True))]

    def reload_examples(self):
        self.examples = {}
        self.learning_error = None
        index = self.learned_dir/'index.json'
        try:
            self.examples = json.loads(index.read_text()) if index.exists() else {}
            if not isinstance(self.examples, dict):
                raise ValueError('Индекс образцов должен быть словарём')
        except (OSError, ValueError) as exc:
            self.examples = {}
            self.learning_error = str(exc)
        self.groups = {}
        for kind in ['ultimate', 'standard', 'hero']:
            rows = self.choices(kind)
            features, ids, sources = [], [], []
            allowed = {r['abilityId'] for r in rows}
            for ident in allowed:
                if ident in self.vendor_features:
                    features.append(self.vendor_features[ident]); ids.append(ident); sources.append('valve')
            for digest, sample in self.examples.items():
                if sample['abilityId'] not in allowed:
                    continue
                try:
                    # Filenames are derived from a validated digest, not arbitrary index paths.
                    if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
                        raise ValueError('Invalid example hash')
                    features.append(feature(Image.open(self.learned_dir/(digest+'.png'))))
                    ids.append(sample['abilityId']); sources.append('learned')
                except (OSError, ValueError) as exc:
                    self.learning_error = str(exc)
            self.groups[kind] = (np.stack(features), np.array(ids), sources)

    def learn(self, im, slot, ability_id):
        if self.learning_error:
            raise ValueError('Не удалось прочитать сохранённые образцы: '+self.learning_error)
        if ability_id not in {r['abilityId'] for r in self.choices(slot['kind'])}:
            raise ValueError('Способность не относится к этой группе')
        if not slot.get('available', True):
            raise ValueError('Затемнённую позицию нельзя использовать как образец. Выберите видимую иконку.')
        sample = icon_crop(im, slot).resize((64, 64), Image.Resampling.LANCZOS)
        digest = hashlib.sha256(sample.tobytes()).hexdigest()
        self.learned_dir.mkdir(parents=True, exist_ok=True)
        sample.save(self.learned_dir/(digest+'.png'))
        self.examples[digest] = {'abilityId': ability_id, 'name': self.rows[ability_id]['name']}
        atomic_json(self.learned_dir/'index.json', self.examples)
        self.reload_examples()
        return digest

    def forget(self, im, slot):
        sample = icon_crop(im, slot).resize((64,64), Image.Resampling.LANCZOS)
        digest = hashlib.sha256(sample.tobytes()).hexdigest()
        if digest in self.examples:
            del self.examples[digest]
            atomic_json(self.learned_dir/'index.json', self.examples)
            self.reload_examples()
            return True
        return False

    def recognize(self, im, mode='full'):
        im = im.convert('RGB'); w, h = im.size
        if mode not in ('full', 'board'):
            raise ValueError('Неизвестный формат изображения')
        if mode == 'full' and abs(w/h - REFERENCE[0]/REFERENCE[1]) > .08:
            raise ValueError('Выделите область драфта: кнопка «Выделить сетку». Нужны все иконки, включая портреты по краям.')
        result = []
        for slot in slots(w, h, mode):
            x, y, sx, sy = (slot[k] for k in ('x','y','sx','sy'))
            templates, ids, sources = self.groups[slot['kind']]
            crops = []
            for size in [34,40,46,52,58,64,72]:
                for dx,dy in [(0,0),(-4,0),(4,0),(0,-4),(0,4),(-8,0),(8,0),(0,-8),(0,8),(-12,0),(12,0),(0,-12),(0,12)]:
                    shifted = {**slot, 'x': x+dx*sx, 'y': y+dy*sy}
                    crops.append(feature(icon_crop(im, shifted, size)))
            samples = np.stack(crops)
            distances = ((samples[:,None,:]-templates[None,:,:])**2).mean(axis=2).min(axis=0)
            # Multiple examples of the same ability must not compete in the margin test.
            by_id = {}
            for i, ident in enumerate(ids):
                ident = int(ident)
                if ident not in by_id or distances[i] < distances[by_id[ident]]:
                    by_id[ident] = i
            order = sorted(by_id, key=lambda ident: float(distances[by_id[ident]]))
            ident = order[0]; ti = by_id[ident]
            score = float(distances[ti]); margin = float(distances[by_id[order[1]]] - score)
            row = self.rows[ident]
            brightness = float(np.asarray(icon_crop(im, slot, 36)).mean()/255)
            available = brightness > .07
            learned = sources[ti] == 'learned'
            accepted = available and score < (.28 if learned else (.55 if slot['hero'] else .50)) and margin > (.018 if learned else .012)
            result.append({**slot, 'available': available, 'accepted': bool(accepted), 'source': sources[ti], 'score': round(score,4), 'margin': round(margin,4), 'abilityId': ident, 'name': row['name'], 'winrate': row['winrate'], 'candidates': [{'abilityId': k, 'name': self.rows[k]['name'], 'winrate': self.rows[k]['winrate']} for k in order[:3]]})
        return result


def recommendations(results):
    selected = {}
    for kind, count in [('ultimate',1), ('standard',3)]:
        eligible = [r for r in results if r['kind'] == kind and r['accepted'] and r.get('available', True)]
        for rank, r in enumerate(sorted(eligible, key=lambda r: (-r['winrate'],r['slot']))[:count],1):
            selected[r['slot']] = rank
    return selected


def annotate(im, results):
    """Draw compact, consistent labels anchored to each tile's lower edge."""
    out=im.convert('RGB').copy(); d=ImageDraw.Draw(out)
    scale = min(results[0]['sx'],results[0]['sy']) if results else im.width/REFERENCE[0]
    try: font=ImageFont.truetype('/usr/share/fonts/TTF/DejaVuSans-Bold.ttf',max(13,int(15*scale)))
    except OSError: font=ImageFont.load_default(size=max(13,int(15*scale)))
    best = recommendations(results)
    for r in results:
        x=r['x']; y=r['y']
        # Place every label below its icon center using the same anchor.
        label_y = y + 25*r['sy']
        if r['accepted']:
            text=f"{r['winrate']*100:.1f}%"
            color = '#8bf0b0' if r['winrate']>=.5 else '#ffbd83'
            if r['slot'] in best:
                color = '#ffe173' if r['kind']=='ultimate' else '#64e9ff'
                d.rounded_rectangle((x-27*r['sx'], y-27*r['sy'], x+27*r['sx'], y+36*r['sy']), radius=3*scale, outline=color, width=max(2,int(2*scale)))
                d.text((x-23*r['sx'],y-25*r['sy']),str(best[r['slot']]),font=font,fill=color,stroke_width=max(1,int(scale)),stroke_fill='#101722')
            # Text only: no wide rectangle that can hide the icon. A dark outline keeps it readable.
            bbox=d.textbbox((0,0),text,font=font,stroke_width=max(1,int(2*scale))); tw=bbox[2]-bbox[0]
            d.text((x-tw/2,label_y-bbox[1]),text,font=font,fill=color,stroke_width=max(1,int(2*scale)),stroke_fill='#101722')
        else:
            # Uncertain slots remain visible as small, square question markers.
            side=max(14,int(17*scale)); half=side/2
            d.rounded_rectangle((x-half,label_y-half,x+half,label_y+half),radius=2*scale,fill='#121a24',outline='#d5d9df',width=max(1,int(scale)))
            qbbox=d.textbbox((0,0),'?',font=font); qw=qbbox[2]-qbbox[0]; qh=qbbox[3]-qbbox[1]
            d.text((x-qw/2,label_y-qh/2-qbbox[1]),'?',font=font,fill='#d5d9df',stroke_width=max(1,int(scale)),stroke_fill='#121a24')
    return out



if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('--mode',choices=['full','board'],default='full');p.add_argument('--output',default='outputs/annotated.png');a=p.parse_args()
    im=Image.open(a.input);results=Recognizer().recognize(im,a.mode);out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);annotate(im,results).save(out);atomic_json(out.with_suffix('.json'),results)
    print(f'{sum(r["accepted"] for r in results)}/{len(results)} confident matches; output: {out}')
