# City Horizon carousel modular art

These files are persistent production visual sources for `carousel_parts_3`.

The `.png.b64` files contain base64-encoded transparent RGBA PNG assets. They are stored this way only so the repository connector can version the exact raster bytes as text; `CarouselPartLibrary` decodes them before rendering.

- `base.png.b64`, `platform.png.b64`, `canopy.png.b64`, `center_pole.png.b64`, `finial.png.b64`, and `rosette.png.b64` are modular structural/decorative components.
- `horse_e.png.b64`, `horse_s.png.b64`, `horse_w.png.b64`, and `horse_n.png.b64` are the four directional horse presentations.
- Runtime animation moves and depth-sorts these persistent images; it does not redraw the carousel procedurally per frame.
- Screen placement is not encoded in the art files. World positions are projected through `src/ch_core/projection.cpp::ch::world_to_screen_point`.

The art files can be replaced independently without changing animation topology, stable part IDs, pivots, or the runtime projection contract.
