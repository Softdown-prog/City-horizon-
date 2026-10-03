#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, math, shutil, subprocess, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PROJECT = REPO/'C++/MapForge2/projects/coaster_flame_switchback_02.mapforge.json'
BASE = REPO/'C++/MapForge2/src/coaster_project_video_main.cpp'
PROOF = REPO/'C++/MapForge2/src/coaster_video_proof_main.cpp'
GOUT = REPO/'out/ch_blender_agent/coaster.flame.switchback.v4.01.geometry'
SOUT = REPO/'out/ch_blender_agent/coaster.flame.switchback.v4.02.structure'
MOUT = REPO/'out/ch_blender_agent/coaster.flame.switchback.v4.03.motion'
BINS = (-46.,-30.,-14.,0.,14.,30.,46.)

def args():
    av=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    p=argparse.ArgumentParser(); p.add_argument('--task',required=True,choices=('geometry','structure','motion','video'))
    p.add_argument('--project',default=str(PROJECT.relative_to(REPO))); p.add_argument('--output',required=True); return p.parse_args(av)

def rp(v):
    p=Path(v); p=(p if p.is_absolute() else REPO/p).resolve(); p.relative_to(REPO); return p

def load(p): return json.loads(p.read_text(encoding='utf-8'))
def write(p,x): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n',encoding='utf-8')
def run(cmd): print('+',' '.join(map(str,cmd)),flush=True); subprocess.run(list(map(str,cmd)),cwd=REPO,check=True)
def st(i,l,r,**kw): x={'id':i,'type':'straight','length':l,'rise':r}; x.update(kw); return x

def geometry(src,out):
    p=load(src); p['projectId']='coaster.flame.switchback.03'; p['assetId']='ride.coaster_flame_switchback_03'; p['name']='Flame Switchback V4'
    p['captureRequest']='switchback-v4-worker-pool-2026-10-03'
    p['workerPoolRevision']={'contract':'CH_COASTER_WORKER_POOL_REVISION_V2','revision':4,'preservesClosedPlan':True,'poseAtlasContract':'CH_COASTER_CAR_ATLAS_RUNTIME_V2'}
    repl={
      'lift_hill':[st('lift_entry',6,2,driveMode='lift',targetSpeedMps=5.5),st('lift_main',14,8,driveMode='lift',targetSpeedMps=5.5)],
      'first_drop':[st('first_drop_entry',4,-1),st('first_drop_main',16,-9)],
      'airtime_climb':[st('airtime_entry',8,4),st('airtime_crest',6,4),st('airtime_release',6,-2)],
      'second_climb':[st('second_climb_entry',8,3),st('second_climb_main',6,5),st('second_climb_release',6,-2)],
      'second_drop':[st('second_drop_entry',4,-1),st('second_drop_main',10,-6),st('second_drop_exit',6,-1)],
      'brake_descent':[st('brake_descent_main',8,-3,driveMode='brake',targetSpeedMps=7),st('brake_descent_exit',12,-1,driveMode='brake',targetSpeedMps=5.5)]}
    q=[]
    for x in p['pieces']: q.extend(repl.get(x.get('id'),[x]))
    p['pieces']=q; worst=0.0
    for x in q:
        if x.get('type')!='straight': continue
        pitch=math.degrees(math.atan2(float(x.get('rise',0)),float(x['length']))); e=min(abs(pitch-b) for b in BINS); worst=max(worst,e)
        if e>8.01: raise RuntimeError(f"pose coverage {x['id']} error={e:.3f}")
    dst=out/'coaster_flame_switchback_03.mapforge.json'; write(dst,p)
    write(out/'geometry_report.json',{'contract':'CH_COASTER_GEOMETRY_REFINEMENT_V4','status':'ok','projectId':p['projectId'],'pieceCount':len(q),'maxPitchSnapErrorDegrees':worst,'changes':['stronger lift entry/main rhythm','two crest-release airtime hills','staged drops','eased brake return']})
    write(out/'worker_summary.json',{'contract':'CH_COASTER_WORKER_TASK_REPORT_V2','task':'geometry','status':'ok'})

def structure(out):
    s=BASE.read_text(encoding='utf-8')
    swaps={
      'constexpr double kSupportSpacingM = 3.0;':'constexpr double kSupportSpacingM = 4.0;',
      'QPen spinePen(QColor(69,45,39)); spinePen.setWidthF(7.5);':'QPen spinePen(QColor(126,48,38)); spinePen.setWidthF(8.8);',
      'QPen railPen(QColor(201,205,207)); railPen.setWidthF(2.7);':'QPen railPen(QColor(224,228,230)); railPen.setWidthF(3.0);',
      'QPen sleeper(QColor(92,59,39)); sleeper.setWidthF(2.4);':'QPen sleeper(QColor(76,50,39)); sleeper.setWidthF(3.0);',
      's.x + nx * 0.60, s.y + ny * 0.60':'s.x + nx * 0.72, s.y + ny * 0.72',
      's.x - nx * 0.60, s.y - ny * 0.60':'s.x - nx * 0.72, s.y - ny * 0.72'}
    for a,b in swaps.items():
        if a not in s: raise RuntimeError('structure marker missing: '+a[:40])
        s=s.replace(a,b,1)
    a=s.index('void draw_supports('); b=s.index('void draw_track(',a)
    sup='''void draw_supports(QPainter& painter, const Projection& projection,\n                   const ch::coaster::CenterlineRoute& route) {\n    QPen leg(QColor(71,76,80)); leg.setWidthF(3.2);\n    QPen brace(QColor(105,111,114)); brace.setWidthF(1.5);\n    for (double d=0.0; d<route.length_m(); d+=kSupportSpacingM) {\n        const auto s=route.sample(d); if (!s || s->z<0.60) continue;\n        const double l=std::hypot(s->tangent_x,s->tangent_y);\n        const double nx=l>1e-6?-s->tangent_y/l:-1.0, ny=l>1e-6?s->tangent_x/l:0.0;\n        const QPointF ta=projection.map(s->x+nx*.50,s->y+ny*.50,s->z-.10);\n        const QPointF tb=projection.map(s->x-nx*.50,s->y-ny*.50,s->z-.10);\n        const QPointF fa=projection.map(s->x+nx*.82,s->y+ny*.82,0.0);\n        const QPointF fb=projection.map(s->x-nx*.82,s->y-ny*.82,0.0);\n        painter.setPen(leg); painter.drawLine(ta,fa); painter.drawLine(tb,fb);\n        painter.setPen(brace); painter.drawLine(ta,tb);\n        if (s->z>3.0) { painter.drawLine(fa,projection.map(s->x-nx*.62,s->y-ny*.62,s->z*.48)); painter.drawLine(fb,projection.map(s->x+nx*.62,s->y+ny*.62,s->z*.48)); }\n    }\n}\n\n'''
    s=s[:a]+sup+s[b:]
    a=s.index('void draw_station('); b=s.index('void draw_train(',a)
    sta='''void draw_station(QPainter& painter, const Projection& p) {\n    QPolygonF base; base<<p.map(9.4,-2.8,.02)<<p.map(25.6,-2.8,.02)<<p.map(25.6,2.8,.02)<<p.map(9.4,2.8,.02);\n    painter.setPen(QPen(QColor(74,59,47),1.8)); painter.setBrush(QColor(190,158,116)); painter.drawPolygon(base);\n    QPen post(QColor(86,62,49)); post.setWidthF(3.0); painter.setPen(post);\n    painter.drawLine(p.map(10.6,-2.25,.04),p.map(10.6,-2.25,2.25)); painter.drawLine(p.map(10.6,2.25,.04),p.map(10.6,2.25,2.25));\n    painter.drawLine(p.map(24.4,-2.25,.04),p.map(24.4,-2.25,2.25)); painter.drawLine(p.map(24.4,2.25,.04),p.map(24.4,2.25,2.25));\n    QPolygonF roof; roof<<p.map(10,-2.65,2.25)<<p.map(25,-2.65,2.25)<<p.map(25,2.65,2.25)<<p.map(10,2.65,2.25);\n    painter.setPen(QPen(QColor(70,24,21),2.2)); painter.setBrush(QColor(133,39,33)); painter.drawPolygon(roof);\n    painter.setPen(QPen(QColor(226,171,54),3.0)); painter.drawLine(p.map(10,-2.65,2.28),p.map(25,-2.65,2.28));\n}\n\n'''
    s=s[:a]+sta+s[b:]
    dst=out/'coaster_project_video_main_v4.cpp'; dst.write_text(s,encoding='utf-8')
    write(out/'structure_report.json',{'contract':'CH_COASTER_STRUCTURE_REFINEMENT_V4','status':'ok','changes':['A-frame elevated supports','flame-red track beam','brighter rails and wider sleepers','larger supported station roof']})
    write(out/'worker_summary.json',{'contract':'CH_COASTER_WORKER_TASK_REPORT_V2','task':'structure','status':'ok'})

def motion(out):
    s=PROOF.read_text(encoding='utf-8')
    old='constexpr double kSpriteScaleCoefficient = 0.035976898743442;'
    if old not in s: raise RuntimeError('sprite scale marker missing')
    s=s.replace(old,'constexpr double kSpriteScaleCoefficient = 0.0400;',1)
    mark='void draw_train_continuous('
    helper='''double ride_speed_mps(const ch::coaster::CenterlineRoute& route,double d) {\n    const auto s=route.sample(d); if(!s) return kTrainSpeedMps;\n    return std::clamp(10.2-std::clamp(s->tangent_z,-.72,.72)*8.0,5.2,16.0);\n}\nstd::vector<double> build_lead_timeline(const ch::coaster::CenterlineRoute& route) {\n    std::vector<double> v{0.0}; double d=0.0,L=route.length_m();\n    for(int guard=0; guard<kFps*120 && d<L; ++guard){ d=std::min(L,d+ride_speed_mps(route,d)/double(kFps)); v.push_back(d>=L-1e-9?0.0:d); }\n    return v;\n}\n\n'''
    if mark not in s: raise RuntimeError('motion insertion marker missing')
    s=s.replace(mark,helper+mark,1)
    old='''    const double lapSeconds = route.length_m() / kTrainSpeedMps;\n    const int frameCount = std::max(2, static_cast<int>(std::ceil(lapSeconds * kFps)) + 1);\n    if (!write_capture_metadata(outputDir, route, frameCount, lapSeconds)) return 7;\n'''
    new='''    const auto leadTimeline = build_lead_timeline(route);\n    const int frameCount = static_cast<int>(leadTimeline.size());\n    const double lapSeconds = static_cast<double>(frameCount - 1) / kFps;\n    if (!write_capture_metadata(outputDir, route, frameCount, lapSeconds)) return 7;\n'''
    if old not in s: raise RuntimeError('timing marker missing')
    s=s.replace(old,new,1)
    old='''        const double lapProgress = static_cast<double>(frame) /\n                                   static_cast<double>(frameCount - 1);\n        const double lead = ch::coaster::normalize_route_distance(\n            lapProgress * route.length_m(), route.length_m(), true);\n'''
    if old not in s: raise RuntimeError('lead marker missing')
    s=s.replace(old,'        const double lead = leadTimeline[static_cast<std::size_t>(frame)];\n',1)
    dst=out/'coaster_video_proof_main_v4.cpp'; dst.write_text(s,encoding='utf-8')
    write(out/'motion_report.json',{'contract':'CH_COASTER_MOTION_REFINEMENT_V4','status':'ok','minSpeedMps':5.2,'maxSpeedMps':16.0,'changes':['uphill slowdown/downhill acceleration','exact full-lap timeline','larger train sprites']})
    write(out/'worker_summary.json',{'contract':'CH_COASTER_WORKER_TASK_REPORT_V2','task':'motion','status':'ok'})

def wait(paths):
    end=time.time()+300
    while time.time()<end:
        miss=[p for p in paths if not p.is_file()]
        if not miss:return
        print('Worker 4 waiting:',','.join(str(p.relative_to(REPO)) for p in miss),flush=True); time.sleep(2)
    raise FileNotFoundError('worker dependencies missing')

def video(out):
    proj=GOUT/'coaster_flame_switchback_03.mapforge.json'; ps=SOUT/'coaster_project_video_main_v4.cpp'; pv=MOUT/'coaster_video_proof_main_v4.cpp'; wait([proj,ps,pv])
    tmp=REPO/'out/ch_blender_agent/.coaster_switchback_v4_video_tmp'; frames=tmp/'frames'; build=REPO/'build/ch-coaster-switchback-v4-worker4'
    if tmp.exists(): shutil.rmtree(tmp)
    frames.mkdir(parents=True); out.mkdir(parents=True,exist_ok=True)
    ob=tmp/'base.cpp'; op=tmp/'proof.cpp'; shutil.copy2(BASE,ob); shutil.copy2(PROOF,op)
    try:
        shutil.copy2(ps,BASE); shutil.copy2(pv,PROOF)
        run(['cmake','-S','tools/animation_preview/coaster_video_proof','-B',build,'-G','Ninja']); run(['cmake','--build',build,'--target','MapForge2CoasterVideoProof','--parallel'])
        renderer=build/'MapForge2CoasterVideoProof'; atlas=REPO/'assets/vehicles/coaster_flame_01/car_pose_atlas_v2.png'; run([renderer,frames,atlas,proj])
        cap=load(frames/'capture_meta.json'); n=int(cap['frameCount']); mp4=out/'coaster_flame_switchback_v4_worker4.mp4'; sheet=out/'contact_sheet_switchback_v4.png'
        run(['ffmpeg','-y','-framerate','30','-i',frames/'frame_%04d.png','-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',mp4])
        iv=max(1,n//12); vf=f"select='not(mod(n\\,{iv}))',scale=640:-1,tile=4x3"; run(['ffmpeg','-y','-i',mp4,'-vf',vf,'-frames:v','1','-update','1',sheet])
        shutil.copy2(frames/'capture_meta.json',out/'capture_meta.json'); shutil.copy2(proj,out/'coaster_flame_switchback_03.mapforge.json')
        write(out/'video_report.json',{'contract':'CH_COASTER_WORKER4_VIDEO_REPORT_V2','status':'ok','projectId':'coaster.flame.switchback.03','frameCount':n,'fps':30,'routeLengthM':cap.get('routeMeters'),'lapSeconds':cap.get('lapSeconds'),'video':mp4.name,'integratedWorkers':['geometry','structure','motion']})
    finally: shutil.copy2(ob,BASE); shutil.copy2(op,PROOF)

def main():
    a=args(); out=rp(a.output); out.mkdir(parents=True,exist_ok=True)
    if a.task=='geometry': geometry(rp(a.project),out)
    elif a.task=='structure': structure(out)
    elif a.task=='motion': motion(out)
    else: video(out)
if __name__=='__main__': main()
