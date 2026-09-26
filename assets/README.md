# Assets — City Horizon

## Fonte oficial dos assets visuais

A fonte oficial para novos assets visuais do City Horizon é o pipeline Blender / Tycoon Photo Studio do projeto.

Arquivos e diretórios principais:

- `tools/blender_bake_runner.py`
- `tools/tycoon_photo_studio/`
- `tools/tycoon_photo_studio/contracts/ch_stylized_prerender_v1.json`
- `C++/MapForge2/presets/tycoon_asset_bake_contract.json`

O PNG usado pelo runtime é um produto derivado. A fonte autoritativa deve ser o arquivo de configuração, gramática procedural ou cena/import 3D correspondente, junto do preset de estúdio e do contrato de bake.

## Contrato visual atual

O contrato visual ativo é `CH_STYLIZED_PRERENDER_V1`.

Ele define o alvo como um visual 2D pre-renderizado estilizado próprio do City Horizon, produzido com ferramentas 3D modernas, mas avaliado pela leitura final no runtime. Tycoons clássicos continuam úteis como referência de legibilidade, escala, silhueta e clareza, porém não existe objetivo de reproduzir literalmente as limitações gráficas de jogos dos anos 2000.

O padrão de câmera permanece isométrico/dimétrico fixo 2:1, yaw de 45°, elevação de 30° e tile de referência 128×64. Materiais, iluminação, microdetalhe e pós-processamento devem servir à leitura em escala de gameplay. Aparência de render 3D moderno, fotorealismo desnecessário e detalhe microscópico sem leitura devem ser evitados.

A `park_tree_broadleaf_02` é o primeiro exemplar de referência de vegetação desse contrato. Ela estabelece nível de estilização, legibilidade, silhueta orgânica e profundidade pre-renderizada controlada; não significa copiar sua aparência exata para todas as categorias de asset.

Novos prédios, assets de farm, decoração, vegetação, pedra, água, props, ruas, calçadas e demais elementos do mapa devem ser recriados e promovidos por esse pipeline, em vez de reutilizar os pacotes visuais antigos.

## Registro de construções no runtime

O footprint lógico e o sprite precisam usar o mesmo ponto de chão. O runtime ancora construções no canto projetado mais próximo da câmera do footprint; já os bakes `CH_RUNTIME_BUILDING_V1` podem registrar no manifesto o pivot do `projected world origin`, que fica no centro lógico do footprint. Esses dois pivots não devem ser copiados como se fossem equivalentes.

Para um prédio 2×2 no contrato 128×64, o canto de chão usado pelo runtime fica 64 px abaixo do world origin na vista canônica. Portanto, ao promover um bake 2×2 cujo manifesto fornece o pivot do world origin, o `spriteAnchors.y` deve incluir esse deslocamento antes de ser normalizado pela altura do frame. O mesmo cálculo deve ser refeito para footprints diferentes; não reutilizar um número fixo de outro asset.

A ordem de revisão/bake `south, east, west, north` também não é a ordem numérica de rotação do runtime. `BuildingRotation` gira no sentido horário a partir de South: `r0 = south`, `r90 = west`, `r180 = north`, `r270 = east`. As definições devem mapear os PNGs nomeados para esses quatro índices explicitamente; nunca interpretar a ordem do sprite sheet de revisão como ordem de `BuildingRotation`.

Esse contrato é parte da lógica de colocação: uma construção visualmente deslocada pode parecer estar sobre uma rua mesmo quando o footprint lógico foi corretamente recusado/aceito. Antes de promover um prédio, o contorno de footprint, o sprite e a borda de acesso à rua precisam coincidir nas quatro rotações.

## Estado temporário do runtime

A grama canônica permanece como asset legado de terreno:

- `assets/terrain/grass_isometric_01.png`
- `assets/terrain/grass_isometric_01.json`

O primeiro tile de terra aprovado pelo pipeline atual também está promovido para uso do jogo:

- `assets/terrain/dirt_isometric_01.png`
- `assets/terrain/dirt_isometric_01.json`

O tile de terra foi normalizado para 128×64 RGBA e validado no MapForge pelo workflow `Test Atomic Path in MapForge`, run `35670104713`. Ele é a fonte visual aprovada para futuras variantes de conexão/auto-tile; não reutilizar os sprites antigos de caminho como arte final.

O contrato técnico de tile de chão também permanece em `assets/terrain/ground_tile_contract.json`.

Água/costa, pedra, decoração, farming, construções, props, veículos, parques, ruas, calçadas e demais bibliotecas visuais antigas removidas devem voltar somente pelo pipeline atual e pelo gate de validação correspondente.

## Regra para novos assets

1. Criar ou editar a fonte no pipeline Blender / Tycoon Photo Studio.
2. Gerar o bake headless com a câmera e o estúdio oficiais.
3. Validar footprint, pivot, transparência, escala, rotações e `CH_STYLIZED_PRERENDER_V1` quando aplicável.
4. Testar o resultado no Map Forge / runtime sobre a grade real.
5. Promover somente o PNG aprovado em escala de gameplay para uso do jogo.
6. Não reintroduzir sprites, variantes experimentais ou bibliotecas antigas fora desse fluxo.

Áudio, UI e dados de jogo como missões e cenários não fazem parte desta limpeza de assets visuais e permanecem versionados normalmente.
