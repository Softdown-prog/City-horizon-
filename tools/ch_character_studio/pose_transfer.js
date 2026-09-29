(() => {
  const W = 48, H = 64;

  const LAYER_ANCHORS = {
    silhouette: ["head","neck","chest","pelvis","shoulder_L","shoulder_R","elbow_L","elbow_R","hand_L","hand_R","hip_L","hip_R","knee_L","knee_R","ankle_L","ankle_R","foot_L","foot_R"],
    skin: ["head","neck","hand_L","hand_R"],
    hair: ["head","head_top","neck"],
    face: ["head","head_top","neck"],
    upper_clothing: ["neck","chest","pelvis","shoulder_L","shoulder_R","elbow_L","elbow_R","hand_L","hand_R"],
    lower_clothing: ["pelvis","hip_L","hip_R","knee_L","knee_R","ankle_L","ankle_R"],
    footwear: ["ankle_L","ankle_R","foot_L","foot_R"],
    accessories_back: ["head","neck","chest","pelvis","shoulder_L","shoulder_R","hand_L","hand_R","hip_L","hip_R","foot_L","foot_R"],
    accessories_front: ["head","neck","chest","pelvis","shoulder_L","shoulder_R","hand_L","hand_R","hip_L","hip_R","foot_L","foot_R"],
    paint_over: ["head","neck","chest","pelvis","shoulder_L","shoulder_R","elbow_L","elbow_R","hand_L","hand_R","hip_L","hip_R","knee_L","knee_R","ankle_L","ankle_R","foot_L","foot_R"]
  };

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

  function anchorsFor(layer, sourcePoints, targetPoints) {
    const requested = LAYER_ANCHORS[layer] || LAYER_ANCHORS.paint_over;
    return requested
      .filter(name => Array.isArray(sourcePoints[name]) && Array.isArray(targetPoints[name]))
      .map(name => ({
        name,
        sx: Number(sourcePoints[name][0]), sy: Number(sourcePoints[name][1]),
        tx: Number(targetPoints[name][0]), ty: Number(targetPoints[name][1])
      }));
  }

  function displacementAt(x, y, anchors) {
    if (!anchors.length) return [0, 0];
    const nearest = anchors
      .map(anchor => {
        const dx = x - anchor.sx, dy = y - anchor.sy;
        return {anchor, d2: dx * dx + dy * dy};
      })
      .sort((a, b) => a.d2 - b.d2)
      .slice(0, Math.min(4, anchors.length));

    let sum = 0, dx = 0, dy = 0;
    for (const item of nearest) {
      const weight = 1 / (item.d2 + 3.0);
      sum += weight;
      dx += (item.anchor.tx - item.anchor.sx) * weight;
      dy += (item.anchor.ty - item.anchor.sy) * weight;
    }
    return sum ? [dx / sum, dy / sum] : [0, 0];
  }

  function alphaOver(dst, di, src, si) {
    const sa = src[si + 3] / 255;
    if (sa <= 0) return;
    const da = dst[di + 3] / 255;
    const oa = sa + da * (1 - sa);
    if (oa <= 0) return;
    for (let channel = 0; channel < 3; channel++) {
      const sv = src[si + channel] / 255;
      const dv = dst[di + channel] / 255;
      dst[di + channel] = Math.round(((sv * sa) + (dv * da * (1 - sa))) / oa * 255);
    }
    dst[di + 3] = Math.round(oa * 255);
  }

  function fillPinholes(image) {
    const source = new Uint8ClampedArray(image.data);
    const out = image.data;
    const neighbors = [[-1,0],[1,0],[0,-1],[0,1]];
    for (let y = 1; y < H - 1; y++) {
      for (let x = 1; x < W - 1; x++) {
        const i = (y * W + x) * 4;
        if (source[i + 3] !== 0) continue;
        const samples = [];
        for (const [dx, dy] of neighbors) {
          const ni = ((y + dy) * W + (x + dx)) * 4;
          if (source[ni + 3] >= 160) samples.push(ni);
        }
        if (samples.length < 3) continue;
        for (let c = 0; c < 4; c++) {
          out[i + c] = Math.round(samples.reduce((sum, ni) => sum + source[ni + c], 0) / samples.length);
        }
      }
    }
    return image;
  }

  function transferLayer(sourceImage, layer, sourceFrame, targetFrame) {
    const out = blankImageData();
    const anchors = anchorsFor(layer, sourceFrame.points || {}, targetFrame.points || {});
    if (!anchors.length) return cloneImageData(sourceImage);

    const src = sourceImage.data;
    const dst = out.data;
    for (let y = 0; y < H; y++) {
      for (let x = 0; x < W; x++) {
        const si = (y * W + x) * 4;
        if (src[si + 3] === 0) continue;
        const [dx, dy] = displacementAt(x, y, anchors);
        const tx = Math.round(x + dx), ty = Math.round(y + dy);
        if (tx < 0 || tx >= W || ty < 0 || ty >= H) continue;
        alphaOver(dst, (ty * W + tx) * 4, src, si);
      }
    }
    return fillPinholes(out);
  }

  function transferLayers(sourceLayers, sourceFrame, targetFrame, layerNames) {
    const result = {};
    for (const name of layerNames) {
      if (name === "outline") continue;
      const source = sourceLayers[name];
      result[name] = source
        ? transferLayer(source, name, sourceFrame, targetFrame)
        : blankImageData();
    }
    return result;
  }

  function hexToRgba(hex) {
    const value = String(hex || "#342e2b").replace("#", "");
    return [
      parseInt(value.slice(0, 2), 16),
      parseInt(value.slice(2, 4), 16),
      parseInt(value.slice(4, 6), 16),
      255
    ];
  }

  function buildOutline(layers, color, layerNames) {
    const coverage = new Uint8Array(W * H);
    for (const name of layerNames) {
      if (name === "outline") continue;
      const image = layers[name];
      if (!image) continue;
      for (let i = 0; i < W * H; i++) {
        if (image.data[i * 4 + 3] > 0) coverage[i] = 1;
      }
    }

    const out = blankImageData();
    const rgba = hexToRgba(color);
    const neighbors = [[-1,-1],[0,-1],[1,-1],[-1,0],[1,0],[-1,1],[0,1],[1,1]];
    for (let y = 0; y < H; y++) {
      for (let x = 0; x < W; x++) {
        const index = y * W + x;
        if (coverage[index]) continue;
        let adjacent = false;
        for (const [dx, dy] of neighbors) {
          const nx = x + dx, ny = y + dy;
          if (nx < 0 || nx >= W || ny < 0 || ny >= H) continue;
          if (coverage[ny * W + nx]) { adjacent = true; break; }
        }
        if (!adjacent) continue;
        const p = index * 4;
        out.data[p] = rgba[0]; out.data[p + 1] = rgba[1];
        out.data[p + 2] = rgba[2]; out.data[p + 3] = rgba[3];
      }
    }
    return out;
  }

  window.CH_POSE_TRANSFER = {
    contract: "CH_CHARACTER_POSE_TRANSFER_V0",
    validateLandmarks,
    cloneImageData,
    blankImageData,
    transferLayer,
    transferLayers,
    buildOutline
  };
})();
