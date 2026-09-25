# Bilheteria: estudo de acabamento V1

`finish_study.png` é uma revisão visual RGBA da referência enviada pelo
usuário. `finish_study_192px.png` mostra a leitura do mesmo estudo em tamanho
reduzido, com transparência preservada. Ambos são **conceitos para revisão**;
não são exportações do Building Composer nem sprites aprovados para `assets/`.

A fonte reproduzível da bilheteria continua em
`C++/MapForge2/src/composer_preview_main.cpp` e os módulos desenhados em
`C++/MapForge2/src/building_facade_renderer.cpp`. A revisão conserva a vista
isométrica fixa, telhado piramidal vermelho, balcão com toldo listrado na face
SOUTH, arco e letreiro azul na face EAST, madeira, quoinas de pedra e bandeira
amarela. O acabamento pretendido é telha com cursos legíveis, reboco sutil,
sombras locais sob toldo e eiras, balcão com topo/profundidade, moldura do arco
e letreiro em relevo. Evitar microtextura e contornos pretos a 192 px.

O renderer usa um único edifício 2×2 nas quatro rotações canônicas. Depois de
gerar `building_composer_ticket_booth_review.png` e
`building_composer_ticket_booth_4view.png`, revisar visualmente as quatro vistas
e comparar numa captura de mapa antes de promover a sprite. O estudo de imagem
não garante correspondência exata com as saídas procedurais.
