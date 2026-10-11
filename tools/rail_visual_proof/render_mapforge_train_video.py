#!/usr/bin/env python3
"""MapForge C++ rail-sprite video: genuine MapForge frames + native train poses.

This is a render proof, not interactive city_builder screen footage. Modular
Blender rails are sampled on the native route for *visual* testing: physical
module-to-module seam and wheel/port alignment is NOT certified here.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
import subprocess
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw
from render_live_train_video import images_for, layout_for, sprite_view, W, H, FPS

ROOT = Path(__file__).resolve().parents[2]
SCALE = 0.42
# Trains use the existing approved CH_RAIL_VISUAL_ALIGNMENT_V2 pivot.
SPRITE_SCALE = 0.38  # legacy; calibrated per real PNG below
ANCHOR = [256, 380]
MODULE_SPAN_WORLD = 3.0
CURVE_ART_RADIUS_WORLD = 1.5
NATIVE_ROUTE_CURVE_RADIUS_WORLD = 7.0


def sample_route(track, step=3.0):
    lengths=[0.0]
    for a,b in zip(track,track[1:]):
        lengths.append(lengths[-1]+math.dist(a,b))
    samples=[]
    d=1.5
    while d<lengths[-1]-1.5:
        ix=next((i for i in range(len(lengths)-1) if lengths[i]<=d<=lengths[i+1]),len(lengths)-2)
        v=max(0,min(1,(d-lengths[ix])/max(1e-8,lengths[ix+1]-lengths[ix])))
        x=track[ix][0]+v*(track[ix+1][0]-track[ix][0])
        y=track[ix][1]+v*(track[ix+1][1]-track[ix][1])
        p=track[max(0,ix-3)]
        q=track[min(len(track)-1,ix+4)]
        theta=math.atan2(q[1]-p[1],q[0]-p[0])
        samples.append((x,y,theta))
        d+=step
    return samples


def kind_direction(samples,index):
    x,y,theta=samples[index]
    # Detect a true bend; use matching pre-rendered 90-degree module art only
    # as a visual guide, not as a validated replacement for radius-7 geometry.
    prev=samples[max(0,index-2)][2]
    following=samples[min(len(samples)-1,index+2)][2]
    delta=math.atan2(math.sin(following-prev),math.cos(following-prev))
    kind='straight'
    if abs(delta)>0.12:
        kind='curve_left_90' if delta>0 else 'curve_right_90'
    direction='south' if abs(math.cos(theta))>=abs(math.sin(theta)) else 'west'
    if kind!='straight':
        direction= ('south' if -math.pi/4<=theta<math.pi/4 else
                    'west' if math.pi/4<=theta<3*math.pi/4 else
                    'north' if theta>=3*math.pi/4 or theta< -3*math.pi/4 else 'east')
    return kind,direction


def point(x,y,focus_x,focus_y):
    # Exact CH_CAMERA_V1 r0, using MapForge camera focusTile/focusScreen convention.
    return (W*0.5 + (x-y-focus_x+focus_y)*64*SCALE,
            H*0.55 + (x+y-focus_x-focus_y)*32*SCALE)


def render(trace_path,outdir,capture_exe):
    trace=json.loads(trace_path.read_text())
    assert trace['contract']=='CH_RAIL_LIVE_VIDEO_PROOF_V1'
    assert trace['checks']['eight_units'] and trace['checks']['curve_heading_change']
    frames=trace['frames']
    assert len(frames)==216
    outdir.mkdir(parents=True,exist_ok=True)
    rails=ROOT/'assets/rail/prerendered_v1'
    # Use the real straight Blender rail artwork as a source for tangent-aligned
    # rail images along the radius-7 native C++ route. A 90-degree Blender
    # module has radius 1.5, so stamping that module on radius 7 cannot work.
    # Every rotated rail image is derived from real Blender PNG pixels.
    samples=sample_route(trace['track'], step=2.8)
    inventory={}
    rail_specs=[]
    prepared=outdir/'aligned_rail_sprite_cache'
    prepared.mkdir(parents=True,exist_ok=True)
    straight_images={}
    for direction in ('south','west'):
        png=rails/f'straight_{direction}.png'
        inventory[png.name]=hashlib.sha256(png.read_bytes()).hexdigest()
        straight_images[direction]=Image.open(png).convert('RGBA')
    for i,(x,y,theta) in enumerate(samples):
        # World x projects down-right; world y down-left (camera r0).
        screen_angle=math.degrees(math.atan2(math.sin(theta)*32+math.cos(theta)*32,
                                              math.cos(theta)*64-math.sin(theta)*64))
        # Select the closest Blender cardinal source before rotating it.
        canonical={'south':math.degrees(math.atan2(32,64)),
                   'west':math.degrees(math.atan2(32,-64))}
        direction=min(canonical,key=lambda d:abs((screen_angle-canonical[d]+180)%360-180))
        angle=(screen_angle-canonical[direction]+180)%360-180
        source=straight_images[direction]
        # Rotation around transparent canvas midpoint, preserving all real
        # sleeper/rail pixel data rather than drawing fake replacement rails.
        rotated=source.rotate(-angle,resample=Image.Resampling.BICUBIC,expand=True)
        bbox=rotated.getchannel('A').getbbox()
        if bbox is None: raise RuntimeError('empty transformed real Blender rail')
        # Use transparent-alpha centre as path anchor; bottom-of-bbox (legacy)
        # made tracks hover off the actual runtime centreline.
        anchor=[(bbox[0]+bbox[2])/2,(bbox[1]+bbox[3])/2]
        # The footprint is tuned to the local centreline sample span, not
        # an entire 90-degree radius-incompatible curve module.
        span_px=2.95*math.hypot(64*math.cos(theta)-64*math.sin(theta),
                                 32*math.cos(theta)+32*math.sin(theta))
        source_box=source.getchannel('A').getbbox()
        source_diag=math.hypot(source_box[2]-source_box[0],source_box[3]-source_box[1])
        target_scale=span_px/max(1,source_diag)
        target_file=prepared/f'aligned_{i:03d}.png'
        rotated.save(target_file)
        rail_specs.append({'path':str(target_file.resolve()),'world':[x,y],
                           'anchorPixels':anchor,'scale':round(target_scale,6)})
    # These are tangent-conformed render images for visual proof only. This
    # DOES NOT promote the incompatible Blender curve modules to runtime.
    locos,loco_manifest=images_for('locomotive')
    coaches,coach_manifest=images_for('coach')
    resized={}
    for role,images in [('locomotive',locos),('coach',coaches)]:
        for key,im in images.items():
            size=round(max(0.35,SCALE)*layout_for(role,key)[0])
            resized[(role,key)]=im.resize((size,size),Image.Resampling.LANCZOS)
    outfile=outdir/'city_horizon_trem_mapforge_trilhos_blender.mp4'
    ffmpeg=subprocess.Popen(['ffmpeg','-y','-hide_banner','-loglevel','error','-f','rawvideo',
       '-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-',
       '-an','-c:v','libx264','-preset','veryfast','-crf','22','-pix_fmt','yuv420p',
       '-movflags','+faststart',str(outfile)],stdin=subprocess.PIPE)
    focus_x=focus_y=None
    with tempfile.TemporaryDirectory(prefix='ch-mapforge-frames-') as td:
        directory=Path(td)
        request_file=directory/'request.json'
        capture_file=directory/'mapforge.png'
        candidate=rails/'straight_south.png'
        for n,frame in enumerate(frames):
            units=frame['units']
            x=(units[0]['x']+units[-1]['x'])/2
            y=(units[0]['y']+units[-1]['y'])/2
            if focus_x is None:
                focus_x,focus_y=x,y
            else:
                focus_x+=(x-focus_x)*0.14
                focus_y+=(y-focus_y)*0.14
            req={'contract':'MAPFORGE_CAPTURE_REQUEST_V1',
              'capture':{'canvas':{'width':W,'height':H},
                 'camera':{'contract':'CH_CAMERA_V1','rotationQuarterTurns':0,
                           'zoom':SCALE,'focusTile':[focus_x-0.5,focus_y-0.5],
                           'focusScreen':[0.5,0.55]},
                 'stage':{'minTile':-64,'maxTile':64,'drawGrid':False,'drawGrassTexture':True},
                 'candidate':{'tile':[-100,-100],'showFootprint':False,'showAnchor':False,
                              'scale':0.00001},
                 'railSprites':rail_specs}}
            request_file.write_text(json.dumps(req))
            subprocess.run([str(capture_exe),str(capture_file),str(candidate),str(request_file)],
                env={**os.environ,'QT_QPA_PLATFORM':'offscreen'},check=True,
                stdout=subprocess.DEVNULL)
            with Image.open(capture_file) as bg:
                screen=bg.convert('RGB')
            draw=ImageDraw.Draw(screen)
            for a,b in zip(units,units[1:]):
                if b['index']!=a['index']+1: continue
                length=5.2 if a['kind']=='locomotive' else 3.9
                start=point(a['x']-a['tx']*length*0.5,a['y']-a['ty']*length*0.5,focus_x,focus_y)
                end=point(b['x']+b['tx']*1.95,b['y']+b['ty']*1.95,focus_x,focus_y)
                draw.line([start,end],fill=(75,61,45),width=3)
            for unit in sorted(units,key=lambda u:u['x']+u['y']):
                role=unit['kind']
                available=locos if role=='locomotive' else coaches
                view=sprite_view(unit,available)
                image=resized[(role,view)]
                px,py=point(unit['x'],unit['y'],focus_x,focus_y)
                _,ax,ay=layout_for(role,view)
                screen.paste(image,(round(px-image.width*ax/1024),
                                    round(py-image.height*ay/1024)),image)
            draw=ImageDraw.Draw(screen)
            draw.rectangle((0,0,W,49),fill=(21,34,31))
            draw.text((18,14),'CITY HORIZON | MAPFORGE + BLENDER PNG | C++ TRAIN RUNTIME',
                      fill=(235,239,219))
            draw.rectangle((0,H-32,W,H),fill=(21,34,31))
            draw.text((18,H-23),'PROVA VISUAL: trilhos modulares em revisao de juntas e escala | nao captura interativa',
                      fill=(245,220,156))
            if n==120:
                screen.save(outdir/'trem_mapforge_preview.png')
            ffmpeg.stdin.write(screen.tobytes())
            if n%36==0:
                print(f'Rendered MapForge+Blender+C++ frame {n}/{len(frames)}',flush=True)
    ffmpeg.stdin.close()
    if ffmpeg.wait()!=0 or not outfile.is_file() or outfile.stat().st_size<100000:
        raise RuntimeError('MP4 encoder failure')
    report={'contract':'CH_RAIL_MAPFORGE_BLENDER_VIDEO_V1',
       'renderSource':'MapForge2MapCapture compiled Qt/C++ for every video frame',
       'movementSource':trace['source'],'trainUnitsMax':trace['checks']['max_units'],
       'frames':216,'fps':FPS,'resolution':[W,H],'camera':'CH_CAMERA_V1 r0',
       'realBlenderTrackImages':inventory,'trackInstances':len(rail_specs),
       'seamApproval':False,'fullInteractiveGameCapture':False,
       'spritePlacement':'real Blender straight PNG pixels rotated to follow native C++ route tangent, alpha-centre anchor',
       'nativeCurveRadiusWorld':NATIVE_ROUTE_CURVE_RADIUS_WORLD,
       'blenderCurveModuleRadiusWorld':CURVE_ART_RADIUS_WORLD,
       'curveGeometryCompatible':False,
       'curveVisualMode':'tangent-conformed authentic Blender straight texture sprites; not approved 90-degree modules',
       'warning':'Native radius-7 curves and baked radius-1.5 modules cannot be claimed port-aligned without a matched route or re-bake.',
       'video':outfile.name}
    (outdir/'mapforge_video_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS: real MapForge scene frames and native C++ train composed to',outfile)


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--trace',type=Path,required=True)
    ap.add_argument('--outdir',type=Path,required=True)
    ap.add_argument('--capture-exe',type=Path,required=True)
    args=ap.parse_args()
    render(args.trace,args.outdir,args.capture_exe.resolve())
