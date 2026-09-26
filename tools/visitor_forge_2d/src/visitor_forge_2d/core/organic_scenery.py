"""Deterministic raster-painted organic scenery for City Horizon."""
from __future__ import annotations
import argparse, hashlib, json, math, random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

CONTRACT='CH_2D_ORGANIC_SCENERY_V1'
CAMERA_CONTRACT='CH_CAMERA_V1'
WORK_SCALE=4

def _hex(v): return tuple(int(v[i:i+2],16) for i in (1,3,5))
def _lerp(a,b,t): return a+(b-a)*t
def _alpha_safe_resize(im,size):
    rgba=im.convert('RGBA')
    try: return rgba.convert('RGBa').resize(size,Image.Resampling.LANCZOS).convert('RGBA')
    except (ValueError,OSError): return rgba.resize(size,Image.Resampling.LANCZOS)

def _paint(mask, top, bottom, right_shade=0.0, highlight=None):
    w,h=mask.size; a=_hex(top); b=_hex(bottom)
    surf=Image.new('RGBA',(w,h)); pix=surf.load()
    for y in range(h):
        ty=y/max(1,h-1)
        for x in range(w):
            tx=x/max(1,w-1); base=[_lerp(a[c],b[c],ty) for c in range(3)]
            shade=1-right_shade*tx
            glow=0
            if highlight:
                hx,hy,r,s=highlight; d=math.hypot(tx-hx,ty-hy); glow=max(0,1-d/r)*s
            pix[x,y]=(*(max(0,min(255,round(v*shade+255*glow))) for v in base),0)
    surf.putalpha(mask); return surf

def _composite(work,mask,top,bottom,**kw):
    work.alpha_composite(_paint(mask,top,bottom,kw.get('right_shade',0),kw.get('highlight')))

def _irregular_blob(mask,rng,cx,cy,rx,ry,lobes=18,fill=255):
    pts=[]
    for i in range(lobes):
        a=2*math.pi*i/lobes; j=1+rng.uniform(-.18,.18)
        pts.append((round((cx+math.cos(a)*rx*j)*WORK_SCALE),round((cy+math.sin(a)*ry*j)*WORK_SCALE)))
    ImageDraw.Draw(mask).polygon(pts,fill=fill)

def _tapered_stroke(mask,p0,p1,p2,w0,w1,samples=42,fill=255):
    d=ImageDraw.Draw(mask)
    for i in range(samples+1):
        t=i/samples; u=1-t
        x=u*u*p0[0]+2*u*t*p1[0]+t*t*p2[0]; y=u*u*p0[1]+2*u*t*p1[1]+t*t*p2[1]
        w=_lerp(w0,w1,t)*WORK_SCALE; r=max(1,w*.5); x*=WORK_SCALE; y*=WORK_SCALE
        d.ellipse((x-r,y-r,x+r,y+r),fill=fill)

def _needle_fan(mask,rng,cx,cy,length,width,angle,branches=7,fill=255):
    for _ in range(branches):
        a=angle+rng.uniform(-.48,.48)
        l=length*rng.uniform(.62,1.08)
        ex=cx+math.cos(a)*l; ey=cy+math.sin(a)*l*.48
        mx=_lerp(cx,ex,.48); my=_lerp(cy,ey,.48)+rng.uniform(-1.3,1.3)
        _tapered_stroke(mask,(cx,cy),(mx,my),(ex,ey),width*rng.uniform(.65,1.0),.35,samples=18,fill=fill)

def _branch(mask,rng,root,tip,width,droop,side,density=6,fill=255):
    rx,ry=root; tx,ty=tip; ctrl=((rx+tx)/2, min(ry,ty)+droop)
    _tapered_stroke(mask,root,ctrl,tip,width,.6,fill=fill)
    for j in range(1,density+1):
        t=j/(density+1); u=1-t
        cx=u*u*rx+2*u*t*ctrl[0]+t*t*tx; cy=u*u*ry+2*u*t*ctrl[1]+t*t*ty
        _irregular_blob(mask,rng,cx,cy,max(2.8,width*(.72-.18*t)),max(1.8,width*(.34-.08*t)),10,fill)
        _needle_fan(mask,rng,cx,cy,max(4,width*(1.7-.55*t)),max(1.5,width*.28),(-.35 if side<0 else math.pi+.35),6,fill)

def _raster_dabs(layer,rng,mask,color,count,alpha_range=(10,34),size_range=(.6,2.2)):
    """Scatter deterministic raster dabs clipped by the foliage mask."""
    bbox=mask.getbbox()
    if not bbox: return
    draw=ImageDraw.Draw(layer,'RGBA'); mp=mask.load(); col=_hex(color)
    for _ in range(count):
        for _try in range(18):
            x=rng.randrange(bbox[0],bbox[2]); y=rng.randrange(bbox[1],bbox[3])
            if mp[x,y] > 110: break
        else: continue
        r=rng.uniform(*size_range)*WORK_SCALE; a=rng.randint(*alpha_range)
        dx=rng.uniform(-.8,.3)*r; dy=rng.uniform(-.3,.45)*r
        draw.ellipse((x-r+dx,y-r*.38+dy,x+r+dx,y+r*.38+dy),fill=(*col,a))
    blurred=layer.filter(ImageFilter.GaussianBlur(.18*WORK_SCALE))
    layer.alpha_composite(blurred)

def _dense_crown_masks(recipe,rng,W,H):
    tiers=recipe['tiers']; cx=96
    back=Image.new('L',(W,H)); core=Image.new('L',(W,H)); front=Image.new('L',(W,H))
    for i,t in enumerate(tiers):
        y=float(t['y']); span=float(t['span']); thick=float(t['thickness']); skew=float(t.get('skew',0))
        next_y=float(tiers[min(i+1,len(tiers)-1)]['y'])
        bridge_h=max(thick*.72,(next_y-y)*.52 if i<len(tiers)-1 else thick*.72)
        _irregular_blob(core,rng,cx+skew,y+thick*.50,span*.20,bridge_h*.42,16)
        _irregular_blob(back,rng,cx+skew,y+3,span*.30,thick*.48,16)
        _irregular_blob(front,rng,cx+skew,y+thick*.68,span*.22,thick*.40,14)
        for side in (-1,1):
            asym=1+rng.uniform(-.06,.07)
            _branch(back,rng,(cx+skew,y-2),(cx+skew+side*span*asym,y+thick*.26+rng.uniform(-1.5,1.5)),max(7.5,thick*.46),-thick*.05,side,max(6,int(span/10)))
            _branch(core,rng,(cx+skew,y),(cx+skew+side*span*.96*asym,y+thick*.62+rng.uniform(-1,2.5)),max(8.5,thick*.52),thick*.22,side,max(7,int(span/9)))
            _branch(front,rng,(cx+skew,y+2),(cx+skew+side*span*.78,y+thick*.96),max(7.2,thick*.42),thick*.31,side,max(6,int(span/10)))
    for i in range(len(tiers)-1):
        a,b=tiers[i],tiers[i+1]
        y=_lerp(float(a['y']),float(b['y']),.55)+rng.uniform(-1,1)
        span=_lerp(float(a['span']),float(b['span']),.52)*.74
        thick=_lerp(float(a['thickness']),float(b['thickness']),.52)
        _irregular_blob(core,rng,cx+rng.uniform(-2,2),y+thick*.40,span*.15,thick*.26,12)
        for side in (-1,1):
            _branch(core,rng,(cx+rng.uniform(-2,2),y),(cx+side*span,y+thick*.52),max(5.2,thick*.32),thick*.18,side,5)
    core=core.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(.12*WORK_SCALE))
    front=front.filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.GaussianBlur(.10*WORK_SCALE))
    back=back.filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.GaussianBlur(.10*WORK_SCALE))
    return back,core,front

def render(recipe):
    if recipe.get('contract')!=CONTRACT: raise ValueError(f'recipe must declare {CONTRACT}')
    if recipe.get('camera',{}).get('contract')!=CAMERA_CONTRACT: raise ValueError('organic gameplay scenery must declare CH_CAMERA_V1')
    if recipe['camera'].get('tile')!=[128,64]: raise ValueError('CH_CAMERA_V1 review requires 128x64 tile')
    canvas=recipe.get('canvas',[192,256]); anchor=recipe.get('anchor',[96,239]); seed=int(recipe.get('seed',1)); rng=random.Random(seed)
    W,H=canvas[0]*WORK_SCALE,canvas[1]*WORK_SCALE; pal=recipe['palette']; work=Image.new('RGBA',(W,H))
    sm=Image.new('L',(W,H)); ImageDraw.Draw(sm).ellipse((45*WORK_SCALE,229*WORK_SCALE,147*WORK_SCALE,244*WORK_SCALE),fill=155); sm=sm.filter(ImageFilter.GaussianBlur(2.6*WORK_SCALE))
    sh=Image.new('RGBA',(W,H),(*_hex(pal['ground_shadow']),0)); sh.putalpha(sm); work.alpha_composite(sh)
    trunk=Image.new('L',(W,H)); d=ImageDraw.Draw(trunk); d.polygon([(82*WORK_SCALE,120*WORK_SCALE),(111*WORK_SCALE,122*WORK_SCALE),(106*WORK_SCALE,239*WORK_SCALE),(85*WORK_SCALE,239*WORK_SCALE)],fill=255)
    _composite(work,trunk,pal['trunk_top'],pal['trunk_bottom'],right_shade=.19,highlight=(.41,.48,.28,.12))
    back,core,front=_dense_crown_masks(recipe,rng,W,H)
    _composite(work,back,pal['back_top'],pal['back_bottom'],right_shade=.24,highlight=(.33,.22,.42,.06))
    _composite(work,core,pal['mid_top'],pal['mid_bottom'],right_shade=.19,highlight=(.30,.30,.50,.10))
    tex=Image.new('RGBA',(W,H)); _raster_dabs(tex,rng,core,pal.get('occlusion','#123B30'),int(recipe.get('raster',{}).get('shadowDabs',220)),(10,34),(.6,2.2)); work.alpha_composite(tex)
    _composite(work,front,pal['front_top'],pal['front_bottom'],right_shade=.16,highlight=(.28,.37,.48,.13))
    hi=Image.new('RGBA',(W,H)); _raster_dabs(hi,rng,front,pal['highlight'],int(recipe.get('raster',{}).get('highlightDabs',180)),(8,30),(.5,1.8)); work.alpha_composite(hi)
    detail=Image.new('RGBA',(W,H)); dd=ImageDraw.Draw(detail,'RGBA'); fp=front.load(); bbox=front.getbbox(); hcol=_hex(pal['highlight']); scol=_hex(pal.get('occlusion','#123B30'))
    count=int(recipe.get('raster',{}).get('needleStrokes',260))
    if bbox:
        for _ in range(count):
            for _try in range(18):
                x=rng.randrange(bbox[0],bbox[2]); y=rng.randrange(bbox[1],bbox[3])
                if fp[x,y]>100: break
            else: continue
            lx=rng.uniform(2.0,6.0)*WORK_SCALE; ang=rng.uniform(-.25,.18)
            c=hcol if rng.random()<.58 else scol; a=rng.randint(22,65)
            dd.line((x,y,x-lx,y+math.sin(ang)*lx*.35),fill=(*c,a),width=max(1,round(rng.uniform(.35,.8)*WORK_SCALE)))
    detail=detail.filter(ImageFilter.GaussianBlur(.12*WORK_SCALE)); work.alpha_composite(detail)
    frame=_alpha_safe_resize(work,tuple(canvas)); bounds=frame.getchannel('A').getbbox()
    return frame,{'contract':CONTRACT,'id':recipe['id'],'canvas':canvas,'anchor':anchor,'bounds':list(bounds),'seed':seed,'camera':recipe['camera'],'raster':recipe.get('raster',{}),'runtimePromotion':False,'artApproved':False}

def review_board(frame):
    w,h=frame.size; board=Image.new('RGBA',(w*3+48,h*2+40),(76,116,48,255)); board.alpha_composite(frame,(16,20+h//2)); board.alpha_composite(frame.resize((w*2,h*2),Image.Resampling.NEAREST),(w+32,20)); d=ImageDraw.Draw(board); d.text((16,4),'1x / gameplay',fill=(247,244,220,255)); d.text((w+32,4),'2x / inspection',fill=(247,244,220,255)); return board

def isometric_board(frame,anchor):
    board=Image.new('RGBA',(768,480),(46,77,55,255)); d=ImageDraw.Draw(board); gx,gy=384,314; hw,hh=64,32
    for x in range(-3,4):
        for y in range(-3,4):
            cx=gx+(x-y)*hw; cy=gy+(x+y)*hh; poly=[(cx,cy-hh),(cx+hw,cy),(cx,cy+hh),(cx-hw,cy)]; fill=(76,119,66,255) if (x+y)%2==0 else (71,113,64,255); d.polygon(poly,fill=fill,outline=(105,148,93,205))
    d.polygon([(gx,gy-hh),(gx+hw,gy),(gx,gy+hh),(gx-hw,gy)],fill=(82,132,72,255),outline=(174,207,145,255)); board.alpha_composite(frame,(round(gx-anchor[0]),round(gy-anchor[1]))); d.ellipse((gx-3,gy-3,gx+3,gy+3),fill=(255,224,132,255)); d.text((18,16),'CH_CAMERA_V1 / 30deg elevation / 45deg yaw / 128x64',fill=(247,244,220,255)); d.text((18,36),'dense raster foliage / gameplay 1x / 2:1 ground contact',fill=(220,232,205,255)); return board

def export(recipe_path,output_dir):
    raw=recipe_path.read_bytes(); recipe=json.loads(raw); frame,meta=render(recipe); output_dir.mkdir(parents=True,exist_ok=True); stem=recipe['id']; png=output_dir/f'{stem}.png'; review=output_dir/f'{stem}_review.png'; iso=output_dir/f'{stem}_isometric_review.png'; report=output_dir/f'{stem}.json'; frame.save(png); review_board(frame).save(review); isometric_board(frame,meta['anchor']).save(iso); meta.update({'recipe':str(recipe_path),'recipeSha256':hashlib.sha256(raw).hexdigest(),'png':str(png),'review':str(review),'isometricReview':str(iso)}); report.write_text(json.dumps(meta,indent=2)+'\n'); return {'png':str(png),'review':str(review),'isometricReview':str(iso),'metadata':str(report)}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--recipe',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); a=ap.parse_args(); print(json.dumps(export(a.recipe,a.output),indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
