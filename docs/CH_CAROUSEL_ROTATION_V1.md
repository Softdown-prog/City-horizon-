# CH_CAROUSEL_ROTATION_V1

This contract defines the canonical pre-rendered rotation sampling for the City Horizon carousel.

## Canonical sampling

The canopy has 24 alternating radial stripes: 12 primary stripes and 12 secondary stripes. A full stripe spans 15 degrees. To avoid visible jumps, City Horizon samples at half-stripe increments:

- canopy stripes: 24 total;
- primary stripes: 12;
- secondary stripes: 12;
- full stripe angle: 15 degrees;
- exported frames per full turn: 48;
- angular step: 7.5 degrees.

Export frames `1..48` only. Frame `n` represents:

`angleDegrees = (n - 1) * 7.5`

Frame 48 is 352.5 degrees. Frame 49 may exist only as a non-exported 360-degree loop closure key.

## Playback

Canonical playback is 8 fps. Forty-eight frames therefore produce one revolution every 6 seconds. Runtime timing may change later without changing the 48 unique angular samples unless a new visual review explicitly approves a different sampling contract.

## Four directions

Beauty animation is authored for SOUTH, EAST, WEST and NORTH using the fixed CH camera/studio. The camera and lights never rotate. The asset root selects the canonical direction and the internal `CarouselRotor` supplies the per-frame spin.

Production count is 48 frames per direction = 192 beauty frames.

For economical visual review, a proxy may render the canonical subset `1,5,9,...,45` (12 samples per direction, 48 review PNGs total). Those proxy samples are review-only and do not replace the 48-frame production contract.

## Color mask

Use `CH_COLOR_MASK_V1` for the same animated frame set:

- R channel: primary canopy stripe family (Listra A);
- G channel: secondary canopy stripe family (Listra B);
- B channel: unused;
- all other carousel parts: fixed color.

For every frame and direction, beauty and mask must share exactly the same camera, canvas, pivot, asset direction, rotor angle and frame index. The runtime must select the beauty and mask frame using the same animation cursor.

## Packaging

Per direction, production contains 48 ordered frames. A spritesheet may use one row with 48 columns, or a runtime frame sequence may keep the frames separate if the renderer contract requires it.

Recommended names:

- beauty: `<assetId>_<direction>_animation.png`;
- color mask: `<assetId>_<direction>_color_mask_animation.png`.

## Validation gates

Reject production if:

- canopy stripe count is not 24;
- stripe families are not 12 + 12;
- production frame count is not 48 per direction;
- angular step is not 7.5 degrees;
- frame 48 duplicates 360 degrees;
- frame 49 is exported;
- beauty and mask frame counts/order/canvas/pivot differ;
- anything outside the canopy stripe families is included in the color mask.
