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

`python tools/ch_actor_lab/build_umbrella_overlays.py` gera 36 overlays e 36 máscaras em `assets/characters/ch_actor_green_01/umbrella/{frames,masks}/`, usando exatamente os nomes e a grade 48×64 dos frames aprovados. A ferramenta amostra a mão externa em cada pose para posicionar a haste, sem modificar o personagem original; `art/umbrella_v1/review.png` mostra idle e duas fases de caminhada das quatro direções. Para produzir também a simulação de escala de jogo em `art/umbrella_v1/{map_review.png,walk_review.gif}`, use `--map-capture tools/visitor_forge_2d/art/concepts/map_review/four_directions_56px.png`. Essa composição sobre uma captura anterior **não é uma captura do runtime SDL**. R da máscara seleciona o tecido, B guarda a sombra e A preserva o recorte; o cabo e o contorno mantêm suas cores. O runtime compõe e guarda em cache uma textura por quadro/cor, desenha sobre o ator somente com chuva e não altera a navegação nem o pivô do pé. Ao regenerar, confira a prancha e o resultado sobre mapa no tamanho de jogo.
