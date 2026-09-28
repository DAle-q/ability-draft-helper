"""Additional in-game portrait appearances, used only for hero slots."""
import json
from pathlib import Path
from PIL import Image

def load_portraits(root, rows, feature):
    path=Path(root)/'data/hero-portraits.json'
    if not path.exists():return [],[]
    identities=[];templates=[]
    for entry in json.loads(path.read_text()):
        ident=entry['abilityId']
        if ident not in rows:continue
        with Image.open(Path(root)/entry['path']) as image:
            image=image.convert('RGB');w,h=image.size
            for top in [0,10,20,30]:
                for height in [60,72,90,102]:
                    if top+height>102:continue
                    crop=image.crop((0,top*h/102,w,(top+height)*h/102))
                    identities.append(rows[ident]);templates.append(feature(crop))
    return identities,templates
