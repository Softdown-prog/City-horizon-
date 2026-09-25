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

## Contrato das quatro direções

A bilheteria é **um único objeto físico 2×2**. SOUTH, EAST, WEST e NORTH são
somente rotações canônicas da mesma definição; nenhuma vista pode ser redesenhada
ou espelhada manualmente para parecer melhor na tela.

- O balcão e o toldo pertencem fisicamente à fachada SOUTH.
- O arco de entrada e o frontão azul pertencem fisicamente à fachada EAST.
- Quoinas, acabamento de beiral e telhado pertencem à estrutura e acompanham a
  rotação.
- A bandeira fica ancorada ao centro do telhado e não muda de posição física.
- NORTH e WEST não recebem cópias inventadas do balcão ou do arco. Essas vistas
  apenas mostram as faces que realmente ficam visíveis depois da rotação.
- Proporção, paleta, altura, footprint e iluminação devem permanecer idênticos
  entre as quatro vistas.

Esse contrato existe para permitir que modelos menores continuem o asset sem
inferir posições por aparência de tela. Ao editar uma peça, pensar sempre em
**fachada lógica do prédio**, nunca em "lado esquerdo/direito da imagem".

## Régua de escala com NPC

A referência de personagem do jogo para este asset é **56 px de altura**. A
bilheteria deve continuar lendo como uma construção pequena de parque, mas toda
abertura funcional precisa parecer utilizável por esse NPC.

Metas visuais para o próximo passe:

- NPC de referência: 56 px.
- topo livre da passagem do arco: alvo de aproximadamente 68 px acima do chão
  (cerca de 1,21× a altura do NPC);
- folga sobre a cabeça na passagem: aproximadamente 12 px;
- topo do balcão de atendimento: alvo de aproximadamente 28–32 px acima do chão;
- borda frontal do toldo: deve permanecer acima do balcão e próxima da linha da
  cabeça do NPC, sem interceptar a área de atendimento;
- parede até o beiral: manter a leitura compacta já aprovada;
- telhado, frontão e bandeira contam para a silhueta total, mas não devem ser
  usados para justificar uma porta ou balcão fora de escala.

Antes de promover a sprite, comparar pelo menos uma vista com uma silhueta de
NPC de 56 px posicionada no arco e outra diante do balcão. Essa régua é apenas
de revisão e não deve ser exportada no PNG final.

## Gate de revisão

O renderer usa um único edifício 2×2 nas quatro rotações canônicas. Depois de
gerar `building_composer_ticket_booth_review.png` e
`building_composer_ticket_booth_4view.png`, revisar visualmente as quatro vistas
e comparar numa captura de mapa antes de promover a sprite. O estudo de imagem
não garante correspondência exata com as saídas procedurais.

Não promover enquanto uma rotação exigir correção manual independente. Qualquer
correção deve voltar para a geometria, módulo ou socket físico compartilhado,
para que as quatro direções sejam regeneradas pela mesma fonte.
