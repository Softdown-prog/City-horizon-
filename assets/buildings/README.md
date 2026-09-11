# Assets de edifícios

Os edifícios são sprites 2D já renderizados na mesma projeção isométrica do jogo.

- A câmera do jogo não gira o sprite nem tenta aplicar perspectiva 3D.
- Cada PNG é desenhado usando a âncora `x=0.5`, `y=1.0`: o centro inferior do canvas fica no vértice inferior do footprint no mapa.
- Para um footprint 2x2, esse vértice corresponde a `worldX + 2`, `worldY + 2`.
- O PNG deve ser RGBA com fundo realmente transparente; o JSON ao lado registra classificação e dimensões de grade.
