(() => {
  const FRAME_W = 48, FRAME_H = 64;
  const SOCKETS = {
    left_hand: {landmark:"hand_L", label:"Mão esquerda"},
    right_hand: {landmark:"hand_R", label:"Mão direita"}
  };
  const AUTO_DEPTH = {S:"front", E:"front", N:"back", W:"back"};

  function blankFrame() {
    return new ImageData(FRAME_W, FRAME_H);
  }

  function placeImage(source, targetX, targetY) {
    const out = blankFrame();
    const src = source.data, dst = out.data;
    for (let sy = 0; sy < source.height; sy++) {
      for (let sx = 0; sx < source.width; sx++) {
        const si = (sy * source.width + sx) * 4;
        if (!src[si + 3]) continue;
        const x = targetX + sx, y = targetY + sy;
        if (x < 0 || x >= FRAME_W || y < 0 || y >= FRAME_H) continue;
        const di = (y * FRAME_W + x) * 4;
        dst[di] = src[si]; dst[di + 1] = src[si + 1];
        dst[di + 2] = src[si + 2]; dst[di + 3] = src[si + 3];
      }
    }
    return out;
  }

  function resolveDepth(direction, requested) {
    if (requested === "front" || requested === "back") return requested;
    return AUTO_DEPTH[direction] || "front";
  }

  function render(state, frame, maskEngine) {
    const empty = {front:blankFrame(), back:blankFrame(), mask:blankFrame(), placement:null};
    if (!state?.enabled || !state.visual || !frame?.points) return empty;
    const socket = SOCKETS[state.socket] || SOCKETS.right_hand;
    const point = frame.points[socket.landmark];
    if (!Array.isArray(point)) return empty;

    const gripX = Number.isFinite(state.gripAnchor?.[0]) ? state.gripAnchor[0] : Math.floor(state.visual.width / 2);
    const gripY = Number.isFinite(state.gripAnchor?.[1]) ? state.gripAnchor[1] : Math.floor(state.visual.height / 2);
    const offsetX = Number(state.offset?.[0] || 0), offsetY = Number(state.offset?.[1] || 0);
    const x = Math.round(Number(point[0]) + offsetX - gripX);
    const y = Math.round(Number(point[1]) + offsetY - gripY);
    const depth = resolveDepth(frame.direction, state.depth);
    const visual = placeImage(state.visual, x, y);
    const sourceMask = state.mask || maskEngine.objectFallbackMask(state.visual);
    const mask = placeImage(sourceMask, x, y);

    return {
      front: depth === "front" ? visual : blankFrame(),
      back: depth === "back" ? visual : blankFrame(),
      mask,
      placement: {
        socket: state.socket,
        landmark: socket.landmark,
        depth,
        topLeft: [x, y],
        hand: [Number(point[0]), Number(point[1])]
      }
    };
  }

  window.CH_HELD_OBJECTS = {
    contract: "CH_CHARACTER_HAND_SOCKET_V0",
    sockets: SOCKETS,
    autoDepth: AUTO_DEPTH,
    render,
    blankFrame
  };
})();
