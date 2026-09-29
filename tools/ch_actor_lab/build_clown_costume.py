"""Build the V4 frame-aligned clown costume for the approved CH Actor.

V4 is a visual-only pass. Locomotion, 48x64 frame contract, filenames and
[24,60] ground anchor remain unchanged. Artwork is authored at 4x resolution
and downsampled to native size so face, wig, gloves and costume volumes read
closer to the approved CH Actor instead of looking like native-resolution masks.
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
SS = 4

PRIMARY_SHADE=(181,181,181,248); PRIMARY_MID=(207,207,207,255); PRIMARY_LIGHT=(236,236,236,255)
SECONDARY_SHADE=(157,157,157,248); SECONDARY_MID=(187,187,187,255); SECONDARY_LIGHT=(220,220,220,255)
WIG_DARK=(144,144,144,255); WIG_BASE=(178,178,178,255); WIG_LIGHT=(215,215,215,255)
OUTLINE=(52,46,43,238); FACE=(246,239,221,252); FACE_SHADOW=(211,190,170,242)
NOSE=(222,54,45,255); NOSE_LIGHT=(249,120,96,255); MOUTH=(145,52,57,255)
EYE=(45,42,41,255); EYE_MAKEUP=(69,114,174,210)
COLLAR=(241,239,224,255); COLLAR_SHADOW=(193,198,190,255)
GLOVE=(246,244,232,255); GLOVE_SHADOW=(198,202,196,255)
BUTTON=(239,204,62,255); BUTTON_SHADOW=(164,129,38,255)
SHOE=(43,54,62,255); SHOE_LIGHT=(73,87,95,255)


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


def P(point): return tuple(round(v*SS) for v in point)
def BOX(box): return tuple(round(v*SS) for v in box)
def W(value): return max(1,round(value*SS))


def mask_color(channel):
    return {"R":(255,0,0,255),"G":(0,255,0,255),"B":(0,0,255,255)}[channel]


def tint_line(draw, mask_draw, points, fill, channel, width, joint="curve"):
    pts=[P(p) for p in points]; w=W(width)
    draw.line(pts,fill=fill,width=w,joint=joint)
    mask_draw.line(pts,fill=mask_color(channel),width=w,joint=joint)


def tint_polygon(draw, mask_draw, points, fill, channel):
    pts=[P(p) for p in points]
    draw.polygon(pts,fill=fill); mask_draw.polygon(pts,fill=mask_color(channel))


def tint_ellipse(draw, mask_draw, box, fill, channel, outline=None, width=0):
    b=BOX(box); ow=W(width) if width else 1
    draw.ellipse(b,fill=fill,outline=outline,width=ow)
    mask_draw.ellipse(b,fill=mask_color(channel))


def shades(channel):
    return ((PRIMARY_SHADE,PRIMARY_MID,PRIMARY_LIGHT) if channel=="R"
            else (SECONDARY_SHADE,SECONDARY_MID,SECONDARY_LIGHT))


def leg_points(sign, sine, cosine, direction):
    # Exact approved ActorPainter.leg() kinematics.
    swing=sign*sine; hip=(sign*.078,.405,0)
    z=.145*swing+.025*sign*cosine
    lifted=max(0,swing)*.032+max(0,sign*cosine)*.012
    foot=(sign*(.082+.008*abs(sine)),.035+lifted,z)
    knee=(sign*.08,.225+lifted*.33,z*.42-.028*max(0,swing))
    return project(hip,direction),project(knee,direction),project(foot,direction)


def arm_points(sign, sine, bob, direction):
    # Exact approved ActorPainter.arm() kinematics.
    opposite=-sign*sine
    shoulder=(sign*.175,.685+bob,-.005)
    elbow=(sign*.205,.565+bob,.055*opposite)
    hand=(sign*.19,.445+bob,.115*opposite+.01)
    return project(shoulder,direction),project(elbow,direction),project(hand,direction)


def draw_leg(draw, mask_draw, sign, channel, sine, cosine, direction):
    pts=leg_points(sign,sine,cosine,direction); shade,mid,light=shades(channel)
    tint_line(draw,mask_draw,pts,shade,channel,5.0)
    tint_line(draw,mask_draw,pts,mid,channel,3.2)
    tint_line(draw,mask_draw,[(x-.65,y-.10) for x,y in pts[:-1]],light,channel,.75)
    fx,fy=pts[-1]; toe=3.5 if sign>0 else -3.5
    shoe=[(fx-1.9,fy-.9),(fx+toe+1.9,fy-.8),(fx+toe+2.4,fy+.2),(fx+toe+1.7,fy+1.7),(fx-1.7,fy+1.7)]
    draw.polygon([P(p) for p in shoe],fill=SHOE,outline=OUTLINE)
    draw.line((P((fx-.2,fy-.25)),P((fx+toe,fy-.1))),fill=SHOE_LIGHT,width=W(.65))


def draw_arm(draw, mask_draw, sign, channel, sine, bob, direction):
    pts=arm_points(sign,sine,bob,direction); shade,mid,light=shades(channel)
    tint_line(draw,mask_draw,pts[:2],shade,channel,4.8)
    tint_line(draw,mask_draw,pts[:2],mid,channel,3.1)
    tint_line(draw,mask_draw,pts[1:],shade,channel,3.8)
    tint_line(draw,mask_draw,pts[1:],mid,channel,2.25)
    draw.line((P((pts[0][0]-.55,pts[0][1]-.15)),P((pts[1][0]-.55,pts[1][1]))),fill=light,width=W(.55))
    hx,hy=pts[-1]; ex,ey=pts[-2]; vx,vy=hx-ex,hy-ey; ln=max(1e-4,math.hypot(vx,vy)); nx,ny=-vy/ln,vx/ln
    cuff=[(hx+nx*1.75,hy+ny*1.75),(hx-nx*1.75,hy-ny*1.75)]
    draw.line([P(p) for p in cuff],fill=COLLAR_SHADOW,width=W(1.7)); draw.line([P(p) for p in cuff],fill=COLLAR,width=W(.8))
    draw.ellipse(BOX((hx-1.65,hy-1.85,hx+1.65,hy+1.85)),fill=GLOVE,outline=OUTLINE,width=W(.35))
    draw.ellipse(BOX((hx-.85,hy-1.05,hx+.10,hy-.25)),fill=(255,254,244,255))
    draw.arc(BOX((hx-.8,hy-.1,hx+1.1,hy+1.45)),35,145,fill=GLOVE_SHADOW,width=W(.45))


def draw_front(draw, mask_draw, chest, lower):
    cx,cy=chest; lx,ly=lower
    left=[(cx-6.6,cy+.2),(cx-4.2,cy-4.0),(cx-.8,cy-4.25),(cx-.65,cy+5.7),(cx-4.8,cy+4.8)]
    right=[(cx+6.6,cy+.2),(cx+4.2,cy-4.0),(cx+.8,cy-4.25),(cx+.65,cy+5.7),(cx+4.8,cy+4.8)]
    tint_polygon(draw,mask_draw,left,PRIMARY_SHADE,"R"); tint_polygon(draw,mask_draw,right,SECONDARY_SHADE,"G")
    tint_polygon(draw,mask_draw,[(cx-5.2,cy-.3),(cx-2.0,cy-3.2),(cx-1.7,cy+3.9),(cx-4.0,cy+3.3)],PRIMARY_MID,"R")
    tint_polygon(draw,mask_draw,[(cx+5.2,cy-.3),(cx+2.0,cy-3.2),(cx+1.7,cy+3.9),(cx+4.0,cy+3.3)],SECONDARY_MID,"G")
    tint_line(draw,mask_draw,[(cx-4.0,cy-.4),(cx-2.8,cy-2.0),(cx-2.5,cy+2.8)],PRIMARY_LIGHT,"R",.65)
    tint_line(draw,mask_draw,[(cx+4.0,cy-.4),(cx+2.8,cy-2.0),(cx+2.5,cy+2.8)],SECONDARY_LIGHT,"G",.65)
    # Smaller layered ruff: readable but no longer a giant white bar.
    ruff=[(cx-5.0,cy-4.0),(cx-3.2,cy-5.25),(cx-1.3,cy-4.2),(cx,cy-5.3),(cx+1.3,cy-4.2),(cx+3.2,cy-5.25),(cx+5.0,cy-4.0),(cx+3.3,cy-2.4),(cx,cy-3.0),(cx-3.3,cy-2.4)]
    draw.polygon([P(p) for p in ruff],fill=COLLAR_SHADOW)
    draw.line([P(p) for p in ruff[:7]],fill=COLLAR,width=W(1.15),joint="curve")
    draw.line((P((cx,cy-.9)),P((cx,cy+4.8))),fill=(64,56,52,150),width=W(.45))
    for by in (cy+1.05,cy+3.55):
        draw.ellipse(BOX((cx-.65,by-.65,cx+.65,by+.65)),fill=BUTTON_SHADOW)
        draw.ellipse(BOX((cx-.55,by-.7,cx+.35,by+.2)),fill=BUTTON)
    draw.line((P((lx-4.5,ly)),P((lx+4.5,ly))),fill=(64,56,52,95),width=W(.45))


def draw_back(draw, mask_draw, chest, lower):
    cx,cy=chest; lx,ly=lower
    left=[(cx-5.8,cy-3.1),(cx-.7,cy-4.0),(cx-.6,cy+5.0),(lx-4.0,ly+1.0)]
    right=[(cx+5.8,cy-3.1),(cx+.7,cy-4.0),(cx+.6,cy+5.0),(lx+4.0,ly+1.0)]
    tint_polygon(draw,mask_draw,left,PRIMARY_SHADE,"R"); tint_polygon(draw,mask_draw,right,SECONDARY_SHADE,"G")
    tint_line(draw,mask_draw,[(cx-4.0,cy-2.0),(cx-3.0,cy+3.2)],PRIMARY_MID,"R",.8)
    tint_line(draw,mask_draw,[(cx+4.0,cy-2.0),(cx+3.0,cy+3.2)],SECONDARY_MID,"G",.8)
    draw.line((P((cx,cy-3)),P((cx,cy+4.8))),fill=(64,56,52,130),width=W(.45))
    draw.arc(BOX((cx-4.7,cy-5.7,cx+4.7,cy-.1)),8,172,fill=COLLAR_SHADOW,width=W(1.1))
    draw.arc(BOX((cx-4.0,cy-5.5,cx+4.0,cy-.6)),8,172,fill=COLLAR,width=W(.65))


def draw_wig_back(draw, mask_draw, hx, hy, facing, xbias):
    # Smaller connected silhouette; V3 was visually wider than the head/body balance.
    cx=hx+xbias*.25
    tint_ellipse(draw,mask_draw,(cx-6.6,hy-6.8,cx+6.6,hy+2.7),WIG_DARK,"B",outline=OUTLINE,width=.55)
    puffs=[(-5.5,-1.0,2.7,3.1),(-4.6,-4.4,3.0,2.7),(-1.7,-6.6,3.1,2.6),(1.7,-6.8,3.0,2.7),(4.5,-4.7,2.9,2.8),(5.7,-1.2,2.5,3.0)]
    if facing<=.2: puffs += [(-2.5,1.0,3.0,2.4),(2.5,1.0,3.0,2.4)]
    for i,(dx,dy,rx,ry) in enumerate(puffs):
        fill=WIG_LIGHT if i in (2,3) else WIG_BASE
        tint_ellipse(draw,mask_draw,(cx+dx-rx,hy+dy-ry,cx+dx+rx,hy+dy+ry),fill,"B")
    # A few broad shadow arcs imply curls without the flower/balloon silhouette.
    for box in ((cx-5.1,hy-5.6,cx-.9,hy-1.2),(cx-.8,hy-7.0,cx+3.0,hy-2.8),(cx+2.1,hy-5.4,cx+5.7,hy-1.0)):
        draw.arc(BOX(box),205,325,fill=(74,52,45,145),width=W(.55))


def draw_face(draw, fx, fy, xbias):
    # Slight 3/4 lateral shift keeps the face seated inside the head in E/S views.
    fx += xbias
    draw.ellipse(BOX((fx-4.55,fy-5.7,fx+4.55,fy+4.8)),fill=FACE,outline=FACE_SHADOW,width=W(.55))
    draw.arc(BOX((fx-4.55,fy-5.7,fx+4.55,fy+4.8)),72,126,fill=FACE_SHADOW,width=W(.55))
    draw.ellipse(BOX((fx-3.9,fy-4.7,fx-2.8,fy-3.5)),fill=(255,252,240,210))
    # Compact eyes + restrained blue accents.
    for ex in (-2.05,2.05):
        draw.ellipse(BOX((fx+ex-.55,fy-1.95,fx+ex+.55,fy-.85)),fill=EYE)
    draw.line((P((fx-3.25,fy-3.35)),P((fx-1.95,fy-2.65))),fill=EYE_MAKEUP,width=W(.55))
    draw.line((P((fx+3.25,fy-3.35)),P((fx+1.95,fy-2.65))),fill=EYE_MAKEUP,width=W(.55))
    draw.ellipse(BOX((fx-1.05,fy-.95,fx+1.05,fy+1.10)),fill=NOSE,outline=(163,48,42,220),width=W(.35))
    draw.ellipse(BOX((fx-.35,fy-.65,fx+.35,fy+.05)),fill=NOSE_LIGHT)
    draw.arc(BOX((fx-2.7,fy+.75,fx+2.7,fy+3.55)),14,166,fill=MOUTH,width=W(.65))
    draw.ellipse(BOX((fx-3.4,fy+1.15,fx-2.75,fy+1.8)),fill=(194,99,86,165))
    draw.ellipse(BOX((fx+2.75,fy+1.15,fx+3.4,fy+1.8)),fill=(194,99,86,165))


def draw_wig_front(draw, mask_draw, hx, hy, xbias):
    # Two small front curls integrate the wig with the forehead after face paint.
    cx=hx+xbias*.25
    for dx,dy,rx,ry,fill in ((-3.0,-5.0,2.2,1.6,WIG_BASE),(1.0,-6.0,2.5,1.7,WIG_LIGHT)):
        tint_ellipse(draw,mask_draw,(cx+dx-rx,hy+dy-ry,cx+dx+rx,hy+dy+ry),fill,"B")


def build_frame(direction_key, direction, phase, idle):
    big=(FRAME[0]*SS,FRAME[1]*SS)
    overlay=Image.new("RGBA",big,(0,0,0,0)); mask=Image.new("RGBA",big,(0,0,0,0))
    draw=ImageDraw.Draw(overlay); mask_draw=ImageDraw.Draw(mask)
    sine,cosine,bob=phase_state(phase,idle)
    draw_leg(draw,mask_draw,-1,"R",sine,cosine,direction); draw_leg(draw,mask_draw,1,"G",sine,cosine,direction)
    order=sorted((-1,1),key=lambda sign:depth((sign*.18,0,0),direction)); channels={-1:"R",1:"G"}
    draw_arm(draw,mask_draw,order[0],channels[order[0]],sine,bob,direction)
    facing=math.cos(direction-YAW); z=.11 if facing>.2 else -.025
    chest=project((0,.67+bob,z),direction); lower=project((0,.53+bob,z),direction)
    (draw_front if facing>.2 else draw_back)(draw,mask_draw,chest,lower)
    draw_arm(draw,mask_draw,order[1],channels[order[1]],sine,bob,direction)
    hx,hy=project((0,.875+bob,0),direction)
    xbias={"s":-.15,"e":.85,"w":-.85,"n":.10}[direction_key]
    draw_wig_back(draw,mask_draw,hx,hy,facing,xbias)
    if facing>.2:
        fx,fy=project((0,.858+bob,.113),direction); draw_face(draw,fx,fy,xbias)
        draw_wig_front(draw,mask_draw,hx,hy,xbias)
    overlay=overlay.resize(FRAME,Image.Resampling.LANCZOS)
    mask=mask.resize(FRAME,Image.Resampling.LANCZOS)
    return overlay,mask


def build(root, review_path):
    frame_dir=root/"frames"; mask_dir=root/"masks"; frame_dir.mkdir(parents=True,exist_ok=True); mask_dir.mkdir(parents=True,exist_ok=True)
    angles={logical.lower():angle for logical,_,angle in DIRECTIONS}; entries=[]
    for key in "senw":
        names=[(f"{key}_idle.png",0.0,True)]+[(f"{key}_walk_{i:02d}.png",i/8.0,False) for i in range(8)]
        for filename,phase,idle in names:
            overlay,mask=build_frame(key,angles[key],phase,idle); overlay.save(frame_dir/filename); mask.save(mask_dir/filename); entries.append(filename)
    manifest={
        "contract":"CH_ACTOR_COSTUME_V4","actor":"ch_actor_green_01","costume":"clown_01",
        "motionPolicy":"reuse_approved_actor_frames_without_pose_changes",
        "frame":{"width":FRAME[0],"height":FRAME[1],"groundAnchor":list(ANCHOR),"authoringSupersample":SS},
        "maskChannels":{"R":"primary_costume","G":"secondary_costume","B":"wig","A":"overlay_alpha"},
        "fixedArt":["white_face_makeup","red_nose","red_mouth","blue_eye_makeup","white_ruff","white_gloves","gold_buttons","dark_shoes"],
        "visualRevision":{"version":4,"goals":["4x_supersampled_costume_art","smaller_connected_wig_silhouette","better_three_quarter_face_seating","restrained_makeup","softer_costume_volume","preserve_approved_walk_and_ground_anchor"]},
        "frames":entries,
        "notes":["Overlay names match approved CH Actor frame names one-for-one.","Approved body/walk PNGs are never rewritten.","Arm and leg joint formulas mirror software_render.py.","Costume art is authored at 4x then downsampled to 48x64.","Dark shoes remain outside tint masks."]}
    (root/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    review_path.parent.mkdir(parents=True,exist_ok=True); board=Image.new("RGBA",(4*144,3*192),(42,65,56,255))
    for col,key in enumerate("senw"):
        for row,filename in enumerate((f"{key}_idle.png",f"{key}_walk_02.png",f"{key}_walk_06.png")):
            image=Image.open(frame_dir/filename).convert("RGBA").resize((144,192),Image.Resampling.NEAREST); board.alpha_composite(image,(col*144,row*192))
    board.save(review_path)


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("--root",type=Path,default=DEFAULT_ROOT); parser.add_argument("--review",type=Path,default=DEFAULT_REVIEW)
    args=parser.parse_args(); build(args.root,args.review); print(f"Wrote refined clown costume V4 to {args.root}")


if __name__=="__main__": main()
