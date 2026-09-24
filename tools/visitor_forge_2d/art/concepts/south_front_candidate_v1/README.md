# SOUTH frontal — aparência aprovada, caminhada em prévia

Este estudo usa o mesmo visitante como referência e corrige somente a
orientação visual SOUTH. O usuário aprovou a vista frontal, inclusive a
diferença no rosto. Não substitui `frames_preview/` nem altera EAST, NORTH ou
WEST: a nova caminhada ainda precisa ser vista no jogo antes da promoção.

- `south_front_master.png`: fonte RGBA de 512×512, derivada de uma revisão
  visual frontal e normalizada no canvas do Visitor Forge. Editar este master
  para qualquer retoque durável de rosto, cor ou juntas.
- `south_idle.png`, `south_walk_a.png`, `south_walk_b.png`: três frames
  exportados pelo rig de recorte 2D, em 128×128, com pés na linha 115 e
  anchor `[64,116]`. A e B alternam o pé de apoio, levantam o pé oposto e
  balançam os braços; cada pose dura 220 ms.
- `poses/south_walk_a.json`, `poses/south_walk_b.json`: poses exclusivas da
  candidata; as poses das demais direções e do SOUTH original permanecem.
- `south_old_vs_front_three_poses.png`: três frames existentes à esquerda,
  três candidatos frontais à direita, em escala nativa sobre fundo neutro.
- `south_old_vs_front_map_56px.png`: esquerda original, direita candidato,
  mesma captura de MapForge, mesmo ponto dos pés e corpo exibido a 56 px.
- `south_gait_56px.png`: idle, A e B da candidata em escala de jogo (56 px
  de altura), com os pés alinhados na mesma linha.

No recorte original, A/B diferiam pouco do idle (silhueta 5–6%). Nas novas
poses, a diferença é 26,6% e 26,4%; o pé mais baixo permanece na linha 115
nos três PNGs. Isto demonstra uma alternância de pés na arte, sem ainda
demonstrar ausência de deslizamento durante movimento no motor.

Para reconstruir os três frames após retocar o master:

```bash
ch-visitor-forge-2d build-concept-rig \
  --master tools/visitor_forge_2d/art/concepts/south_front_candidate_v1/south_front_master.png \
  --direction south \
  --asset-root out/visitor_forge_2d/south_front/parts \
  --definition-output out/visitor_forge_2d/south_front/definition.json

ch-visitor-forge-2d prototype \
  --definition out/visitor_forge_2d/south_front/definition.json \
  --pose tools/visitor_forge_2d/poses/concept/south_idle.json \
  --pose tools/visitor_forge_2d/art/concepts/south_front_candidate_v1/poses/south_walk_a.json \
  --pose tools/visitor_forge_2d/art/concepts/south_front_candidate_v1/poses/south_walk_b.json \
  --asset-root out/visitor_forge_2d/south_front/parts \
  --output out/visitor_forge_2d/south_front/frames
```

A opção local `CH_VISITOR_FORGE_PREVIEW=ON` inclui este estudo como quinta
aparência F8, depois da prévia atual do Visitor Forge. Nesta mesma aparência,
EAST/NORTH/WEST já usam os novos passos da receita vizinha
`../directional_gait_candidate_v1/`. Para realmente ver
SOUTH andando, marque início com F3 e destino numa rua ao longo de +Y com
F4; F6 envia o visitante pelo caminho. F7 sempre usa seis tiles ao longo
de +X e portanto mostra EAST. A trajetória SOUTH aparece diagonal na tela
isométrica; a correção aqui é a direção **do corpo**, não a projeção do mapa.
Ao selecionar a candidata via F8, a prévia F6 inicia em 0,30 tile/s para
acompanhar os passos curtos (440 ms por ciclo); o ajuste de velocidade F7 ainda
permite outros valores e pode exigir nova calibração visual. Se ela atravessar
um trajeto a velocidade diferente, reavaliar a cadência junto com a rota.

**Gate visual restante:** rodar F6 para SOUTH num caminho +Y e verificar,
em movimento, contato alternado dos sapatos, transparência nas juntas e
possível deslizamento; somente então decidir sobre a promoção ao runtime.
