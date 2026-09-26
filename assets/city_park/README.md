# City Park assets

Esta pasta guarda os assets aprovados para o runtime do parque de diversões. Cada família jogável precisa de uma definição em `assets/definitions/` apontando para um sprite daqui; a aba **CITY PARK** em Construções reúne essas definições automaticamente pelo caminho da textura. O manifesto, as quatro direções e as folhas de animação de uma mesma família formam um único item do catálogo.

Itens atuais:

- `ferris_wheel/`: roda-gigante animada (`ferris_wheel_01`).
- `ticket_booth/`: bilheteria estática 2×2 com quatro direções (`park_ticket_booth_01`). Não depende de rua nem de caminho e foi concebida para ficar próxima das atrações.

## Footprint visual x ocupação física das atrações

Atrações grandes podem ter um sprite/envelope visual maior que a área que realmente deve bloquear o mapa. Nesses casos a definição mantém `footprint` como envelope visual usado para ancoragem/render e declara `occupancyFootprint` como a área física reservada para colisão entre construções.

A roda-gigante usa envelope visual 6×5 e ocupação física central 4×3 com offset 1×1. Isso mantém a arte, escala e pivôs atuais, mas libera a faixa externa para colocar a bilheteria, caminhos e futuros props próximos da área de embarque sem atravessar a base física da atração.

Novos brinquedos do City Park que precisarem de bilheteria próxima devem seguir o mesmo princípio: o `occupancyFootprint` deve representar somente a base física que realmente não pode receber outra construção, e deve rotacionar junto com o brinquedo. Não aumente a colisão apenas para cobrir transparência, sombra ou o volume aéreo do sprite.

## Bilheteria e preço das atrações

A bilheteria é o controle de preço do brinquedo com ingresso mais próximo. O vínculo usa o `footprint` visual da bilheteria e da atração e aceita contato direto, sobreposição apenas do envelope visual liberado pelo `occupancyFootprint` ou até um tile vazio de separação. Isso permite posicioná-la ao lado da entrada/escadas da roda-gigante sem exigir rua ou caminho.

Ao clicar na bilheteria, o painel normal de preço ao cliente fica disponível. Alterar esse valor sincroniza o preço da atração compatível mais próxima. A atração continua sendo a entidade que gera a receita; a bilheteria não cria uma segunda cobrança nem duplica o faturamento. Quando existe uma bilheteria vinculada, ela é a fonte autoritativa do preço. Sem bilheteria próxima, o preço continua podendo ser configurado diretamente na atração.

Para os próximos brinquedos, o contrato atual considera compatível qualquer definição de categoria `service`, com preço de serviço habilitado e sprite em `assets/city_park/`. Se mais de uma atração estiver no alcance, vence a de menor distância; em empate, a instância mais antiga. Se mais de uma bilheteria resolver para a mesma atração, a bilheteria colocada primeiro é autoritativa e as demais espelham o preço dela.

Esse vínculo de preço não implementa embarque de visitantes. A simulação de filas, embarque e acionamento da animação durante o passeio continua sendo uma etapa de gameplay separada.

Mantenha câmera isométrica, escala, RGBA transparente, pivôs consistentes e empacotamento compatível com a engine ao promover novos assets para esta pasta.
