(() => {
  function ellipse(ctx, x, y, rx, ry, fill, stroke = null, lineWidth = 1) {
    ctx.beginPath();
    ctx.ellipse(x, y, rx, ry, 0, 0, Math.PI * 2);
    ctx.fillStyle = fill;
    ctx.fill();
    if (stroke) {
      ctx.strokeStyle = stroke;
      ctx.lineWidth = lineWidth;
      ctx.stroke();
    }
  }

  function roundedRect(ctx, x, y, w, h, r, fill, stroke = null) {
    const left = x - w / 2;
    const top = y - h / 2;
    const right = left + w;
    const bottom = top + h;
    const rr = Math.max(0, Math.min(r, w / 2, h / 2));
    ctx.beginPath();
    ctx.moveTo(left + rr, top);
    ctx.lineTo(right - rr, top);
    ctx.quadraticCurveTo(right, top, right, top + rr);
    ctx.lineTo(right, bottom - rr);
    ctx.quadraticCurveTo(right, bottom, right - rr, bottom);
    ctx.lineTo(left + rr, bottom);
    ctx.quadraticCurveTo(left, bottom, left, bottom - rr);
    ctx.lineTo(left, top + rr);
    ctx.quadraticCurveTo(left, top, left + rr, top);
    ctx.closePath();
    ctx.fillStyle = fill;
    ctx.fill();
    if (stroke) {
      ctx.strokeStyle = stroke;
      ctx.lineWidth = 1;
      ctx.stroke();
    }
  }

  function directionSign(direction) {
    if (direction === "E") return 1;
    if (direction === "W") return -1;
    return 0;
  }

  function polygon(ctx, points, fill, stroke = null) {
    if (!points.length) return;
    ctx.beginPath();
    ctx.moveTo(points[0][0], points[0][1]);
    for (let i = 1; i < points.length; i++) ctx.lineTo(points[i][0], points[i][1]);
    ctx.closePath();
    ctx.fillStyle = fill;
    ctx.fill();
    if (stroke) {
      ctx.strokeStyle = stroke;
      ctx.lineWidth = 1;
      ctx.stroke();
    }
  }

  const SHAPES = [
    {
      id: "face_oval", label: "Rosto oval", group: "Rosto", layer: "skin",
      draw(ctx, x, y, color, scale, direction) {
        const side = directionSign(direction);
        ellipse(ctx, x + side * scale * 0.35, y, 3.9 * scale, 4.8 * scale, color);
      }
    },
    {
      id: "hair_cap", label: "Cabelo / touca", group: "Cabelo", layer: "hair",
      draw(ctx, x, y, color, scale, direction) {
        const side = directionSign(direction);
        ellipse(ctx, x + side * scale * 0.25, y - 1.3 * scale, 4.8 * scale, 3.4 * scale, color);
        ellipse(ctx, x - 3.1 * scale, y + 0.4 * scale, 1.8 * scale, 2.6 * scale, color);
        ellipse(ctx, x + 3.1 * scale, y + 0.4 * scale, 1.8 * scale, 2.6 * scale, color);
      }
    },
    {
      id: "hair_puff", label: "Cabelo volumoso", group: "Cabelo", layer: "hair",
      draw(ctx, x, y, color, scale) {
        const puffs = [[-3.3,-1.0,2.4],[-2.2,-3.1,2.5],[0,-3.8,2.7],[2.4,-3.0,2.5],[3.5,-.8,2.3],[0,.1,3.2]];
        for (const [dx,dy,r] of puffs) ellipse(ctx, x + dx*scale, y + dy*scale, r*scale, r*scale, color);
      }
    },
    {
      id: "eye_pair", label: "Par de olhos", group: "Rosto", layer: "face",
      draw(ctx, x, y, color, scale, direction) {
        const side = directionSign(direction);
        const spacing = direction === "S" ? 2.1 : 1.65;
        if (direction === "N") return;
        ellipse(ctx, x - spacing*scale + side*.35*scale, y, .62*scale, .82*scale, color);
        ellipse(ctx, x + spacing*scale + side*.35*scale, y, .62*scale, .82*scale, color);
      }
    },
    {
      id: "round_nose", label: "Nariz redondo", group: "Rosto", layer: "face",
      draw(ctx, x, y, color, scale, direction) {
        if (direction === "N") return;
        const side = directionSign(direction);
        ellipse(ctx, x + side*.55*scale, y, 1.15*scale, 1.05*scale, color);
      }
    },
    {
      id: "smile", label: "Sorriso", group: "Rosto", layer: "face",
      draw(ctx, x, y, color, scale, direction) {
        if (direction === "N") return;
        const side = directionSign(direction);
        ctx.beginPath();
        ctx.arc(x + side*.4*scale, y - 1.0*scale, 2.7*scale, .15*Math.PI, .85*Math.PI);
        ctx.strokeStyle = color;
        ctx.lineWidth = Math.max(1, scale*.8);
        ctx.stroke();
      }
    },
    {
      id: "ruff", label: "Gola / rufo", group: "Roupa", layer: "upper_clothing",
      draw(ctx, x, y, color, scale) {
        const pts = [[-5,0],[-3.8,-1.8],[-2.0,-.7],[0,-2.0],[2,-.7],[3.8,-1.8],[5,0],[3.3,1.7],[0,.8],[-3.3,1.7]];
        polygon(ctx, pts.map(([dx,dy]) => [x+dx*scale,y+dy*scale]), color);
      }
    },
    {
      id: "torso", label: "Torso / casaco", group: "Roupa", layer: "upper_clothing",
      draw(ctx, x, y, color, scale, direction) {
        const side = directionSign(direction);
        const pts = direction === "N"
          ? [[-4.8,-5],[4.8,-5],[4.2,5],[-4.2,5]]
          : [[-5,-4.8],[5,-4.8],[4.2,5.2],[-4.2,5.2]];
        polygon(ctx, pts.map(([dx,dy]) => [x+dx*scale+side*.35*scale,y+dy*scale]), color);
      }
    },
    {
      id: "sleeve", label: "Manga", group: "Roupa", layer: "upper_clothing",
      draw(ctx, x, y, color, scale) {
        roundedRect(ctx, x, y, 3.8*scale, 9.0*scale, 1.5*scale, color);
      }
    },
    {
      id: "trouser_leg", label: "Perna / calça", group: "Roupa", layer: "lower_clothing",
      draw(ctx, x, y, color, scale) {
        const pts = [[-2,-6],[2,-6],[2.5,5.2],[1.7,6],[-2.2,6],[-2.5,5.2]];
        polygon(ctx, pts.map(([dx,dy]) => [x+dx*scale,y+dy*scale]), color);
      }
    },
    {
      id: "shoe", label: "Sapato", group: "Corpo", layer: "footwear",
      draw(ctx, x, y, color, scale, direction) {
        const side = directionSign(direction);
        roundedRect(ctx, x + side*1.0*scale, y, 5.2*scale, 2.7*scale, 1.1*scale, color);
      }
    },
    {
      id: "glove", label: "Luva", group: "Corpo", layer: "accessories_front",
      draw(ctx, x, y, color, scale) {
        ellipse(ctx, x, y, 2.0*scale, 2.3*scale, color);
        roundedRect(ctx, x, y + 1.8*scale, 2.8*scale, 2.2*scale, .7*scale, color);
      }
    }
  ];

  window.CH_CHARACTER_SHAPES = Object.freeze(SHAPES);
})();
