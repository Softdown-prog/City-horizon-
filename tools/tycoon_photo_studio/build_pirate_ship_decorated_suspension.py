#!/usr/bin/env python3
from __future__ import annotations
import math, sys
from pathlib import Path
import bpy
from mathutils import Vector

HERE=Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0,str(HERE))
import build_pirate_ship_clean_reference as base


def sleeve_between(name,a,b,t,length,width,depth,mat,parent):
    a=Vector(a); b=Vector(b); v=b-a
    direction=v.normalized(); center=a+v*t
    half=length*.5
    start=center-direction*half; end=center+direction*half
    o=base.box(name,tuple(center),(width,depth,length),mat,parent,.035)
    o.rotation_mode='QUATERNION'
    o.rotation_quaternion=(end-start).to_track_quat('Z','Y')
    return o


def decorate_suspension(root,c,M):
    d=c['dimensions']; pz=float(d['pivotZ']); cz=float(d['shipCenterZ'])
    attach_z=cz+.35; attach_x=float(d['shipLength'])*.40
    fractions=d.get('armDecorationFractions',[.22,.48,.74])
    park_palette=[M['funRed'],M['funBlue'],M['funYellow']]
    park_names=['Red','Blue','Yellow']

    for y,label in ((-1.2,'NearPendulum'),(1.2,'FarPendulum')):
        for side_index,(x,side) in enumerate(((-attach_x,'Bow'),(attach_x,'Stern'))):
            for i,t in enumerate(fractions):
                idx=(i+side_index+(0 if y<0 else 1))%len(park_palette)
                sleeve_between(
                    f'{label}_{side}_{park_names[idx]}Cuff_{i}',
                    (0,y,pz),(x,y,attach_z),float(t),.66,.72,.72,
                    park_palette[idx],root)
            lower_idx=(side_index+2+(0 if y<0 else 1))%len(park_palette)
            sleeve_between(
                f'{label}_{side}_{park_names[lower_idx]}LowerCollar',
                (0,y,pz),(x,y,attach_z),.91,.46,.78,.78,
                park_palette[lower_idx],root)

    mast_top=pz-.65
    mast_bottom=float(d.get('centralMastAttachZ',cz+.45))
    mast_r=float(d.get('centralMastRadius',.42))
    mast_fracs=d.get('mastDecorationFractions',[.24,.46,.68,.86])
    for i,t in enumerate(mast_fracs):
        z=mast_top+(mast_bottom-mast_top)*float(t)
        idx=i%len(park_palette)
        base.cyl_axis(
            f'CentralMast{park_names[idx]}Band_{i}',
            (0,0,z),mast_r*1.34,.30,'Z',park_palette[idx],root)

    base.cyl_axis('CentralMastUpperRedCollar',(0,0,mast_top-.25),mast_r*1.46,.48,'Z',M['funRed'],root)
    base.cyl_axis('CentralMastLowerBlueCollar',(0,0,mast_bottom+.30),mast_r*1.46,.48,'Z',M['funBlue'],root)

    med_z=mast_top+(mast_bottom-mast_top)*.55
    for side_index,y in enumerate((-.48,.48)):
        outer=M['funYellow'] if side_index==0 else M['funRed']
        hub=M['funBlue'] if side_index==0 else M['funYellow']
        side='Near' if y<0 else 'Far'
        base.cyl_axis(f'CentralMastMedallion_{side}',(0,y,med_z),.76,.18,'Y',outer,root)
        base.cyl_axis(f'CentralMastMedallionHub_{side}',(0,y*1.04,med_z),.38,.22,'Y',hub,root)


_original_build=base.build

def decorated_build(root,c,M):
    _original_build(root,c,M)
    decorate_suspension(root,c,M)

base.build=decorated_build

if __name__=='__main__':
    base.main()
