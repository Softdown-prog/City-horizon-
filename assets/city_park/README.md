# City Park assets

Esta pasta guarda os assets aprovados para o runtime do parque de diversões. Cada família jogável precisa de uma definição em `assets/definitions/` apontando para um sprite daqui; a aba **CITY PARK** em Construções reúne essas definições automaticamente pelo caminho da textura. O manifesto, as quatro direções e as folhas de animação de uma mesma família formam um único item do catálogo.

Itens atuais:

- `ferris_wheel/`: roda-gigante animada (`ferris_wheel_01`).
- `ticket_booth/`: bilheteria estática 2×2 com quatro direções (`park_ticket_booth_01`). Não depende de rua nem de caminho e foi concebida para ficar próxima das atrações.

## Footprint visual x ocupação física das atrações

Atrações grandes podem ter um sprite/envelope visual maior que a área que realmente deve bloquear o mapa. Nesses casos a definição mantém `footprint` como envelope visual usado para ancoragem/render e declara `occupancyFootprint` como a área física reservada para colisão entre construções.

A roda-gigante usa envelope visual 6×5 e ocupação física central 4×3 com offset 1×1. Isso mantém a arte, escala e pivôs atuais, mas libera a faixa externa para colocar a bilheteria, caminhos e futuros props próximos da área de embarque sem atravessar a base física da atração.

Novos brinquedos do City Park que precisarem de bilheteria próxima devem seguir o mesmo princípio: o `occupancyFootprint` deve representar somente a base física que realmente não pode receber outra construção, e deve rotacionar junto com o brinquedo. Não aumente a colisão apenas para cobrir transparência, sombra ou o volume aéreo do sprite.

## Bilheteria, inauguração e preço das atrações

O contrato do City Park segue a lógica de tycoon: **construir o brinquedo não o inaugura automaticamente**. Uma atração com ingresso declara `requiresTicketBooth: true` e nasce fechada/inoperante. Para inaugurar e operar, o jogador precisa construir uma bilheteria com `isParkTicketBooth: true` próxima da atração.

O vínculo usa a ocupação física real das duas construções e aceita contato direto ou até um tile vazio de separação. Isso permite posicionar a bilheteria ao lado da entrada/escadas da roda-gigante sem exigir rua ou caminho. Cada bilheteria atende uma única atração e cada atração recebe uma única bilheteria. Quando existem várias opções no alcance, o vínculo escolhe a atração livre mais próxima e usa a instância mais antiga como desempate determinístico.

Enquanto não houver bilheteria vinculada, o brinquedo permanece fechado: não inicia atividade e não gera clientes nem receita de ingresso. Ao construir uma bilheteria válida perto dele, o brinquedo passa a `operational` e fica inaugurado. Se a bilheteria for demolida, a atração volta a fechar imediatamente e qualquer atividade temporária é encerrada.

Ao clicar na bilheteria, o painel normal de preço ao cliente controla o ingresso do brinquedo vinculado. A bilheteria é a fonte autoritativa desse valor; a atração continua sendo a entidade que recebe os clientes e gera a receita. A bilheteria não cria uma segunda cobrança nem duplica o faturamento.

Para os próximos brinquedos pagos, declare `requiresTicketBooth: true`, mantenha um preço de serviço válido e configure um `occupancyFootprint` coerente com a base física. A bilheteria padrão declara `isParkTicketBooth: true`. Os intervalos e passos de preço entre bilheteria e atração devem ser compatíveis.

Este contrato cobre requisito de inauguração, vínculo, operação e preço. A simulação completa de visitantes formando fila, entrando fisicamente na atração e desembarcando continua sendo uma etapa de gameplay separada.

Mantenha câmera isométrica, escala, RGBA transparente, pivôs consistentes e empacotamento compatível com a engine ao promover novos assets para esta pasta.
