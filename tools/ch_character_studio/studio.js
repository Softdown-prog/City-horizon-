(() => {
  const W = 48, H = 64;
  const LAYERS = [
    "silhouette","skin","hair","face","upper_clothing","lower_clothing",
    "footwear","accessories_back","accessories_front","paint_over","outline"
  ];
  const PALETTE = ["#f6c29e","#d43b2f","#f2d744","#2b71c9","#26313a","#ffffff","#1f2937","#8b5cf6","#ef4444","#22c55e"];
  const SHAPES = window.CH_CHARACTER_SHAPES || [];

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

  let activeLayer = "paint_over";
  let tool = "brush";
  let drawing = false;
  let lastPoint = null;

  const color = document.getElementById("color");
  const brushSize = document.getElementById("brushSize");
  const sizeLabel = document.getElementById("sizeLabel");
  const status = document.getElementById("status");
  const layersEl = document.getElementById("layers");
  const swatchesEl = document.getElementById("swatches");
  const shapeSelect = document.getElementById("shapeSelect");
  const shapeScale = document.getElementById("shapeScale");
  const shapeScaleLabel = document.getElementById("shapeScaleLabel");

  function setStatus(msg) { status.textContent = msg; }
  function canvasFor(name) { return buffers.get(name); }

  function redraw() {
    vctx.clearRect(0, 0, W, H);
    vctx.drawImage(base, 0, 0);
    for (const name of LAYERS) {
      if (visibility.get(name)) vctx.drawImage(canvasFor(name), 0, 0);
    }
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

  function stampSmartShape(ev) {
    const shape = selectedShape();
    if (!shape) {
      setStatus("Nenhuma forma inteligente disponível.");
      return;
    }
    const {x, y} = pointFromEvent(ev);
    if (!buffers.has(shape.layer)) {
      setStatus(`Forma ${shape.label} pediu camada desconhecida: ${shape.layer}`);
      return;
    }
    activeLayer = shape.layer;
    visibility.set(activeLayer, true);
    const ctx = canvasFor(activeLayer).getContext("2d");
    ctx.save();
    ctx.imageSmoothingEnabled = false;
    const direction = document.getElementById("direction").value;
    shape.draw(ctx, x, y, color.value, Number(shapeScale.value), direction);
    ctx.restore();
    buildLayerList();
    redraw();
    setStatus(`${shape.label} aplicado em ${activeLayer} · direção ${direction} · ${shapeScale.value}×`);
  }

  function setTool(next) {
    tool = next;
    for (const [id, name] of [["brushBtn","brush"],["eraserBtn","eraser"],["shapeBtn","shape"]]) {
      document.getElementById(id).classList.toggle("active", name === tool);
    }
    const labels = {brush:"Pincel", eraser:"Borracha", shape:"Forma inteligente"};
    setStatus(`${labels[tool]} ativo.`);
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

  document.getElementById("brushBtn").addEventListener("click", () => setTool("brush"));
  document.getElementById("eraserBtn").addEventListener("click", () => setTool("eraser"));
  document.getElementById("shapeBtn").addEventListener("click", () => setTool("shape"));
  document.getElementById("clearBtn").addEventListener("click", () => {
    canvasFor(activeLayer).getContext("2d").clearRect(0,0,W,H);
    redraw();
    setStatus(`Camada ${activeLayer} limpa.`);
  });
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
      redraw();
      setStatus(`Passe base carregado: ${file.name}`);
      URL.revokeObjectURL(img.src);
    };
    img.src = URL.createObjectURL(file);
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
    const dir = document.getElementById("direction").value.toLowerCase();
    const frame = document.getElementById("frame").value;
    downloadCanvas(canvasFor(activeLayer), `${dir}_${frame}_${activeLayer}.png`);
  });

  document.getElementById("exportComposite").addEventListener("click", () => {
    const out = document.createElement("canvas");
    out.width=W; out.height=H;
    const ctx = out.getContext("2d");
    ctx.drawImage(base,0,0);
    for (const name of LAYERS) if (visibility.get(name)) ctx.drawImage(canvasFor(name),0,0);
    const dir = document.getElementById("direction").value.toLowerCase();
    const frame = document.getElementById("frame").value;
    downloadCanvas(out, `${dir}_${frame}_character.png`);
  });

  document.getElementById("exportSpec").addEventListener("click", () => {
    const spec = {
      contract: "CH_CHARACTER_ART_SPEC_V0",
      characterId: "character_new",
      frame: {size:[48,64], groundAnchor:[24,60]},
      directions:["S","E","N","W"],
      motion:{source:"approved_ch_actor",walkFrames:8,allowArtToModifyPose:false},
      appearance:{
        palette:{skin:PALETTE[0],hair:PALETTE[1],primary:PALETTE[2],secondary:PALETTE[3],shoes:PALETTE[4]},
        layers:LAYERS.map(name => ({name, enabled:visibility.get(name), opacity:1.0})),
        smartShapes:{library:"CH_CHARACTER_SHAPES_V0", directionAware:true}
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
  redraw();
})();
