(() => {
  const W = 48, H = 64;
  const CHANNELS = {
    R: [255, 0, 0, 255],
    G: [0, 255, 0, 255],
    B: [0, 0, 255, 255]
  };
  const BANKS = {
    appearance: {
      label: "Aparência",
      channels: {R:"skin", G:"hair", B:"appearance_accent"},
      sources: {R:["skin"], G:["hair"], B:["face"]}
    },
    clothing: {
      label: "Roupas",
      channels: {R:"primary_clothing", G:"secondary_clothing", B:"clothing_accent"},
      sources: {
        R:["upper_clothing"],
        G:["lower_clothing"],
        B:["footwear","accessories_back","accessories_front"]
      }
    },
    held_object: {
      label: "Objeto na mão",
      channels: {R:"object_primary", G:"object_secondary", B:"object_accent"},
      sources: {}
    }
  };

  function blank(width = W, height = H) {
    return new ImageData(width, height);
  }

  function clone(image) {
    return new ImageData(new Uint8ClampedArray(image.data), image.width, image.height);
  }

  function paintAlphaAsChannel(out, source, rgba) {
    const src = source.data, dst = out.data;
    for (let i = 0; i < source.width * source.height; i++) {
      const a = src[i * 4 + 3];
      if (!a) continue;
      const p = i * 4;
      dst[p] = rgba[0]; dst[p + 1] = rgba[1]; dst[p + 2] = rgba[2];
      dst[p + 3] = Math.max(dst[p + 3], a);
    }
  }

  function fromLayers(layers, bankName) {
    const bank = BANKS[bankName];
    if (!bank || bankName === "held_object") return blank();
    const out = blank();
    for (const channel of ["R","G","B"]) {
      for (const layerName of bank.sources[channel] || []) {
        const image = layers[layerName];
        if (image) paintAlphaAsChannel(out, image, CHANNELS[channel]);
      }
    }
    return out;
  }

  function objectFallbackMask(visual) {
    const out = blank(visual.width, visual.height);
    const src = visual.data, dst = out.data;
    for (let i = 0; i < visual.width * visual.height; i++) {
      const a = src[i * 4 + 3];
      if (!a) continue;
      const p = i * 4;
      dst[p] = 255; dst[p + 1] = 0; dst[p + 2] = 0; dst[p + 3] = a;
    }
    return out;
  }

  function validateObjectMask(mask, visual) {
    if (!mask || !visual) throw new Error("objeto e máscara precisam estar carregados");
    if (mask.width !== visual.width || mask.height !== visual.height) {
      throw new Error(`máscara do objeto deve ter ${visual.width}x${visual.height}px`);
    }
    return mask;
  }

  function channelLabel(bankName, channel) {
    return BANKS[bankName]?.channels?.[channel] || channel;
  }

  function maskFileName(bank, direction, frame) {
    return `${direction.toLowerCase()}_${frame}_mask_${bank}.png`;
  }

  window.CH_CHARACTER_COLOR_MASKS = {
    contract: "CH_CHARACTER_COLOR_MASK_V0",
    frameSize: [W, H],
    banks: BANKS,
    channels: CHANNELS,
    blank,
    clone,
    fromLayers,
    objectFallbackMask,
    validateObjectMask,
    channelLabel,
    maskFileName
  };
})();
