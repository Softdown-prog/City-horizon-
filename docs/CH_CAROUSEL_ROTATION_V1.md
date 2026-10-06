# CH_CAROUSEL_ROTATION_V1

This contract defines the canonical pre-rendered rotation sampling for the City Horizon carousel.

## Canonical sampling

The canopy has 24 alternating radial stripes: 12 primary stripes and 12 secondary stripes. A full stripe spans 15 degrees. Production samples at half-stripe increments:

- canopy stripes: 24 total;
- primary stripes: 12;
- secondary stripes: 12;
- production frames per turn: 48;
- production angular step: 7.5 degrees.

Export frames `1..48` only. Frame `n` represents `(n - 1) * 7.5` degrees. Frame 48 is 352.5 degrees. Frame 49 may exist only as a non-exported 360-degree loop-closure key.

## Playback

Canonical playback is 8 fps. Forty-eight frames produce one revolution every 6 seconds.

## Four directions

The fixed CH camera/studio supplies SOUTH, EAST, WEST and NORTH. The camera and lights never rotate. `AssetRoot` selects the canonical direction and the internal `CarouselRotor` supplies the per-frame spin.

Production count is 48 frames per direction = 192 beauty frames.

## Review proxy and anti-alias rule

Do not review the canopy at 30-degree intervals. The 24-stripe alternating pattern repeats visually every 30 degrees, so sampling at that interval can make a correctly rotating canopy appear stationary.

The canonical economical review therefore samples `1,3,5,...,47`:

- 24 review frames per direction;
- 15-degree visual step;
- 96 review PNGs across four directions;
- production contract remains 48 frames per direction.

This review is dense enough to show canopy movement and avoids the stripe-period aliasing seen in the earlier 12-frame review.

## Color mask

Use `CH_COLOR_MASK_V1` for the same animated frame set:

- R channel: primary canopy stripe family (Listra A);
- G channel: secondary canopy stripe family (Listra B);
- B channel: unused;
- all other carousel parts: fixed color.

Beauty and mask must use the same direction, frame index, pivot, canvas and rotor angle.

## Validation gates

Reject production if:

- canopy stripe count is not 24;
- stripe families are not 12 + 12;
- production frame count is not 48 per direction;
- production angular step is not 7.5 degrees;
- frame 48 duplicates 360 degrees;
- frame 49 is exported;
- beauty and mask frame counts/order/canvas/pivot differ;
- anything outside the canopy stripe families is included in the color mask.
