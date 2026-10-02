// Keep the established modal polish byte-for-byte in a base include, then add
// the reusable nine-slice chrome pilots and topbar interaction layer. These
// files are included inside GameplayUi::render, so they share the real button
// states, panel bounds and renderer.
#include "ui_modal_polish_base.inl"
#include "ui_build_panel_nine_slice.inl"
#include "ui_window_nine_slice.inl"
#include "ui_topbar_interaction_fx.inl"
#include "ui_weather_indicator.inl"
