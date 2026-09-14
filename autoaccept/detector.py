"""Conservative English accept-button detection; no input operations here."""
import csv,io,re,subprocess
import numpy as np
from PIL import Image

def button_from_words(image, words):
    w,h=image.size
    groups={}
    for word in words:
        if float(word.get('conf',-1))<65:continue
        key=tuple(word.get(k) for k in ('block_num','par_num','line_num'))
        groups.setdefault(key,[]).append(word)
    candidates=[]
    for line in groups.values():
        line.sort(key=lambda t:int(t['left']))
        text=' '.join(re.sub('[^A-Z]','',t['text'].upper()) for t in line).strip()
        if text not in ('ACCEPT','ACCEPT GAME','ACCEPT MATCH'):continue
        x=min(int(t['left']) for t in line);y=min(int(t['top']) for t in line)
        right=max(int(t['left'])+int(t['width']) for t in line)
        bottom=max(int(t['top'])+int(t['height']) for t in line)
        cx=(x+right)/2;cy=(y+bottom)/2;th=bottom-y
        above=[t for t in words if float(t.get('conf',-1))>=65
               and y-h*.25<int(t['top'])<y
               and abs(int(t['left'])+int(t['width'])/2-cx)<w*.12]
        header=' '.join(t['text'].upper() for t in above)
        if not ('ABILITY' in header and 'DRAFT' in header and 'READY' in header):continue
        if not (.35*w<cx<.65*w and .25*h<cy<.78*h and th>=9):continue
        # Require green background surrounding the text, not merely green letters.
        box=(max(0,int(x-th)),max(0,int(y-th*.7)),min(w,int(right+th)),min(h,int(bottom+th*.7)))
        a=np.asarray(image.crop(box)).astype(float)
        green=(a[:,:,1]>a[:,:,0]*1.12)&(a[:,:,1]>a[:,:,2]*1.12)&(a[:,:,1]>45)
        if green.mean()<.32:continue
        candidates.append({'x':cx,'y':cy,'text':text})
    return candidates[0] if len(candidates)==1 else None

def detect_button(image):
    # Reduce ultrawide capture to a central region; coordinates remain source pixels.
    w,h=image.size;left=int(w*.3);top=int(h*.2)
    crop=image.crop((left,top,int(w*.7),int(h*.82)))
    # White lettering on a dark/green button: normalize for OCR.
    crop=crop.convert('L').point(lambda p:0 if p>170 else 255)
    payload=io.BytesIO();crop.save(payload,format='PNG')
    result=subprocess.run(['tesseract','stdin','stdout','-l','eng','--psm','11','tsv'],
                          input=payload.getvalue(),capture_output=True,timeout=8,check=True)
    words=list(csv.DictReader(io.StringIO(result.stdout.decode()),delimiter='\t'))
    for word in words:
        word['left']=int(word['left'])+left;word['top']=int(word['top'])+top
    return button_from_words(image,words)
