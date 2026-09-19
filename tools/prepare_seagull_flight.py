"""Cut, de-background and normalize the approved eight-frame seagull sheet."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from PIL import Image

def main():
    p=argparse.ArgumentParser(); p.add_argument('source',type=Path); p.add_argument('asset_root',type=Path); a=p.parse_args()
    sheet=Image.open(a.source).convert('RGBA'); out=a.asset_root/'assets'/'ambient'/'seagull_north'/'frames'; out.mkdir(parents=True,exist_ok=True)
    cols,rows=4,2; cw,ch=sheet.width//cols,sheet.height//rows
    names=[]
    for i in range(8):
        x=(i%cols)*cw; y=(i//cols)*ch; im=sheet.crop((x,y,x+cw,y+ch)).convert('RGBA'); px=im.load()
        for yy in range(ch):
            for xx in range(cw):
                r,g,b,al=px[xx,yy]
                # Black studio background and shadow are not part of this aerial sprite.
                if max(r,g,b)<=52: px[xx,yy]=(0,0,0,0)
                elif al<255: px[xx,yy]=(r,g,b,al)
        box=im.getbbox()
        if not box: raise RuntimeError(f'empty frame {i}')
        bird=im.crop(box); canvas=Image.new('RGBA',(128,128)); scale=min(112/bird.width,112/bird.height)
        bird=bird.resize((round(bird.width*scale),round(bird.height*scale)),Image.Resampling.LANCZOS)
        canvas.alpha_composite(bird,((128-bird.width)//2,(128-bird.height)//2))
        name=f'flight_north_{i:02d}.png'; canvas.save(out/name); names.append('assets/ambient/seagull_north/frames/'+name)
    manifest={'id':'seagull_north','clips':[{'id':'fly_north_calm','state':'fly','direction':'north','fps':3.5,'loop':True,'frames':names}]}
    d=a.asset_root/'assets'/'definitions'/'animations'; d.mkdir(parents=True,exist_ok=True); (d/'seagull_north.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'frames':len(names),'canvas':[128,128],'manifest':str(d/'seagull_north.json')}))
if __name__=='__main__': main()
