# CH Actor Lab — candidato

Abra `index.html` em um navegador com WebGL e acesso ao Three.js r128 pelo CDN indicado no HTML. Esta é uma adaptação do protótipo fornecido pelo usuário para testar um visitante alternativo; não é arte aprovada nem substitui os assets do Visitor Forge 2D.

- Câmera fixa `CH_CAMERA_V1`: yaw 45°, elevação 30°, ortográfica.
- Quatro linhas lógicas S/E/W/N, com rotação do ator e câmera fixa.
- Exportação pelo botão **Exportar PNG RGBA**. A imagem de inspeção ampliada ou captura da tela não é a spritesheet.
- O botão **Exportar manifesto JSON** grava dimensões, fases, câmera, direções, paleta e pivô correspondentes aos controles atuais.
- Para a configuração inicial, o PNG deve ser RGBA **384 × 256**, 8 quadros de **48 × 64** em cada uma das 4 linhas. O pivô é **(24, 60)** em cada quadro.
- O fundo de rua e o ponto vermelho existem apenas no preview.

O modelo original tinha a sola da bota acima de `Y=0` e o enquadramento colocava a origem projetada abaixo da borda do quadro. Esta versão aproxima a sola do chão e posiciona a origem no ground anchor. Ela também separa coxa e canela para um joelho flexionar na perna que avança. Não há garantia de qualidade visual pelo contrato numérico: inspecione as quatro vistas e a caminhada animada em escala de jogo antes de integrar no SDL3.

## Geração offline verificável

`software_render.py` é um segundo renderizador, determinístico e sem navegador ou CDN. Ele mantém o visual do candidato (jaqueta verde, calça azul, cabelo marrom) e usa uma descrição articulada única para todas as vistas. O rosto e a camisa aparecem apenas em SOUTH/EAST; NORTH/WEST mostram as costas. O movimento usa oito fases, balanço oposto de braços, flexão da perna que avança e poses de transferência de peso distintas em `t=0` e `t=0.5`.

```bash
python tools/ch_actor_lab/software_render.py \
  --output tools/ch_actor_lab/art/software_v1 \
  --catalog tools/ch_actor_lab/runtime_preview/ch_actor_software_v1.json \
  --map-capture out/visitor_forge_2d/map_capture/mapforge_ice_cream_inactive_vs_active.png
```

O argumento `--map-capture` é opcional e produz uma composição PNG/GIF de inspeção; a captura MapForge não é gerada por esta ferramenta. O GIF desenha tiles de validação de cimento, areia, rua e terra sobre a captura de grama, com ponto amarelo no contato do pé; esses tiles são uma simulação visual, não uma captura do SDL3. Os 36 PNGs versionados em `art/software_v1/frames/` são 48×64 RGBA (8 walking + idle por direção). O manifesto também é versionado; atlas e prévias são reconstruídos pelo comando acima. Nenhum fundo de mapa é misturado aos frames.

Com `CH_VISITOR_FORGE_PREVIEW=ON`, o catálogo `ch_actor_software_v1` aparece como opção de teste F8 e como visual inicial de F7, se estiver presente. O teste usa escala nativa, anchor `[24,60]`, aproximadamente 138 ms por fase e rota de 0,30 tile/s. A frente do sprite acompanha o movimento: S↙, E↘, W↖, N↗ na câmera padrão. F7 tenta primeiro um trajeto sobre pisos pintados, depois rua. O contato fica no centro do tile, e a navegação atravessa estilos adjacentes de terra, areia, cimento e rua, mas nunca grama vazia ou piso de grama. O personagem fica `walking` durante o deslocamento e `idle` ao chegar, preservando a última direção; F6 aceita início e destino em pisos ou ruas. A inclusão é somente no modo debug; os PNGs ainda não foram promovidos a `assets/` nem aprovados como arte final. Confirme a passada no executável antes da promoção.
