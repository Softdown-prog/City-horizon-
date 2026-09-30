(() => {
  'use strict';
  const CONTRACT = Object.freeze({
    version:'CH_ACTOR_VALIDATED_V1', camera:'CH_CAMERA_V1', yawDeg:45, pitchDeg:30, anchorOffsetPx:4,
    directions:[
      {logical:'S',screen:'SW',row:0,angleRad:Math.PI/2},
      {logical:'E',screen:'SE',row:1,angleRad:0},
      {logical:'W',screen:'NW',row:2,angleRad:Math.PI},
      {logical:'N',screen:'NE',row:3,angleRad:-Math.PI/2}
    ]
  });
  const DEFAULT_STATE = Object.freeze({w:48,h:64,count:8,leg:.32,arm:.18,bounce:.004,outline:true});
  const DEFAULT_COLORS = Object.freeze({jacket:'#15803d',shirt:'#f8fafc',pants:'#1d4ed8',hair:'#5a3825',skin:'#f6c29e',shoes:'#1f2937'});
  const direction = logical => CONTRACT.directions.find(d => d.logical === logical);
  const phases = count => count===2 ? [.25,.75] : Array.from({length:count},(_,i)=>i/count);

  function makeMaterials(THREE, colors={}) {
    const merged={...DEFAULT_COLORS,...colors};
    return Object.fromEntries(Object.entries(merged).map(([key,value])=>[key,new THREE.MeshLambertMaterial({color:value})]));
  }

  function createActor(THREE, scene, options={}) {
    const palette=makeMaterials(THREE,options.colors);
    const root=new THREE.Group(); root.name='CH_ACTOR_ROOT_LOCKED'; scene.add(root);
    if(options.lights!==false){
      scene.add(new THREE.AmbientLight(0xffffff,.75));
      const sun=new THREE.DirectionalLight(0xffffff,.85); sun.position.set(-6,14,9); scene.add(sun);
      const bounce=new THREE.DirectionalLight(0x94a3b8,.3); bounce.position.set(6,-2,-6); scene.add(bounce);
    }
    const add=(parent,geo,mat,x,y,z,name)=>{const mesh=new THREE.Mesh(geo,mat);mesh.position.set(x,y,z);mesh.name=name||'';parent.add(mesh);return mesh};
    const parts={};
    const torso=new THREE.Group(); torso.name='torso_LOCKED'; torso.position.y=.42; root.add(torso);
    parts.torsoBody=add(torso,new THREE.CylinderGeometry(.14,.12,.32,12),palette.jacket,0,.16,0,'torsoBody');
    parts.shirt=add(torso,new THREE.BoxGeometry(.09,.28,.05),palette.shirt,0,.16,.12,'shirt');
    parts.suspenders=[];
    for(const x of [-.07,.07]) parts.suspenders.push(add(torso,new THREE.BoxGeometry(.045,.29,.05),palette.jacket,x,.16,.135,'suspender'));

    const head=new THREE.Group(); head.name='head_LOCKED_CHILD_OF_TORSO'; head.position.y=.32; torso.add(head);
    parts.face=add(head,new THREE.SphereGeometry(.15,12,10),palette.skin,0,.14,0,'face'); parts.face.scale.set(.9,1.05,.9);
    parts.hairCap=add(head,new THREE.SphereGeometry(.17,12,10,0,Math.PI*2,0,Math.PI*.58),palette.hair,0,.17,-.02,'hairCap'); parts.hairCap.scale.set(.96,.92,1);
    parts.hairTuft=add(head,new THREE.SphereGeometry(.045,8,6),palette.hair,0,.24,.125,'hairTuft');
    parts.eyeDots=[];
    for(const x of [-.055,.055]) parts.eyeDots.push(add(head,new THREE.SphereGeometry(.01,6,4),palette.hair,x,.155,.133,'eyeDot'));

    const arms=[];
    for(const sign of [-1,1]){
      const group=new THREE.Group(); group.name=sign<0?'arm_L_LOCKED':'arm_R_LOCKED'; group.position.set(sign*.17,.29,0); torso.add(group);
      const sleeve=add(group,new THREE.CylinderGeometry(.052,.047,.22,8),palette.jacket,0,-.11,0,'sleeve');
      const hand=add(group,new THREE.SphereGeometry(.046,8,6),palette.skin,0,-.23,0,'hand');
      arms.push({sign,group,sleeve,hand});
    }

    const legs=[];
    for(const sign of [-1,1]){
      const hip=new THREE.Group(); hip.name=sign<0?'leg_L_LOCKED':'leg_R_LOCKED'; hip.position.set(sign*.08,.40,0); root.add(hip);
      const thigh=add(hip,new THREE.CylinderGeometry(.064,.056,.20,8),palette.pants,0,-.10,0,'thigh');
      const knee=new THREE.Group(); knee.position.y=-.20; hip.add(knee);
      const shin=add(knee,new THREE.CylinderGeometry(.057,.05,.17,8),palette.pants,0,-.085,0,'shin');
      const shoe=add(knee,new THREE.BoxGeometry(.095,.065,.16),palette.shoes,0,-.17,.035,'shoe');
      legs.push({sign,hip,knee,thigh,shin,shoe});
    }

    const shadow=add(root,new THREE.CircleGeometry(.23,20),new THREE.MeshBasicMaterial({color:0x101827,transparent:true,opacity:.35}),0,.004,0,'shadow');
    shadow.rotation.x=-Math.PI/2; shadow.scale.set(.9,.55,1);
    return {contract:CONTRACT.version,root,torso,head,arms,legs,parts,palette,shadow};
  }

  function pose(actor, phase, values={}) {
    const leg=values.leg ?? .32, arm=values.arm ?? .18, bounce=values.bounce ?? .004;
    const s=Math.sin(2*Math.PI*phase), c=Math.cos(2*Math.PI*phase), a=leg*s;
    actor.legs[0].hip.rotation.x=a; actor.legs[1].hip.rotation.x=-a;
    actor.legs[0].knee.rotation.x=-.30*Math.max(0,-s)-.08*Math.max(0,c);
    actor.legs[1].knee.rotation.x=-.30*Math.max(0,s)-.08*Math.max(0,-c);
    actor.arms[0].group.rotation.x=-arm*s; actor.arms[1].group.rotation.x=arm*s;
    actor.torso.position.y=.42+bounce*Math.abs(Math.sin(4*Math.PI*phase));
  }

  function setDirection(actor, logical){const d=direction(logical);if(!d)throw Error(`Unknown CH Actor direction ${logical}`);actor.root.rotation.y=d.angleRad;return d;}

  function configureCamera(THREE, renderer, camera, w=48, h=64){
    renderer.setSize(w,h,false);
    const elev=Math.PI*CONTRACT.pitchDeg/180, yaw=Math.PI*CONTRACT.yawDeg/180, dist=12, targetY=.475;
    camera.position.set(Math.sin(yaw)*Math.cos(elev)*dist,targetY+Math.sin(elev)*dist,Math.cos(yaw)*Math.cos(elev)*dist);
    camera.lookAt(0,targetY,0);
    const height=1.35, aspect=w/h;
    camera.left=-height*aspect/2; camera.right=height*aspect/2;
    const projectedGround=-targetY*Math.cos(elev);
    camera.top=projectedGround+((h-CONTRACT.anchorOffsetPx)/h)*height;
    camera.bottom=camera.top-height; camera.updateProjectionMatrix();
  }

  window.CH_ACTOR_VALIDATED_V1=Object.freeze({CONTRACT,DEFAULT_STATE,DEFAULT_COLORS,phases,createActor,pose,setDirection,configureCamera});
})();
