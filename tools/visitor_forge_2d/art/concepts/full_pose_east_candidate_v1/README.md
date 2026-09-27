# EAST — duas poses completas para revisão

`east_pose_a_master.png` e `east_pose_b_master.png` são pinturas RGBA completas
de 512×512 baseadas na aparência canônica do `visitor_male_01`. A perna próxima
avança em A e recua em B; os braços acompanham o passo em oposição. Não há
recorte de perna nem deformação de junta entre os quadros.

`export_preview.py` reduz os dois masters a 128×128 com alfa preservado e
produz `east_walk_128px.png` (A / B), `east_walk_56px.png` (idle / A / B) e
`east_walk_56px.gif` (A / B em 270 ms por quadro). Executar a partir da raiz
do repositório:

```bash
python tools/visitor_forge_2d/art/concepts/full_pose_east_candidate_v1/export_preview.py
```

O par EAST recebeu aprovação visual provisória na comparação A/B. O catálogo
`runtime_preview/visitor_male_01_full_pose_east_candidate.json` o mantém como
sexta aparência do teste F8, após a candidata anterior; F3/F4/F6 em rota EAST
testa a cadência de 270 ms por quadro a 0,30 tile/s. Uma compilação explícita
do `city_builder` com `CH_VISITOR_FORGE_PREVIEW=ON` atualiza os arquivos de
prévia junto ao executável.

**Gate pendente:** conferir em movimento no mapa contato dos pés, transição com
idle, rosto e braços. WEST, NORTH e SOUTH ainda apontam para os quadros
anteriores neste catálogo. Nada foi promovido a `assets/`.
