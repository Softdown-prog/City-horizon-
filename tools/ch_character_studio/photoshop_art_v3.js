(() => {
  const API = window.CH_STUDIO_API;
  if (!API) {
    console.error("CH Photoshop Art V3 requires CH_STUDIO_API");
    return;
  }

  const W = API.width || 48;
  const H = API.height || 64;
  const view = document.getElementById("view");
  const parent = view?.parentElement;
  const right = document.querySelector("aside.right");
  if (!view || !parent || !right) return;

  const PRESETS = {
    pixel_1: {label:"Pixel 1", size:1, shape:"square", spacing:100, opacity:100, flow:100},
    pixel_2: {label:"Pixel 2", size:2, shape:"square", spacing:75, opacity:100, flow:100},
    hard_round: {label:"Hard Round", size:3, shape:"disk", spacing:35, opacity:100, flow:100},
    marker: {label:"Marker", size:4, shape:"square", spacing:25, opacity:85, flow:55},
    dither: {label:"Dither", size:4, shape:"dither", spacing:25, opacity:100, flow:100},
    airbrush: {label:"Airbrush", size:6, shape:"airbrush", spacing:15, opacity:65, flow:18}
  };

  const overlay = document.createElement("canvas");
  overlay.id = "photoshopArtV3View";
  overlay.width = W;
  overlay.height = H;
  Object.assign(overlay.style, {
    position:"absolute", inset:"0", width:"480px", height:"640px",
    imageRendering:"pixelated", pointerEvents:"none", cursor:"crosshair", zIndex:"7"
  });
  parent.appendChild(overlay);
  overlay.getContext("2d").imageSmoothingEnabled = false;

  const stage2Panel = [...right.querySelectorAll(".panel")].find(p => p.textContent.includes("Photoshop · Etapa 2"));
  const stage1Panel = [...right.querySelectorAll(".panel")].find(p => p.textContent.includes("Photoshop · Etapa 1"));
  const panel = document.createElement("div");
  panel.className = "panel";
  panel.innerHTML = `
    <h3>Photoshop · Etapa 3</h3>
    <div class="stack">
      <label>Brush preset <select id="ps3Preset"></select></label>
      <div class="row"><button id="ps3Brush">Pincel artístico</button><button id="ps3Stop">Encerrar pincel</button></div>
      <label>Tamanho <span id="ps3SizeLabel">1</span> px <input id="ps3Size" type="range" min="1" max="12" value="1"></label>
      <label>Spacing <span id="ps3SpacingLabel">25</span>% <input id="ps3Spacing" type="range" min="5" max="200" value="25"></label>
      <label>Opacity <span id="ps3OpacityLabel">100</span>% <input id="ps3Opacity" type="range" min="1" max="100" value="100"></label>
      <label>Flow <span id="ps3FlowLabel">100</span>% <input id="ps3Flow" type="range" min="1" max="100" value="100"></label>
      <label>Simetria <select id="ps3Symmetry"><option value="off">Desligada</option><option value="vertical">Vertical</option><option value="horizontal">Horizontal</option><option value="quad">Vertical + horizontal</option></select></label>
    </div>

    <h3 style="margin-top:14px">Gradiente</h3>
    <div class="stack">
      <div class="row"><label>Cor A <input id="ps3GradA" type="color" value="#ffffff"></label><label>Cor B <input id="ps3GradB" type="color" value="#000000"></label></div>
      <label>Tipo <select id="ps3GradientType"><option value="linear">Linear</option><option value="radial">Radial</option></select></label>
      <label>Ângulo <input id="ps3GradientAngle" type="number" min="-360" max="360" step="15" value="90"></label>
      <label>Opacidade <span id="ps3GradientOpacityLabel">100</span>% <input id="ps3GradientOpacity" type="range" min="1" max="100" value="100"></label>
      <button id="ps3ApplyGradient">Aplicar gradiente na alfa existente</button>
    </div>

    <h3 style="margin-top:14px">Levels</h3>
    <div class="row"><label class="grow">Black <input id="ps3LevelBlack" type="number" min="0" max="254" value="0"></label><label class="grow">White <input id="ps3LevelWhite" type="number" min="1" max="255" value="255"></label></div>
    <div class="row"><label class="grow">Gamma <input id="ps3LevelGamma" type="number" min="0.1" max="9.99" step="0.05" value="1"></label></div>
    <div class="row"><label class="grow">Out Black <input id="ps3OutBlack" type="number" min="0" max="254" value="0"></label><label class="grow">Out White <input id="ps3OutWhite" type="number" min="1" max="255" value="255"></label></div>
    <button id="ps3ApplyLevels" style="width:100%;margin-top:6px">Aplicar Levels</button>

    <h3 style="margin-top:14px">Curves</h3>
    <div class="hint">Saída dos pontos de entrada 0 / 64 / 128 / 192 / 255.</div>
    <div class="row" style="margin-top:6px">
      <input id="ps3Curve0" type="number" min="0" max="255" value="0" style="width:54px">
      <input id="ps3Curve64" type="number" min="0" max="255" value="64" style="width:54px">
      <input id="ps3Curve128" type="number" min="0" max="255" value="128" style="width:54px">
      <input id="ps3Curve192" type="number" min="0" max="255" value="192" style="width:54px">
      <input id="ps3Curve255" type="number" min="0" max="255" value="255" style="width:54px">
    </div>
    <button id="ps3ApplyCurves" style="width:100%;margin-top:6px">Aplicar Curves</button>

    <h3 style="margin-top:14px">Hue / Saturation</h3>
    <div class="stack">
      <label>Hue <span id="ps3HueLabel">0</span>° <input id="ps3Hue" type="range" min="-180" max="180" value="0"></label>
      <label>Saturation <span id="ps3SatLabel">0</span>% <input id="ps3Sat" type="range" min="-100" max="100" value="0"></label>
      <label>Lightness <span id="ps3LightLabel">0</span>% <input id="ps3Light" type="range" min="-100" max="100" value="0"></label>
      <button id="ps3ApplyHsl">Aplicar Hue/Saturation</button>
    </div>
    <div id="ps3Status" class="status photoshop-note" style="margin-top:8px">Etapa 3 pronta.</div>
    <div class="hint">Estas ferramentas editam pixels de arte da camada semântica ativa. Motion, landmarks, ground anchor e câmera oficial permanecem bloqueados.</div>
  `;
  (stage2Panel || stage1Panel)?.after(panel);

  const $ = id => document.getElementById(id);
  const presetSelect = $("ps3Preset");
  const sizeInput = $("ps3Size");
  const spacingInput = $("ps3Spacing");
  const opacityInput = $("ps3Opacity");
  const flowInput = $("ps3Flow");
  const symmetrySelect = $("ps3Symmetry");
  const statusEl = $("ps3Status");

  for (const [id, preset] of Object.entries(PRESETS)) {
    const option = document.createElement("option");
    option.value = id;
    option.textContent = preset.label;
    presetSelect.appendChild(option);
  }

  let brushActive = false;
  let drawing = false;
  let lastPoint = null;
  let strokeOriginal = null;
  let strokeWorking = null;
  let strokeCoverage = null;
  let strokeCanvas = null;

  function status(message) {
    statusEl.textContent = message;
    API.setStatus(message);
  }

  function selectedSemanticCanvas() {
    const stack = window.CH_PHOTOSHOP_LAYER_STACK;
    const state = stack?.getState?.();
    if (state?.selectedId && !String(state.selectedId).startsWith("core:")) {
      status("Etapa 3: selecione uma camada semântica (skin, hair, roupa etc.) antes de pintar ou ajustar.");
      return null;
    }
    return API.getActiveLayerCanvas();
  }

  function pointFromEvent(ev) {
    const r = overlay.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(W - 1, (ev.clientX - r.left) * W / r.width)),
      y: Math.max(0, Math.min(H - 1, (ev.clientY - r.top) * H / r.height))
    };
  }

  function parseHex(hex) {
    const h = String(hex).replace("#", "");
    return [parseInt(h.slice(0,2),16), parseInt(h.slice(2,4),16), parseInt(h.slice(4,6),16)];
  }

  function updateLabels() {
    $("ps3SizeLabel").textContent = sizeInput.value;
    $("ps3SpacingLabel").textContent = spacingInput.value;
    $("ps3OpacityLabel").textContent = opacityInput.value;
    $("ps3FlowLabel").textContent = flowInput.value;
    $("ps3GradientOpacityLabel").textContent = $("ps3GradientOpacity").value;
    $("ps3HueLabel").textContent = $("ps3Hue").value;
    $("ps3SatLabel").textContent = $("ps3Sat").value;
    $("ps3LightLabel").textContent = $("ps3Light").value;
  }

  function usePreset(id) {
    const p = PRESETS[id] || PRESETS.pixel_1;
    sizeInput.value = p.size;
    spacingInput.value = p.spacing;
    opacityInput.value = p.opacity;
    flowInput.value = p.flow;
    updateLabels();
    status(`Brush preset: ${p.label}.`);
  }

  function stopStage1Tools() {
    for (const id of ["psRectSelect","psLasso","psMove","psEyedropper","psBucket"]) {
      const button = document.getElementById(id);
      if (button?.classList.contains("active")) button.click();
    }
  }

  function setBrushActive(active) {
    brushActive = Boolean(active);
    drawing = false;
    lastPoint = null;
    overlay.style.pointerEvents = brushActive ? "auto" : "none";
    $("ps3Brush").classList.toggle("active", brushActive);
    if (brushActive) {
      stopStage1Tools();
      API.setTool("external");
      status("Pincel artístico Etapa 3 ativo.");
    } else {
      API.setTool("brush");
      status("Pincel artístico encerrado.");
    }
  }

  function symmetryPoints(point) {
    const mode = symmetrySelect.value;
    const points = [[point.x, point.y]];
    if (mode === "vertical" || mode === "quad") points.push([W - 1 - point.x, point.y]);
    if (mode === "horizontal" || mode === "quad") points.push([point.x, H - 1 - point.y]);
    if (mode === "quad") points.push([W - 1 - point.x, H - 1 - point.y]);
    const unique = new Map();
    for (const [x,y] of points) unique.set(`${Math.round(x*1000)}:${Math.round(y*1000)}`, {x,y});
    return [...unique.values()];
  }

  function stampWeight(shape, dx, dy, size, px, py) {
    const half = Math.max(0.5, size / 2);
    if (shape === "square") return Math.abs(dx) <= half && Math.abs(dy) <= half ? 1 : 0;
    const r = Math.sqrt(dx*dx + dy*dy) / half;
    if (r > 1) return 0;
    if (shape === "dither") return ((px + py) & 1) === 0 ? 1 : 0;
    if (shape === "airbrush") return Math.max(0, 1 - r);
    return 1;
  }

  function blendStrokePixel(index, weight) {
    if (weight <= 0 || !strokeOriginal || !strokeWorking || !strokeCoverage) return;
    const opacity = Number(opacityInput.value) / 100;
    const flow = Number(flowInput.value) / 100;
    const previous = strokeCoverage[index];
    const accumulated = 1 - (1 - previous) * (1 - flow * weight);
    const coverage = Math.min(opacity, accumulated);
    if (coverage <= previous + 1e-6) return;
    strokeCoverage[index] = coverage;

    const p = index * 4;
    const color = parseHex(API.getColor());
    const oa = strokeOriginal.data[p+3] / 255;
    const targetA = coverage + oa * (1 - coverage);
    const baseContribution = oa * (1 - coverage);
    const denom = Math.max(1e-6, targetA);
    strokeWorking.data[p] = Math.round((color[0] * coverage + strokeOriginal.data[p] * baseContribution) / denom);
    strokeWorking.data[p+1] = Math.round((color[1] * coverage + strokeOriginal.data[p+1] * baseContribution) / denom);
    strokeWorking.data[p+2] = Math.round((color[2] * coverage + strokeOriginal.data[p+2] * baseContribution) / denom);
    strokeWorking.data[p+3] = Math.round(targetA * 255);
  }

  function stamp(point) {
    const preset = PRESETS[presetSelect.value] || PRESETS.pixel_1;
    const size = Math.max(1, Number(sizeInput.value));
    for (const mirrored of symmetryPoints(point)) {
      const minX = Math.max(0, Math.floor(mirrored.x - size));
      const maxX = Math.min(W - 1, Math.ceil(mirrored.x + size));
      const minY = Math.max(0, Math.floor(mirrored.y - size));
      const maxY = Math.min(H - 1, Math.ceil(mirrored.y + size));
      for (let y=minY; y<=maxY; y++) {
        for (let x=minX; x<=maxX; x++) {
          const weight = stampWeight(preset.shape, (x + .5) - mirrored.x, (y + .5) - mirrored.y, size, x, y);
          if (weight > 0) blendStrokePixel(y * W + x, weight);
        }
      }
    }
    strokeCanvas.getContext("2d").putImageData(strokeWorking,0,0);
    API.redraw();
  }

  function paintSegment(a, b) {
    const dx = b.x - a.x, dy = b.y - a.y;
    const distance = Math.sqrt(dx*dx + dy*dy);
    const spacingPx = Math.max(.25, Number(sizeInput.value) * Number(spacingInput.value) / 100);
    const steps = Math.max(1, Math.ceil(distance / spacingPx));
    for (let i=1; i<=steps; i++) {
      const t = i / steps;
      stamp({x:a.x + dx*t, y:a.y + dy*t});
    }
  }

  overlay.addEventListener("pointerdown", ev => {
    if (!brushActive) return;
    const canvas = selectedSemanticCanvas();
    if (!canvas) return;
    API.checkpoint("art_brush_v3");
    strokeCanvas = canvas;
    const c = canvas.getContext("2d");
    strokeOriginal = c.getImageData(0,0,W,H);
    strokeWorking = new ImageData(new Uint8ClampedArray(strokeOriginal.data), W, H);
    strokeCoverage = new Float32Array(W * H);
    drawing = true;
    lastPoint = pointFromEvent(ev);
    overlay.setPointerCapture(ev.pointerId);
    stamp(lastPoint);
  });
  overlay.addEventListener("pointermove", ev => {
    if (!drawing || !lastPoint) return;
    const point = pointFromEvent(ev);
    paintSegment(lastPoint, point);
    lastPoint = point;
  });
  function endStroke() {
    if (!drawing) return;
    drawing = false;
    lastPoint = null;
    strokeOriginal = strokeWorking = strokeCoverage = strokeCanvas = null;
    API.saveFrame();
    API.redraw();
  }
  overlay.addEventListener("pointerup", endStroke);
  overlay.addEventListener("pointercancel", endStroke);

  function eachOpaquePixel(reason, transform) {
    const canvas = selectedSemanticCanvas();
    if (!canvas) return false;
    API.checkpoint(reason);
    const c = canvas.getContext("2d");
    const image = c.getImageData(0,0,W,H);
    for (let i=0; i<W*H; i++) {
      const p = i*4;
      if (!image.data[p+3]) continue;
      const rgb = transform(image.data[p], image.data[p+1], image.data[p+2], i);
      image.data[p] = Math.max(0, Math.min(255, Math.round(rgb[0])));
      image.data[p+1] = Math.max(0, Math.min(255, Math.round(rgb[1])));
      image.data[p+2] = Math.max(0, Math.min(255, Math.round(rgb[2])));
    }
    c.putImageData(image,0,0);
    API.saveFrame();
    API.redraw();
    return true;
  }

  function applyGradient() {
    const a = parseHex($("ps3GradA").value), b = parseHex($("ps3GradB").value);
    const type = $("ps3GradientType").value;
    const opacity = Number($("ps3GradientOpacity").value) / 100;
    const angle = Number($("ps3GradientAngle").value) * Math.PI / 180;
    const cx = (W-1)/2, cy = (H-1)/2;
    const dirX = Math.cos(angle), dirY = Math.sin(angle);
    const halfSpan = Math.abs(dirX)*W/2 + Math.abs(dirY)*H/2 || 1;
    if (!eachOpaquePixel("gradient_v3", (r,g,bb,index) => {
      const x=index%W, y=Math.floor(index/W);
      let t;
      if (type === "radial") {
        const maxR = Math.sqrt(cx*cx + cy*cy) || 1;
        t = Math.min(1, Math.sqrt((x-cx)**2 + (y-cy)**2) / maxR);
      } else {
        t = Math.max(0, Math.min(1, .5 + ((x-cx)*dirX + (y-cy)*dirY) / (2*halfSpan)));
      }
      const gr = a[0] + (b[0]-a[0])*t;
      const gg = a[1] + (b[1]-a[1])*t;
      const gb = a[2] + (b[2]-a[2])*t;
      return [r + (gr-r)*opacity, g + (gg-g)*opacity, bb + (gb-bb)*opacity];
    })) return;
    status(`${type === "radial" ? "Gradiente radial" : "Gradiente linear"} aplicado preservando alpha.`);
  }

  function applyLevels() {
    const black = Math.max(0, Math.min(254, Number($("ps3LevelBlack").value)));
    const white = Math.max(black+1, Math.min(255, Number($("ps3LevelWhite").value)));
    const gamma = Math.max(.1, Math.min(9.99, Number($("ps3LevelGamma").value)||1));
    const outBlack = Math.max(0, Math.min(254, Number($("ps3OutBlack").value)));
    const outWhite = Math.max(outBlack+1, Math.min(255, Number($("ps3OutWhite").value)));
    const map = value => {
      const normalized = Math.max(0, Math.min(1, (value-black)/(white-black)));
      const corrected = Math.pow(normalized, 1/gamma);
      return outBlack + corrected*(outWhite-outBlack);
    };
    if (!eachOpaquePixel("levels_v3", (r,g,b) => [map(r),map(g),map(b)])) return;
    status(`Levels aplicados: ${black}/${gamma.toFixed(2)}/${white} → ${outBlack}/${outWhite}.`);
  }

  function curveMap(value, outputs) {
    const xs = [0,64,128,192,255];
    let segment = 0;
    while (segment < xs.length-2 && value > xs[segment+1]) segment++;
    const t = (value-xs[segment]) / Math.max(1, xs[segment+1]-xs[segment]);
    return outputs[segment] + (outputs[segment+1]-outputs[segment])*t;
  }

  function applyCurves() {
    const outputs = ["0","64","128","192","255"].map(v => Math.max(0,Math.min(255,Number($(`ps3Curve${v}`).value))));
    if (!eachOpaquePixel("curves_v3", (r,g,b) => [curveMap(r,outputs),curveMap(g,outputs),curveMap(b,outputs)])) return;
    status(`Curves aplicada: ${outputs.join(" / ")}.`);
  }

  function rgbToHsl(r,g,b) {
    r/=255; g/=255; b/=255;
    const max=Math.max(r,g,b), min=Math.min(r,g,b); let h=0,s=0; const l=(max+min)/2;
    if(max!==min){const d=max-min;s=l>.5?d/(2-max-min):d/(max+min);switch(max){case r:h=(g-b)/d+(g<b?6:0);break;case g:h=(b-r)/d+2;break;default:h=(r-g)/d+4;}h/=6;}
    return [h,s,l];
  }
  function hue2rgb(p,q,t){if(t<0)t+=1;if(t>1)t-=1;if(t<1/6)return p+(q-p)*6*t;if(t<1/2)return q;if(t<2/3)return p+(q-p)*(2/3-t)*6;return p;}
  function hslToRgb(h,s,l){let r,g,b;if(s===0)r=g=b=l;else{const q=l<.5?l*(1+s):l+s-l*s,p=2*l-q;r=hue2rgb(p,q,h+1/3);g=hue2rgb(p,q,h);b=hue2rgb(p,q,h-1/3);}return[r*255,g*255,b*255];}

  function applyHsl() {
    const hue = Number($("ps3Hue").value)/360;
    const sat = Number($("ps3Sat").value)/100;
    const light = Number($("ps3Light").value)/100;
    if (!eachOpaquePixel("hue_saturation_v3", (r,g,b) => {
      let [h,s,l]=rgbToHsl(r,g,b);
      h=(h+hue)%1;if(h<0)h+=1;
      s=sat>=0?s+(1-s)*sat:s*(1+sat);
      l=light>=0?l+(1-l)*light:l*(1+light);
      return hslToRgb(h,Math.max(0,Math.min(1,s)),Math.max(0,Math.min(1,l)));
    })) return;
    status(`Hue/Saturation aplicado: H ${Math.round(hue*360)}° · S ${Math.round(sat*100)}% · L ${Math.round(light*100)}%.`);
  }

  presetSelect.addEventListener("change",()=>usePreset(presetSelect.value));
  $("ps3Brush").addEventListener("click",()=>setBrushActive(true));
  $("ps3Stop").addEventListener("click",()=>setBrushActive(false));
  for (const element of [sizeInput,spacingInput,opacityInput,flowInput,$("ps3GradientOpacity"),$("ps3Hue"),$("ps3Sat"),$("ps3Light")]) element.addEventListener("input",updateLabels);
  $("ps3ApplyGradient").addEventListener("click",applyGradient);
  $("ps3ApplyLevels").addEventListener("click",applyLevels);
  $("ps3ApplyCurves").addEventListener("click",applyCurves);
  $("ps3ApplyHsl").addEventListener("click",applyHsl);

  for (const id of ["brushBtn","eraserBtn","shapeBtn","psRectSelect","psLasso","psMove","psEyedropper","psBucket","ps2MaskEdit"]) {
    document.getElementById(id)?.addEventListener("click",()=>{if(brushActive)setBrushActive(false);});
  }
  window.addEventListener("ch-studio-frame-changed",()=>{if(brushActive)setBrushActive(false);});

  usePreset("pixel_1");
  updateLabels();
  status("Photoshop Etapa 3 pronta: brushes, spacing/opacity/flow, simetria, gradiente, Levels, Curves e Hue/Saturation.");

  window.CH_PHOTOSHOP_ART_V3 = {
    contract:"CH_CHARACTER_ART_TOOLS_V0",
    presets:{...PRESETS},
    setBrushActive,
    applyGradient,
    applyLevels,
    applyCurves,
    applyHsl
  };
})();
