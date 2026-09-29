(() => {
  const W = 48, H = 64;
  const LAYERS = [
    "silhouette","skin","hair","face","upper_clothing","lower_clothing",
    "footwear","accessories_back","accessories_front","paint_over","outline"
  ];
  const PALETTE = ["#f6c29e","#d43b2f","#f2d744","#2b71c9","#26313a","#ffffff","#1f2937","#8b5cf6","#ef4444","#22c55e"];

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

  const color = document.getElementById("color");
  const brushSize = document.getElementById("brushSize");
  const sizeLabel = document.getElementById("sizeLabel");
  const status = document.getElementById("status");
  const layersEl = document.getElementById("layers");
  const swatchesEl = document.getElementById("swatches");

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
      row.addEventListener("click", () => { activeLayer = name; buildLayerList(); setStatus(`Camada ativa: ${name}`); });
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

  function pointFromEvent(ev) {
    const r = view.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(W - 1, Math.floor((ev.clientX - r.left) * W / r.width))),
      y: Math.max(0, Math.min(H - 1, Math.floor((ev.clientY - r.top) * H / r.height)))
    };
  }

  function paint(ev) {
    if (!drawing) return;
    const {x, y} = pointFromEvent(ev);
    const c = canvasFor(activeLayer);
    const ctx = c.getContext("2d");
    const size = Number(brushSize.value);
    const half = Math.floor(size / 2);
    if (tool === "eraser") ctx.clearRect(x - half, y - half, size, size);
    else {
      ctx.fillStyle = color.value;
      ctx.fillRect(x - half, y - half, size, size);
    }
    redraw();
  }

  view.addEventListener("pointerdown", ev => { drawing = true; view.setPointerCapture(ev.pointerId); paint(ev); });
  view.addEventListener("pointermove", paint);
  view.addEventListener("pointerup", () => drawing = false);
  view.addEventListener("pointercancel", () => drawing = false);

  document.getElementById("brushBtn").addEventListener("click", () => {
    tool = "brush";
    document.getElementById("brushBtn").classList.add("active");
    document.getElementById("eraserBtn").classList.remove("active");
  });
  document.getElementById("eraserBtn").addEventListener("click", () => {
    tool = "eraser";
    document.getElementById("eraserBtn").classList.add("active");
    document.getElementById("brushBtn").classList.remove("active");
  });
  document.getElementById("clearBtn").addEventListener("click", () => {
    canvasFor(activeLayer).getContext("2d").clearRect(0,0,W,H);
    redraw(); setStatus(`Camada ${activeLayer} limpa.`);
  });
  brushSize.addEventListener("input", () => sizeLabel.textContent = brushSize.value);

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
    const out = document.createElement("canvas"); out.width=W; out.height=H;
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
        layers:LAYERS.map(name => ({name, enabled:visibility.get(name), opacity:1.0}))
      }
    };
    const blob = new Blob([JSON.stringify(spec,null,2)+"\n"],{type:"application/json"});
    const a=document.createElement("a"); a.href=URL.createObjectURL(blob); a.download="character_new.character.json"; a.click();
    setTimeout(()=>URL.revokeObjectURL(a.href),1000);
  });

  buildLayerList(); buildSwatches(); redraw();
})();
