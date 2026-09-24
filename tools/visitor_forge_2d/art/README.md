# Peças 2D autoradas

Esta pasta recebe PNGs de origem desenhados para o Visitor Forge. O compositor
procura cada peça aqui antes de usar a versão procedural em `--asset-root`.

Exemplo de caminho: `visitor_male_01/south/torso.png`. Copie a peça correspondente
da pasta gerada, pinte dentro do mesmo canvas e mantenha PNG RGBA com alpha.
O compositor recusa dimensões diferentes, imagem vazia ou ausência do diretório
`--art-root`; um arquivo não encontrado cai na peça procedural.

As peças desta pasta são fontes versionadas, não sprites classificados no jogo.
Revise `idle`, `walk A` e `walk B` no tamanho nativo sobre terreno antes de
promover qualquer biblioteca. Retoques na pasta temporária `out/` não são
fontes persistentes.

`concepts/visitor_male_01_south_master.png` é a fonte de 512 px para o estudo
articulável de `build-concept-rig`. As peças derivadas desse estudo vão para
`out/` e podem ser reconstruídas. Não confunda o master e seus previews com
camadas autoradas em `art/visitor_male_01/south/` ou com arte aprovada no jogo.
