# City Park assets

Esta pasta guarda os assets aprovados para o runtime do parque de diversões. Cada família jogável precisa de uma definição em `assets/definitions/` apontando para um sprite daqui; a aba **CITY PARK** em Construções reúne essas definições automaticamente pelo caminho da textura. O manifesto, as quatro direções e as folhas de animação de uma mesma família formam um único item do catálogo.

Itens atuais:

- `ferris_wheel/`: roda-gigante animada (`ferris_wheel_01`).
- `ticket_booth/`: bilheteria estática 2×2 com quatro direções (`park_ticket_booth_01`). Não depende de rua nem de caminho e foi concebida para ficar próxima das atrações.

## Footprint visual x ocupação física das atrações

Atrações grandes podem ter um sprite/envelope visual maior que a área que realmente deve bloquear o mapa. Nesses casos a definição mantém `footprint` como envelope visual usado para ancoragem/render e declara `occupancyFootprint` como a área física reservada para colisão entre construções.

A roda-gigante usa envelope visual 6×5 e ocupação física central 4×3 com offset 1×1. Isso mantém a arte, escala e pivôs atuais, mas libera a faixa externa para colocar a bilheteria, caminhos e futuros props próximos da área de embarque sem atravessar a base física da atração.

Novos brinquedos do City Park que precisarem de bilheteria próxima devem seguir o mesmo princípio: o `occupancyFootprint` deve representar somente a base física que realmente não pode receber outra construção, e deve rotacionar junto com o brinquedo. Não aumente a colisão apenas para cobrir transparência, sombra ou o volume aéreo do sprite.

O vínculo visual da bilheteria com a roda não implementa embarque de visitantes. A simulação de filas, embarque e acionamento da animação durante o passeio requer uma etapa de gameplay própria. O preço do ingresso continua configurado na atração; a bilheteria não cobra um segundo ingresso.

Mantenha câmera isométrica, escala, RGBA transparente, pivôs consistentes e empacotamento compatível com a engine ao promover novos assets para esta pasta.
