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

O pedestre `ch_actor_green_01` foi aprovado na prévia de gameplay e promovido para `assets/characters/ch_actor_green_01/frames/` e `assets/definitions/animations/ch_actor_green_01.json`. A fonte reproduzível permanece em `tools/ch_actor_lab/software_render.py`. Os PNGs são RGBA 48×64 (8 quadros de caminhada e 1 parado para cada uma das quatro direções); o pivô é `[24,60]` e a câmera é `CH_CAMERA_V1`. O runtime posiciona esse pivô no centro lógico do tile caminhável, sem depender da opção de compilação de previews. O primeiro uso é um único pedestre de circulação automática em piso/rua; outros estados e população persistente aguardam uma etapa de gameplay.

A grama canônica permanece como asset legado de terreno:

- `assets/terrain/grass_isometric_01.png`
- `assets/terrain/grass_isometric_01.json`

O primeiro tile de terra aprovado pelo pipeline atual também está promovido para uso do jogo:

- `assets/terrain/dirt_isometric_01.png`
- `assets/terrain/dirt_isometric_01.json`

O tile de terra foi normalizado para 128×64 RGBA e validado no MapForge pelo workflow `Test Atomic Path in MapForge`, run `35670104713`. Ele é a fonte visual aprovada para futuras variantes de conexão/auto-tile; não reutilizar os sprites antigos de caminho como arte final.

O contrato técnico de tile de chão também permanece em `assets/terrain/ground_tile_contract.json`.

O pinheiro e o canteiro dourado da decoração usam PNGs 2D RGBA aprovados para integração no catálogo de construção: `assets/tree/pine_tree_01.png` e `assets/decor/flower_bed_01.png`. As definições 1×1 em `assets/definitions/` guardam escala, âncora e caminho das fontes em `tools/tycoon_photo_studio/art/concepts/nature_2d_generated_v2/`. O estudo procedural original do pinheiro e do canteiro permanece no Visitor Forge 2D; ele não reproduz estes dois PNGs promovidos.

As três novas árvores aprovadas para o runtime são `pine_small_v1`, `pine_tall_v1` e `pine_robust_v1`. Seus PNGs transparentes em `assets/tree/` são cópias byte a byte dos resultados do Visitor Forge 2D em `tools/visitor_forge_2d/art/concepts/pine_family_v1/`. Cada definição em `assets/definitions/` usa `category: decor`, footprint 1×1, `artScale: 1.0` e o pivô normalizado da receita original: `[76,137]` em 152×150, `[88,249]` em 176×264 e `[110,217]` em 220×231. Assim, o centro do tronco permanece no chão do tile 128×64 da câmera `CH_CAMERA_V1` (yaw 45°, elevação 30°), mantendo as alturas de 136, 252 e 220 px em zoom 1. O pinheiro anterior continua como opção separada no catálogo.

As novas árvores decíduas ramificadas aprovadas para o runtime de decor são `broadleaf_zoo_forked_v1` e `broadleaf_zoo_tall_v1`. Geradas proceduralmente via `build_tycoon_tree_2d.py` com copas multi-cluster e troncos ramificados em V, seus PNGs transparentes estão integrados em `assets/tree/` com definições 1×1 em `assets/definitions/` (`category: decor`, pivôs normalizados `[96,248]` em 192×256 e `[112,278]` em 224×288 na câmera `CH_CAMERA_V1`).

A árvore folhosa de outono aprovada `park_tree_early_autumn_01` usa os quatro PNGs do Visitor Forge 2D em `assets/tree/park_tree_early_autumn_01_{south,west,north,east}.png`. A definição em `assets/definitions/` registra os sprites nas rotações `0,1,2,3`, respectivamente, com footprint 1×1, pivô `[96,239]` em 192×256 (`anchor`: `[0.5,0.93359375]`), escala 1 e custo $55. O jogo carrega as quatro texturas pelo catálogo de decoração e escolhe a vista relativa à rotação da câmera. O brief reproduzível está em `tools/visitor_forge_2d/examples/briefs/park_tree_early_autumn.json`.

A mangueira `park_tree_mango_01` usa quatro sprites RGBA 256×320 em `assets/tree/`, registrados nas rotações `0:SOUTH, 1:WEST, 2:NORTH, 3:EAST` em `assets/definitions/park_tree_mango_01.json`. É decoração construível em grama, footprint 1×1, custo $95, escala 1 e âncora `[128,311]` (`[0.5,0.971875]`). Os PNGs são exportações do Forge 2D pela receita `tools/visitor_forge_2d/examples/park_tree_mango_01.json`, que monta madeira e folhagem autoradas com hashes de fonte e downsample alpha-safe. As vistas são desenhos direcionais coerentes, não uma prova de rotação geométrica 3D. A revisão 1× e o contexto de tile estão em `tools/visitor_forge_2d/art/concepts/mango_tree_v1/`.

A água rasa e profunda aprovada está em `assets/terrain/water/`, com bases periódicas, overlays originais, mapas de índices e atlas de brilho com ciclo de paletas. O manifesto `water_surfaces.json` e o README da pasta descrevem as coordenadas e o tempo dos quadros. A fonte permanece no bake CH Blender e nos scripts de preparação e promoção de água. O renderer compartilha a amostragem contínua nas quatro rotações. Água rasa custa $50 e água profunda $100 por tile em terreno próprio e livre; a seleção inicial é pelas teclas 1/2 até a UI de terreno ser criada.

Água/costa, pedra, decoração, farming, construções, props, veículos, parques, ruas, calçadas e demais bibliotecas visuais antigas removidas devem voltar somente pelo pipeline atual e pelo gate de validação correspondente.

## Regra para novos assets

1. Criar ou editar a fonte no pipeline Blender / Tycoon Photo Studio.
2. Gerar o bake headless com a câmera e o estúdio oficiais.
3. Validar footprint, pivot, transparência, escala, rotações e `CH_STYLIZED_PRERENDER_V1` quando aplicável.
4. Testar o resultado no Map Forge / runtime sobre a grade real.
5. Promover somente o PNG aprovado em escala de gameplay para uso do jogo.
6. Não reintroduzir sprites, variantes experimentais ou bibliotecas antigas fora desse fluxo.

Áudio, UI e dados de jogo como missões e cenários não fazem parte desta limpeza de assets visuais e permanecem versionados normalmente.
