from pathlib import Path

# CH_MONEY_SPEND_FX_V2 integration worker. Kept idempotent so concurrent main updates can rebase safely.
path = Path('src/main_runtime_impl.cpp')
text = path.read_text(encoding='utf-8')
original = text


def once(old: str, new: str, label: str) -> None:
    global text
    if new in text:
        return
    if old not in text:
        raise SystemExit(f'missing integration anchor: {label}')
    text = text.replace(old, new, 1)

once('#include "economy_system.h"\n', '#include "economy_system.h"\n#include "money_spend_fx.h"\n', 'include')
once('    GameplayUi gameplay_ui;\n', '    GameplayUi gameplay_ui;\n    MoneySpendFx money_spend_fx;\n', 'instance')

once(
'''                            status = placement->name + " BUILT: " + format_money(placement->build_cost) + " SPENT";\n''',
'''                            status = placement->name + " BUILT: " + format_money(placement->build_cost) + " SPENT";\n                            money_spend_fx.spawn(placement->build_cost, event.button.x, event.button.y);\n''',
'building-spend')

once(
'''                            status = definition->display_name + " PLACED: " + format_money(definition->build_cost);\n                            (void)play_sound(SoundEvent::ui_confirm);\n''',
'''                            status = definition->display_name + " PLACED: " + format_money(definition->build_cost);\n                            money_spend_fx.spawn(definition->build_cost, event.button.x, event.button.y);\n                            (void)play_sound(SoundEvent::ui_confirm);\n''',
'water-spend')

once(
'''                    status = changed == 0 ? "NENHUM PISO ALTERADO" :\n                        "PISO ALTERADO: " + std::to_string(changed) + " TILE(S)" +\n                        (blocked == 0 ? "" : " | " + std::to_string(blocked) + " BLOQUEADOS");\n                    (void)play_sound(changed == 0 ? SoundEvent::ui_error : SoundEvent::ui_confirm);\n''',
'''                    status = changed == 0 ? "NENHUM PISO ALTERADO" :\n                        "PISO ALTERADO: " + std::to_string(changed) + " TILE(S)" +\n                        (blocked == 0 ? "" : " | " + std::to_string(blocked) + " BLOQUEADOS");\n                    if (changed > 0 && tile_cost > 0) {\n                        money_spend_fx.spawn(static_cast<std::int64_t>(changed) * tile_cost, event.button.x, event.button.y);\n                    }\n                    (void)play_sound(changed == 0 ? SoundEvent::ui_error : SoundEvent::ui_confirm);\n''',
'floor-spend')

once(
'''                    const int placed = roads.place_segment(segment);\n                    status = placed == 0 ? "ROAD ALREADY EXISTS" : "ROAD PLACED: " + std::to_string(placed) + " TILE(S), " +\n                        format_money(static_cast<std::int64_t>(placed) * kRoadCostPerTile) + " SPENT";\n''',
'''                    const int placed = roads.place_segment(segment);\n                    status = placed == 0 ? "ROAD ALREADY EXISTS" : "ROAD PLACED: " + std::to_string(placed) + " TILE(S), " +\n                        format_money(static_cast<std::int64_t>(placed) * kRoadCostPerTile) + " SPENT";\n                    if (placed > 0) {\n                        money_spend_fx.spawn(static_cast<std::int64_t>(placed) * kRoadCostPerTile, event.button.x, event.button.y);\n                    }\n''',
'road-spend')

once(
'''            if (farming.try_remove_resource(resource->id, quantity)) economy.earn_agricultural_sale(revenue, simulation_clock.date());\n            status = resource->display_name + " SOLD: " + std::to_string(quantity) + " | " + format_money(revenue);\n''',
'''            if (farming.try_remove_resource(resource->id, quantity)) {\n                economy.earn_agricultural_sale(revenue, simulation_clock.date());\n                money_spend_fx.spawn_income(revenue, static_cast<float>(viewport_width) - 180.0F, 92.0F);\n            }\n            status = resource->display_name + " SOLD: " + std::to_string(quantity) + " | " + format_money(revenue);\n''',
'agricultural-income')

once(
'''        render_weather(renderer, weather, viewport_width, viewport_height);\n        gameplay_ui.update_layout(viewport_width, viewport_height, make_ui_model(mouse_tile));\n''',
'''        render_weather(renderer, weather, viewport_width, viewport_height);\n        money_spend_fx.render(renderer);\n        gameplay_ui.update_layout(viewport_width, viewport_height, make_ui_model(mouse_tile));\n''',
'render')

if text != original:
    path.write_text(text, encoding='utf-8')
    print('CH_MONEY_SPEND_FX_V2 integrated')
else:
    print('CH_MONEY_SPEND_FX_V2 already integrated')
