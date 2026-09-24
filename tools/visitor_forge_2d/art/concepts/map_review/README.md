# Revisão de escala no MapForge

- `south_97_vs_56.png`: mesmo `south_idle` diante da mesma loja e com o mesmo
  ponto dos pés. Esquerda: corpo nativo de 97 px; direita: candidato de 56 px.
- `four_directions_56px.png`: as quatro direções no mesmo ponto, com 56 px.
- `south_97_vs_56.json`: dimensões, coordenadas e SHA-256 do frame e captura.
- `ferris_97_vs_56.png` e `.json`: a mesma comparação junto à roda-gigante.

Contexto: [MapForge Ice Cream Comparison, run 35934307091](https://github.com/Softdown-prog/City-horizon-/actions/runs/35934307091),
artefato `MapForge-Ice-Cream-Inactive-vs-Active` (ID `10781869942`). O PNG da
captura é `mapforge_ice_cream_inactive_vs_active.png`. O exemplo de reprodução
está no README da ferramenta. São composições de revisão, não sprites do jogo.
O segundo contexto vem do [MapForge Capture, run 35932996026](https://github.com/Softdown-prog/City-horizon-/actions/runs/35932996026),
artefato `MapForge2-Deterministic-Asset-Capture` (ID `10782236410`), arquivo
`mapforge_asset_capture.png`.

O resultado sugere exibir o visitante menor, mas não aprova 56 px como escala
final. Falta verificar na engine as calçadas, edifícios diferentes, ordenação
de profundidade e animação durante o movimento.
