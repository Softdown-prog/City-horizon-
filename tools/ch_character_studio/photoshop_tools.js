(() => {
  const API = window.CH_STUDIO_API;
  if (!API) {
    console.error("CH Photoshop tools require CH_STUDIO_API");
    return;
  }

  const W = 48, H = 64;
  const overlay = document.getElementById("photoshopView");
  const ctx = overlay.getContext("2d");
  ctx.imageSmoothingEnabled = false;

  const toolButtons = {
    rect: document.getElementById("psRectSelect"),
    lasso: document.getElementById("psLasso"),
    move: document.getElementById("psMove"),
    eyedropper: document.getElementById("psEyedropper"),
    bucket: document.getElementById("psBucket")
  };
  const undoBtn = document.getElementById("psUndo");
  const redoBtn = document.getElementById("psRedo");
  const deselectBtn = document.getElementById("psDeselect");
  const fillBtn = document.getElementById("psFillSelection");
  const deleteBtn = document.getElementById("psDeleteSelection");
  const applyTransformBtn = document.getElementById("psApplyTransform");
  const toleranceInput = document.getElementById("psTolerance");
  const transformX = document.getElementById("psTransformX");
  const transformY = document.getElementById("psTransformY");
  const transformScale = document.getElementById("psTransformScale");
  const transformRotate = document.getElementById("psTransformRotate");
  const flipH = document.getElementById("psFlipH");
  const flipV = document.getElementById("psFlipV");
  const layerOpacity = document.getElementById("psLayerOpacity");
  const layerOpacityLabel = document.getElementById("psLayerOpacityLabel");
  const layerBlend = document.getElementById("psLayerBlend");
  const psStatus = document.getElementById("psStatus");

  let activeTool = null;
  let selection = new Uint8Array(W * H);
  let dragStart = null;
  let dragPoint = null;
  let lassoPoints = [];
  let moving = false;
  let moveOrigin = null;
  let moveEnd = null;

  function status(message) {
    if (psStatus) psStatus.textContent = message;
    API.setStatus(message);
  }

  function pointFromEvent(ev) {
    const r = overlay.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(W - 1, Math.floor((ev.clientX - r.left) * W / r.width))),
      y: Math.max(0, Math.min(H - 1, Math.floor((ev.clientY - r.top) * H / r.height)))
    };
  }

  function anySelection() {
    for (const value of selection) if (value) return true;
    return false;
  }

  function selectionBounds() {
    let minX = W, minY = H, maxX = -1, maxY = -1;
    for (let y = 0; y < H; y++) {
      for (let x = 0; x < W; x++) {
        if (!selection[y * W + x]) continue;
        minX = Math.min(minX, x); minY = Math.min(minY, y);
        maxX = Math.max(maxX, x); maxY = Math.max(maxY, y);
      }
    }
    return maxX < 0 ? null : {minX, minY, maxX, maxY, width:maxX-minX+1, height:maxY-minY+1};
  }

  function clearSelection() {
    selection.fill(0);
    dragStart = dragPoint = null;
    lassoPoints = [];
    drawOverlay();
    status("Seleção limpa.");
  }

  function setRectSelection(a, b) {
    selection.fill(0);
    const x0 = Math.min(a.x, b.x), x1 = Math.max(a.x, b.x);
    const y0 = Math.min(a.y, b.y), y1 = Math.max(a.y, b.y);
    for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) selection[y * W + x] = 1;
  }

  function setLassoSelection(points) {
    selection.fill(0);
    if (points.length < 3) return;
    const mask = document.createElement("canvas"); mask.width=W; mask.height=H;
    const mctx = mask.getContext("2d");
    mctx.beginPath(); mctx.moveTo(points[0].x + .5, points[0].y + .5);
    for (const p of points.slice(1)) mctx.lineTo(p.x + .5, p.y + .5);
    mctx.closePath(); mctx.fillStyle="#fff"; mctx.fill();
    const data = mctx.getImageData(0,0,W,H).data;
    for (let i=0;i<W*H;i++) if (data[i*4+3]) selection[i]=1;
  }

  function drawOverlay() {
    ctx.clearRect(0,0,W,H);
    if (activeTool === "rect" && dragStart && dragPoint) {
      const x=Math.min(dragStart.x,dragPoint.x), y=Math.min(dragStart.y,dragPoint.y);
      const w=Math.abs(dragPoint.x-dragStart.x)+1, h=Math.abs(dragPoint.y-dragStart.y)+1;
      ctx.strokeStyle="#ffffff"; ctx.setLineDash([1,1]); ctx.lineWidth=1;
      ctx.strokeRect(x+.5,y+.5,w,h); ctx.setLineDash([]);
    }
    if (activeTool === "lasso" && lassoPoints.length > 1) {
      ctx.strokeStyle="#ffffff"; ctx.setLineDash([1,1]); ctx.beginPath();
      ctx.moveTo(lassoPoints[0].x+.5,lassoPoints[0].y+.5);
      for (const p of lassoPoints.slice(1)) ctx.lineTo(p.x+.5,p.y+.5);
      ctx.stroke(); ctx.setLineDash([]);
    }
    if (anySelection()) {
      const image = ctx.createImageData(W,H);
      for (let y=0;y<H;y++) for (let x=0;x<W;x++) {
        const i=y*W+x; if (!selection[i]) continue;
        const edge = x===0||y===0||x===W-1||y===H-1 || !selection[i-1] || !selection[i+1] || !selection[i-W] || !selection[i+W];
        if (!edge) continue;
        const p=i*4;
        const white=((x+y)&1)===0;
        image.data[p]=white?255:40; image.data[p+1]=white?255:40; image.data[p+2]=white?255:40; image.data[p+3]=255;
      }
      ctx.putImageData(image,0,0);
    }
    if (moving && moveOrigin && moveEnd) {
      const dx=moveEnd.x-moveOrigin.x, dy=moveEnd.y-moveOrigin.y;
      const b=selectionBounds();
      if (b) {
        ctx.strokeStyle="#f4d35e"; ctx.strokeRect(b.minX+dx+.5,b.minY+dy+.5,b.width,b.height);
      }
    }
  }

  function setTool(name) {
    activeTool = activeTool === name ? null : name;
    API.setTool(activeTool ? "external" : "brush");
    overlay.style.pointerEvents = activeTool ? "auto" : "none";
    for (const [key, button] of Object.entries(toolButtons)) if (button) button.classList.toggle("active", activeTool === key);
    const labels={rect:"Seleção retangular",lasso:"Laço",move:"Mover seleção",eyedropper:"Conta-gotas",bucket:"Balde"};
    status(activeTool ? `${labels[activeTool]} ativo.` : "Ferramenta Photoshop desativada.");
    drawOverlay();
  }

  function selectedLayerCanvas() { return API.getActiveLayerCanvas(); }

  function hexToRgba(hex) {
    const h=String(hex).replace("#","");
    return [parseInt(h.slice(0,2),16),parseInt(h.slice(2,4),16),parseInt(h.slice(4,6),16),255];
  }

  function rgbaToHex(r,g,b) {
    return "#"+[r,g,b].map(v=>Math.max(0,Math.min(255,v)).toString(16).padStart(2,"0")).join("");
  }

  function sampleEyedropper(p) {
    const data=API.getCompositeCanvas().getContext("2d").getImageData(p.x,p.y,1,1).data;
    if (!data[3]) { status("Conta-gotas: pixel transparente."); return; }
    const hex=rgbaToHex(data[0],data[1],data[2]); API.setColor(hex); status(`Conta-gotas: ${hex}.`);
  }

  function colorDistance(a,b) {
    return Math.max(Math.abs(a[0]-b[0]),Math.abs(a[1]-b[1]),Math.abs(a[2]-b[2]),Math.abs(a[3]-b[3]));
  }

  function floodFill(p) {
    const canvas=selectedLayerCanvas();
    if (!canvas) return;
    API.checkpoint("paint_bucket");
    const c=canvas.getContext("2d");
    const image=c.getImageData(0,0,W,H); const data=image.data;
    const start=(p.y*W+p.x)*4; const target=[data[start],data[start+1],data[start+2],data[start+3]];
    const fill=hexToRgba(API.getColor()); const tol=Number(toleranceInput?.value||0);
    if (colorDistance(target,fill)===0) return;
    const stack=[[p.x,p.y]]; const seen=new Uint8Array(W*H);
    while (stack.length) {
      const [x,y]=stack.pop(); const idx=y*W+x; if (seen[idx]) continue; seen[idx]=1;
      if (anySelection() && !selection[idx]) continue;
      const off=idx*4; const here=[data[off],data[off+1],data[off+2],data[off+3]];
      if (colorDistance(here,target)>tol) continue;
      data[off]=fill[0]; data[off+1]=fill[1]; data[off+2]=fill[2]; data[off+3]=255;
      if (x>0) stack.push([x-1,y]); if (x<W-1) stack.push([x+1,y]);
      if (y>0) stack.push([x,y-1]); if (y<H-1) stack.push([x,y+1]);
    }
    c.putImageData(image,0,0); API.redraw(); status(`Balde aplicado · tolerância ${tol}.`);
  }

  function fillSelection() {
    const canvas=selectedLayerCanvas(); if (!canvas) return;
    API.checkpoint("fill_selection");
    const c=canvas.getContext("2d"); const image=c.getImageData(0,0,W,H); const rgba=hexToRgba(API.getColor());
    const selected=anySelection();
    for (let i=0;i<W*H;i++) {
      if (selected && !selection[i]) continue;
      const p=i*4; image.data[p]=rgba[0]; image.data[p+1]=rgba[1]; image.data[p+2]=rgba[2]; image.data[p+3]=255;
    }
    c.putImageData(image,0,0); API.redraw(); status(selected?"Seleção preenchida.":"Camada inteira preenchida.");
  }

  function deleteSelection() {
    if (!anySelection()) { status("Delete exige uma seleção ativa."); return; }
    const canvas=selectedLayerCanvas(); if (!canvas) return;
    API.checkpoint("delete_selection");
    const c=canvas.getContext("2d"); const image=c.getImageData(0,0,W,H);
    for (let i=0;i<W*H;i++) if (selection[i]) image.data[i*4+3]=0;
    c.putImageData(image,0,0); API.redraw(); status("Pixels selecionados apagados.");
  }

  function selectionMaskCanvas() {
    const c=document.createElement("canvas"); c.width=W; c.height=H;
    const x=c.getContext("2d"); const image=x.createImageData(W,H);
    for (let i=0;i<W*H;i++) if (selection[i]) { const p=i*4; image.data[p]=image.data[p+1]=image.data[p+2]=image.data[p+3]=255; }
    x.putImageData(image,0,0); return c;
  }

  function extractSelectedPixels() {
    const source=selectedLayerCanvas();
    const out=document.createElement("canvas"); out.width=W; out.height=H;
    const s=source.getContext("2d").getImageData(0,0,W,H); const o=out.getContext("2d").createImageData(W,H);
    for (let i=0;i<W*H;i++) if (selection[i]) {
      const p=i*4; o.data[p]=s.data[p]; o.data[p+1]=s.data[p+1]; o.data[p+2]=s.data[p+2]; o.data[p+3]=s.data[p+3];
    }
    out.getContext("2d").putImageData(o,0,0); return out;
  }

  function clearSelectedPixels(canvas) {
    const c=canvas.getContext("2d"); const image=c.getImageData(0,0,W,H);
    for (let i=0;i<W*H;i++) if (selection[i]) image.data[i*4+3]=0;
    c.putImageData(image,0,0);
  }

  function transformedCanvas(source, dx, dy, scale, angleDeg, flipHorizontal, flipVertical) {
    const out=document.createElement("canvas"); out.width=W; out.height=H;
    const o=out.getContext("2d"); o.imageSmoothingEnabled=false;
    const b=selectionBounds(); if (!b) return out;
    const cx=(b.minX+b.maxX+1)/2, cy=(b.minY+b.maxY+1)/2;
    o.translate(cx+dx,cy+dy); o.rotate(angleDeg*Math.PI/180);
    o.scale(scale*(flipHorizontal?-1:1),scale*(flipVertical?-1:1));
    o.translate(-cx,-cy); o.drawImage(source,0,0); return out;
  }

  function applyTransform(dx=0,dy=0,scale=1,angle=0,fh=false,fv=false) {
    if (!anySelection()) { status("Transformar exige uma seleção ativa."); return; }
    const canvas=selectedLayerCanvas(); if (!canvas) return;
    API.checkpoint("transform_selection");
    const pixels=extractSelectedPixels(); const mask=selectionMaskCanvas();
    clearSelectedPixels(canvas);
    const transformed=transformedCanvas(pixels,dx,dy,scale,angle,fh,fv);
    const c=canvas.getContext("2d"); c.imageSmoothingEnabled=false; c.drawImage(transformed,0,0);
    const maskTransformed=transformedCanvas(mask,dx,dy,scale,angle,fh,fv).getContext("2d").getImageData(0,0,W,H).data;
    selection.fill(0); for (let i=0;i<W*H;i++) if (maskTransformed[i*4+3]) selection[i]=1;
    API.redraw(); drawOverlay(); status(`Transform aplicado: Δ(${dx},${dy}) · ${Math.round(scale*100)}% · ${angle}°.`);
  }

  function syncLayerControls() {
    const layer=API.getActiveLayer();
    if (!layer) return;
    const opacity=Math.round(API.getLayerOpacity(layer)*100);
    layerOpacity.value=opacity; layerOpacityLabel.textContent=opacity;
    layerBlend.value=API.getLayerBlendMode(layer);
  }

  overlay.addEventListener("pointerdown", ev => {
    const p=pointFromEvent(ev); overlay.setPointerCapture(ev.pointerId);
    if (activeTool==="rect") { dragStart=dragPoint=p; drawOverlay(); return; }
    if (activeTool==="lasso") { lassoPoints=[p]; drawOverlay(); return; }
    if (activeTool==="eyedropper") { sampleEyedropper(p); return; }
    if (activeTool==="bucket") { floodFill(p); return; }
    if (activeTool==="move") {
      if (!anySelection()) { status("Mover exige uma seleção ativa."); return; }
      moving=true; moveOrigin=moveEnd=p; drawOverlay();
    }
  });

  overlay.addEventListener("pointermove", ev => {
    const p=pointFromEvent(ev);
    if (activeTool==="rect" && dragStart) { dragPoint=p; drawOverlay(); }
    else if (activeTool==="lasso" && lassoPoints.length) {
      const last=lassoPoints[lassoPoints.length-1]; if (last.x!==p.x||last.y!==p.y) lassoPoints.push(p); drawOverlay();
    } else if (activeTool==="move" && moving) { moveEnd=p; drawOverlay(); }
  });

  overlay.addEventListener("pointerup", ev => {
    const p=pointFromEvent(ev);
    if (activeTool==="rect" && dragStart) {
      setRectSelection(dragStart,p); dragStart=dragPoint=null; drawOverlay(); status("Seleção retangular definida.");
    } else if (activeTool==="lasso" && lassoPoints.length) {
      lassoPoints.push(p); setLassoSelection(lassoPoints); lassoPoints=[]; drawOverlay(); status("Seleção por laço definida.");
    } else if (activeTool==="move" && moving) {
      moveEnd=p; const dx=moveEnd.x-moveOrigin.x, dy=moveEnd.y-moveOrigin.y; moving=false;
      if (dx||dy) applyTransform(dx,dy,1,0,false,false); else drawOverlay();
      moveOrigin=moveEnd=null;
    }
  });
  overlay.addEventListener("pointercancel",()=>{dragStart=dragPoint=null;lassoPoints=[];moving=false;drawOverlay();});

  for (const [name,button] of Object.entries(toolButtons)) if (button) button.addEventListener("click",()=>setTool(name));
  undoBtn?.addEventListener("click",()=>API.undo());
  redoBtn?.addEventListener("click",()=>API.redo());
  deselectBtn?.addEventListener("click",clearSelection);
  fillBtn?.addEventListener("click",fillSelection);
  deleteBtn?.addEventListener("click",deleteSelection);
  applyTransformBtn?.addEventListener("click",()=>applyTransform(
    Number(transformX.value)||0, Number(transformY.value)||0,
    Math.max(.05,(Number(transformScale.value)||100)/100), Number(transformRotate.value)||0,
    Boolean(flipH.checked), Boolean(flipV.checked)
  ));
  layerOpacity?.addEventListener("input",()=>{
    const value=Math.max(0,Math.min(100,Number(layerOpacity.value)||0)); layerOpacityLabel.textContent=value;
    API.setLayerOpacity(API.getActiveLayer(),value/100);
  });
  layerBlend?.addEventListener("change",()=>API.setLayerBlendMode(API.getActiveLayer(),layerBlend.value));

  window.addEventListener("ch-studio-layer-changed",syncLayerControls);
  window.addEventListener("ch-studio-frame-changed",()=>{clearSelection();syncLayerControls();});
  window.addEventListener("ch-studio-history",()=>drawOverlay());

  document.addEventListener("keydown", ev => {
    if (ev.target instanceof HTMLInputElement || ev.target instanceof HTMLSelectElement || ev.target instanceof HTMLTextAreaElement) return;
    const key=ev.key.toLowerCase();
    if ((ev.ctrlKey||ev.metaKey) && key==="z") { ev.preventDefault(); ev.shiftKey?API.redo():API.undo(); return; }
    if ((ev.ctrlKey||ev.metaKey) && key==="d") { ev.preventDefault(); clearSelection(); return; }
    if (ev.key==="Delete"||ev.key==="Backspace") { if (anySelection()) { ev.preventDefault(); deleteSelection(); } return; }
    if (key==="m") setTool("rect");
    else if (key==="l") setTool("lasso");
    else if (key==="v") setTool("move");
    else if (key==="i") setTool("eyedropper");
    else if (key==="g") setTool("bucket");
  });

  syncLayerControls();
  drawOverlay();
  window.CH_PHOTOSHOP_TOOLS = {
    contract:"CH_CHARACTER_PHOTOSHOP_TOOLS_V0",
    clearSelection,
    hasSelection:anySelection,
    applyTransform,
    fillSelection,
    deleteSelection
  };
})();
