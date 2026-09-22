from pathlib import Path

path = Path('src/ui_manager.cpp')
text = path.read_text(encoding='utf-8')

old = '''    const float toolbar_width = std::max(100.0F, width - kMargin * 2.0F);
    const float context_width = std::clamp(toolbar_width * 0.25F, 190.0F, 330.0F);
    const float tools_width = std::max(1.0F, toolbar_width - context_width - 8.0F);
'''
new = '''    const float toolbar_width = std::max(100.0F, width - kMargin * 2.0F);
    const float context_width = std::clamp(toolbar_width * 0.25F, 190.0F, 330.0F);
    const float context_x = kMargin + toolbar_width - context_width;
    const float tools_width = std::max(1.0F, toolbar_width - context_width - 8.0F);
'''
if old not in text:
    raise SystemExit('toolbar context anchor not found')
text = text.replace(old, new, 1)

old = '''    add_button({kMargin + 4.0F + tool_width * 5.0F, tool_y, tool_width - 6.0F, tool_height}, "AGRICULTURA", UiAction::open_agriculture_panel, true, model.active_tool == UiTool::agriculture);
    add_button({kMargin + 4.0F + tool_width * 6.0F, tool_y, tool_width - 6.0F, tool_height}, "DECORACAO", UiAction::activate_decoration, true, model.active_tool == UiTool::decoration);

    if (model.build_panel_open) {
'''
new = '''    add_button({kMargin + 4.0F + tool_width * 5.0F, tool_y, tool_width - 6.0F, tool_height}, "AGRICULTURA", UiAction::open_agriculture_panel, true, model.active_tool == UiTool::agriculture);
    add_button({kMargin + 4.0F + tool_width * 6.0F, tool_y, tool_width - 6.0F, tool_height}, "DECORACAO", UiAction::activate_decoration, true, model.active_tool == UiTool::decoration);

    if (model.placement_rotatable && model.active_tool == UiTool::buildings) {
        constexpr float rotation_gap = 6.0F;
        const float rotation_width = std::max(72.0F, (context_width - 18.0F - rotation_gap) * 0.5F);
        const float rotation_y = toolbar_y + 39.0F;
        add_button({context_x + 6.0F, rotation_y, rotation_width, 28.0F}, "ESQ", UiAction::rotate_left);
        add_button({context_x + 12.0F + rotation_width, rotation_y, rotation_width, 28.0F}, "DIR", UiAction::rotate_right);
    }

    if (model.build_panel_open) {
'''
if old not in text:
    raise SystemExit('toolbar buttons anchor not found')
text = text.replace(old, new, 1)

old = '''            case UiTool::buildings: title = "MODO CONSTRUCOES"; description = model_.build_panel_open ? "SELECIONE UM ITEM PARA POSICIONAR" : "ESCOLHA UMA CONSTRUCAO"; break;
'''
new = '''            case UiTool::buildings:
                title = "MODO CONSTRUCOES";
                description = model_.placement_rotatable ? "ROTACIONE COM Z/X OU OS BOTOES" :
                    (model_.build_panel_open ? "SELECIONE UM ITEM PARA POSICIONAR" : "ESCOLHA UMA CONSTRUCAO");
                break;
'''
if old not in text:
    raise SystemExit('building context description anchor not found')
text = text.replace(old, new, 1)

path.write_text(text, encoding='utf-8')
