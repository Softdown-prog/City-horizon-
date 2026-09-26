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
def _quad(p0,p1,p2,t):
    u=1-t
    return (u*u*p0[0]+2*u*t*p1[0]+t*t*p2[0], u*u*p0[1]+2*u*t*p1[1]+t*t*p2[1])
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

def _irregular_blob(mask,rng,cx,cy,rx,ry,lobes=18,fill=255,jitter=.18):
    pts=[]
    for i in range(lobes):
        a=2*math.pi*i/lobes; j=1+rng.uniform(-jitter,jitter)
        pts.append((round((cx+math.cos(a)*rx*j)*WORK_SCALE),round((cy+math.sin(a)*ry*j)*WORK_SCALE)))
    ImageDraw.Draw(mask).polygon(pts,fill=fill)

def _tapered_stroke(mask,p0,p1,p2,w0,w1,samples=42,fill=255):
    d=ImageDraw.Draw(mask)
    for i in range(samples+1):
        t=i/samples; x,y=_quad(p0,p1,p2,t)
        w=_lerp(w0,w1,t)*WORK_SCALE; r=max(1,w*.5); x*=WORK_SCALE; y*=WORK_SCALE
        d.ellipse((x-r,y-r,x+r,y+r),fill=fill)

def _needle_tuft(mask,rng,cx,cy,scale,base_angle,fill=255,strokes=9):
    """Paint a tight deterministic fan of pointed needles around a branch station."""
    for k in range(strokes):
        offset=(k-(strokes-1)/2)/max(1,(strokes-1)/2)
        a=base_angle + offset*rng.uniform(.20,.42) + rng.uniform(-.08,.08)
        length=scale*rng.uniform(.72,1.18)
        width=max(.65,scale*rng.uniform(.10,.16))
        ex=cx+math.cos(a)*length
        ey=cy+math.sin(a)*length*.44 + abs(offset)*scale*.06
        mx=_lerp(cx,ex,.52); my=_lerp(cy,ey,.52)+rng.uniform(-.8,.8)
        _tapered_stroke(mask,(cx,cy),(mx,my),(ex,ey),width,.24,samples=15,fill=fill)

def _branch(mask,rng,root,tip,width,droop,side,density=7,fill=255,tuft_strength=1.0):
    rx,ry=root; tx,ty=tip; ctrl=((rx+tx)/2, min(ry,ty)+droop)
    _tapered_stroke(mask,root,ctrl,tip,width,.45,samples=44,fill=fill)
    base_angle=(-.05 if side<0 else math.pi+.05)
    for j in range(1,density+1):
        t=j/(density+1)
        cx,cy=_quad(root,ctrl,tip,t)
        pad_w=max(2.3,width*(.62-.16*t)); pad_h=max(1.3,width*(.24-.05*t))
        _irregular_blob(mask,rng,cx,cy,pad_w,pad_h,10,fill,jitter=.12)
        _needle_tuft(mask,rng,cx,cy,max(4.4,width*(1.45-.35*t))*tuft_strength,base_angle,fill,strokes=7 if t>.45 else 9)

def _crown_masks(recipe,rng,W,H):
    """Build a dense conifer crown from overlapping branch fans rather than shelves."""
    tiers=recipe['tiers']; cx=96
    back=Image.new('L',(W,H)); mid=Image.new('L',(W,H)); front=Image.new('L',(W,H)); core=Image.new('L',(W,H))
    for t in tiers:
        y=float(t['y']); span=float(t['span']); thick=float(t['thickness']); skew=float(t.get('skew',0))
        _irregular_blob(core,rng,cx+skew,y+thick*.55,max(4.5,span*.12),thick*.60,16,255,jitter=.12)
        for side in (-1,1):
            asym=1+rng.uniform(-.08,.08)
            for off,fac in [(-3.5,.96),(1.0,.82)]:
                _branch(back,rng,(cx+skew,y+off),(cx+skew+side*span*fac*asym,y+thick*(.16 if off<0 else .32)+rng.uniform(-1.4,1.4)),max(4.4,thick*.29),thick*(.02 if off<0 else .10),side,max(5,int(span/12)),tuft_strength=.92)
            for off,fac in [(0,.98),(4.0,.88)]:
                _branch(mid,rng,(cx+skew,y+off),(cx+skew+side*span*fac*asym,y+thick*(.52 if off==0 else .66)+rng.uniform(-1.2,2.0)),max(5.2,thick*.34),thick*(.18 if off==0 else .24),side,max(6,int(span/10)),tuft_strength=1.02)
            _branch(front,rng,(cx+skew,y+3),(cx+skew+side*span*.76*asym,y+thick*.90+rng.uniform(-.5,2.0)),max(4.7,thick*.31),thick*.31,side,max(5,int(span/11)),tuft_strength=.98)
        for _ in range(3):
            cx2=cx+skew+rng.uniform(-span*.18,span*.18)
            cy2=y+thick*rng.uniform(.40,.85)
            _irregular_blob(front,rng,cx2,cy2,max(3.0,span*.07),max(2.2,thick*.18),12,255,jitter=.15)
            _needle_tuft(front,rng,cx2,cy2,max(5.0,thick*.32),rng.choice([-.15, math.pi+.15]),255,7)
    for i in range(len(tiers)-1):
        a,b=tiers[i],tiers[i+1]
        y=_lerp(float(a['y']),float(b['y']),.52)+rng.uniform(-1.6,1.6)
        span=_lerp(float(a['span']),float(b['span']),.50)*.66
        thick=_lerp(float(a['thickness']),float(b['thickness']),.50)
        side=-1 if i%2==0 else 1
        _branch(mid,rng,(cx+rng.uniform(-2,2),y),(cx+side*span,y+thick*.55),max(4.2,thick*.25),thick*.18,side,max(4,int(span/12)),tuft_strength=.9)
        _irregular_blob(core,rng,cx+rng.uniform(-2,2),y+thick*.35,max(3.5,span*.08),thick*.28,12)
    core=core.filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.GaussianBlur(.08*WORK_SCALE))
    mid=mid.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(.05*WORK_SCALE))
    front=front.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(.04*WORK_SCALE))
    back=back.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(.04*WORK_SCALE))
    return back,core,mid,front


def _crown_masks_broadleaf(recipe, rng, W, H):
    """Build a rounded deciduous canopy from layered irregular blobs.

    Broadleaf trees have a wide, roughly spherical crown rather than a spire.
    The algorithm places three depth layers (back / mid / front) of overlapping
    organic blobs whose size, position and slight vertical offset vary with each
    tier entry in the recipe.  The same raster-texture passes used for conifers
    are reused unchanged on the output masks, so a single colour palette can
    describe both species.

    Recipe tier fields for broadleaf:
      y          -- vertical centre of this cluster (canvas pixels)
      span       -- half-width of the cluster (canvas pixels)
      thickness  -- vertical radius of the cluster (canvas pixels)
      skew       -- horizontal shift of the cluster centre (canvas pixels, optional)
      lobes      -- polygon vertex count for _irregular_blob; higher = rounder
                    (optional, default 20)

    A recipe may also set crownCx (canvas x of the trunk centre, default 96).
    """
    tiers = recipe['tiers']
    cx = float(recipe.get('crownCx', 96))
    back  = Image.new('L', (W, H))
    mid   = Image.new('L', (W, H))
    front = Image.new('L', (W, H))
    core  = Image.new('L', (W, H))

    for t in tiers:
        y     = float(t['y'])
        span  = float(t['span'])
        thick = float(t['thickness'])
        skew  = float(t.get('skew', 0))
        lobes = int(t.get('lobes', 20))
        tcx   = cx + skew

        # Core: dense centre mass feeds the shadow depth channel.
        _irregular_blob(core, rng, tcx, y, span * .52, thick * .62, lobes, 255, jitter=.14)

        # Back layer: slightly raised to simulate rear canopy depth.
        for _ in range(rng.randint(2, 4)):
            ox = rng.uniform(-span * .38, span * .38)
            oy = rng.uniform(-thick * .30, 0)
            _irregular_blob(back, rng,
                            tcx + ox, y + oy,
                            max(5.0, span * rng.uniform(.42, .68)),
                            max(3.5, thick * rng.uniform(.38, .58)),
                            lobes, 255, jitter=.18)

        # Mid layer: the main visible foliage mass.
        for _ in range(rng.randint(3, 6)):
            ox = rng.uniform(-span * .55, span * .55)
            oy = rng.uniform(-thick * .18, thick * .22)
            _irregular_blob(mid, rng,
                            tcx + ox, y + oy,
                            max(6.0, span * rng.uniform(.48, .76)),
                            max(4.0, thick * rng.uniform(.42, .62)),
                            lobes, 255, jitter=.20)

        # Front layer: protruding clusters at the outer silhouette.
        for _ in range(rng.randint(2, 4)):
            ox = rng.uniform(-span * .68, span * .68)
            oy = rng.uniform(0, thick * .38)
            _irregular_blob(front, rng,
                            tcx + ox, y + oy,
                            max(4.5, span * rng.uniform(.32, .54)),
                            max(3.0, thick * rng.uniform(.30, .48)),
                            lobes, 255, jitter=.22)

    # Gentle blur merges blob edges; MaxFilter preserves silhouette fullness.
    core  = core.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(.06 * WORK_SCALE))
    back  = back.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(.05 * WORK_SCALE))
    mid   = mid.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(.04 * WORK_SCALE))
    front = front.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(.04 * WORK_SCALE))
    return back, core, mid, front


def _scatter_texture(layer,rng,mask,color,count,alpha_range=(12,36),size_range=(.45,1.7),elongate=2.0):
    bbox=mask.getbbox()
    if not bbox: return
    draw=ImageDraw.Draw(layer,'RGBA'); mp=mask.load(); col=_hex(color)
    for _ in range(count):
        for _try in range(20):
            x=rng.randrange(bbox[0],bbox[2]); y=rng.randrange(bbox[1],bbox[3])
            if mp[x,y] > 120: break
        else: continue
        r=rng.uniform(*size_range)*WORK_SCALE; a=rng.randint(*alpha_range)
        dx=rng.uniform(-.4,.2)*r; dy=rng.uniform(-.2,.35)*r
        draw.ellipse((x-r*elongate+dx,y-r*.38+dy,x+r*.35+dx,y+r*.38+dy),fill=(*col,a))

def _final_raster_pass(frame,rng,pal,recipe):
    """Restore a pre-rendered/raster texture at gameplay scale after supersampling."""
    out=frame.convert('RGBA'); alpha=out.getchannel('A'); bbox=alpha.getbbox()
    if not bbox: return out
    px=alpha.load(); draw=ImageDraw.Draw(out,'RGBA')
    dark=_hex(pal.get('occlusion','#123B30')); light=_hex(pal['highlight'])
    cfg=recipe.get('raster',{})
    grain=int(cfg.get('finalGrain',620)); needles=int(cfg.get('finalNeedles',300))
    for _ in range(grain):
        for _try in range(20):
            x=rng.randrange(bbox[0],bbox[2]); y=rng.randrange(bbox[1],bbox[3])
            if px[x,y]>170: break
        else: continue
        if rng.random()<.58:
            c=dark; a=rng.randint(12,28)
        else:
            c=light; a=rng.randint(9,24)
        if rng.random()<.72:
            draw.point((x,y),fill=(*c,a))
        else:
            draw.line((x,y,x-rng.choice([1,2]),y+rng.choice([0,1])),fill=(*c,a),width=1)
    for _ in range(needles):
        for _try in range(20):
            x=rng.randrange(bbox[0],bbox[2]); y=rng.randrange(bbox[1],bbox[3])
            if px[x,y]>190: break
        else: continue
        length=rng.choice([2,2,3,3,4]); c=light if rng.random()<.58 else dark; a=rng.randint(18,48)
        draw.line((x,y,x-length,y+rng.choice([0,0,1])),fill=(*c,a),width=1)
    return out.filter(ImageFilter.UnsharpMask(radius=.65,percent=115,threshold=3))

def render(recipe):
    if recipe.get('contract')!=CONTRACT: raise ValueError(f'recipe must declare {CONTRACT}')
    if recipe.get('camera',{}).get('contract')!=CAMERA_CONTRACT: raise ValueError('organic gameplay scenery must declare CH_CAMERA_V1')
    if recipe['camera'].get('tile')!=[128,64]: raise ValueError('CH_CAMERA_V1 review requires 128x64 tile')
    canvas=recipe.get('canvas',[192,256]); anchor=recipe.get('anchor',[96,239]); seed=int(recipe.get('seed',1)); rng=random.Random(seed)
    W,H=canvas[0]*WORK_SCALE,canvas[1]*WORK_SCALE; pal=recipe['palette']; work=Image.new('RGBA',(W,H))
    sm=Image.new('L',(W,H)); ImageDraw.Draw(sm).ellipse((49*WORK_SCALE,230*WORK_SCALE,143*WORK_SCALE,244*WORK_SCALE),fill=145); sm=sm.filter(ImageFilter.GaussianBlur(2.4*WORK_SCALE))
    sh=Image.new('RGBA',(W,H),(*_hex(pal['ground_shadow']),0)); sh.putalpha(sm); work.alpha_composite(sh)
    trunk=Image.new('L',(W,H)); d=ImageDraw.Draw(trunk); d.polygon([(86*WORK_SCALE,119*WORK_SCALE),(107*WORK_SCALE,121*WORK_SCALE),(103*WORK_SCALE,239*WORK_SCALE),(89*WORK_SCALE,239*WORK_SCALE)],fill=255)
    _composite(work,trunk,pal['trunk_top'],pal['trunk_bottom'],right_shade=.19,highlight=(.41,.48,.28,.12))
    bark=Image.new('RGBA',(W,H)); bd=ImageDraw.Draw(bark,'RGBA'); tc=_hex(pal.get('trunk_light','#DCA066'))
    for xo,y0,y1 in [(-4,166,231),(1,147,220),(5,188,232)]: bd.line(((96+xo)*WORK_SCALE,y0*WORK_SCALE,(95+xo)*WORK_SCALE,y1*WORK_SCALE),fill=(*tc,76),width=2*WORK_SCALE)
    work.alpha_composite(bark)
    crown_style = recipe.get('crownStyle', 'conifer')
    if crown_style == 'broadleaf':
        back, core, mid, front = _crown_masks_broadleaf(recipe, rng, W, H)
    elif crown_style == 'conifer':
        back, core, mid, front = _crown_masks(recipe, rng, W, H)
    else:
        raise ValueError(f"Unknown crownStyle {crown_style!r}; choose 'conifer' or 'broadleaf'")
    _composite(work,back,pal['back_top'],pal['back_bottom'],right_shade=.25,highlight=(.32,.21,.42,.05))
    _composite(work,core,pal['mid_bottom'],pal['back_bottom'],right_shade=.22,highlight=(.31,.27,.50,.05))
    _composite(work,mid,pal['mid_top'],pal['mid_bottom'],right_shade=.19,highlight=(.29,.30,.50,.10))
    tex=Image.new('RGBA',(W,H)); _scatter_texture(tex,rng,mid,pal.get('occlusion','#123B30'),int(recipe.get('raster',{}).get('shadowDabs',300)),(10,34),(.5,1.8),2.3); work.alpha_composite(tex)
    _composite(work,front,pal['front_top'],pal['front_bottom'],right_shade=.16,highlight=(.27,.36,.48,.14))
    hi=Image.new('RGBA',(W,H)); _scatter_texture(hi,rng,front,pal['highlight'],int(recipe.get('raster',{}).get('highlightDabs',260)),(8,30),(.45,1.45),2.4); work.alpha_composite(hi)
    detail=Image.new('RGBA',(W,H)); dd=ImageDraw.Draw(detail,'RGBA'); mask=Image.new('L',(W,H)); ImageDraw.Draw(mask).bitmap((0,0),mid,fill=255); ImageDraw.Draw(mask).bitmap((0,0),front,fill=255)
    mp=mask.load(); bbox=mask.getbbox(); hcol=_hex(pal['highlight']); scol=_hex(pal.get('occlusion','#123B30'))
    count=int(recipe.get('raster',{}).get('needleStrokes',500))
    if bbox:
        for _ in range(count):
            for _try in range(18):
                x=rng.randrange(bbox[0],bbox[2]); y=rng.randrange(bbox[1],bbox[3])
                if mp[x,y]>100: break
            else: continue
            lx=rng.uniform(2.5,7.0)*WORK_SCALE; c=hcol if rng.random()<.55 else scol; a=rng.randint(18,62)
            dd.line((x,y,x-lx,y+rng.uniform(-.4,.8)*WORK_SCALE),fill=(*c,a),width=max(1,round(rng.uniform(.3,.7)*WORK_SCALE)))
    work.alpha_composite(detail.filter(ImageFilter.GaussianBlur(.08*WORK_SCALE)))
    frame=_alpha_safe_resize(work,tuple(canvas))
    frame=_final_raster_pass(frame,rng,pal,recipe)
    bounds=frame.getchannel('A').getbbox()
    return frame,{'contract':CONTRACT,'id':recipe['id'],'canvas':canvas,'anchor':anchor,'bounds':list(bounds),'seed':seed,'crownStyle':crown_style,'camera':recipe['camera'],'raster':recipe.get('raster',{}),'runtimePromotion':False,'artApproved':False}

def review_board(frame):
    w,h=frame.size; board=Image.new('RGBA',(w*3+48,h*2+40),(76,116,48,255)); board.alpha_composite(frame,(16,20+h//2)); board.alpha_composite(frame.resize((w*2,h*2),Image.Resampling.NEAREST),(w+32,20)); d=ImageDraw.Draw(board); d.text((16,4),'1x / gameplay',fill=(247,244,220,255)); d.text((w+32,4),'2x / inspection',fill=(247,244,220,255)); return board

def isometric_board(frame,anchor,label='CH_CAMERA_V1 / 30deg / 45deg yaw / 128x64'):
    board=Image.new('RGBA',(768,480),(46,77,55,255)); d=ImageDraw.Draw(board); gx,gy=384,314; hw,hh=64,32
    for x in range(-3,4):
        for y in range(-3,4):
            cx=gx+(x-y)*hw; cy=gy+(x+y)*hh; poly=[(cx,cy-hh),(cx+hw,cy),(cx,cy+hh),(cx-hw,cy)]; fill=(76,119,66,255) if (x+y)%2==0 else (71,113,64,255); d.polygon(poly,fill=fill,outline=(105,148,93,205))
    d.polygon([(gx,gy-hh),(gx+hw,gy),(gx,gy+hh),(gx-hw,gy)],fill=(82,132,72,255),outline=(174,207,145,255)); board.alpha_composite(frame,(round(gx-anchor[0]),round(gy-anchor[1]))); d.ellipse((gx-3,gy-3,gx+3,gy+3),fill=(255,224,132,255)); d.text((18,16),label,fill=(247,244,220,255)); d.text((18,36),'CH_2D_ORGANIC_SCENERY_V1 / gameplay 1x',fill=(220,232,205,255)); return board

def export(recipe_path,output_dir):
    raw=recipe_path.read_bytes(); recipe=json.loads(raw); frame,meta=render(recipe); output_dir.mkdir(parents=True,exist_ok=True); stem=recipe['id']; png=output_dir/f'{stem}.png'; review=output_dir/f'{stem}_review.png'; iso=output_dir/f'{stem}_isometric_review.png'; report=output_dir/f'{stem}.json'; frame.save(png); review_board(frame).save(review); isometric_board(frame,meta['anchor']).save(iso); meta.update({'recipe':str(recipe_path),'recipeSha256':hashlib.sha256(raw).hexdigest(),'png':str(png),'review':str(review),'isometricReview':str(iso)}); report.write_text(json.dumps(meta,indent=2)+'\n'); return {'png':str(png),'review':str(review),'isometricReview':str(iso),'metadata':str(report)}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--recipe',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); a=ap.parse_args(); print(json.dumps(export(a.recipe,a.output),indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
