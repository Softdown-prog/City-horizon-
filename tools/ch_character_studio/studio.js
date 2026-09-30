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
  const HISTORY_LIMIT = 50;

  const view = document.getElementById("view");
  const vctx = view.getContext("2d");
  vctx.imageSmoothingEnabled = false;

  const base = document.createElement("canvas");
  base.width = W; base.height = H;
  const bctx = base.getContext("2d");
  bctx.imageSmoothingEnabled = false;

  const buffers = new Map();
  const visibility = new Map();
  const opacity = new Map();
  const blendMode = new Map();
  for (const name of LAYERS) {
    const canvas = document.createElement("canvas");
    canvas.width = W; canvas.height = H;
    canvas.getContext("2d").imageSmoothingEnabled = false;
    buffers.set(name, canvas);
    visibility.set(name, true);
    opacity.set(name, 1.0);
    blendMode.set(name, "source-over");
  }

  const directionSelect = document.getElementById("direction");
  const frameSelect = document.getElementById("frame");
  const frameStore = new Map();
  const historyStore = new Map();
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

  function setStatus(message) { status.textContent = message; }
  function canvasFor(name) { return buffers.get(name); }
  function currentDirection() { return directionSelect.value; }
  function currentFrameKey() { return `${directionSelect.value}:${frameSelect.value}`; }
  function keyDirection(key) { return String(key).split(":", 1)[0]; }

  function dispatch(name, detail={}) {
    window.dispatchEvent(new CustomEvent(name, {detail}));
  }

  function redraw() {
    vctx.clearRect(0, 0, W, H);
    vctx.globalAlpha = 1;
    vctx.globalCompositeOperation = "source-over";
    vctx.drawImage(base, 0, 0);
    for (const name of LAYERS) {
      if (!visibility.get(name)) continue;
      vctx.save();
      vctx.globalAlpha = opacity.get(name) ?? 1;
      vctx.globalCompositeOperation = blendMode.get(name) || "source-over";
      vctx.drawImage(canvasFor(name), 0, 0);
      vctx.restore();
    }
    vctx.globalAlpha = 1;
    vctx.globalCompositeOperation = "source-over";
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

  function captureState() {
    return {
      base: cloneImageData(snapshotCanvas(base)),
      layers: cloneLayers(snapshotLayers()),
      opacity: Object.fromEntries(LAYERS.map(name => [name, opacity.get(name) ?? 1])),
      blendMode: Object.fromEntries(LAYERS.map(name => [name, blendMode.get(name) || "source-over"])),
      activeLayer
    };
  }

  function restoreState(state) {
    if (!state) return;
    bctx.clearRect(0,0,W,H);
    if (state.base) bctx.putImageData(cloneImageData(state.base),0,0);
    for (const name of LAYERS) {
      const ctx = canvasFor(name).getContext("2d");
      ctx.clearRect(0,0,W,H);
      if (state.layers?.[name]) ctx.putImageData(cloneImageData(state.layers[name]),0,0);
      if (state.opacity && Number.isFinite(state.opacity[name])) opacity.set(name,state.opacity[name]);
      if (state.blendMode?.[name]) blendMode.set(name,state.blendMode[name]);
    }
    if (state.activeLayer && buffers.has(state.activeLayer)) activeLayer=state.activeLayer;
    buildLayerList();
    redraw();
    dispatch("ch-studio-layer-changed", {layer:activeLayer});
  }

  function historyFor(key=loadedFrameKey) {
    if (!historyStore.has(key)) historyStore.set(key,{undo:[],redo:[]});
    return historyStore.get(key);
  }

  function checkpoint(reason="edit") {
    const history=historyFor();
    history.undo.push({reason,state:captureState()});
    if (history.undo.length>HISTORY_LIMIT) history.undo.shift();
    history.redo.length=0;
    dispatch("ch-studio-history", {action:"checkpoint",reason,canUndo:true,canRedo:false});
  }

  function undo() {
    const history=historyFor();
    if (!history.undo.length) { setStatus("Nada para desfazer neste frame."); return false; }
    history.redo.push({reason:"redo",state:captureState()});
    const item=history.undo.pop();
    restoreState(item.state);
    saveLoadedFrame();
    setStatus(`Desfeito: ${item.reason}.`);
    dispatch("ch-studio-history", {action:"undo",canUndo:history.undo.length>0,canRedo:true});
    return true;
  }

  function redo() {
    const history=historyFor();
    if (!history.redo.length) { setStatus("Nada para refazer neste frame."); return false; }
    history.undo.push({reason:"undo",state:captureState()});
    const item=history.redo.pop();
    restoreState(item.state);
    saveLoadedFrame();
    setStatus("Ação refeita.");
    dispatch("ch-studio-history", {action:"redo",canUndo:true,canRedo:history.redo.length>0});
    return true;
  }

  function saveLoadedFrame() {
    frameStore.set(loadedFrameKey, {
      base: cloneImageData(snapshotCanvas(base)),
      layers: cloneLayers(snapshotLayers())
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
      if (state.base) bctx.putImageData(cloneImageData(state.base), 0, 0);
      for (const name of LAYERS) if (state.layers?.[name]) canvasFor(name).getContext("2d").putImageData(cloneImageData(state.layers[name]), 0, 0);
    }
    loadedFrameKey = key;
    redraw();
    setStatus(`Frame ativo: ${key.replace(":", " / ")}${state ? " · arte restaurada" : " · novo"}.`);
    dispatch("ch-studio-frame-changed", {key});
  }

  function switchFrame() {
    if (drawing) { drawing = false; lastPoint = null; }
    saveLoadedFrame();
    loadFrameState(currentFrameKey());
  }

  function setActiveLayer(name) {
    if (!buffers.has(name)) return false;
    activeLayer=name;
    buildLayerList();
    setStatus(`Camada ativa: ${name}`);
    dispatch("ch-studio-layer-changed", {layer:name});
    return true;
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
      meta.textContent = name === activeLayer ? `${Math.round((opacity.get(name)??1)*100)}%` : "";
      row.append(check, label, meta);
      row.addEventListener("click", () => setActiveLayer(name));
      layersEl.appendChild(row);
    });
  }

  function buildSwatches() {
    if (!swatchesEl || swatchesEl.children.length) return;
    PALETTE.forEach(hex => {
      const el = document.createElement("button");
      el.className = "swatch"; el.style.background = hex; el.title = hex;
      el.addEventListener("click", () => {
        color.value = hex;
        [...swatchesEl.children].forEach(node => node.classList.remove("active"));
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
      const group = document.createElement("optgroup"); group.label = groupName;
      for (const shape of shapes) {
        const option = document.createElement("option"); option.value = shape.id; option.textContent = shape.label; group.appendChild(option);
      }
      shapeSelect.appendChild(group);
    }
  }

  function buildTemplateSelect() {
    templateSelect.innerHTML = "";
    for (const template of TEMPLATES) {
      const option = document.createElement("option"); option.value = template.id; option.textContent = template.label; templateSelect.appendChild(option);
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
    else { ctx.fillStyle = color.value; ctx.fillRect(x - half, y - half, size, size); }
  }

  function paintSegment(from, to) {
    const ctx = canvasFor(activeLayer).getContext("2d");
    const size = Number(brushSize.value); const erase = tool === "eraser";
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
    paintSegment(lastPoint || point, point); lastPoint = point; redraw();
  }

  function selectedShape() { return SHAPES.find(shape => shape.id === shapeSelect.value) || null; }

  function drawShape(shape, x, y, fill, scale) {
    if (!shape || !buffers.has(shape.layer)) return false;
    visibility.set(shape.layer, true);
    const ctx = canvasFor(shape.layer).getContext("2d");
    ctx.save(); ctx.imageSmoothingEnabled = false; shape.draw(ctx, x, y, fill, scale, currentDirection()); ctx.restore();
    return true;
  }

  function stampSmartShape(ev) {
    const shape = selectedShape();
    if (!shape) { setStatus("Nenhuma forma inteligente disponível."); return; }
    const {x, y} = pointFromEvent(ev);
    if (!drawShape(shape, x, y, color.value, Number(shapeScale.value))) { setStatus(`Forma ${shape.label} pediu camada desconhecida: ${shape.layer}`); return; }
    setActiveLayer(shape.layer); redraw();
    setStatus(`${shape.label} aplicado em ${activeLayer} · direção ${currentDirection()} · ${shapeScale.value}×`);
  }

  function clearArtLayers() {
    for (const name of LAYERS) canvasFor(name).getContext("2d").clearRect(0, 0, W, H);
  }

  function applyTemplate() {
    const template = TEMPLATES.find(item => item.id === templateSelect.value); if (!template) return;
    checkpoint("apply_template"); clearArtLayers();
    const palette = template.palette || {}; let applied = 0;
    for (const placement of template.placements || []) {
      const shape = SHAPES.find(item => item.id === placement.shape);
      const fill = palette[placement.color] || placement.color || color.value;
      if (drawShape(shape, placement.x, placement.y, fill, placement.scale || 1)) applied += 1;
    }
    setActiveLayer("paint_over"); redraw();
    setStatus(`${template.label} aplicado: ${applied} peças artísticas · pose e movimento preservados.`);
  }

  function fallbackOutline(layers) {
    const coverage = new Uint8Array(W * H);
    for (const name of LAYERS) {
      if (name === "outline") continue;
      const image = layers[name]; if (!image) continue;
      for (let i = 0; i < W * H; i++) if (image.data[i * 4 + 3] > 0) coverage[i] = 1;
    }
    const out = blankImageData();
    const value = outlineColor.value.replace("#", "");
    const rgba = [parseInt(value.slice(0,2),16),parseInt(value.slice(2,4),16),parseInt(value.slice(4,6),16),255];
    const neighbors = [[-1,-1],[0,-1],[1,-1],[-1,0],[1,0],[-1,1],[0,1],[1,1]];
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const index = y * W + x; if (coverage[index]) continue;
      let adjacent = false;
      for (const [dx, dy] of neighbors) {
        const nx=x+dx, ny=y+dy;
        if (nx>=0&&nx<W&&ny>=0&&ny<H&&coverage[ny*W+nx]) { adjacent=true; break; }
      }
      if (!adjacent) continue;
      const p=index*4; out.data[p]=rgba[0];out.data[p+1]=rgba[1];out.data[p+2]=rgba[2];out.data[p+3]=255;
    }
    return out;
  }

  function outlineForLayers(layers) {
    return POSE_TRANSFER ? POSE_TRANSFER.buildOutline(layers, outlineColor.value, LAYERS) : fallbackOutline(layers);
  }

  function generateOutline() {
    checkpoint("generate_outline");
    const image = outlineForLayers(snapshotLayers());
    canvasFor("outline").getContext("2d").putImageData(image,0,0);
    visibility.set("outline",true); setActiveLayer("outline"); redraw();
    let count=0; for(let i=3;i<image.data.length;i+=4) if(image.data[i]) count++;
    setStatus(`Outline dilatado 1 px gerado: ${count} pixels · base CH Blender ignorada.`);
  }

  function clearOutline() {
    checkpoint("clear_outline"); canvasFor("outline").getContext("2d").clearRect(0,0,W,H); redraw(); setStatus("Outline limpo.");
  }

  function setTool(next) {
    tool = next;
    for (const [id, name] of [["brushBtn","brush"],["eraserBtn","eraser"],["shapeBtn","shape"]]) {
      document.getElementById(id)?.classList.toggle("active", name === tool);
    }
    const labels = {brush:"Pincel", eraser:"Borracha", shape:"Forma inteligente", external:"Ferramenta externa"};
    if (labels[tool]) setStatus(`${labels[tool]} ativo.`);
  }

  function landmarkFrame(key) { return landmarksPackage?.frames?.[key] || null; }

  function refreshReferenceUi() {
    const ready = Boolean(referenceArt && landmarksPackage && POSE_TRANSFER);
    applyReferenceBtn.disabled = !ready; propagateDirectionBtn.disabled = !ready;
    if (!referenceArt) {
      referenceStatus.textContent = landmarksPackage ? "Landmarks carregados. Marque um frame artístico como referência." : "Nenhuma referência marcada.";
      return;
    }
    referenceStatus.textContent = `Referência: ${referenceArt.key.replace(":", " / ")} · ${ready ? "pronta para propagação" : "aguardando landmarks"}.`;
  }

  function markReference() {
    if (!POSE_TRANSFER) { setStatus("Módulo CH_CHARACTER_POSE_TRANSFER_V0 não foi carregado."); return; }
    if (!landmarksPackage) { setStatus("Carregue landmarks.json do CH Blender antes de marcar a referência."); return; }
    const key=currentFrameKey(); if(!landmarkFrame(key)){setStatus(`Landmarks não contêm ${key}.`);return;}
    saveLoadedFrame(); referenceArt={key,layers:cloneLayers(frameStore.get(key).layers)}; refreshReferenceUi();
    setStatus(`Frame ${key.replace(":", " / ")} congelado como referência artística.`);
  }

  function transferredLayersFor(targetKey) {
    if (!referenceArt || !landmarksPackage || !POSE_TRANSFER) throw new Error("referência/landmarks indisponíveis");
    if (keyDirection(referenceArt.key) !== keyDirection(targetKey)) throw new Error("propagação automática só é permitida dentro da mesma direção");
    const sourceFrame=landmarkFrame(referenceArt.key), targetFrame=landmarkFrame(targetKey);
    if(!sourceFrame||!targetFrame) throw new Error(`landmarks ausentes para ${targetKey}`);
    const layers=targetKey===referenceArt.key ? cloneLayers(referenceArt.layers) : POSE_TRANSFER.transferLayers(referenceArt.layers,sourceFrame,targetFrame,LAYERS);
    layers.outline=outlineForLayers(layers); return layers;
  }

  function applyReferenceToCurrent() {
    const targetKey=currentFrameKey();
    try {
      checkpoint("apply_pose_reference");
      const layers=transferredLayersFor(targetKey);
      for(const name of LAYERS) canvasFor(name).getContext("2d").putImageData(layers[name]||blankImageData(),0,0);
      saveLoadedFrame(); redraw(); setStatus(`Aparência de ${referenceArt.key.replace(":", " / ")} adaptada para ${targetKey.replace(":", " / ")} por landmarks.`);
    } catch(error){setStatus(`Propagação recusada: ${error.message}`);}
  }

  function propagateReferenceDirection() {
    if(!referenceArt)return;
    const direction=keyDirection(referenceArt.key); saveLoadedFrame(); let generated=0;
    try {
      for(const frame of ANIMATION_FRAMES){
        const targetKey=`${direction}:${frame}`; const existing=frameStore.get(targetKey); const layers=transferredLayersFor(targetKey);
        frameStore.set(targetKey,{base:existing?.base?cloneImageData(existing.base):blankImageData(),layers,generatedFrom:referenceArt.key}); generated++;
      }
      if(currentDirection()===direction) loadFrameState(currentFrameKey());
      refreshReferenceUi(); setStatus(`${generated} frames de ${direction} receberam a aparência da referência ${referenceArt.key.replace(":", " / ")} · outline recalculado.`);
    } catch(error){setStatus(`Propagação recusada: ${error.message}`);}
  }

  function setLayerOpacity(name,value) {
    if(!buffers.has(name)) return false;
    opacity.set(name,Math.max(0,Math.min(1,Number(value)))); buildLayerList(); redraw(); dispatch("ch-studio-layer-changed",{layer:name}); return true;
  }
  function setLayerBlendMode(name,value) {
    if(!buffers.has(name)) return false;
    const allowed=new Set(["source-over","multiply","screen","overlay","darken","lighten","soft-light","hard-light","difference"]);
    blendMode.set(name,allowed.has(value)?value:"source-over"); redraw(); dispatch("ch-studio-layer-changed",{layer:name}); return true;
  }

  view.addEventListener("pointerdown", ev => {
    view.setPointerCapture(ev.pointerId);
    if (tool === "shape") { checkpoint("smart_shape"); stampSmartShape(ev); return; }
    if (tool === "brush" || tool === "eraser") checkpoint(tool);
    drawing = true; lastPoint = pointFromEvent(ev); paint(ev);
  });
  view.addEventListener("pointermove", paint);
  view.addEventListener("pointerup", () => { drawing=false; lastPoint=null; saveLoadedFrame(); });
  view.addEventListener("pointercancel", () => { drawing=false; lastPoint=null; });

  directionSelect.addEventListener("change", switchFrame);
  frameSelect.addEventListener("change", switchFrame);
  document.getElementById("brushBtn").addEventListener("click",()=>setTool("brush"));
  document.getElementById("eraserBtn").addEventListener("click",()=>setTool("eraser"));
  document.getElementById("shapeBtn").addEventListener("click",()=>setTool("shape"));
  document.getElementById("clearBtn").addEventListener("click",()=>{checkpoint("clear_layer");canvasFor(activeLayer).getContext("2d").clearRect(0,0,W,H);redraw();setStatus(`Camada ${activeLayer} limpa.`);});
  document.getElementById("applyTemplate").addEventListener("click",applyTemplate);
  document.getElementById("generateOutline").addEventListener("click",generateOutline);
  document.getElementById("clearOutline").addEventListener("click",clearOutline);
  document.getElementById("markReference").addEventListener("click",markReference);
  applyReferenceBtn.addEventListener("click",applyReferenceToCurrent);
  propagateDirectionBtn.addEventListener("click",propagateReferenceDirection);
  brushSize.addEventListener("input",()=>sizeLabel.textContent=brushSize.value);
  shapeScale.addEventListener("input",()=>shapeScaleLabel.textContent=Number(shapeScale.value).toFixed(2));
  shapeSelect.addEventListener("change",()=>{const shape=selectedShape();if(shape)setStatus(`${shape.label} selecionado · destino: ${shape.layer}. Clique no canvas para aplicar.`);});

  document.addEventListener("keydown", ev => {
    if(ev.target instanceof HTMLInputElement||ev.target instanceof HTMLSelectElement||ev.target instanceof HTMLTextAreaElement)return;
    if(ev.ctrlKey||ev.metaKey)return;
    const key=ev.key.toLowerCase();
    if(key==="b")setTool("brush"); else if(key==="e")setTool("eraser"); else if(key==="s")setTool("shape");
  });

  document.getElementById("baseFile").addEventListener("change",ev=>{
    const file=ev.target.files?.[0]; if(!file)return;
    const img=new Image();
    img.onload=()=>{checkpoint("import_base");bctx.clearRect(0,0,W,H);bctx.imageSmoothingEnabled=false;bctx.drawImage(img,0,0,W,H);saveLoadedFrame();redraw();setStatus(`Passe base carregado em ${currentFrameKey()}: ${file.name}`);URL.revokeObjectURL(img.src);};
    img.src=URL.createObjectURL(file);
  });

  landmarksFile.addEventListener("change",async ev=>{
    const file=ev.target.files?.[0];if(!file)return;
    try{const parsed=JSON.parse(await file.text());landmarksPackage=POSE_TRANSFER?POSE_TRANSFER.validateLandmarks(parsed):parsed;const count=Object.keys(landmarksPackage.frames||{}).length;refreshReferenceUi();setStatus(`Landmarks CH Blender carregados: ${count} estados · ${file.name}.`);}
    catch(error){landmarksPackage=null;refreshReferenceUi();setStatus(`Falha ao carregar landmarks: ${error.message}`);}
  });

  function downloadCanvas(canvas,name){canvas.toBlob(blob=>{const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);},"image/png");}

  document.getElementById("exportLayer").addEventListener("click",()=>{const dir=currentDirection().toLowerCase();downloadCanvas(canvasFor(activeLayer),`${dir}_${frameSelect.value}_${activeLayer}.png`);});
  document.getElementById("exportComposite").addEventListener("click",()=>{const out=document.createElement("canvas");out.width=W;out.height=H;const c=out.getContext("2d");c.imageSmoothingEnabled=false;c.drawImage(base,0,0);for(const name of LAYERS){if(!visibility.get(name))continue;c.save();c.globalAlpha=opacity.get(name)??1;c.globalCompositeOperation=blendMode.get(name)||"source-over";c.drawImage(canvasFor(name),0,0);c.restore();}downloadCanvas(out,`${currentDirection().toLowerCase()}_${frameSelect.value}_character.png`);});

  document.getElementById("exportSpec").addEventListener("click",()=>{
    saveLoadedFrame();
    const spec={contract:"CH_CHARACTER_ART_SPEC_V0",characterId:"character_new",frame:{size:[48,64],groundAnchor:[24,60]},directions:["S","E","N","W"],motion:{source:"approved_ch_actor",walkFrames:8,allowArtToModifyPose:false},appearance:{palette:{skin:PALETTE[0],hair:PALETTE[1],primary:PALETTE[2],secondary:PALETTE[3],shoes:PALETTE[4]},layers:LAYERS.map(name=>({name,enabled:visibility.get(name),opacity:opacity.get(name)??1,blendMode:blendMode.get(name)||"source-over"})),smartShapes:{library:"CH_CHARACTER_SHAPES_V0",directionAware:true},template:templateSelect.value||null,outline:{mode:"dilated_1px",color:outlineColor.value,excludesBlenderUnderlay:true},poseTransfer:{contract:"CH_CHARACTER_POSE_TRANSFER_V0",landmarksContract:"CH_CHARACTER_LANDMARKS_V0",landmarksLoaded:Boolean(landmarksPackage),referenceFrame:referenceArt?.key||null,sameDirectionOnly:true},photoshopTools:{contract:"CH_CHARACTER_PHOTOSHOP_TOOLS_V0",historyPerFrame:true},editedFrames:[...frameStore.keys()].sort()}};
    const blob=new Blob([JSON.stringify(spec,null,2)+"\n"],{type:"application/json"});const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download="character_new.character.json";a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);
  });

  window.CH_STUDIO_API = {
    contract:"CH_CHARACTER_STUDIO_API_V0",
    width:W,height:H,layers:[...LAYERS],
    getFrameKey:currentFrameKey,
    getActiveLayer:()=>activeLayer,
    setActiveLayer,
    getActiveLayerCanvas:()=>canvasFor(activeLayer),
    getLayerCanvas:canvasFor,
    getCompositeCanvas:()=>view,
    getColor:()=>color.value,
    setColor:value=>{color.value=value;dispatch("ch-studio-color-changed",{color:value});},
    getLayerOpacity:name=>opacity.get(name)??1,
    setLayerOpacity,
    getLayerBlendMode:name=>blendMode.get(name)||"source-over",
    setLayerBlendMode,
    setTool,
    setStatus,
    redraw,
    checkpoint,
    undo,
    redo,
    saveFrame:saveLoadedFrame,
    getLandmarksPackage:()=>landmarksPackage
  };

  buildLayerList();buildSwatches();buildShapeSelect();buildTemplateSelect();refreshReferenceUi();redraw();
  dispatch("ch-studio-layer-changed",{layer:activeLayer});
})();
