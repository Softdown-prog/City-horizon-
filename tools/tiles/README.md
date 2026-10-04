# City Horizon — Tile Pipeline

Esta pasta é a entrada canônica para agentes que trabalham com **tiles de chão/caminhos**. Não é necessário vasculhar todas as ferramentas do repositório antes de produzir um tile.

## Princípio: receita por tipo de tile, não regra global

Não existe uma obrigação de gerar rampas, escadas, 16 máscaras ou transições para todo material. O agente deve primeiro classificar o pedido e aplicar somente a receita necessária.

Exemplos:

- **caminho plano conectado** → contrato `atomic-path` + família N/E/S/W de 16 máscaras;
- **material de terreno** (areia, lama, cascalho) → pode usar transição/blend suave contra a superfície de baixo, sem exigir 16 máscaras;
- **rampa/escada/subida/descida** → só gerar quando o asset solicitado realmente precisar dessas variantes;
- **água** → usar pipeline contínuo próprio; não tratar como caminho;
- **overlay/decal** → usar receita de overlay; não forçar contrato de caminho.

A ausência de uma variante não é erro se aquela variante não fizer parte da receita escolhida para o material.

## Contrato do jogo

Para caminhos atômicos atuais:

- PNG RGBA
- 128 x 64 px
- losango isométrico 2:1
- alpha fora do losango
- sem halo, borda decorativa, bevel, pixels pretos/coloridos ou resíduos da imagem-fonte
- interior da textura deve permanecer visualmente estável
- conexões N/E/S/W usam família de 16 máscaras **somente quando o asset for um caminho conectado**

A autoridade geométrica é `assets/terrain/ground_tile_contract.json`, perfil `atomic-path`.

## Pipeline oficial — caminho conectado

1. **Fonte artística** — começar por uma textura/imagem visualmente boa. Não usar procedural para inventar a arte do material por padrão.
2. **Normalização** — produzir o losango 128x64 RGBA.
3. **Limpeza de borda** — preencher RGB transparente antes de copiar amostras para a borda, remover bevel/rim e contaminação somente no perímetro. Nunca espalhar correção para o centro.
4. **Seam** — igualar apenas amostras que realmente se encontram nas bordas opostas. Não difundir cores da borda para o interior.
5. **Autotile** — quando necessário, gerar as 16 máscaras N/E/S/W a partir do tile-base limpo.
6. **Gates** — validar contrato geométrico, pixels escuros indevidos e, quando houver família conectada, validar as 16 máscaras e pares de bordas compatíveis.
7. **Preview visual** — verificar reta, curva, cruzamento, repetição e tile isolado. Gate técnico aprovado NÃO equivale a aprovação artística.
8. **Runtime** — publicar PNGs apenas após aprovação do preview visual. Os workflows de geração armazenam candidatos como artefatos e nunca fazem commit dos tiles automaticamente.

## Pipeline opcional — transição de material

Para materiais como areia, lama ou cascalho que devem se misturar visualmente com a superfície inferior, usar `tools/tiles/material_transition_worker.py`.

Esse worker:

- não é obrigatório;
- não cria escadas/rampas;
- não cria automaticamente 16 máscaras;
- preserva o material no centro;
- reduz alpha somente numa faixa curta da borda;
- usa pequena irregularidade determinística para evitar um contorno geométrico perfeito;
- permite preview sobre uma textura de fundo.

Exemplo:

```bash
python tools/tiles/material_transition_worker.py \
  --source assets/terrain/sand_isometric_01.png \
  --output out/sand_transition_overlay.png \
  --underlay out/grass_atomic_preview.png \
  --preview out/sand_to_grass_preview.png
```

A intenção visual é uma transição discreta tipo "tingimento" areia→grama, sem borda dura e sem transformar areia em caminho rígido.

## Problemas já aprendidos

### Linhas verdes entre tiles
Não esconder aumentando o sprite. Verificar alpha, diamond mask, alinhamento 128x64 e igualdade das bordas que se encontram.

### Mancha radial / efeito de estrela
Foi causado por correções de borda difundidas para o interior. É proibido usar centre-pull ou harmonização que pinte vários pixels em direção ao centro.

### Pontas pretas/vermelhas/coloridas
São contaminação da fonte ou de amostragem de borda. A limpeza deve detectar outliers somente na faixa externa e substituí-los por textura válida encontrada mais para dentro da mesma região.
Em especial, copiar RGB de pixels transparentes pretos e só depois tornar a borda opaca cria pontos pretos mesmo quando a fonte parecia correta.

### Emendas entre máscaras
O erro da borda de um tile isolado não comprova continuidade da família. Comparar todas as duplas de lados que podem encostar com o mesmo estado de conexão e rejeitar diferença de cor excessiva. Em cada par, comparar RGB apenas onde os dois pixels são opacos: o contorno rasterizado pode deslocar um pixel entre lados opostos.

### Repetição artificial
Não resolver deformando o tile. Preservar a textura-base; variantes artísticas podem ser adicionadas depois.

## Ferramentas canônicas atuais

As implementações históricas ainda podem estar em `tools/` por compatibilidade com workflows existentes. Antes de mover código, atualizar todos os imports/workflows no mesmo commit para não quebrar CI.

- `tools/ground_tile_worker.py` — preparação, limpeza, seam e preview repetido.
- `tools/tile_geometry.py` — máscara de losango compartilhada por normalização, worker, geradores e gate.
- `tools/normalize_atomic_path_tile.py` — normalização do caminho atômico.
- `tools/generate_sand_paths.py` — gerador da família de areia conectada quando areia for usada como caminho.
- `tools/tiles/material_transition_worker.py` — blend opcional para materiais de terreno sobre a superfície inferior.
- `tools/tiles/validate_atomic_path_candidate.py` — worker seguro para chamar o gate `atomic-path` com os argumentos corretos.
- `tools/validate_ground_tiles.py` — gate do contrato geométrico.
- `tools/validate_path_tiles.py` — gate das 16 máscaras, pixels escuros e emendas compatíveis.
- `tools/extract_ground_tile_sheet.py` — extração de sheets de terreno.
- `assets/terrain/ground_tile_contract.json` — contrato canônico.

## Regra para agentes

Ao receber tarefa de tile, **ler este README primeiro** e escolher a receita mínima necessária para aquele asset. Não criar outro normalizador, seam fixer ou gerador específico antes de verificar se o worker existente cobre o caso. Se surgir um defeito recorrente, corrigir a ferramenta reutilizável e documentar a causa aqui.

Não presumir que todo tile precisa de 16 máscaras, rampas, escadas ou transições. Esses recursos são opt-in conforme o tipo de asset e o pedido atual.

Não alterar Blender/building pipeline para corrigir tiles. Tiles e buildings são domínios separados.

## Estrutura alvo

```text
tools/
  tiles/       # pipeline de tiles
  buildings/   # pipeline de buildings
  audio/       # pipeline de áudio
  sprites/     # pipeline de sprites/personagens
```

A migração física dos scripts existentes deve ser incremental: documentação/entrada primeiro, depois mover scripts por domínio atualizando imports e workflows juntos. Isso evita quebrar Actions que já estão em produção.

## Piloto de água contínua

Água é terreno semântico raso/profundo. As receitas Blender em `tools/tycoon_photo_studio/assets/water_surface_*_01.json` produzem a fonte visual; `.github/workflows/tycoon-water-bake.yml` exporta as quatro vistas 128×64 e os mosaicos de diagnóstico. Esses PNGs isolados não devem ser promovidos como tiles repetidos: as bordas alfa e as fases diferentes criam linhas e blocos visíveis.

`tools/tycoon_photo_studio/prepare_water_world_preview.py` usa esses bakes como fonte artística para uma textura periódica amostrada no espaço do mundo, com base rasa/profunda e quatro prévias de rotação sobre uma região 5×5. A profunda usa azul mais forte; o contorno das capturas recebe suavização apenas na silhueta. O script também exporta `<variante>_glint_overlay.png` (brilho RGBA periódico, de baixa opacidade) e `<variante>_motion_preview.gif` (16 quadros, 2 s) para avaliação visual. A animação desloca só o brilho, preservando a base e as bordas contínuas; não usa máscara de terreno nem água 3D no runtime. Antes de promover ao runtime, verificar visualmente as prévias no tamanho do jogo e adaptar a amostragem contínua já prevista em `src/ch_render/map_renderer.cpp`; a margem simples fica como passo separado. A família N/E/S/W de 16 máscaras deste documento pertence aos caminhos, não à superfície da água.

A base e o brilho aprovados foram promovidos a `assets/terrain/water/`. `tools/tycoon_photo_studio/promote_water_surface.py` preserva esses PNGs e acrescenta um mapa de indices e um atlas RGBA de 16 quadros. O ciclo de paletas muda apenas a opacidade do reflexo em ate 3/255, alem do deslocamento suave ja aprovado. O manifesto `assets/terrain/water/water_surfaces.json` documenta periodo mundial de quatro tiles, coordenadas do atlas e duracao de cada quadro. O renderer do jogo e do MapForge agora consome a base e o atlas de brilho em coordenadas do mundo; o jogo registra IDs e cobra $50/$100 por água rasa/profunda. A interface visual de seleção continua como etapa futura.
