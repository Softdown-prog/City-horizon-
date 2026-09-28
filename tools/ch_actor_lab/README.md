# CH Actor Lab — fonte do pedestre aprovado

Abra `index.html` em um navegador com WebGL e acesso ao Three.js r128 pelo CDN indicado no HTML. É um laboratório de comparação do protótipo fornecido pelo usuário. A fonte determinística do visual aprovado é `software_render.py`; o runtime consome apenas as cópias congeladas em `assets/`.

- Câmera fixa `CH_CAMERA_V1`: yaw 45°, elevação 30°, ortográfica.
- Quatro linhas lógicas S/E/W/N, com rotação do ator e câmera fixa.
- Exportação pelo botão **Exportar PNG RGBA**. A imagem de inspeção ampliada ou captura da tela não é a spritesheet.
- O botão **Exportar manifesto JSON** grava dimensões, fases, câmera, direções, paleta e pivô correspondentes aos controles atuais.
- Para a configuração inicial, o PNG deve ser RGBA **384 × 256**, 8 quadros de **48 × 64** em cada uma das 4 linhas. O pivô é **(24, 60)** em cada quadro.
- O fundo de rua e o ponto vermelho existem apenas no preview.

O modelo original tinha a sola da bota acima de `Y=0` e o enquadramento colocava a origem projetada abaixo da borda do quadro. Esta versão aproxima a sola do chão e posiciona a origem no ground anchor. Ela também separa coxa e canela para um joelho flexionar na perna que avança. O laboratório WebGL não é a fonte dos quadros congelados do runtime.

## Geração offline verificável

`software_render.py` é um segundo renderizador, determinístico e sem navegador ou CDN. Ele mantém o visual do candidato (jaqueta verde, calça azul, cabelo marrom) e usa uma descrição articulada única para todas as vistas. O rosto e a camisa aparecem apenas em SOUTH/EAST; NORTH/WEST mostram as costas. O movimento usa oito fases, balanço oposto de braços, flexão da perna que avança e poses de transferência de peso distintas em `t=0` e `t=0.5`.

```bash
python tools/ch_actor_lab/software_render.py \
  --output tools/ch_actor_lab/art/software_v1 \
  --catalog tools/ch_actor_lab/runtime_preview/ch_actor_software_v1.json \
  --map-capture out/visitor_forge_2d/map_capture/mapforge_ice_cream_inactive_vs_active.png
```

O argumento `--map-capture` é opcional e produz uma composição PNG/GIF de inspeção; a captura MapForge não é gerada por esta ferramenta. O GIF desenha tiles de validação de cimento, areia, rua e terra sobre a captura de grama, com ponto amarelo no contato do pé; esses tiles são uma simulação visual, não uma captura do SDL3. Os 36 PNGs versionados em `art/software_v1/frames/` são 48×64 RGBA (8 walking + idle por direção). O manifesto também é versionado; atlas e prévias são reconstruídos pelo comando acima. Nenhum fundo de mapa é misturado aos frames.

Os 36 quadros aprovados foram copiados sem alteração para `assets/characters/ch_actor_green_01/frames/`. O catálogo de produção `assets/definitions/animations/ch_actor_green_01.json` aponta para eles. A câmera padrão usa S↙, E↘, W↖, N↗, pivô `[24,60]` e a velocidade é 0,30 tile/s. O runtime carrega esse catálogo independentemente de `CH_VISITOR_FORGE_PREVIEW`; F7/F8 permanecem controles de desenvolvedor. O nó de decisões escolhe um passeio por tiles de terra, areia, cimento ou rua, dá oportunidade para visita comercial e retorna à residência acessível para repousar. Não atravessa grama nem obstáculos. O save individual de pedestres fica para outra etapa.

## Máscara de roupas no runtime

`python tools/ch_actor_lab/build_clothing_masks.py` cria os 36 PNGs em `assets/characters/ch_actor_green_01/masks/` e uma prancha de revisão em `art/color_masks_v1/review.png`. Cada máscara tem exatamente 48×64 e o mesmo nome do frame. O canal R marca a jaqueta, G marca a calça, B guarda a luz e sombra da peça, e A acompanha o alpha original nos pixels marcados. O runtime recompõe somente o RGB dessas peças, preservando o alpha, a pose e o pivô dos PNGs aprovados. A paleta de jaquetas e calças é sorteada uma vez quando a instância nasce e não é recalculada ao caminhar, mudar de direção, visitar ou repousar. Outros personagens não usam essas máscaras.

## Overlay de guarda-chuva

`python tools/ch_actor_lab/build_umbrella_overlays.py` gera 36 overlays e 36 máscaras em `assets/characters/ch_actor_green_01/umbrella/{frames,masks}/`, usando exatamente os nomes e a grade 48×64 dos frames aprovados. A ferramenta amostra a mão externa em cada pose para posicionar a haste, sem modificar o personagem original; `art/umbrella_v1/review.png` mostra idle e duas fases de caminhada das quatro direções. O tecido tem cinco gomos com variação de luz, ponteira metálica e acabamento na borda. R da máscara seleciona o tecido, B guarda a sombra e A preserva o recorte; o cabo e o contorno mantêm suas cores. O runtime compõe e guarda em cache uma textura por quadro/cor, desenha sobre o ator somente com chuva e não altera a navegação nem o pivô do pé.

Para reconstruir a simulação de escala de jogo em `art/umbrella_v1/{map_review.png,walk_review.gif}`, use `--map-capture tools/ch_actor_lab/art/umbrella_v1/map_background.png`. Esse fundo é um recorte limpo da captura MapForge `mapforge_ice_cream_inactive_vs_active.png`, sem personagem. **Não use** `tools/visitor_forge_2d/art/concepts/map_review/four_directions_56px.png`: essa prancha já contém o ator parado descartado. A simulação só adiciona o pedestre atual com guarda-chuva sobre o fundo limpo; **não é uma captura do runtime SDL**. Confira também a prancha e a animação no tamanho de jogo após regenerar.

### Estudo da copa no CH Blender

`tools/tycoon_photo_studio/build_actor_umbrella_guarded.py` cria um guarda-chuva curvo em gomos no estúdio e câmera congelados. Os jobs `character.actor_umbrella.preflight.001` e `character.actor_umbrella.proxy.001` fazem o preflight e um proxy SOUTH. O proxy gera `proxy_south.png` e `fabric_mask_south.png` com a mesma projeção. `compose_blender_umbrella_study.py --proxy-dir out/ch_blender_agent/character.actor_umbrella.proxy.001` monta uma comparação da copa 3D reduzida com a arte atual, desenhando a parte inferior da haste até a mão em cada pose. Este é um **estudo**, sem promoção automática para `assets/`; a pasta de runtime continua usando os overlays aprovados até que o proxy seja inspecionado no tamanho de jogo. O bake final em quatro direções exige o gate de revisão do CH Blender e nova validação do recorte/máscara 48×64.

O proxy `character.actor_umbrella.proxy.003` passou no preflight, mas a comparação no mapa em 48×64 revelou uma copa achatada, clara e com pouco contraste. A revisão `character.actor_umbrella.proxy.004` eleva a coroa do modelo 3D; a composição usa o passe de tecido para recuperar a cor do jogo e preservar a iluminação de cada gomo, com contorno de um pixel. Refaça a comparação com os PNGs do mesmo job usando `--proxy-dir out/ch_blender_agent/character.actor_umbrella.proxy.004`. A cor, a máscara e o contato na mão devem ser inspecionados juntos. Não reutilize o SHA de aprovação do proxy anterior após modificar a geometria.

O estudo `character.actor_umbrella.proxy.005` mantém a geometria elevada, mas troca o tecido por branco e alterna seis dos doze gomos como faixas recoloríveis. O CH Blender gera `proxy_south.png`, `fabric_mask_south.png` (cobertura total do tecido) e `accent_mask_south.png` (somente os seis gomos alternados). `compose_blender_umbrella_study.py --proxy-dir out/ch_blender_agent/character.actor_umbrella.proxy.005` reduz os três passes juntos, preserva a luz nos gomos e gera `palette.png` com verde, vermelho, rosa, azul, laranja, amarelo e roxo. No par 48×64, R da máscara de overlay seleciona apenas as faixas; o tecido branco, nervuras, ponteira e cabo ficam fora da recoloração. O runtime já sorteia uma destas sete cores por pedestre, mas somente os assets aprovados e promovidos a `assets/` são usados pelo jogo. Revisar o proxy SOUTH no mapa antes de pedir o bake final das quatro direções.

Depois da aprovação visual do proxy `.005`, um job `qualityStage: final` deve registrar seu SHA-256 no gate `approval` e chamar o mesmo builder. O estágio final produz `canopy_<direction>.png`, `fabric_mask_<direction>.png` e `accent_mask_<direction>.png` para SOUTH/EAST/WEST/NORTH. `python tools/ch_actor_lab/compose_blender_umbrella_final.py --final-dir <artifact-final> --output <diretorio-de-revisao>` monta os 36 overlays 48×64 em staging, verifica alinhamento da máscara em todas as poses e gera `four_directions.png`. Inspecionar as quatro vistas e o mapa antes de substituir `assets/characters/ch_actor_green_01/umbrella/`; o C++ já recolore os pixels R=255 e sorteia a cor no nascimento.

O proxy `.005` foi aprovado visualmente e o job `character.actor_umbrella.final.001` (workflow run `36358804067`) gerou as quatro direções. Os 36 pares em `assets/characters/ch_actor_green_01/umbrella/{frames,masks}/` agora são derivados desse bake CH Blender, com a copa branca e seis gomos alternados recoloríveis; a origem e o SHA aprovado constam em `umbrella/manifest.json`. `build_umbrella_overlays.py` documenta o protótipo anterior e **não deve sobrescrever** os PNGs promovidos. No runtime, a máscara R seleciona apenas os gomos coloridos; as sete cores continuam sendo sorteadas uma vez por pedestre em `src/pedestrian_system.cpp` e exibidas apenas durante a chuva.
