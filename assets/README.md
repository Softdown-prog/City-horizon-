# Assets — City Horizon

## Fonte oficial dos assets visuais

A fonte oficial para novos assets visuais do City Horizon é o pipeline Blender / Tycoon Photo Studio do projeto.

Arquivos e diretórios principais:

- `tools/blender_bake_runner.py`
- `tools/tycoon_photo_studio/`
- `C++/MapForge2/presets/tycoon_asset_bake_contract.json`

O PNG usado pelo runtime é um produto derivado. A fonte autoritativa deve ser o arquivo de configuração, gramática procedural ou cena/import 3D correspondente, junto do preset de estúdio e do contrato de bake.

O padrão visual atual usa câmera isométrica/dimétrica fixa 2:1, yaw de 45°, elevação de 30° e tile de referência 128×64. Novos prédios, assets de farm, decoração, vegetação, pedra, água, props, ruas, calçadas e demais elementos do mapa devem ser recriados e promovidos por esse pipeline, em vez de reutilizar os pacotes visuais antigos.

## Estado temporário do runtime

Por decisão de produção, o único asset visual legado de terreno mantido por enquanto é a grama canônica:

- `assets/terrain/grass_isometric_01.png`
- `assets/terrain/grass_isometric_01.json`

O contrato técnico de tile de chão também permanece em `assets/terrain/ground_tile_contract.json`.

Água/costa, pedra, caminhos, decoração, farming, construções, props, veículos, parques, ruas, calçadas, variantes geradas e demais bibliotecas visuais antigas foram removidos. Quando alguma dessas categorias voltar ao jogo, ela deverá nascer novamente no pipeline Blender e passar pelo bake/validation gate atual.

## Regra para novos assets

1. Criar ou editar a fonte no pipeline Blender / Tycoon Photo Studio.
2. Gerar o bake headless com a câmera e o estúdio oficiais.
3. Validar footprint, pivot, transparência, escala e rotações exigidas pelo contrato.
4. Testar o resultado no Map Forge / runtime sobre a grade real.
5. Promover somente o PNG aprovado para uso do jogo.
6. Não reintroduzir sprites, variantes experimentais ou bibliotecas antigas fora desse fluxo.

Áudio, UI e dados de jogo como missões e cenários não fazem parte desta limpeza de assets visuais e permanecem versionados normalmente.
