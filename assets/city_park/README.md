# City Park assets

Esta pasta guarda os assets aprovados para o runtime do parque de diversões. Cada família jogável precisa de uma definição em `assets/definitions/` apontando para um sprite daqui; a aba **CITY PARK** em Construções reúne essas definições automaticamente pelo caminho da textura. O manifesto, as quatro direções e as folhas de animação de uma mesma família formam um único item do catálogo.

Itens atuais:

- `ferris_wheel/`: roda-gigante animada (`ferris_wheel_01`).
- `ticket_booth/`: bilheteria estática 2×2 com quatro direções (`park_ticket_booth_01`). Precisa de rua ou caminho adjacente e foi concebida como entrada da roda-gigante.

O vínculo visual da bilheteria com a roda não implementa embarque de visitantes. A simulação de filas, embarque e acionamento da animação durante o passeio requer uma etapa de gameplay própria. O preço do ingresso continua configurado na roda-gigante; a bilheteria não cobra um segundo ingresso.

Mantenha câmera isométrica, escala, RGBA transparente, pivôs consistentes e empacotamento compatível com a engine ao promover novos assets para esta pasta.
