# City Horizon Map Forge

O Map Forge usa `build/Debug/assets` como árvore runtime. O editor lista
objetos, terrenos e cenários desta mesma árvore; o City Builder lê o cenário
selecionado por `assets/scenarios/active_scenario.txt`.

## Uso humano

Execute `python -m tools.map_forge.main`. Selecione um terreno ou objeto para
ver sua miniatura, escolha um cenário na lista e use **Exportar e ativar no
City Builder** para que o próximo lançamento do jogo carregue esse cenário.

## Worker determinístico

Um worker só aceita recipes versionadas e falha antes de escrever se o cenário
não passar pela validação nativa ou se o nome tentar sair de `assets/scenarios`.

```powershell
python -m tools.map_forge.scenario_worker `
  --asset-root build/Debug `
  --recipe coastal_forest_hydroelectric `
  --scenario-id costa_floresta_hidro.json `
  --activate
```

Recipes disponíveis:

- `coastal_forest_hydroelectric`
- `beach_water_v2`

O worker jamais altera o cenário-fonte e recusa sobrescrever uma saída existente
sem `--overwrite`. Ele produz o JSON do cenário, manifest, validação e, quando
recebe `--activate`, o marcador que o City Builder consome.
