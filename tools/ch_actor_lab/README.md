# CH Actor Lab — candidato

Abra `index.html` em um navegador com WebGL e acesso ao Three.js r128 pelo CDN indicado no HTML. Esta é uma adaptação do protótipo fornecido pelo usuário para testar um visitante alternativo; não é arte aprovada nem substitui os assets do Visitor Forge 2D.

- Câmera fixa `CH_CAMERA_V1`: yaw 45°, elevação 30°, ortográfica.
- Quatro linhas lógicas S/E/W/N, com rotação do ator e câmera fixa.
- Exportação pelo botão **Exportar PNG RGBA**. A imagem de inspeção ampliada ou captura da tela não é a spritesheet.
- O botão **Exportar manifesto JSON** grava dimensões, fases, câmera, direções, paleta e pivô correspondentes aos controles atuais.
- Para a configuração inicial, o PNG deve ser RGBA **384 × 256**, 8 quadros de **48 × 64** em cada uma das 4 linhas. O pivô é **(24, 60)** em cada quadro.
- O fundo de rua e o ponto vermelho existem apenas no preview.

O modelo original tinha a sola da bota acima de `Y=0` e o enquadramento colocava a origem projetada abaixo da borda do quadro. Esta versão aproxima a sola do chão e posiciona a origem no ground anchor. Ela também separa coxa e canela para um joelho flexionar na perna que avança. Não há garantia de qualidade visual pelo contrato numérico: inspecione as quatro vistas e a caminhada animada em escala de jogo antes de integrar no SDL3.
