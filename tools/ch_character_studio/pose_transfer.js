(() => {
  const W = 48, H = 64;

  const BONE_SETS = {
    skin: [
      ["head","head_top","neck"],
      ["hand_L","elbow_L","hand_L"],
      ["hand_R","elbow_R","hand_R"]
    ],
    hair: [["head","head_top","neck"]],
    face: [["head","head_top","neck"]],
    upper_clothing: [
      ["torso","neck","pelvis"],
      ["upper_arm_L","shoulder_L","elbow_L"],
      ["forearm_L","elbow_L","hand_L"],
      ["upper_arm_R","shoulder_R","elbow_R"],
      ["forearm_R","elbow_R","hand_R"]
    ],
    lower_clothing: [
      ["thigh_L","hip_L","knee_L"],
      ["shin_L","knee_L","ankle_L"],
      ["thigh_R","hip_R","knee_R"],
      ["shin_R","knee_R","ankle_R"]
    ],
    footwear: [
      ["foot_L","ankle_L","foot_L"],
      ["foot_R","ankle_R","foot_R"]
    ],
    accessories_front: [
      ["torso","neck","pelvis"],
      ["forearm_L","elbow_L","hand_L"],
      ["forearm_R","elbow_R","hand_R"]
    ],
    accessories_back: [
      ["head","head_top","neck"],
      ["torso","neck","pelvis"],
      ["upper_arm_L","shoulder_L","elbow_L"],
      ["upper_arm_R","shoulder_R","elbow_R"],
      ["thigh_L","hip_L","knee_L"],
      ["thigh_R","hip_R","knee_R"]
    ],
    silhouette: [
      ["head","head_top","neck"],
      ["torso","neck","pelvis"],
      ["upper_arm_L","shoulder_L","elbow_L"],
      ["forearm_L","elbow_L","hand_L"],
      ["upper_arm_R","shoulder_R","elbow_R"],
      ["forearm_R","elbow_R","hand_R"],
      ["thigh_L","hip_L","knee_L"],
      ["shin_L","knee_L","ankle_L"],
      ["foot_L","ankle_L","foot_L"],
      ["thigh_R","hip_R","knee_R"],
      ["shin_R","knee_R","ankle_R"],
      ["foot_R","ankle_R","foot_R"]
    ]
  };
  BONE_SETS.paint_over = BONE_SETS.silhouette;

  const SCALE_DAMPING = 0.55;
  const SCALE_MIN = 0.88;
  const SCALE_MAX = 1.14;

  function cloneImageData(image) {
    return new ImageData(new Uint8ClampedArray(image.data), image.width, image.height);
  }

  function blankImageData() {
    return new ImageData(W, H);
  }

  function validateLandmarks(data) {
    if (!data || data.contract !== "CH_CHARACTER_LANDMARKS_V0") {
      throw new Error("landmarks.json não usa CH_CHARACTER_LANDMARKS_V0");
    }
    if (!Array.isArray(data.frameSize) || data.frameSize[0] !== W || data.frameSize[1] !== H) {
      throw new Error("landmarks.json precisa usar frame 48x64");
    }
    if (!Array.isArray(data.groundAnchor) || data.groundAnchor[0] !== 24 || data.groundAnchor[1] !== 60) {
      throw new Error("landmarks.json precisa usar ground anchor [24,60]");
    }
    if (!data.frames || typeof data.frames !== "object") {
      throw new Error("landmarks.json não contém frames");
    }
    return data;
  }

  function validBone(bone, sourcePoints, targetPoints) {
    return Array.isArray(sourcePoints[bone[1]]) && Array.isArray(sourcePoints[bone[2]]) &&
           Array.isArray(targetPoints[bone[1]]) && Array.isArray(targetPoints[bone[2]]);
  }

  function pointSegmentDistance(px, py, a, b) {
    const ax=Number(a[0]), ay=Number(a[1]), bx=Number(b[0]), by=Number(b[1]);
    const vx=bx-ax, vy=by-ay, length2=vx*vx+vy*vy;
    if (length2 <= 1e-9) return Math.hypot(px-ax, py-ay);
    const t=Math.max(0,Math.min(1,((px-ax)*vx+(py-ay)*vy)/length2));
    return Math.hypot(px-(ax+vx*t), py-(ay+vy*t));
  }

  function sourceOwnership(sourceImage, bones, sourcePoints) {
    const owner = new Int16Array(W * H); owner.fill(-1);
    for (let y=0;y<H;y++) for (let x=0;x<W;x++) {
      const index=y*W+x, p=index*4;
      if (!sourceImage.data[p+3]) continue;
      let best=-1, bestDistance=Infinity;
      for (let i=0;i<bones.length;i++) {
        const bone=bones[i], a=sourcePoints[bone[1]], b=sourcePoints[bone[2]];
        const distance=pointSegmentDistance(x+.5,y+.5,a,b);
        if (distance<bestDistance) { bestDistance=distance; best=i; }
      }
      owner[index]=best;
    }
    return owner;
  }

  function inverseSimilarity(sourceA, sourceB, targetA, targetB) {
    const sax=Number(sourceA[0]), say=Number(sourceA[1]), sbx=Number(sourceB[0]), sby=Number(sourceB[1]);
    const tax=Number(targetA[0]), tay=Number(targetA[1]), tbx=Number(targetB[0]), tby=Number(targetB[1]);
    const svx=sbx-sax, svy=sby-say, tvx=tbx-tax, tvy=tby-tay;
    const sourceLength=Math.max(1e-6,Math.hypot(svx,svy));
    const targetLength=Math.max(1e-6,Math.hypot(tvx,tvy));
    const angle=Math.atan2(tvy,tvx)-Math.atan2(svy,svx);
    const rawScale=targetLength/sourceLength;
    const scale=Math.max(SCALE_MIN,Math.min(SCALE_MAX,1+(rawScale-1)*SCALE_DAMPING));
    const c=Math.cos(angle), s=Math.sin(angle);
    const m00=scale*c, m01=-scale*s, m10=scale*s, m11=scale*c;
    const determinant=m00*m11-m01*m10;
    if (Math.abs(determinant)<=1e-9) return {i00:1,i01:0,i10:0,i11:1,ox:sax-tax,oy:say-tay};
    const i00=m11/determinant, i01=-m01/determinant, i10=-m10/determinant, i11=m00/determinant;
    return {i00,i01,i10,i11,ox:sax-(i00*tax+i01*tay),oy:say-(i10*tax+i11*tay)};
  }

  function transferLayer(sourceImage, layer, sourceFrame, targetFrame) {
    const sourcePoints=sourceFrame.points||{}, targetPoints=targetFrame.points||{};
    const requested=BONE_SETS[layer]||BONE_SETS.paint_over;
    const bones=requested.filter(bone=>validBone(bone,sourcePoints,targetPoints));
    if (!bones.length) return cloneImageData(sourceImage);

    const owner=sourceOwnership(sourceImage,bones,sourcePoints);
    const transforms=bones.map(bone=>inverseSimilarity(
      sourcePoints[bone[1]],sourcePoints[bone[2]],targetPoints[bone[1]],targetPoints[bone[2]]
    ));
    const out=blankImageData();

    for (let y=0;y<H;y++) for (let x=0;x<W;x++) {
      const ordered=bones.map((bone,index)=>({
        index,
        distance:pointSegmentDistance(x+.5,y+.5,targetPoints[bone[1]],targetPoints[bone[2]])
      })).sort((a,b)=>a.distance-b.distance);

      for (const candidate of ordered) {
        const t=transforms[candidate.index];
        const sx=t.i00*(x+.5)+t.i01*(y+.5)+t.ox;
        const sy=t.i10*(x+.5)+t.i11*(y+.5)+t.oy;
        const ix=Math.round(sx-.5), iy=Math.round(sy-.5);
        if (ix<0||ix>=W||iy<0||iy>=H) continue;
        const sourceIndex=iy*W+ix;
        if (owner[sourceIndex]!==candidate.index) continue;
        const sp=sourceIndex*4;
        if (!sourceImage.data[sp+3]) continue;
        const dp=(y*W+x)*4;
        out.data[dp]=sourceImage.data[sp];
        out.data[dp+1]=sourceImage.data[sp+1];
        out.data[dp+2]=sourceImage.data[sp+2];
        out.data[dp+3]=sourceImage.data[sp+3];
        break;
      }
    }
    return fillPinholes(out);
  }

  function fillPinholes(image) {
    const source=new Uint8ClampedArray(image.data), out=image.data;
    const neighbors=[[-1,0],[1,0],[0,-1],[0,1]];
    for (let y=1;y<H-1;y++) for (let x=1;x<W-1;x++) {
      const i=(y*W+x)*4;
      if (source[i+3]!==0) continue;
      const samples=[];
      for (const [dx,dy] of neighbors) {
        const ni=((y+dy)*W+(x+dx))*4;
        if (source[ni+3]>=160) samples.push(ni);
      }
      if (samples.length<3) continue;
      for (let c=0;c<4;c++) out[i+c]=Math.round(samples.reduce((sum,ni)=>sum+source[ni+c],0)/samples.length);
    }
    return image;
  }

  function transferLayers(sourceLayers, sourceFrame, targetFrame, layerNames) {
    const result={};
    for (const name of layerNames) {
      if (name==="outline") continue;
      const source=sourceLayers[name];
      result[name]=source ? transferLayer(source,name,sourceFrame,targetFrame) : blankImageData();
    }
    return result;
  }

  function hexToRgba(hex) {
    const value=String(hex||"#342e2b").replace("#","");
    return [parseInt(value.slice(0,2),16),parseInt(value.slice(2,4),16),parseInt(value.slice(4,6),16),255];
  }

  function buildOutline(layers, color, layerNames) {
    const coverage=new Uint8Array(W*H);
    for (const name of layerNames) {
      if (name==="outline") continue;
      const image=layers[name]; if (!image) continue;
      for (let i=0;i<W*H;i++) if (image.data[i*4+3]>0) coverage[i]=1;
    }
    const out=blankImageData(), rgba=hexToRgba(color);
    const neighbors=[[-1,-1],[0,-1],[1,-1],[-1,0],[1,0],[-1,1],[0,1],[1,1]];
    for (let y=0;y<H;y++) for (let x=0;x<W;x++) {
      const index=y*W+x; if (coverage[index]) continue;
      let adjacent=false;
      for (const [dx,dy] of neighbors) {
        const nx=x+dx, ny=y+dy;
        if (nx>=0&&nx<W&&ny>=0&&ny<H&&coverage[ny*W+nx]) {adjacent=true;break;}
      }
      if (!adjacent) continue;
      const p=index*4; out.data[p]=rgba[0];out.data[p+1]=rgba[1];out.data[p+2]=rgba[2];out.data[p+3]=rgba[3];
    }
    return out;
  }

  window.CH_POSE_TRANSFER={
    contract:"CH_CHARACTER_POSE_TRANSFER_V0",
    algorithmVersion:"segmented_bone_skinning_v1",
    scaleDamping:SCALE_DAMPING,
    scaleClamp:[SCALE_MIN,SCALE_MAX],
    validateLandmarks,
    cloneImageData,
    blankImageData,
    transferLayer,
    transferLayers,
    buildOutline
  };
})();
