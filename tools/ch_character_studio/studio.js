(() => {
  const W = 48, H = 64;
  const LAYERS = [
    "silhouette","skin","hair","face","upper_clothing","lower_clothing",
    "footwear","accessories_back","accessories_front","paint_over","outline"
  ];
  const ANIMATION_FRAMES = ["idle","walk_00","walk_01","walk_02","walk_03","walk_04","walk_05","walk_06","walk_07"];
  const PALETTE = ["#f6c29e","#d43b2f","#f2d744","#2b71c9","#26313a","#ffffff","#1f2937","#8b5cf6","#ef4444","#22c55e"];
  const SHAPES = window.CH_CHARACTER_SHAPES || [];
  const TEMPLATES = window.CH_CHARACTER_TEMPLATES || [];
  const POSE_TRANSFER = window.CH_POSE_TRANSFER || null;

  const view = document.getElementById("view");
  const vctx = view.getContext("2d");
  vctx.imageSmoothingEnabled = false;

  const base = document.createElement("canvas");
  base.width = W; base.height = H;
  const bctx = base.getContext("2d");
  const buffers = new Map();
  const visibility = new Map();
  for (const name of LAYERS) {
    const c = document.createElement("canvas");
    c.width = W; c.height = H;
    buffers.set(name, c);
    visibility.set(name, true);
  }

  const directionSelect = document.getElementById("direction");
  const frameSelect = document.getElementById("frame");
  const frameStore = new Map();
  let loadedFrameKey = `${directionSelect.value}:${frameSelect.value}`;
  let activeLayer = "paint_over";
  let tool = "brush";
  let drawing = false;
  let lastPoint = null;
  let landmarksPackage = null;
  let referenceArt = null;

  const color = document.getElementById("color");
  const brushSize = document.getElementById("brushSize");
  const sizeLabel = document.getElementById("sizeLabel");
  const status = document.getElementById("status");
  const layersEl = document.getElementById("layers");
  const swatchesEl = document.getElementById("swatches");
  const shapeSelect = document.getElementById("shapeSelect");
  const shapeScale = document.getElementById("shapeScale");
  const shapeScaleLabel = document.getElementById("shapeScaleLabel");
  const templateSelect = document.getElementById("templateSelect");
  const outlineColor = document.getElementById("outlineColor");
  const landmarksFile = document.getElementById("landmarksFile");
  const referenceStatus = document.getElementById("referenceStatus");
  const applyReferenceBtn = document.getElementById("applyReference");
  const propagateDirectionBtn = document.getElementById("propagateDirection");

  function setStatus(msg) { status.textContent = msg; }
  function canvasFor(name) { return buffers.get(name); }
  function currentDirection() { return directionSelect.value; }
  function currentFrameKey() { return `${directionSelect.value}:${frameSelect.value}`; }
  function keyDirection(key) { return String(key).split(":", 1)[0]; }

  function redraw() {
    vctx.clearRect(0, 0, W, H);
    vctx.drawImage(base, 0, 0);
    for (const name of LAYERS) {
      if (visibility.get(name)) vctx.drawImage(canvasFor(name), 0, 0);
    }
  }

  function snapshotCanvas(canvas) {
    return canvas.getContext("2d").getImageData(0, 0, W, H);
  }

  function cloneImageData(image) {
    if (POSE_TRANSFER) return POSE_TRANSFER.cloneImageData(image);
    return new ImageData(new Uint8ClampedArray(image.data), image.width, image.height);
  }

  function blankImageData() {
    return POSE_TRANSFER ? POSE_TRANSFER.blankImageData() : new ImageData(W, H);
  }

  function snapshotLayers() {
    const layers = {};
    for (const name of LAYERS) layers[name] = snapshotCanvas(canvasFor(name));
    return layers;
  }

  function cloneLayers(layers) {
    const cloned = {};
    for (const name of LAYERS) cloned[name] = layers[name] ? cloneImageData(layers[name]) : blankImageData();
    return cloned;
  }

  function saveLoadedFrame() {
    frameStore.set(loadedFrameKey, {
      base: snapshotCanvas(base),
      layers: snapshotLayers()
    });
  }

  function clearWorkingCanvases() {
    bctx.clearRect(0, 0, W, H);
    for (const name of LAYERS) canvasFor(name).getContext("2d").clearRect(0, 0, W, H);
  }

  function loadFrameState(key) {
    clearWorkingCanvases();
    const state = frameStore.get(key);
    if (state) {
      bctx.putImageData(state.base, 0, 0);
      for (const name of LAYERS) {
        if (state.layers[name]) canvasFor(name).getContext("2d").putImageData(state.layers[name], 0, 0);
      }
    }
    loadedFrameKey = key;
    redraw();
    setStatus(`Frame ativo: ${key.replace(":", " / ")}${state ? " · arte restaurada" : " · novo"}.`);
  }

  function switchFrame() {
    if (drawing) { drawing = false; lastPoint = null; }
    saveLoadedFrame();
    loadFrameState(currentFrameKey());
  }

  function buildLayerList() {
    layersEl.innerHTML = "";
    [...LAYERS].reverse().forEach(name => {
      const row = document.createElement("div");
      row.className = `layer ${name === activeLayer ? "selected" : ""}`;
      const check = document.createElement("input");
      check.type = "checkbox";
      check.checked = visibility.get(name);
      check.addEventListener("click", e => e.stopPropagation());
      check.addEventListener("change", () => { visibility.set(name, check.checked); redraw(); });
      const label = document.createElement("span");
      label.textContent = name.replaceAll("_", " ");
      const meta = document.createElement("small");
      meta.textContent = name === activeLayer ? "ativa" : "";
      row.append(check, label, meta);
      row.addEventListener("click", () => {
        activeLayer = name;
        buildLayerList();
        setStatus(`Camada ativa: ${name}`);
      });
      layersEl.appendChild(row);
    });
  }

  function buildSwatches() {
    PALETTE.forEach(hex => {
      const el = document.createElement("button");
      el.className = "swatch";
      el.style.background = hex;
      el.title = hex;
      el.addEventListener("click", () => {
        color.value = hex;
        [...swatchesEl.children].forEach(c => c.classList.remove("active"));
        el.classList.add("active");
      });
      swatchesEl.appendChild(el);
    });
  }

  function buildShapeSelect() {
    shapeSelect.innerHTML = "";
    const groups = new Map();
    for (const shape of SHAPES) {
      if (!groups.has(shape.group)) groups.set(shape.group, []);
      groups.get(shape.group).push(shape);
    }
    for (const [groupName, shapes] of groups) {
      const group = document.createElement("optgroup");
      group.label = groupName;
      for (const shape of shapes) {
        const option = document.createElement("option");
        option.value = shape.id;
        option.textContent = shape.label;
        group.appendChild(option);
      }
      shapeSelect.appendChild(group);
    }
  }

  function buildTemplateSelect() {
    templateSelect.innerHTML = "";
    for (const template of TEMPLATES) {
      const option = document.createElement("option");
      option.value = template.id;
      option.textContent = template.label;
      templateSelect.appendChild(option);
    }
  }

  function pointFromEvent(ev) {
    const r = view.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(W - 1, Math.floor((ev.clientX - r.left) * W / r.width))),
      y: Math.max(0, Math.min(H - 1, Math.floor((ev.clientY - r.top) * H / r.height)))
    };
  }

  function stampPixel(ctx, x, y, size, erase) {
    const half = Math.floor(size / 2);
    if (erase) ctx.clearRect(x - half, y - half, size, size);
    else {
      ctx.fillStyle = color.value;
      ctx.fillRect(x - half, y - half, size, size);
    }
  }

  function paintSegment(from, to) {
    const ctx = canvasFor(activeLayer).getContext("2d");
    const size = Number(brushSize.value);
    const erase = tool === "eraser";
    let x0 = from.x, y0 = from.y, x1 = to.x, y1 = to.y;
    const dx = Math.abs(x1 - x0), sx = x0 < x1 ? 1 : -1;
    const dy = -Math.abs(y1 - y0), sy = y0 < y1 ? 1 : -1;
    let err = dx + dy;
    while (true) {
      stampPixel(ctx, x0, y0, size, erase);
      if (x0 === x1 && y0 === y1) break;
      const e2 = 2 * err;
      if (e2 >= dy) { err += dy; x0 += sx; }
      if (e2 <= dx) { err += dx; y0 += sy; }
    }
  }

  function paint(ev) {
    if (!drawing || (tool !== "brush" && tool !== "eraser")) return;
    const point = pointFromEvent(ev);
    paintSegment(lastPoint || point, point);
    lastPoint = point;
    redraw();
  }

  function selectedShape() {
    return SHAPES.find(shape => shape.id === shapeSelect.value) || null;
  }

  function drawShape(shape, x, y, fill, scale) {
    if (!shape || !buffers.has(shape.layer)) return false;
    visibility.set(shape.layer, true);
    const ctx = canvasFor(shape.layer).getContext("2d");
    ctx.save();
    ctx.imageSmoothingEnabled = false;
    shape.draw(ctx, x, y, fill, scale, currentDirection());
    ctx.restore();
    return true;
  }

  function stampSmartShape(ev) {
    const shape = selectedShape();
    if (!shape) {
      setStatus("Nenhuma forma inteligente disponível.");
      return;
    }
    const {x, y} = pointFromEvent(ev);
    if (!drawShape(shape, x, y, color.value, Number(shapeScale.value))) {
      setStatus(`Forma ${shape.label} pediu camada desconhecida: ${shape.layer}`);
      return;
    }
    activeLayer = shape.layer;
    buildLayerList();
    redraw();
    setStatus(`${shape.label} aplicado em ${activeLayer} · direção ${currentDirection()} · ${shapeScale.value}×`);
  }

  function clearArtLayers() {
    for (const name of LAYERS) canvasFor(name).getContext("2d").clearRect(0, 0, W, H);
  }

  function applyTemplate() {
    const template = TEMPLATES.find(item => item.id === templateSelect.value);
    if (!template) return;
    clearArtLayers();
    const palette = template.palette || {};
    let applied = 0;
    for (const placement of template.placements || []) {
      const shape = SHAPES.find(item => item.id === placement.shape);
      const fill = palette[placement.color] || placement.color || color.value;
      if (drawShape(shape, placement.x, placement.y, fill, placement.scale || 1)) applied += 1;
    }
    activeLayer = "paint_over";
    buildLayerList();
    redraw();
    setStatus(`${template.label} aplicado: ${applied} peças artísticas · pose e movimento preservados.`);
  }

  function fallbackOutline(layers) {
    const coverage = new Uint8Array(W * H);
    for (const name of LAYERS) {
      if (name === "outline") continue;
      const image = layers[name];
      if (!image) continue;
      for (let i = 0; i < W * H; i++) if (image.data[i * 4 + 3] > 0) coverage[i] = 1;
    }
    const out = blankImageData();
    const value = outlineColor.value.replace("#", "");
    const rgba = [parseInt(value.slice(0,2),16),parseInt(value.slice(2,4),16),parseInt(value.slice(4,6),16),255];
    const neighbors = [[-1,-1],[0,-1],[1,-1],[-1,0],[1,0],[-1,1],[0,1],[1,1]];
    for (let y = 0; y < H; y++) {
      for (let x = 0; x < W; x++) {
        const index = y * W + x;
        if (coverage[index]) continue;
        let adjacent = false;
        for (const [dx, dy] of neighbors) {
          const nx = x + dx, ny = y + dy;
          if (nx >= 0 && nx < W && ny >= 0 && ny < H && coverage[ny * W + nx]) { adjacent = true; break; }
        }
        if (!adjacent) continue;
        const p = index * 4;
        out.data[p] = rgba[0]; out.data[p+1] = rgba[1]; out.data[p+2] = rgba[2]; out.data[p+3] = 255;
      }
    }
    return out;
  }

  function outlineForLayers(layers) {
    return POSE_TRANSFER
      ? POSE_TRANSFER.buildOutline(layers, outlineColor.value, LAYERS)
      : fallbackOutline(layers);
  }

  function generateOutline() {
    const layers = snapshotLayers();
    const image = outlineForLayers(layers);
    canvasFor("outline").getContext("2d").putImageData(image, 0, 0);
    visibility.set("outline", true);
    activeLayer = "outline";
    buildLayerList();
    redraw();
    let count = 0;
    for (let i = 3; i < image.data.length; i += 4) if (image.data[i]) count += 1;
    setStatus(`Outline dilatado 1 px gerado: ${count} pixels · base CH Blender ignorada.`);
  }

  function clearOutline() {
    canvasFor("outline").getContext("2d").clearRect(0, 0, W, H);
    redraw();
    setStatus("Outline limpo.");
  }

  function setTool(next) {
    tool = next;
    for (const [id, name] of [["brushBtn","brush"],["eraserBtn","eraser"],["shapeBtn","shape"]]) {
      document.getElementById(id).classList.toggle("active", name === tool);
    }
    const labels = {brush:"Pincel", eraser:"Borracha", shape:"Forma inteligente"};
    setStatus(`${labels[tool]} ativo.`);
  }

  function landmarkFrame(key) {
    return landmarksPackage?.frames?.[key] || null;
  }

  function refreshReferenceUi() {
    const ready = Boolean(referenceArt && landmarksPackage && POSE_TRANSFER);
    applyReferenceBtn.disabled = !ready;
    propagateDirectionBtn.disabled = !ready;
    if (!referenceArt) {
      referenceStatus.textContent = landmarksPackage
        ? "Landmarks carregados. Marque um frame artístico como referência."
        : "Nenhuma referência marcada.";
      return;
    }
    referenceStatus.textContent = `Referência: ${referenceArt.key.replace(":", " / ")} · ${ready ? "pronta para propagação" : "aguardando landmarks"}.`;
  }

  function markReference() {
    if (!POSE_TRANSFER) {
      setStatus("Módulo CH_CHARACTER_POSE_TRANSFER_V0 não foi carregado.");
      return;
    }
    if (!landmarksPackage) {
      setStatus("Carregue landmarks.json do CH Blender antes de marcar a referência.");
      return;
    }
    const key = currentFrameKey();
    if (!landmarkFrame(key)) {
      setStatus(`Landmarks não contêm ${key}.`);
      return;
    }
    saveLoadedFrame();
    referenceArt = {key, layers: cloneLayers(frameStore.get(key).layers)};
    refreshReferenceUi();
    setStatus(`Frame ${key.replace(":", " / ")} congelado como referência artística.`);
  }

  function transferredLayersFor(targetKey) {
    if (!referenceArt || !landmarksPackage || !POSE_TRANSFER) throw new Error("referência/landmarks indisponíveis");
    if (keyDirection(referenceArt.key) !== keyDirection(targetKey)) {
      throw new Error("propagação automática só é permitida dentro da mesma direção");
    }
    const sourceFrame = landmarkFrame(referenceArt.key);
    const targetFrame = landmarkFrame(targetKey);
    if (!sourceFrame || !targetFrame) throw new Error(`landmarks ausentes para ${targetKey}`);
    const layers = targetKey === referenceArt.key
      ? cloneLayers(referenceArt.layers)
      : POSE_TRANSFER.transferLayers(referenceArt.layers, sourceFrame, targetFrame, LAYERS);
    layers.outline = outlineForLayers(layers);
    return layers;
  }

  function applyReferenceToCurrent() {
    const targetKey = currentFrameKey();
    try {
      const layers = transferredLayersFor(targetKey);
      for (const name of LAYERS) canvasFor(name).getContext("2d").putImageData(layers[name] || blankImageData(), 0, 0);
      saveLoadedFrame();
      redraw();
      setStatus(`Aparência de ${referenceArt.key.replace(":", " / ")} adaptada para ${targetKey.replace(":", " / ")} por landmarks.`);
    } catch (error) {
      setStatus(`Propagação recusada: ${error.message}`);
    }
  }

  function propagateReferenceDirection() {
    if (!referenceArt) return;
    const direction = keyDirection(referenceArt.key);
    saveLoadedFrame();
    let generated = 0;
    try {
      for (const frame of ANIMATION_FRAMES) {
        const targetKey = `${direction}:${frame}`;
        const existing = frameStore.get(targetKey);
        const layers = transferredLayersFor(targetKey);
        frameStore.set(targetKey, {
          base: existing?.base ? cloneImageData(existing.base) : blankImageData(),
          layers,
          generatedFrom: referenceArt.key
        });
        generated += 1;
      }
      if (currentDirection() === direction) loadFrameState(currentFrameKey());
      refreshReferenceUi();
      setStatus(`${generated} frames de ${direction} receberam a aparência da referência ${referenceArt.key.replace(":", " / ")} · outline recalculado.`);
    } catch (error) {
      setStatus(`Propagação recusada: ${error.message}`);
    }
  }

  view.addEventListener("pointerdown", ev => {
    view.setPointerCapture(ev.pointerId);
    if (tool === "shape") {
      stampSmartShape(ev);
      return;
    }
    drawing = true;
    lastPoint = pointFromEvent(ev);
    paint(ev);
  });
  view.addEventListener("pointermove", paint);
  view.addEventListener("pointerup", () => { drawing = false; lastPoint = null; });
  view.addEventListener("pointercancel", () => { drawing = false; lastPoint = null; });

  directionSelect.addEventListener("change", switchFrame);
  frameSelect.addEventListener("change", switchFrame);
  document.getElementById("brushBtn").addEventListener("click", () => setTool("brush"));
  document.getElementById("eraserBtn").addEventListener("click", () => setTool("eraser"));
  document.getElementById("shapeBtn").addEventListener("click", () => setTool("shape"));
  document.getElementById("clearBtn").addEventListener("click", () => {
    canvasFor(activeLayer).getContext("2d").clearRect(0,0,W,H);
    redraw();
    setStatus(`Camada ${activeLayer} limpa.`);
  });
  document.getElementById("applyTemplate").addEventListener("click", applyTemplate);
  document.getElementById("generateOutline").addEventListener("click", generateOutline);
  document.getElementById("clearOutline").addEventListener("click", clearOutline);
  document.getElementById("markReference").addEventListener("click", markReference);
  applyReferenceBtn.addEventListener("click", applyReferenceToCurrent);
  propagateDirectionBtn.addEventListener("click", propagateReferenceDirection);
  brushSize.addEventListener("input", () => sizeLabel.textContent = brushSize.value);
  shapeScale.addEventListener("input", () => shapeScaleLabel.textContent = Number(shapeScale.value).toFixed(2));
  shapeSelect.addEventListener("change", () => {
    const shape = selectedShape();
    if (shape) setStatus(`${shape.label} selecionado · destino: ${shape.layer}. Clique no canvas para aplicar.`);
  });

  document.addEventListener("keydown", ev => {
    if (ev.target instanceof HTMLInputElement || ev.target instanceof HTMLSelectElement) return;
    if (ev.key.toLowerCase() === "b") setTool("brush");
    if (ev.key.toLowerCase() === "e") setTool("eraser");
    if (ev.key.toLowerCase() === "s") setTool("shape");
  });

  document.getElementById("baseFile").addEventListener("change", ev => {
    const file = ev.target.files?.[0];
    if (!file) return;
    const img = new Image();
    img.onload = () => {
      bctx.clearRect(0,0,W,H);
      bctx.imageSmoothingEnabled = false;
      bctx.drawImage(img, 0, 0, W, H);
      saveLoadedFrame();
      redraw();
      setStatus(`Passe base carregado em ${currentFrameKey()}: ${file.name}`);
      URL.revokeObjectURL(img.src);
    };
    img.src = URL.createObjectURL(file);
  });

  landmarksFile.addEventListener("change", async ev => {
    const file = ev.target.files?.[0];
    if (!file) return;
    try {
      const parsed = JSON.parse(await file.text());
      landmarksPackage = POSE_TRANSFER ? POSE_TRANSFER.validateLandmarks(parsed) : parsed;
      const count = Object.keys(landmarksPackage.frames || {}).length;
      refreshReferenceUi();
      setStatus(`Landmarks CH Blender carregados: ${count} estados · ${file.name}.`);
    } catch (error) {
      landmarksPackage = null;
      refreshReferenceUi();
      setStatus(`Falha ao carregar landmarks: ${error.message}`);
    }
  });

  function downloadCanvas(canvas, name) {
    canvas.toBlob(blob => {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = name;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    }, "image/png");
  }

  document.getElementById("exportLayer").addEventListener("click", () => {
    const dir = currentDirection().toLowerCase();
    const frame = frameSelect.value;
    downloadCanvas(canvasFor(activeLayer), `${dir}_${frame}_${activeLayer}.png`);
  });

  document.getElementById("exportComposite").addEventListener("click", () => {
    const out = document.createElement("canvas");
    out.width=W; out.height=H;
    const ctx = out.getContext("2d");
    ctx.drawImage(base,0,0);
    for (const name of LAYERS) if (visibility.get(name)) ctx.drawImage(canvasFor(name),0,0);
    const dir = currentDirection().toLowerCase();
    const frame = frameSelect.value;
    downloadCanvas(out, `${dir}_${frame}_character.png`);
  });

  document.getElementById("exportSpec").addEventListener("click", () => {
    saveLoadedFrame();
    const spec = {
      contract: "CH_CHARACTER_ART_SPEC_V0",
      characterId: "character_new",
      frame: {size:[48,64], groundAnchor:[24,60]},
      directions:["S","E","N","W"],
      motion:{source:"approved_ch_actor",walkFrames:8,allowArtToModifyPose:false},
      appearance:{
        palette:{skin:PALETTE[0],hair:PALETTE[1],primary:PALETTE[2],secondary:PALETTE[3],shoes:PALETTE[4]},
        layers:LAYERS.map(name => ({name, enabled:visibility.get(name), opacity:1.0})),
        smartShapes:{library:"CH_CHARACTER_SHAPES_V0", directionAware:true},
        template:templateSelect.value || null,
        outline:{mode:"dilated_1px", color:outlineColor.value, excludesBlenderUnderlay:true},
        poseTransfer:{
          contract:"CH_CHARACTER_POSE_TRANSFER_V0",
          landmarksContract:"CH_CHARACTER_LANDMARKS_V0",
          landmarksLoaded:Boolean(landmarksPackage),
          referenceFrame:referenceArt?.key || null,
          sameDirectionOnly:true
        },
        editedFrames:[...frameStore.keys()].sort()
      }
    };
    const blob = new Blob([JSON.stringify(spec,null,2)+"\n"],{type:"application/json"});
    const a=document.createElement("a");
    a.href=URL.createObjectURL(blob);
    a.download="character_new.character.json";
    a.click();
    setTimeout(()=>URL.revokeObjectURL(a.href),1000);
  });

  buildLayerList();
  buildSwatches();
  buildShapeSelect();
  buildTemplateSelect();
  refreshReferenceUi();
  redraw();
})();
