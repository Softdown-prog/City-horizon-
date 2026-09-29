(() => {
  const canvas = document.getElementById('spatialView');
  const landmarksFile = document.getElementById('landmarksFile');
  const direction = document.getElementById('direction');
  const frame = document.getElementById('frame');
  const showGround = document.getElementById('showGroundAnchor');
  const showFeet = document.getElementById('showFootAnchors');
  const showFootprint = document.getElementById('showFootprint');
  const showSockets = document.getElementById('showSockets');
  const status = document.getElementById('spatialStatus');
  if (!canvas || !landmarksFile) return;

  const ctx = canvas.getContext('2d');
  ctx.imageSmoothingEnabled = false;
  let packageData = null;

  function key() { return `${direction.value}:${frame.value}`; }
  function frameData() { return packageData?.frames?.[key()] || null; }

  function cross(point, fill) {
    if (!Array.isArray(point)) return;
    const x = Math.round(point[0]), y = Math.round(point[1]);
    ctx.fillStyle = fill;
    ctx.fillRect(x - 2, y, 5, 1);
    ctx.fillRect(x, y - 2, 1, 5);
  }

  function dot(point, fill, radius = 1) {
    if (!Array.isArray(point)) return;
    ctx.fillStyle = fill;
    ctx.beginPath();
    ctx.arc(point[0], point[1], radius, 0, Math.PI * 2);
    ctx.fill();
  }

  function drawPolygon(points) {
    if (!Array.isArray(points) || points.length < 3) return;
    ctx.save();
    ctx.strokeStyle = '#55d6be';
    ctx.globalAlpha = 0.9;
    ctx.lineWidth = 0.7;
    ctx.beginPath();
    ctx.moveTo(points[0][0], points[0][1]);
    for (let i = 1; i < points.length; i++) ctx.lineTo(points[i][0], points[i][1]);
    ctx.closePath();
    ctx.stroke();
    ctx.restore();
  }

  function render() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const data = frameData();
    if (!data) {
      status.textContent = packageData ? `Sem dados espaciais para ${key()}.` : 'Carregue landmarks para validar o contato com o chão.';
      return;
    }
    const anchors = data.anchors || {};
    if (showFootprint.checked) drawPolygon(anchors.footprint?.polygonPx);
    if (showGround.checked) cross(anchors.ground || packageData.groundAnchor, '#ffd65a');
    if (showFeet.checked) {
      dot(anchors.leftFoot || data.points?.foot_L, '#65d98a', 1.2);
      dot(anchors.rightFoot || data.points?.foot_R, '#5aa7ff', 1.2);
      const support = anchors.supportFoot;
      if (support) {
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 0.7;
        ctx.beginPath(); ctx.arc(support[0], support[1], 2.0, 0, Math.PI * 2); ctx.stroke();
      }
    }
    if (showSockets.checked) {
      cross(data.sockets?.left_hand || data.points?.hand_L, '#e76fcb');
      cross(data.sockets?.right_hand || data.points?.hand_R, '#9f7aea');
    }

    const ground = anchors.ground || packageData.groundAnchor;
    const support = anchors.supportFoot;
    if (Array.isArray(ground) && Array.isArray(support)) {
      const dx = support[0] - ground[0], dy = support[1] - ground[1];
      const distance = Math.sqrt(dx * dx + dy * dy);
      const state = distance <= 10 ? 'OK' : 'REVISAR';
      status.textContent = `${key()} · apoio ${anchors.supportFootName || '?'} · distância do anchor ${distance.toFixed(2)} px · ${state}`;
    } else {
      status.textContent = `${key()} · dados espaciais carregados.`;
    }
  }

  landmarksFile.addEventListener('change', async event => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const parsed = JSON.parse(await file.text());
      if (parsed.contract !== 'CH_CHARACTER_LANDMARKS_V0') throw new Error('contrato de landmarks inválido');
      packageData = parsed;
      render();
    } catch (error) {
      packageData = null;
      status.textContent = `Falha espacial: ${error.message}`;
      render();
    }
  });

  for (const element of [direction, frame, showGround, showFeet, showFootprint, showSockets]) {
    element.addEventListener('change', render);
  }
  render();
})();

(() => {
  if (window.CH_PHOTOSHOP_LAYER_STACK || document.querySelector('script[data-ch-photoshop-layers-v2]')) return;
  const script = document.createElement('script');
  script.src = 'photoshop_layers_v2.js';
  script.dataset.chPhotoshopLayersV2 = 'true';
  script.async = false;
  script.onerror = () => console.error('Falha ao carregar photoshop_layers_v2.js');
  script.onload = () => {
    if (window.CH_PHOTOSHOP_LAYER_STACK_BRIDGE || document.querySelector('script[data-ch-photoshop-layers-v2-bridge]')) return;
    const bridge = document.createElement('script');
    bridge.src = 'photoshop_layers_v2_bridge.js';
    bridge.dataset.chPhotoshopLayersV2Bridge = 'true';
    bridge.async = false;
    bridge.onerror = () => console.error('Falha ao carregar photoshop_layers_v2_bridge.js');
    document.body.appendChild(bridge);
  };
  document.body.appendChild(script);
})();
