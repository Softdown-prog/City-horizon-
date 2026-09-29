(() => {
  const API = window.CH_STUDIO_API;
  const PS = window.CH_PHOTOSHOP_TOOLS;
  if (!API || !PS) {
    console.error("CH Photoshop Layers V2 requires CH_STUDIO_API and CH_PHOTOSHOP_TOOLS");
    return;
  }

  const W = API.width || 48;
  const H = API.height || 64;
  const CORE_LAYERS = [...API.layers];
  const HISTORY_LIMIT = 40;
  const BLENDS = ["source-over","multiply","screen","overlay","darken","lighten","soft-light","hard-light","difference"];

  const coreGetOpacity = API.getLayerOpacity.bind(API);
  const coreSetOpacity = API.setLayerOpacity.bind(API);
  const coreGetBlend = API.getLayerBlendMode.bind(API);
  const coreSetBlend = API.setLayerBlendMode.bind(API);
  const coreComposite = API.getCompositeCanvas.bind(API);
  const coreRedraw = API.redraw.bind(API);

  const initialOpacity = Object.fromEntries(CORE_LAYERS.map(name => [name, coreGetOpacity(name)]));
  const initialBlend = Object.fromEntries(CORE_LAYERS.map(name => [name, coreGetBlend(name)]));

  const view = document.getElementById("view");
  const parent = view?.parentElement;
  if (!view || !parent) return;

  const stackView = document.createElement("canvas");
  stackView.id = "photoshopLayerStackView";
  stackView.width = W; stackView.height = H;
  Object.assign(stackView.style, {
    position:"absolute", inset:"0", width:"480px", height:"640px",
    imageRendering:"pixelated", pointerEvents:"none", zIndex:"1"
  });
  view.after(stackView);
  const sctx = stackView.getContext("2d");
  sctx.imageSmoothingEnabled = false;

  const maskEditView = document.createElement("canvas");
  maskEditView.id = "photoshopMaskEditView";
  maskEditView.width = W; maskEditView.height = H;
  Object.assign(maskEditView.style, {
    position:"absolute", inset:"0", width:"480px", height:"640px",
    imageRendering:"pixelated", pointerEvents:"none", cursor:"crosshair", zIndex:"6"
  });
  parent.appendChild(maskEditView);
  const mectx = maskEditView.getContext("2d");
  mectx.imageSmoothingEnabled = false;

  const canonicalPanel = document.getElementById("layers")?.closest(".panel");
  if (canonicalPanel) canonicalPanel.style.display = "none";

  const right = document.querySelector("aside.right");
  const firstPhotoshopPanel = [...right.querySelectorAll(".panel")].find(p => p.textContent.includes("Photoshop · Etapa 1"));
  const panel = document.createElement("div");
  panel.className = "panel";
  panel.innerHTML = `
    <h3>Photoshop · Etapa 2</h3>
    <div class="tool-grid">
      <button id="ps2Duplicate">Duplicar camada</button>
      <button id="ps2NewGroup">Novo grupo</button>
      <button id="ps2Clip">Clipping mask</button>
      <button id="ps2Merge">Merge seguro</button>
      <button id="ps2Flatten">Flatten seguro</button>
      <button id="ps2Restore">Reexibir fontes</button>
      <button id="ps2Undo">Undo stack</button>
      <button id="ps2Redo">Redo stack</button>
    </div>
    <div class="stack" style="margin-top:10px">
      <label>Grupo <select id="ps2Group"></select></label>
      <label>Opacidade da camada <span id="ps2OpacityLabel">100</span>%<input id="ps2Opacity" type="range" min="0" max="100" value="100"></label>
      <label>Blend mode <select id="ps2Blend">${BLENDS.map(v => `<option value="${v}">${v === "source-over" ? "Normal" : v}</option>`).join("")}</select></label>
      <div class="row"><label class="grow">X <input id="ps2X" type="number" step="1" value="0"></label><label class="grow">Y <input id="ps2Y" type="number" step="1" value="0"></label></div>
      <div class="row"><label class="grow">Escala % <input id="ps2Scale" type="number" step="5" value="100"></label><label class="grow">Rotação ° <input id="ps2Rotate" type="number" step="15" value="0"></label></div>
      <div class="row"><label><input id="ps2FlipH" type="checkbox"> Flip H</label><label><input id="ps2FlipV" type="checkbox"> Flip V</label></div>
      <div class="row"><button id="ps2ApplyTransform">Atualizar transform</button><button id="ps2ResetTransform">Reset transform</button></div>
      <div class="row"><button id="ps2MaskWhite">Máscara branca</button><button id="ps2MaskAlpha">Máscara da alfa</button></div>
      <div class="row"><button id="ps2MaskInvert">Inverter máscara</button><button id="ps2MaskRemove">Remover máscara</button></div>
      <div class="row"><button id="ps2MaskEdit">Editar máscara</button><button id="ps2MaskColor">Pincel máscara: preto</button></div>
    </div>
    <div id="ps2Stack" style="margin-top:10px"></div>
    <div id="ps2Status" class="status photoshop-note" style="margin-top:8px">Stack avançado pronto.</div>
    <div class="hint">Transform, masks, clipping e grupos são não destrutivos. Merge/flatten criam uma nova camada rasterizada e preservam as fontes ocultas.</div>
  `;
  firstPhotoshopPanel?.after(panel);

  const $ = id => document.getElementById(id);
  const statusEl = $("ps2Status");
  const stackEl = $("ps2Stack");
  const groupSelect = $("ps2Group");
  const opacityInput = $("ps2Opacity");
  const opacityLabel = $("ps2OpacityLabel");
  const blendSelect = $("ps2Blend");
  const txInput = $("ps2X"), tyInput = $("ps2Y"), scaleInput = $("ps2Scale"), rotateInput = $("ps2Rotate");
  const flipHInput = $("ps2FlipH"), flipVInput = $("ps2FlipV");

  let sequence = 0;
  let currentFrameKey = API.getFrameKey();
  let editingMask = false;
  let maskPaintValue = 0;
  let maskDrawing = false;
  let maskLast = null;
  const frameStates = new Map();
  const histories = new Map();

  function blankCanvas() {
    const c = document.createElement("canvas"); c.width=W; c.height=H;
    c.getContext("2d").imageSmoothingEnabled=false; return c;
  }
  function cloneCanvas(source) {
    const c=blankCanvas(); if(source) c.getContext("2d").drawImage(source,0,0); return c;
  }
  function makeMaskWhite() {
    const c=blankCanvas(), x=c.getContext("2d"); x.fillStyle="#fff"; x.fillRect(0,0,W,H); return c;
  }
  function transformDefaults() { return {x:0,y:0,scale:1,rotation:0,flipH:false,flipV:false}; }
  function coreEntry(name) {
    return {id:`core:${name}`,name,kind:"canonical",sourceName:name,visible:true,opacity:initialOpacity[name]??1,blend:initialBlend[name]||"source-over",clip:false,groupId:null,mask:null,transform:transformDefaults()};
  }
  function defaultState() {
    const entries = Object.fromEntries(CORE_LAYERS.map(name => [`core:${name}`,coreEntry(name)]));
    return {order:CORE_LAYERS.map(name=>`core:${name}`),entries,groups:{},selectedId:`core:${API.getActiveLayer()||"paint_over"}`};
  }
  let state = defaultState();

  function cloneEntry(entry) {
    return {...entry,transform:{...entry.transform},mask:entry.mask?cloneCanvas(entry.mask):null,canvas:entry.canvas?cloneCanvas(entry.canvas):null};
  }
  function cloneState(source=state) {
    const entries={}; for(const [id,e] of Object.entries(source.entries)) entries[id]=cloneEntry(e);
    const groups={}; for(const [id,g] of Object.entries(source.groups)) groups[id]={...g};
    return {order:[...source.order],entries,groups,selectedId:source.selectedId};
  }
  function history() {
    if(!histories.has(currentFrameKey)) histories.set(currentFrameKey,{undo:[],redo:[]});
    return histories.get(currentFrameKey);
  }
  function checkpoint(reason) {
    const h=history(); h.undo.push({reason,state:cloneState()}); if(h.undo.length>HISTORY_LIMIT) h.undo.shift(); h.redo.length=0;
  }
  function stackUndo() {
    const h=history(); if(!h.undo.length){status("Nada para desfazer no stack.");return;}
    h.redo.push({reason:"redo",state:cloneState()}); const item=h.undo.pop(); state=cloneState(item.state); renderUi(); status(`Stack desfeito: ${item.reason}.`);
  }
  function stackRedo() {
    const h=history(); if(!h.redo.length){status("Nada para refazer no stack.");return;}
    h.undo.push({reason:"undo",state:cloneState()}); const item=h.redo.pop(); state=cloneState(item.state); renderUi(); status("Stack refeito.");
  }
  function status(message){ statusEl.textContent=message; API.setStatus(message); }
  function entry(id=state.selectedId){ return state.entries[id]||null; }
  function groupFor(e){ return e?.groupId ? state.groups[e.groupId]||null : null; }

  function sourceCanvas(e) {
    return e.kind==="canonical" ? API.getLayerCanvas(e.sourceName) : e.canvas;
  }
  function alphaBounds(canvas) {
    const data=canvas.getContext("2d").getImageData(0,0,W,H).data;
    let minX=W,minY=H,maxX=-1,maxY=-1;
    for(let y=0;y<H;y++) for(let x=0;x<W;x++) if(data[(y*W+x)*4+3]){minX=Math.min(minX,x);minY=Math.min(minY,y);maxX=Math.max(maxX,x);maxY=Math.max(maxY,y);}
    return maxX<0?{cx:W/2,cy:H/2}:{cx:(minX+maxX+1)/2,cy:(minY+maxY+1)/2};
  }
  function transformed(source,t) {
    const out=blankCanvas(), x=out.getContext("2d"), b=alphaBounds(source);
    x.translate(b.cx+t.x,b.cy+t.y); x.rotate(t.rotation*Math.PI/180); x.scale(t.scale*(t.flipH?-1:1),t.scale*(t.flipV?-1:1)); x.translate(-b.cx,-b.cy); x.drawImage(source,0,0); return out;
  }
  function renderedEntry(e, previous=null) {
    const src=sourceCanvas(e); if(!src) return blankCanvas();
    const out=transformed(src,e.transform);
    if(e.mask){const mask=transformed(e.mask,e.transform);const x=out.getContext("2d");x.globalCompositeOperation="destination-in";x.drawImage(mask,0,0);x.globalCompositeOperation="source-over";}
    if(e.clip&&previous){const x=out.getContext("2d");x.globalCompositeOperation="destination-in";x.drawImage(previous,0,0);x.globalCompositeOperation="source-over";}
    return out;
  }
  function renderStackTo(target, includeOnlyArt=true) {
    const x=target.getContext("2d"); x.clearRect(0,0,W,H); x.imageSmoothingEnabled=false;
    let previous=null;
    for(const id of state.order){
      const e=state.entries[id]; if(!e||!e.visible) continue;
      const g=groupFor(e); if(g&&g.visible===false) continue;
      const layer=renderedEntry(e,previous); previous=layer;
      x.save(); x.globalAlpha=(e.opacity??1)*(g?.opacity??1); x.globalCompositeOperation=BLENDS.includes(e.blend)?e.blend:"source-over"; x.drawImage(layer,0,0); x.restore();
    }
    return target;
  }
  function renderStack(){ renderStackTo(stackView); renderMaskEditor(); }
  function combinedCanvas(){const c=blankCanvas();const x=c.getContext("2d");x.drawImage(view,0,0);x.drawImage(stackView,0,0);return c;}

  function zeroCore(){ for(const name of CORE_LAYERS) coreSetOpacity(name,0); coreRedraw(); }
  zeroCore();
  const previousGetComposite = API.getCompositeCanvas;
  API.getCompositeCanvas = combinedCanvas;
  API.getLayerOpacity = name => state.entries[`core:${name}`]?.opacity ?? coreGetOpacity(name);
  API.setLayerOpacity = (name,value) => {const e=state.entries[`core:${name}`];if(!e)return false;e.opacity=Math.max(0,Math.min(1,Number(value)));renderUi(false);return true;};
  API.getLayerBlendMode = name => state.entries[`core:${name}`]?.blend ?? coreGetBlend(name);
  API.setLayerBlendMode = (name,value) => {const e=state.entries[`core:${name}`];if(!e)return false;e.blend=BLENDS.includes(value)?value:"source-over";renderUi(false);return true;};
  API.redraw = () => {coreRedraw();renderStack();};

  function selectedSourceAlphaMask(){
    const e=entry(); if(!e)return null; const src=sourceCanvas(e), out=blankCanvas(), data=src.getContext("2d").getImageData(0,0,W,H).data, image=out.getContext("2d").createImageData(W,H);
    for(let i=0;i<W*H;i++){const a=data[i*4+3],p=i*4;image.data[p]=image.data[p+1]=image.data[p+2]=255;image.data[p+3]=a;}
    out.getContext("2d").putImageData(image,0,0);return out;
  }
  function renderMaskEditor(){
    mectx.clearRect(0,0,W,H); if(!editingMask)return; const e=entry(); if(!e?.mask)return;
    mectx.save();mectx.globalAlpha=.38;mectx.drawImage(e.mask,0,0);mectx.restore();
  }
  function maskPoint(ev){const r=maskEditView.getBoundingClientRect();return{x:Math.max(0,Math.min(W-1,Math.floor((ev.clientX-r.left)*W/r.width))),y:Math.max(0,Math.min(H-1,Math.floor((ev.clientY-r.top)*H/r.height)))}};
  function maskStamp(p){const e=entry();if(!e?.mask)return;const size=Math.max(1,Number(document.getElementById("brushSize")?.value||1)),half=Math.floor(size/2),x=e.mask.getContext("2d");x.fillStyle=`rgb(${maskPaintValue},${maskPaintValue},${maskPaintValue})`;x.fillRect(p.x-half,p.y-half,size,size);}
  function maskSegment(a,b){let x0=a.x,y0=a.y,x1=b.x,y1=b.y;const dx=Math.abs(x1-x0),sx=x0<x1?1:-1,dy=-Math.abs(y1-y0),sy=y0<y1?1:-1;let err=dx+dy;while(true){maskStamp({x:x0,y:y0});if(x0===x1&&y0===y1)break;const e2=2*err;if(e2>=dy){err+=dy;x0+=sx}if(e2<=dx){err+=dx;y0+=sy}}}
  maskEditView.addEventListener("pointerdown",ev=>{if(!editingMask||!entry()?.mask)return;checkpoint("paint_layer_mask");maskDrawing=true;maskLast=maskPoint(ev);maskEditView.setPointerCapture(ev.pointerId);maskStamp(maskLast);renderStack();});
  maskEditView.addEventListener("pointermove",ev=>{if(!maskDrawing)return;const p=maskPoint(ev);maskSegment(maskLast||p,p);maskLast=p;renderStack();});
  maskEditView.addEventListener("pointerup",()=>{maskDrawing=false;maskLast=null;saveFrameState();});
  maskEditView.addEventListener("pointercancel",()=>{maskDrawing=false;maskLast=null;});

  function selectEntry(id){if(!state.entries[id])return;state.selectedId=id;const e=entry();if(e.kind==="canonical")API.setActiveLayer(e.sourceName);syncControls();renderStackList();}
  function uniqueId(prefix){sequence+=1;return`${prefix}_${Date.now().toString(36)}_${sequence}`;}
  function duplicateSelected(){const src=entry();if(!src)return;checkpoint("duplicate_layer");const id=uniqueId("dup"),copy=cloneEntry(src);copy.id=id;copy.kind="duplicate";copy.sourceName=null;copy.canvas=cloneCanvas(sourceCanvas(src));copy.name=`${src.name} copy`;state.entries[id]=copy;const at=state.order.indexOf(src.id);state.order.splice(at+1,0,id);selectEntry(id);renderUi();status(`Camada duplicada: ${copy.name}.`);}
  function createGroup(){const name=prompt("Nome do grupo",`Grupo ${Object.keys(state.groups).length+1}`);if(!name)return;checkpoint("new_group");const id=uniqueId("group");state.groups[id]={id,name,visible:true,opacity:1};entry().groupId=id;renderUi();status(`Grupo criado: ${name}.`);}
  function setGroup(id){checkpoint("assign_group");entry().groupId=id||null;renderUi();}
  function toggleClip(){const e=entry();if(!e)return;checkpoint("clipping_mask");e.clip=!e.clip;renderUi();status(`Clipping mask ${e.clip?"ativado":"desativado"} em ${e.name}.`);}
  function addWhiteMask(){const e=entry();if(!e)return;checkpoint("layer_mask_white");e.mask=makeMaskWhite();renderUi();status(`Máscara branca adicionada a ${e.name}.`);}
  function addAlphaMask(){const e=entry();if(!e)return;checkpoint("layer_mask_alpha");e.mask=selectedSourceAlphaMask();renderUi();status(`Máscara criada da alfa de ${e.name}.`);}
  function invertMask(){const e=entry();if(!e?.mask)return;checkpoint("invert_layer_mask");const x=e.mask.getContext("2d"),img=x.getImageData(0,0,W,H);for(let i=0;i<W*H;i++){const p=i*4,v=255-img.data[p];img.data[p]=img.data[p+1]=img.data[p+2]=v;img.data[p+3]=255;}x.putImageData(img,0,0);renderUi();}
  function removeMask(){const e=entry();if(!e?.mask)return;checkpoint("remove_layer_mask");e.mask=null;editingMask=false;maskEditView.style.pointerEvents="none";renderUi();}
  function toggleMaskEdit(){const e=entry();if(!e?.mask){status("Adicione uma layer mask primeiro.");return;}editingMask=!editingMask;maskEditView.style.pointerEvents=editingMask?"auto":"none";$("ps2MaskEdit").classList.toggle("active",editingMask);renderMaskEditor();status(editingMask?"Edição de layer mask ativa.":"Edição de layer mask encerrada.");}
  function toggleMaskColor(){maskPaintValue=maskPaintValue===0?255:0;$("ps2MaskColor").textContent=`Pincel máscara: ${maskPaintValue===0?"preto":"branco"}`;}

  function updateTransform(){const e=entry();if(!e)return;checkpoint("non_destructive_transform");e.transform={x:Number(txInput.value)||0,y:Number(tyInput.value)||0,scale:Math.max(.05,(Number(scaleInput.value)||100)/100),rotation:Number(rotateInput.value)||0,flipH:flipHInput.checked,flipV:flipVInput.checked};renderUi();status(`Transform não destrutivo atualizado em ${e.name}.`);}
  function resetTransform(){const e=entry();if(!e)return;checkpoint("reset_transform");e.transform=transformDefaults();renderUi();}

  function compositedPair(below,top){const c=blankCanvas(),x=c.getContext("2d");const b=renderedEntry(below,null);x.save();x.globalAlpha=below.opacity??1;x.globalCompositeOperation=below.blend||"source-over";x.drawImage(b,0,0);x.restore();const t=renderedEntry(top,b);x.save();x.globalAlpha=top.opacity??1;x.globalCompositeOperation=top.blend||"source-over";x.drawImage(t,0,0);x.restore();return c;}
  function mergeSafe(){const top=entry(),idx=state.order.indexOf(top?.id);if(!top||idx<=0){status("Merge exige uma camada abaixo.");return;}const below=state.entries[state.order[idx-1]];checkpoint("safe_merge");const id=uniqueId("merged"),c=compositedPair(below,top);below.visible=false;top.visible=false;state.entries[id]={id,name:`Merged ${below.name} + ${top.name}`,kind:"duplicate",canvas:c,visible:true,opacity:1,blend:"source-over",clip:false,groupId:top.groupId||below.groupId||null,mask:null,transform:transformDefaults()};state.order.splice(idx+1,0,id);selectEntry(id);renderUi();status("Merge seguro criado; fontes foram preservadas ocultas.");}
  function flattenSafe(){checkpoint("safe_flatten");const c=blankCanvas();renderStackTo(c);for(const e of Object.values(state.entries))e.visible=false;const id=uniqueId("flattened");state.entries[id]={id,name:"Flattened art",kind:"duplicate",canvas:c,visible:true,opacity:1,blend:"source-over",clip:false,groupId:null,mask:null,transform:transformDefaults()};state.order.push(id);selectEntry(id);renderUi();status("Flatten seguro criado; stack fonte continua preservado oculto.");}
  function restoreSources(){checkpoint("restore_sources");for(const e of Object.values(state.entries)){if(e.kind==="canonical")e.visible=true;else if(e.name==="Flattened art"||e.name.startsWith("Merged "))e.visible=false;}renderUi();status("Camadas-fonte canônicas reexibidas.");}

  function buildGroupOptions(){groupSelect.innerHTML='<option value="">Sem grupo</option>';for(const g of Object.values(state.groups)){const o=document.createElement("option");o.value=g.id;o.textContent=g.name;groupSelect.appendChild(o);}groupSelect.value=entry()?.groupId||"";}
  function syncControls(){const e=entry();if(!e)return;opacityInput.value=Math.round((e.opacity??1)*100);opacityLabel.textContent=opacityInput.value;blendSelect.value=e.blend||"source-over";txInput.value=e.transform.x;tyInput.value=e.transform.y;scaleInput.value=Math.round(e.transform.scale*100);rotateInput.value=e.transform.rotation;flipHInput.checked=e.transform.flipH;flipVInput.checked=e.transform.flipV;buildGroupOptions();$("ps2Clip").classList.toggle("active",e.clip);}
  function renderStackList(){stackEl.innerHTML="";for(const id of [...state.order].reverse()){const e=state.entries[id];if(!e)continue;const row=document.createElement("div");row.className=`layer ${id===state.selectedId?"selected":""}`;const check=document.createElement("input");check.type="checkbox";check.checked=e.visible;check.addEventListener("click",ev=>ev.stopPropagation());check.addEventListener("change",()=>{checkpoint("layer_visibility");e.visible=check.checked;renderUi(false);});const label=document.createElement("span");label.textContent=e.name;const flags=[];if(e.mask)flags.push("mask");if(e.clip)flags.push("clip");if(e.groupId)flags.push("grp");if(e.transform.x||e.transform.y||e.transform.scale!==1||e.transform.rotation||e.transform.flipH||e.transform.flipV)flags.push("T");const meta=document.createElement("small");meta.textContent=flags.join(" · ")||e.kind;row.append(check,label,meta);row.addEventListener("click",()=>selectEntry(id));stackEl.appendChild(row);}}
  function renderUi(full=true){renderStack();if(full){renderStackList();syncControls();}saveFrameState();}

  function saveFrameState(){frameStates.set(currentFrameKey,cloneState());}
  function loadFrameState(key){currentFrameKey=key;state=frameStates.has(key)?cloneState(frameStates.get(key)):defaultState();editingMask=false;maskEditView.style.pointerEvents="none";renderUi();}
  window.addEventListener("ch-studio-frame-changed",ev=>{saveFrameState();loadFrameState(ev.detail?.key||API.getFrameKey());});
  window.addEventListener("ch-studio-layer-changed",ev=>{const id=`core:${ev.detail?.layer}`;if(state.entries[id]){state.selectedId=id;renderStackList();syncControls();}});
  window.addEventListener("ch-studio-history",()=>renderStack());

  function downloadCanvas(canvas,name){canvas.toBlob(blob=>{const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);},"image/png");}
  function selectedRendered(){const e=entry();if(!e)return blankCanvas();const idx=state.order.indexOf(e.id),prev=idx>0?renderedEntry(state.entries[state.order[idx-1]],null):null;return renderedEntry(e,prev);}
  function captureExport(id,handler){const b=$(id);if(!b)return;b.addEventListener("click",ev=>{ev.preventDefault();ev.stopImmediatePropagation();handler();},true);}
  captureExport("exportLayer",()=>downloadCanvas(selectedRendered(),`${API.getFrameKey().replace(":","_").toLowerCase()}_${entry()?.name.replaceAll(" ","_")||"layer"}.png`));
  captureExport("exportComposite",()=>downloadCanvas(combinedCanvas(),`${API.getFrameKey().replace(":","_").toLowerCase()}_character.png`));
  captureExport("exportCompositeObject",()=>{const c=blankCanvas(),x=c.getContext("2d"),back=$("objectBackView"),front=$("objectFrontView");if(back)x.drawImage(back,0,0);x.drawImage(combinedCanvas(),0,0);if(front)x.drawImage(front,0,0);downloadCanvas(c,`${API.getFrameKey().replace(":","_").toLowerCase()}_character_with_object.png`);});
  $("exportSpec")?.addEventListener("click",()=>{for(const name of CORE_LAYERS){const e=state.entries[`core:${name}`];coreSetOpacity(name,e?.opacity??1);coreSetBlend(name,e?.blend||"source-over");}setTimeout(zeroCore,0);},true);

  function exportStackJson(){const safe=cloneState();for(const e of Object.values(safe.entries)){delete e.canvas;delete e.mask;}const payload={contract:"CH_CHARACTER_LAYER_STACK_V0",frame:currentFrameKey,order:safe.order,entries:safe.entries,groups:safe.groups,selectedId:safe.selectedId};const blob=new Blob([JSON.stringify(payload,null,2)+"\n"],{type:"application/json"}),a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download=`${currentFrameKey.replace(":","_").toLowerCase()}_layer_stack.json`;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);}
  const exportBtn=document.createElement("button");exportBtn.textContent="Exportar stack JSON";exportBtn.style.width="100%";exportBtn.addEventListener("click",exportStackJson);panel.appendChild(exportBtn);

  $("ps2Duplicate").addEventListener("click",duplicateSelected);
  $("ps2NewGroup").addEventListener("click",createGroup);
  $("ps2Clip").addEventListener("click",toggleClip);
  $("ps2Merge").addEventListener("click",mergeSafe);
  $("ps2Flatten").addEventListener("click",flattenSafe);
  $("ps2Restore").addEventListener("click",restoreSources);
  $("ps2Undo").addEventListener("click",stackUndo);
  $("ps2Redo").addEventListener("click",stackRedo);
  groupSelect.addEventListener("change",()=>setGroup(groupSelect.value));
  opacityInput.addEventListener("pointerdown",()=>checkpoint("layer_opacity_v2"));
  opacityInput.addEventListener("input",()=>{const e=entry();if(!e)return;e.opacity=Math.max(0,Math.min(1,Number(opacityInput.value)/100));opacityLabel.textContent=opacityInput.value;renderUi(false);});
  blendSelect.addEventListener("focus",()=>checkpoint("layer_blend_v2"));
  blendSelect.addEventListener("change",()=>{const e=entry();if(!e)return;e.blend=BLENDS.includes(blendSelect.value)?blendSelect.value:"source-over";renderUi();});
  $("ps2ApplyTransform").addEventListener("click",updateTransform);
  $("ps2ResetTransform").addEventListener("click",resetTransform);
  $("ps2MaskWhite").addEventListener("click",addWhiteMask);
  $("ps2MaskAlpha").addEventListener("click",addAlphaMask);
  $("ps2MaskInvert").addEventListener("click",invertMask);
  $("ps2MaskRemove").addEventListener("click",removeMask);
  $("ps2MaskEdit").addEventListener("click",toggleMaskEdit);
  $("ps2MaskColor").addEventListener("click",toggleMaskColor);

  function loop(){renderStack();requestAnimationFrame(loop);} requestAnimationFrame(loop);
  renderUi();
  status("Photoshop Etapa 2 pronta: grupos, masks, clipping, transform não destrutivo, duplicate, merge e flatten seguros.");

  window.CH_PHOTOSHOP_LAYER_STACK = {
    contract:"CH_CHARACTER_LAYER_STACK_V0",
    getState:()=>cloneState(),
    render:renderStack,
    duplicateSelected,
    mergeSafe,
    flattenSafe,
    stackUndo,
    stackRedo
  };
})();
