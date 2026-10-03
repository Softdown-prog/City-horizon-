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
    for y,label in ((-1.2,'NearPendulum'),(1.2,'FarPendulum')):
        for x,side in ((-attach_x,'Bow'),(attach_x,'Stern')):
            a=(0,y,pz); b=(x,y,attach_z)
            for i,t in enumerate(fractions):
                sleeve_between(f'{label}_{side}_GoldCuff_{i}',a,b,float(t),.66,.72,.72,M['gold'],root)
            # ornate ship-end collar just above each attachment pin
            sleeve_between(f'{label}_{side}_LowerGoldCollar',a,b,.91,.46,.78,.78,M['gold'],root)

    mast_top=pz-.65
    mast_bottom=float(d.get('centralMastAttachZ',cz+.45))
    mast_r=float(d.get('centralMastRadius',.42))
    mast_fracs=d.get('mastDecorationFractions',[.24,.46,.68,.86])
    for i,t in enumerate(mast_fracs):
        z=mast_top+(mast_bottom-mast_top)*float(t)
        base.cyl_axis(f'CentralMastGoldBand_{i}',(0,0,z),mast_r*1.34,.30,'Z',M['gold'],root)
    # thicker decorative collars near both mechanical ends of the round mast
    base.cyl_axis('CentralMastUpperDecorativeCollar',(0,0,mast_top-.25),mast_r*1.46,.48,'Z',M['gold'],root)
    base.cyl_axis('CentralMastLowerDecorativeCollar',(0,0,mast_bottom+.30),mast_r*1.46,.48,'Z',M['gold'],root)
    # central medallion pair gives the mast a park-ride ornamental focal point without changing mechanics
    med_z=mast_top+(mast_bottom-mast_top)*.55
    for y in (-.48,.48):
        base.cyl_axis('CentralMastMedallion_%s'%('Near' if y<0 else 'Far'),(0,y,med_z),.76,.18,'Y',M['gold'],root)
        base.cyl_axis('CentralMastMedallionHub_%s'%('Near' if y<0 else 'Far'),(0,y*1.04,med_z),.38,.22,'Y',M['truss'],root)


_original_build=base.build

def decorated_build(root,c,M):
    _original_build(root,c,M)
    decorate_suspension(root,c,M)

base.build=decorated_build

if __name__=='__main__':
    base.main()
