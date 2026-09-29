(() => {
  const W = 48, H = 64;
  const MASKS = window.CH_CHARACTER_COLOR_MASKS;
  const HELD = window.CH_HELD_OBJECTS;
  if (!MASKS || !HELD) return;

  const direction = document.getElementById("direction");
  const frame = document.getElementById("frame");
  const mainView = document.getElementById("view");
  const backView = document.getElementById("objectBackView");
  const frontView = document.getElementById("objectFrontView");
  const maskView = document.getElementById("maskView");
  const backCtx = backView.getContext("2d");
  const frontCtx = frontView.getContext("2d");
  const maskViewCtx = maskView.getContext("2d");
  backCtx.imageSmoothingEnabled = false;
  frontCtx.imageSmoothingEnabled = false;
  maskViewCtx.imageSmoothingEnabled = false;

  const maskCanvases = new Map();
  for (const bank of ["appearance", "clothing"]) {
    const canvas = document.createElement("canvas");
    canvas.width = W; canvas.height = H;
    maskCanvases.set(bank, canvas);
  }
  const maskStore = new Map();
  let loadedMaskKey = `${direction.value}:${frame.value}`;
  let landmarks = null;
  let lastObjectRender = {front:HELD.blankFrame(), back:HELD.blankFrame(), mask:HELD.blankFrame(), placement:null};
  let maskTool = "paint";
  let maskDrawing = false;
  let lastMaskPoint = null;

  const objectState = {
    enabled: false,
    assetId: "held_object_new",
    socket: "right_hand",
    depth: "auto",
    gripAnchor: [0, 0],
    offset: [0, 0],
    visual: null,
    mask: null,
    visualName: null,
    maskName: null
  };

  const bankSelect = document.getElementById("maskBank");
  const channelSelect = document.getElementById("maskChannel");
  const maskPreview = document.getElementById("maskPreview");
  const maskPaintBtn = document.getElementById("maskPaintBtn");
  const maskEraseBtn = document.getElementById("maskEraseBtn");
  const maskFillVisible = document.getElementById("maskFillVisible");
  const maskClear = document.getElementById("maskClear");
  const maskExport = document.getElementById("exportMask");
  const maskExportAll = document.getElementById("exportAllMasks");
  const maskStatus = document.getElementById("maskStatus");

  const objectEnabled = document.getElementById("heldObjectEnabled");
  const objectId = document.getElementById("heldObjectId");
  const objectSocket = document.getElementById("heldObjectSocket");
  const objectDepth = document.getElementById("heldObjectDepth");
  const objectFile = document.getElementById("heldObjectFile");
  const objectMaskFile = document.getElementById("heldObjectMaskFile");
  const gripX = document.getElementById("heldGripX");
  const gripY = document.getElementById("heldGripY");
  const offsetX = document.getElementById("heldOffsetX");
  const offsetY = document.getElementById("heldOffsetY");
  const debugSocket = document.getElementById("showHandSocket");
  const objectStatus = document.getElementById("heldObjectStatus");
  const exportCompositeObject = document.getElementById("exportCompositeObject");
  const exportObjectConfig = document.getElementById("exportObjectConfig");
  const landmarksFile = document.getElementById("landmarksFile");

  function key() { return `${direction.value}:${frame.value}`; }
  function currentFrameLandmarks() { return landmarks?.frames?.[key()] || null; }
  function maskCanvas(bank) { return maskCanvases.get(bank) || null; }
  function snapshot(canvas) { return canvas.getContext("2d").getImageData(0, 0, W, H); }
  function put(canvas, image) {
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, W, H);
    if (image) ctx.putImageData(image, 0, 0);
  }

  function saveMasks() {
    maskStore.set(loadedMaskKey, {
      appearance: snapshot(maskCanvas("appearance")),
      clothing: snapshot(maskCanvas("clothing"))
    });
  }

  function loadMasks(nextKey) {
    saveMasks();
    loadedMaskKey = nextKey;
    const saved = maskStore.get(nextKey);
    put(maskCanvas("appearance"), saved?.appearance || MASKS.blank());
    put(maskCanvas("clothing"), saved?.clothing || MASKS.blank());
    renderObject();
    renderMaskPreview();
  }

  function selectedBankImage() {
    if (bankSelect.value === "held_object") return lastObjectRender.mask;
    return snapshot(maskCanvas(bankSelect.value));
  }

  function rebuildChannelOptions() {
    const bank = MASKS.banks[bankSelect.value];
    channelSelect.innerHTML = "";
    for (const channel of ["R","G","B"]) {
      const option = document.createElement("option");
      option.value = channel;
      option.textContent = `${channel} · ${bank.channels[channel]}`;
      channelSelect.appendChild(option);
    }
    const objectBank = bankSelect.value === "held_object";
    maskPaintBtn.disabled = objectBank;
    maskEraseBtn.disabled = objectBank;
    maskFillVisible.disabled = objectBank;
    maskClear.disabled = objectBank;
    maskStatus.textContent = objectBank
      ? "A máscara do objeto acompanha o PNG importado; sem máscara, pixels opacos usam R automaticamente."
      : `${bank.label}: pinte R/G/B sem luz, AO, outline ou dithering.`;
    renderMaskPreview();
  }

  function channelColor() {
    return {R:"rgba(255,0,0,1)", G:"rgba(0,255,0,1)", B:"rgba(0,0,255,1)"}[channelSelect.value];
  }

  function maskPoint(ev) {
    const rect = maskView.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(W - 1, Math.floor((ev.clientX - rect.left) * W / rect.width))),
      y: Math.max(0, Math.min(H - 1, Math.floor((ev.clientY - rect.top) * H / rect.height)))
    };
  }

  function stampMask(point) {
    const canvas = maskCanvas(bankSelect.value);
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const size = 1;
    if (maskTool === "erase") ctx.clearRect(point.x, point.y, size, size);
    else {
      ctx.fillStyle = channelColor();
      ctx.fillRect(point.x, point.y, size, size);
    }
  }

  function maskSegment(from, to) {
    let x0=from.x, y0=from.y, x1=to.x, y1=to.y;
    const dx=Math.abs(x1-x0), sx=x0<x1?1:-1;
    const dy=-Math.abs(y1-y0), sy=y0<y1?1:-1;
    let err=dx+dy;
    while (true) {
      stampMask({x:x0,y:y0});
      if (x0===x1 && y0===y1) break;
      const e2=2*err;
      if (e2>=dy) {err+=dy; x0+=sx;}
      if (e2<=dx) {err+=dx; y0+=sy;}
    }
  }

  function setMaskTool(next) {
    if (bankSelect.value === "held_object") return;
    maskTool = next;
    maskPaintBtn.classList.toggle("active", next === "paint");
    maskEraseBtn.classList.toggle("active", next === "erase");
    maskView.style.pointerEvents = "auto";
    maskPreview.checked = true;
    renderMaskPreview();
  }

  function fillVisibleAlpha() {
    const canvas = maskCanvas(bankSelect.value);
    if (!canvas) return;
    const src = mainView.getContext("2d").getImageData(0,0,W,H).data;
    const image = canvas.getContext("2d").getImageData(0,0,W,H);
    const rgba = MASKS.channels[channelSelect.value];
    for (let i=0;i<W*H;i++) {
      const a=src[i*4+3];
      if (!a) continue;
      const p=i*4;
      image.data[p]=rgba[0]; image.data[p+1]=rgba[1]; image.data[p+2]=rgba[2]; image.data[p+3]=a;
    }
    canvas.getContext("2d").putImageData(image,0,0);
    renderMaskPreview();
    maskStatus.textContent = `Cobertura visível aplicada em ${bankSelect.value}.${channelSelect.value}. Apague áreas que pertencem a outros papéis.`;
  }

  function renderMaskPreview() {
    maskViewCtx.clearRect(0,0,W,H);
    if (maskPreview.checked) {
      const image = selectedBankImage();
      maskViewCtx.save();
      maskViewCtx.globalAlpha = 0.58;
      maskViewCtx.putImageData(image,0,0);
      maskViewCtx.restore();
    }
    if (debugSocket.checked) drawSocketDebug();
  }

  function drawSocketDebug() {
    const frameData = currentFrameLandmarks();
    const socket = HELD.sockets[objectSocket.value] || HELD.sockets.right_hand;
    const p = frameData?.points?.[socket.landmark];
    if (!Array.isArray(p)) return;
    const x=Math.round(p[0]), y=Math.round(p[1]);
    maskViewCtx.save();
    maskViewCtx.fillStyle = "#ffde59";
    maskViewCtx.fillRect(x-1,y,3,1);
    maskViewCtx.fillRect(x,y-1,1,3);
    maskViewCtx.restore();
  }

  async function fileToImageData(file) {
    const img = new Image();
    const url = URL.createObjectURL(file);
    try {
      await new Promise((resolve,reject) => { img.onload=resolve; img.onerror=reject; img.src=url; });
      const canvas=document.createElement("canvas");
      canvas.width=img.naturalWidth; canvas.height=img.naturalHeight;
      const ctx=canvas.getContext("2d"); ctx.imageSmoothingEnabled=false; ctx.drawImage(img,0,0);
      return ctx.getImageData(0,0,canvas.width,canvas.height);
    } finally {
      URL.revokeObjectURL(url);
    }
  }

  function syncObjectInputs() {
    objectState.enabled = objectEnabled.checked;
    objectState.assetId = objectId.value.trim() || "held_object_new";
    objectState.socket = objectSocket.value;
    objectState.depth = objectDepth.value;
    objectState.gripAnchor = [Number(gripX.value)||0, Number(gripY.value)||0];
    objectState.offset = [Number(offsetX.value)||0, Number(offsetY.value)||0];
    renderObject();
  }

  function renderObject() {
    const frameData = currentFrameLandmarks();
    lastObjectRender = HELD.render(objectState, frameData, MASKS);
    put(backView, lastObjectRender.back);
    put(frontView, lastObjectRender.front);
    if (!objectState.enabled) objectStatus.textContent = "Socket preparado, mas invisível. Ative quando o personagem precisar carregar um objeto.";
    else if (!objectState.visual) objectStatus.textContent = "Objeto ativado; carregue um PNG visual para o socket.";
    else if (!frameData) objectStatus.textContent = "Objeto pronto; carregue landmarks.json para prender o objeto à mão.";
    else objectStatus.textContent = `${objectState.assetId} preso em ${objectState.socket} · ${lastObjectRender.placement?.depth || objectState.depth}.`;
    renderMaskPreview();
  }

  function canvasFromImageData(image) {
    const c=document.createElement("canvas"); c.width=image.width; c.height=image.height;
    c.getContext("2d").putImageData(image,0,0); return c;
  }

  function downloadImageData(image, name) {
    const canvas=canvasFromImageData(image);
    canvas.toBlob(blob => {
      const a=document.createElement("a"); a.href=URL.createObjectURL(blob); a.download=name; a.click();
      setTimeout(()=>URL.revokeObjectURL(a.href),1000);
    },"image/png");
  }

  function exportBank(bank) {
    const image = bank === "held_object" ? lastObjectRender.mask : snapshot(maskCanvas(bank));
    downloadImageData(image, MASKS.maskFileName(bank, direction.value, frame.value));
  }

  function exportComposite() {
    const out=document.createElement("canvas"); out.width=W; out.height=H;
    const ctx=out.getContext("2d"); ctx.imageSmoothingEnabled=false;
    ctx.drawImage(backView,0,0); ctx.drawImage(mainView,0,0); ctx.drawImage(frontView,0,0);
    out.toBlob(blob=>{
      const a=document.createElement("a"); a.href=URL.createObjectURL(blob);
      a.download=`${direction.value.toLowerCase()}_${frame.value}_character_with_object.png`; a.click();
      setTimeout(()=>URL.revokeObjectURL(a.href),1000);
    },"image/png");
  }

  function exportConfig() {
    saveMasks();
    const payload = {
      contract: "CH_CHARACTER_STUDIO_ATTACHMENT_CONFIG_V0",
      colorMasks: {
        contract: MASKS.contract,
        banks: Object.fromEntries(Object.entries(MASKS.banks).map(([name,bank]) => [name,{channels:bank.channels}])),
        editedFrames: [...maskStore.keys()].sort()
      },
      heldObject: {
        contract: HELD.contract,
        enabled: objectState.enabled,
        assetId: objectState.assetId,
        socket: objectState.socket,
        depth: objectState.depth,
        gripAnchor: objectState.gripAnchor,
        offset: objectState.offset,
        visualFile: objectState.visualName,
        maskFile: objectState.maskName,
        fallbackMask: objectState.mask ? null : "opaque_to_R_object_primary"
      }
    };
    const blob=new Blob([JSON.stringify(payload,null,2)+"\n"],{type:"application/json"});
    const a=document.createElement("a"); a.href=URL.createObjectURL(blob); a.download="character_attachments.json"; a.click();
    setTimeout(()=>URL.revokeObjectURL(a.href),1000);
  }

  maskView.addEventListener("pointerdown", ev => {
    if (bankSelect.value === "held_object") return;
    maskDrawing=true; maskView.setPointerCapture(ev.pointerId); lastMaskPoint=maskPoint(ev);
    maskSegment(lastMaskPoint,lastMaskPoint); renderMaskPreview();
  });
  maskView.addEventListener("pointermove", ev => {
    if (!maskDrawing) return;
    const point=maskPoint(ev); maskSegment(lastMaskPoint||point,point); lastMaskPoint=point; renderMaskPreview();
  });
  maskView.addEventListener("pointerup",()=>{maskDrawing=false;lastMaskPoint=null;});
  maskView.addEventListener("pointercancel",()=>{maskDrawing=false;lastMaskPoint=null;});

  direction.addEventListener("change",()=>loadMasks(key()));
  frame.addEventListener("change",()=>loadMasks(key()));
  bankSelect.addEventListener("change", rebuildChannelOptions);
  channelSelect.addEventListener("change", renderMaskPreview);
  maskPreview.addEventListener("change",()=>{
    maskView.style.pointerEvents = maskPreview.checked && bankSelect.value !== "held_object" ? "auto" : "none";
    renderMaskPreview();
  });
  maskPaintBtn.addEventListener("click",()=>setMaskTool("paint"));
  maskEraseBtn.addEventListener("click",()=>setMaskTool("erase"));
  maskFillVisible.addEventListener("click",fillVisibleAlpha);
  maskClear.addEventListener("click",()=>{
    const canvas=maskCanvas(bankSelect.value); if (!canvas) return;
    canvas.getContext("2d").clearRect(0,0,W,H); renderMaskPreview();
  });
  maskExport.addEventListener("click",()=>exportBank(bankSelect.value));
  maskExportAll.addEventListener("click",()=>["appearance","clothing","held_object"].forEach(exportBank));

  for (const element of [objectEnabled,objectId,objectSocket,objectDepth,gripX,gripY,offsetX,offsetY]) {
    element.addEventListener("input",syncObjectInputs);
    element.addEventListener("change",syncObjectInputs);
  }
  debugSocket.addEventListener("change",renderMaskPreview);
  objectFile.addEventListener("change",async ev=>{
    const file=ev.target.files?.[0]; if(!file)return;
    try {
      objectState.visual=await fileToImageData(file); objectState.visualName=file.name;
      gripX.value=Math.floor(objectState.visual.width/2); gripY.value=Math.floor(objectState.visual.height/2);
      objectState.gripAnchor=[Number(gripX.value),Number(gripY.value)];
      if (objectState.mask && (objectState.mask.width!==objectState.visual.width || objectState.mask.height!==objectState.visual.height)) objectState.mask=null;
      renderObject();
    } catch(error) { objectStatus.textContent=`Falha ao carregar objeto: ${error.message}`; }
  });
  objectMaskFile.addEventListener("change",async ev=>{
    const file=ev.target.files?.[0]; if(!file)return;
    try {
      const image=await fileToImageData(file); MASKS.validateObjectMask(image,objectState.visual);
      objectState.mask=image; objectState.maskName=file.name; renderObject();
    } catch(error) { objectStatus.textContent=`Máscara recusada: ${error.message}`; }
  });
  landmarksFile.addEventListener("change",async ev=>{
    const file=ev.target.files?.[0]; if(!file)return;
    try { landmarks=JSON.parse(await file.text()); renderObject(); }
    catch(error) { landmarks=null; objectStatus.textContent=`Landmarks inválidos: ${error.message}`; }
  });
  exportCompositeObject.addEventListener("click",exportComposite);
  exportObjectConfig.addEventListener("click",exportConfig);

  rebuildChannelOptions();
  renderObject();
})();
