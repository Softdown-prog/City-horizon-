(() => {
  'use strict';
  const CONTRACT='CH_ACTOR_SKIN_V1';
  const COLORS=Object.freeze({
    skin:'#f3ead7', hair:'#d43b2f', primary:'#d43b2f', secondary:'#2b71c9', accent:'#f2d744',
    white:'#f4f2e3', shoes:'#26313a', nose:'#df3b36', eye:'#2f2b29', bow:'#8b5cf6'
  });

  function mat(THREE,color){return new THREE.MeshLambertMaterial({color});}
  function add(parent,geo,material,x,y,z,name){const m=new THREE.Mesh(geo,material);m.position.set(x,y,z);m.name=name;parent.add(m);return m;}
  function tag(mesh, bank, channel){mesh.userData.chColorMask={bank,channel};return mesh;}

  function apply(THREE, actor, overrides={}){
    if(!actor || actor.contract!=='CH_ACTOR_VALIDATED_V1') throw Error('clown_01 requires CH_ACTOR_VALIDATED_V1');
    const c={...COLORS,...overrides};
    const m={skin:mat(THREE,c.skin),hair:mat(THREE,c.hair),primary:mat(THREE,c.primary),secondary:mat(THREE,c.secondary),accent:mat(THREE,c.accent),white:mat(THREE,c.white),shoes:mat(THREE,c.shoes),nose:mat(THREE,c.nose),eye:mat(THREE,c.eye),bow:mat(THREE,c.bow)};

    // Re-skin existing validated geometry only. No transform, parent, camera or motion edits.
    actor.parts.torsoBody.material=m.primary;
    actor.parts.shirt.material=m.primary;
    actor.parts.suspenders[0].material=m.accent;
    actor.parts.suspenders[1].material=m.secondary;
    tag(actor.parts.torsoBody,'clothing','R'); tag(actor.parts.shirt,'clothing','R');
    tag(actor.parts.suspenders[0],'clothing','G'); tag(actor.parts.suspenders[1],'clothing','B');

    actor.parts.face.material=m.skin;
    actor.parts.hairCap.material=m.hair; actor.parts.hairTuft.material=m.hair;
    actor.parts.eyeDots.forEach(x=>x.material=m.eye);
    tag(actor.parts.face,'appearance','R'); tag(actor.parts.hairCap,'appearance','G'); tag(actor.parts.hairTuft,'appearance','G');

    actor.arms[0].sleeve.material=m.secondary; actor.arms[1].sleeve.material=m.accent;
    actor.arms[0].hand.material=m.white; actor.arms[1].hand.material=m.white;
    tag(actor.arms[0].sleeve,'clothing','B'); tag(actor.arms[1].sleeve,'clothing','G');
    tag(actor.arms[0].hand,'appearance','B'); tag(actor.arms[1].hand,'appearance','B');

    actor.legs[0].thigh.material=m.secondary; actor.legs[0].shin.material=m.secondary;
    actor.legs[1].thigh.material=m.accent; actor.legs[1].shin.material=m.accent;
    actor.legs.forEach((leg,i)=>{leg.shoe.material=m.shoes;tag(leg.thigh,'clothing',i===0?'B':'G');tag(leg.shin,'clothing',i===0?'B':'G');tag(leg.shoe,'clothing','A');});

    // Clown identity is attached to the validated head/torso hierarchy.
    actor.parts.hairCap.scale.set(.76,.72,.78);
    const puffs=[];
    for(const sign of [-1,1]){
      puffs.push(tag(add(actor.head,new THREE.SphereGeometry(.095,10,8),m.hair,sign*.145,.165,.015,`clownHair_${sign<0?'L':'R'}_a`),'appearance','G'));
      puffs.push(tag(add(actor.head,new THREE.SphereGeometry(.080,10,8),m.hair,sign*.125,.225,-.005,`clownHair_${sign<0?'L':'R'}_b`),'appearance','G'));
    }
    const nose=tag(add(actor.head,new THREE.SphereGeometry(.043,10,8),m.nose,0,.135,.142,'clownNose'),'appearance','B');
    const cheekL=add(actor.head,new THREE.SphereGeometry(.022,8,6),m.nose,-.070,.105,.134,'clownCheekL'); cheekL.scale.set(1.25,.7,.45);
    const cheekR=add(actor.head,new THREE.SphereGeometry(.022,8,6),m.nose,.070,.105,.134,'clownCheekR'); cheekR.scale.set(1.25,.7,.45);

    const ruff=tag(add(actor.torso,new THREE.TorusGeometry(.102,.030,8,20),m.white,0,.315,0,'clownRuff'),'appearance','B');
    ruff.rotation.x=Math.PI/2;
    const bowL=tag(add(actor.torso,new THREE.SphereGeometry(.046,8,6),m.bow,-.045,.275,.145,'clownBowL'),'appearance','B'); bowL.scale.set(1.35,.70,.50);
    const bowR=tag(add(actor.torso,new THREE.SphereGeometry(.046,8,6),m.bow,.045,.275,.145,'clownBowR'),'appearance','B'); bowR.scale.set(1.35,.70,.50);
    const buttonA=add(actor.torso,new THREE.SphereGeometry(.012,6,4),m.accent,0,.205,.145,'clownButtonA');
    const buttonB=add(actor.torso,new THREE.SphereGeometry(.012,6,4),m.secondary,0,.155,.145,'clownButtonB');

    actor.skin={contract:CONTRACT,id:'clown_01',colors:c,materials:m,puffs,nose,cheeks:[cheekL,cheekR],ruff,bow:[bowL,bowR],buttons:[buttonA,buttonB],motionAuthority:'CH_ACTOR_VALIDATED_V1',mayModifyMotion:false};
    return actor.skin;
  }

  window.CH_ACTOR_SKINS=window.CH_ACTOR_SKINS||{};
  window.CH_ACTOR_SKINS.clown_01=Object.freeze({contract:CONTRACT,id:'clown_01',apply,colors:COLORS});
})();
