// Keep the established modal polish byte-for-byte in a base include, then add
// the reusable topbar icon interaction layer. Both files are included inside
// GameplayUi::render, so they share the real button states and renderer.
#include "ui_modal_polish_base.inl"
#include "ui_topbar_interaction_fx.inl"
