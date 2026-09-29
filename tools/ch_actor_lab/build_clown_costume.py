"""Build the V3 frame-aligned clown costume for the approved CH Actor.

Visual-only pass: locomotion, 48x64 frame contract, filenames and ground anchor
remain unchanged. Arm and leg joints mirror software_render.py exactly.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw
from software_render import ANCHOR, DIRECTIONS, ELEVATION, FRAME, SCALE, YAW

DEFAULT_ROOT = Path("assets/characters/ch_actor_green_01/costumes/clown_01")
DEFAULT_REVIEW = Path("tools/ch_actor_lab/art/costumes/clown_01_review.png")

PRIMARY_SHADE=(196,196,196,250); PRIMARY_MID=(216,216,216,255); PRIMARY_LIGHT=(238,238,238,255)
SECONDARY_SHADE=(164,164,164,250); SECONDARY_MID=(190,190,190,255); SECONDARY_LIGHT=(220,220,220,255)
WIG_BASE=(181,181,181,255); WIG_MID=(202,202,202,255); WIG_LIGHT=(229,229,229,255)
OUTLINE=(55,47,43,235); FACE=(245,240,226,252); FACE_SHADOW=(214,196,179,245)
NOSE=(226,48,40,255); NOSE_LIGHT=(249,105,82,255); MOUTH=(156,45,51,255)
EYE=(46,43,42,255); EYE_MAKEUP=(61,116,188,220)
COLLAR=(241,241,228,255); COLLAR_SHADOW=(201,207,199,255)
GLOVE=(246,246,235,255); GLOVE_SHADOW=(206,211,205,255)
BUTTON=(246,211,58,255); BUTTON_SHADOW=(176,136,32,255)
SHOE=(48,57,64,255); SHOE_LIGHT=(77,88,96,255)


def project(point, direction):
    x,y,z=point; c,s=math.cos(direction),math.sin(direction)
    x,z=c*x+s*z,-s*x+c*z
    right=math.cos(YAW)*x-math.sin(YAW)*z
    up=math.cos(ELEVATION)*y-math.sin(ELEVATION)*(math.sin(YAW)*x+math.cos(YAW)*z)
    return ANCHOR[0]+SCALE*right, ANCHOR[1]-SCALE*up


def depth(point, direction):
    x,_,z=point; c,s=math.cos(direction),math.sin(direction)
    x,z=c*x+s*z,-s*x+c*z
    return math.sin(YAW)*x+math.cos(YAW)*z


def phase_state(phase, idle):
    if idle: return 0.0,0.0,0.0
    return (math.sin(2*math.pi*phase), math.cos(2*math.pi*phase),
            .004*abs(math.sin(4*math.pi*phase)))


def tint(draw, mask_draw, primitive, xy, fill, channel, **kwargs):
    getattr(draw, primitive)(xy, fill=fill, **kwargs)
    select={"R":(255,0,0,255),"G":(0,255,0,255),"B":(0,0,255,255)}[channel]
    getattr(mask_draw, primitive)(xy, fill=select, **kwargs)


def shades(channel):
    return ((PRIMARY_SHADE,PRIMARY_MID,PRIMARY_LIGHT) if channel=="R"
            else (SECONDARY_SHADE,SECONDARY_MID,SECONDARY_LIGHT))


def leg_points(sign, sine, cosine, direction):
    # Exact approved locomotion contract.
    swing=sign*sine; hip=(sign*.078,.405,0)
    z=.145*swing+.025*sign*cosine
    lifted=max(0,swing)*.032+max(0,sign*cosine)*.012
    foot=(sign*(.082+.008*abs(sine)),.035+lifted,z)
    knee=(sign*.08,.225+lifted*.33,z*.42-.028*max(0,swing))
    return project(hip,direction),project(knee,direction),project(foot,direction)


def arm_points(sign, sine, bob, direction):
    # Exact ActorPainter.arm() joints; costume does not alter motion.
    opposite=-sign*sine
    shoulder=(sign*.175,.685+bob,-.005)
    elbow=(sign*.205,.565+bob,.055*opposite)
    hand=(sign*.19,.445+bob,.115*opposite+.01)
    return project(shoulder,direction),project(elbow,direction),project(hand,direction)


def draw_leg(draw, mask_draw, sign, channel, sine, cosine, direction):
    coords=[tuple(map(round,p)) for p in leg_points(sign,sine,cosine,direction)]
    shade,mid,light=shades(channel)
    tint(draw,mask_draw,"line",coords,shade,channel,width=5,joint="curve")
    tint(draw,mask_draw,"line",coords,mid,channel,width=3,joint="curve")
    tint(draw,mask_draw,"line",[(x-1,y) for x,y in coords[:-1]],light,channel,width=1,joint="curve")
    fx,fy=coords[-1]; toe=4 if sign>0 else -4
    shoe=[(fx-2,fy-1),(fx+toe+2,fy-1),(fx+toe+3,fy),(fx+toe+2,fy+2),(fx-2,fy+2)]
    draw.polygon(shoe,fill=SHOE,outline=OUTLINE)
    draw.line((fx,fy,fx+toe,fy),fill=SHOE_LIGHT,width=1)


def draw_arm(draw, mask_draw, sign, channel, sine, bob, direction):
    pts=[tuple(map(round,p)) for p in arm_points(sign,sine,bob,direction)]
    shade,mid,light=shades(channel)
    tint(draw,mask_draw,"line",pts[:2],shade,channel,width=5,joint="curve")
    tint(draw,mask_draw,"line",pts[:2],mid,channel,width=3,joint="curve")
    tint(draw,mask_draw,"line",pts[1:],shade,channel,width=4,joint="curve")
    tint(draw,mask_draw,"line",pts[1:],mid,channel,width=2,joint="curve")
    draw.line((pts[0][0]-1,pts[0][1],pts[1][0]-1,pts[1][1]),fill=light,width=1)
    hx,hy=pts[-1]; ex,ey=pts[-2]; vx,vy=hx-ex,hy-ey; length=max(1.0,math.hypot(vx,vy))
    nx,ny=-vy/length,vx/length
    cuff=[(round(hx+nx*2),round(hy+ny*2)),(round(hx-nx*2),round(hy-ny*2))]
    draw.line(cuff,fill=COLLAR_SHADOW,width=2); draw.line(cuff,fill=COLLAR,width=1)
    draw.ellipse((hx-2,hy-2,hx+2,hy+2),fill=GLOVE,outline=OUTLINE)
    draw.point((hx-1,hy-1),fill=(255,255,250,255)); draw.point((hx+1,hy+1),fill=GLOVE_SHADOW)


def draw_front(draw, mask_draw, chest, lower):
    cx,cy=map(round,chest); lx,ly=map(round,lower)
    left=[(cx-7,cy),(cx-4,cy-4),(cx-1,cy-4),(cx-1,cy+6),(cx-5,cy+5)]
    right=[(cx+7,cy),(cx+4,cy-4),(cx+1,cy-4),(cx+1,cy+6),(cx+5,cy+5)]
    tint(draw,mask_draw,"polygon",left,PRIMARY_SHADE,"R"); tint(draw,mask_draw,"polygon",right,SECONDARY_SHADE,"G")
    tint(draw,mask_draw,"polygon",[(cx-5,cy-1),(cx-2,cy-3),(cx-2,cy+4),(cx-4,cy+3)],PRIMARY_MID,"R")
    tint(draw,mask_draw,"polygon",[(cx+5,cy-1),(cx+2,cy-3),(cx+2,cy+4),(cx+4,cy+3)],SECONDARY_MID,"G")
    tint(draw,mask_draw,"line",[(cx-4,cy-1),(cx-3,cy-2),(cx-3,cy+3)],PRIMARY_LIGHT,"R",width=1)
    tint(draw,mask_draw,"line",[(cx+4,cy-1),(cx+3,cy-2),(cx+3,cy+3)],SECONDARY_LIGHT,"G",width=1)
    ruff=[(cx-6,cy-4),(cx-4,cy-6),(cx-2,cy-4),(cx,cy-6),(cx+2,cy-4),(cx+4,cy-6),(cx+6,cy-4),(cx+4,cy-2),(cx,cy-3),(cx-4,cy-2)]
    draw.polygon(ruff,fill=COLLAR_SHADOW); draw.line(ruff[:7],fill=COLLAR,width=2)
    draw.line((cx,cy-1,cx,cy+5),fill=(64,56,52,180),width=1)
    for by in (cy+1,cy+4):
        draw.point((cx+1,by+1),fill=BUTTON_SHADOW); draw.point((cx,by),fill=BUTTON)
    draw.line((lx-5,ly,lx+5,ly),fill=(64,56,52,105),width=1)


def draw_back(draw, mask_draw, chest, lower):
    cx,cy=map(round,chest); lx,ly=map(round,lower)
    left=[(cx-6,cy-3),(cx-1,cy-4),(cx-1,cy+5),(lx-4,ly+1)]
    right=[(cx+6,cy-3),(cx+1,cy-4),(cx+1,cy+5),(lx+4,ly+1)]
    tint(draw,mask_draw,"polygon",left,PRIMARY_SHADE,"R"); tint(draw,mask_draw,"polygon",right,SECONDARY_SHADE,"G")
    tint(draw,mask_draw,"line",[(cx-4,cy-2),(cx-3,cy+3)],PRIMARY_MID,"R",width=1)
    tint(draw,mask_draw,"line",[(cx+4,cy-2),(cx+3,cy+3)],SECONDARY_MID,"G",width=1)
    draw.line((cx,cy-3,cx,cy+5),fill=(64,56,52,145),width=1)
    draw.arc((cx-5,cy-6,cx+5,cy),8,172,fill=COLLAR_SHADOW,width=2)
    draw.arc((cx-4,cy-6,cx+4,cy-1),8,172,fill=COLLAR,width=1)


def draw_wig(draw, mask_draw, hx, hy, facing):
    # One connected under-mass prevents the floating-hair-balls silhouette.
    tint(draw,mask_draw,"ellipse",(round(hx-8),round(hy-8),round(hx+8),round(hy+4)),WIG_BASE,"B",outline=OUTLINE,width=1)
    puffs=[(-7,-1,3,4),(-6,-5,4,3),(-3,-8,4,4),(1,-9,4,4),(5,-7,4,3),(7,-3,3,4),(6,1,3,3),(-6,2,3,3)]
    if facing<=.2: puffs += [(-2,0,4,3),(2,0,4,3)]
    for i,(dx,dy,rx,ry) in enumerate(puffs):
        box=(round(hx+dx-rx),round(hy+dy-ry),round(hx+dx+rx),round(hy+dy+ry))
        tint(draw,mask_draw,"ellipse",box,WIG_LIGHT if i in (2,3,4) else WIG_MID,"B")
    for box,start,end in (((hx-7,hy-7,hx-1,hy-1),205,315),((hx-1,hy-10,hx+5,hy-4),200,320),((hx+3,hy-7,hx+8,hy-1),210,330)):
        draw.arc(tuple(round(v) for v in box),start,end,fill=(82,54,43,150),width=1)


def draw_face(draw, fx, fy):
    draw.ellipse((fx-5,fy-6,fx+5,fy+5),fill=FACE,outline=FACE_SHADOW,width=1)
    draw.arc((fx-5,fy-6,fx+5,fy+5),72,126,fill=FACE_SHADOW,width=1)
    draw.point((fx-4,fy-4),fill=(255,252,241,255))
    draw.rectangle((fx-3,fy-2,fx-2,fy-1),fill=EYE); draw.rectangle((fx+2,fy-2,fx+3,fy-1),fill=EYE)
    draw.line((fx-4,fy-4,fx-2,fy-3),fill=EYE_MAKEUP,width=1); draw.line((fx+4,fy-4,fx+2,fy-3),fill=EYE_MAKEUP,width=1)
    draw.ellipse((fx-1,fy-1,fx+1,fy+1),fill=NOSE); draw.point((fx,fy-1),fill=NOSE_LIGHT)
    draw.arc((fx-3,fy+1,fx+3,fy+4),12,168,fill=MOUTH,width=1)
    draw.point((fx-3,fy+2),fill=(199,88,79,220)); draw.point((fx+3,fy+2),fill=(199,88,79,220))


def build_frame(direction_key, direction, phase, idle):
    overlay=Image.new("RGBA",FRAME,(0,0,0,0)); mask=Image.new("RGBA",FRAME,(0,0,0,0))
    draw=ImageDraw.Draw(overlay); mask_draw=ImageDraw.Draw(mask)
    sine,cosine,bob=phase_state(phase,idle)
    draw_leg(draw,mask_draw,-1,"R",sine,cosine,direction); draw_leg(draw,mask_draw,1,"G",sine,cosine,direction)
    order=sorted((-1,1),key=lambda sign:depth((sign*.18,0,0),direction)); channels={-1:"R",1:"G"}
    draw_arm(draw,mask_draw,order[0],channels[order[0]],sine,bob,direction)
    facing=math.cos(direction-YAW); z=.11 if facing>.2 else -.025
    chest=project((0,.67+bob,z),direction); lower=project((0,.53+bob,z),direction)
    (draw_front if facing>.2 else draw_back)(draw,mask_draw,chest,lower)
    draw_arm(draw,mask_draw,order[1],channels[order[1]],sine,bob,direction)
    hx,hy=project((0,.875+bob,0),direction); draw_wig(draw,mask_draw,hx,hy,facing)
    if facing>.2:
        fx,fy=map(round,project((0,.858+bob,.113),direction)); draw_face(draw,fx,fy)
    return overlay,mask


def build(root, review_path):
    frame_dir=root/"frames"; mask_dir=root/"masks"; frame_dir.mkdir(parents=True,exist_ok=True); mask_dir.mkdir(parents=True,exist_ok=True)
    angles={logical.lower():angle for logical,_,angle in DIRECTIONS}; entries=[]
    for key in "senw":
        names=[(f"{key}_idle.png",0.0,True)]+[(f"{key}_walk_{i:02d}.png",i/8.0,False) for i in range(8)]
        for filename,phase,idle in names:
            overlay,mask=build_frame(key,angles[key],phase,idle); overlay.save(frame_dir/filename); mask.save(mask_dir/filename); entries.append(filename)
    manifest={"contract":"CH_ACTOR_COSTUME_V3","actor":"ch_actor_green_01","costume":"clown_01","motionPolicy":"reuse_approved_actor_frames_without_pose_changes","frame":{"width":FRAME[0],"height":FRAME[1],"groundAnchor":list(ANCHOR)},"maskChannels":{"R":"primary_costume","G":"secondary_costume","B":"wig","A":"overlay_alpha"},"fixedArt":["white_face_makeup","red_nose","red_mouth","blue_eye_makeup","white_ruff","white_gloves","gold_buttons","dark_shoes"],"visualRevision":{"version":3,"goals":["dress_approved_arm_motion_with_clown_sleeves_and_gloves","unified_volumetric_wig_mass","cleaner_native_scale_face","stronger_front_and_back_costume_volume","fixed_dark_shoes_outside_tint_masks","preserve_approved_walk_and_ground_anchor"]},"frames":entries,"notes":["Overlay names match approved CH Actor frame names one-for-one.","Approved body/walk PNGs are never rewritten.","Arm and leg joint formulas mirror software_render.py.","No costume primitive is allowed below the approved foot extent.","Tint shading is derived from overlay luminance at runtime."]}
    (root/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    review_path.parent.mkdir(parents=True,exist_ok=True); board=Image.new("RGBA",(4*144,3*192),(42,65,56,255))
    for col,key in enumerate("senw"):
        for row,filename in enumerate((f"{key}_idle.png",f"{key}_walk_02.png",f"{key}_walk_06.png")):
            image=Image.open(frame_dir/filename).convert("RGBA").resize((144,192),Image.Resampling.NEAREST); board.alpha_composite(image,(col*144,row*192))
    board.save(review_path)


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("--root",type=Path,default=DEFAULT_ROOT); parser.add_argument("--review",type=Path,default=DEFAULT_REVIEW)
    args=parser.parse_args(); build(args.root,args.review); print(f"Wrote refined clown costume V3 to {args.root}")


if __name__=="__main__": main()
