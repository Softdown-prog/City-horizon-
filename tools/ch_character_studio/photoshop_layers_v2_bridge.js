(() => {
  const API = window.CH_STUDIO_API;
  const STACK = window.CH_PHOTOSHOP_LAYER_STACK;
  const view = document.getElementById('view');
  const stackView = document.getElementById('photoshopLayerStackView');
  const baseFile = document.getElementById('baseFile');
  if (!API || !STACK || !view || !stackView) return;

  const W = API.width || 48, H = API.height || 64;
  const base = document.createElement('canvas');
  base.width = W; base.height = H;
  const bctx = base.getContext('2d');
  const vctx = view.getContext('2d');
  bctx.imageSmoothingEnabled = false;
  vctx.imageSmoothingEnabled = false;

  function captureBaseFromView() {
    bctx.clearRect(0,0,W,H);
    bctx.drawImage(view,0,0);
  }

  function present() {
    vctx.clearRect(0,0,W,H);
    vctx.globalAlpha = 1;
    vctx.globalCompositeOperation = 'source-over';
    vctx.drawImage(base,0,0);
    vctx.drawImage(stackView,0,0);
    // The main view becomes the authoritative visible composite. Clear the
    // helper canvas afterwards so legacy export handlers cannot double-compose.
    stackView.getContext('2d').clearRect(0,0,W,H);
  }

  function mainCompositeCopy() {
    const c=document.createElement('canvas'); c.width=W; c.height=H;
    c.getContext('2d').drawImage(view,0,0); return c;
  }

  captureBaseFromView();
  API.getCompositeCanvas = mainCompositeCopy;

  window.addEventListener('ch-studio-frame-changed', () => {
    // Studio has already redrawn the new Blender/base pass before dispatching.
    captureBaseFromView();
  });

  if (baseFile) {
    baseFile.addEventListener('change', event => {
      const file=event.target.files?.[0]; if(!file)return;
      const img=new Image();
      img.onload=()=>{
        bctx.clearRect(0,0,W,H);
        bctx.drawImage(img,0,0,W,H);
        URL.revokeObjectURL(img.src);
      };
      img.src=URL.createObjectURL(file);
    });
  }

  function loop() {
    STACK.render();
    present();
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);

  window.CH_PHOTOSHOP_LAYER_STACK_BRIDGE = {
    contract:'CH_CHARACTER_LAYER_STACK_BRIDGE_V0',
    captureBase:captureBaseFromView,
    present
  };
})();
