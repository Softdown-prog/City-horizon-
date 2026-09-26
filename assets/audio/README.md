# Áudio de interface

Esta primeira biblioteca contém uma seleção de 15 efeitos OGG do pacote local
`kenney_interfaceSounds`. Os caminhos em `audio_catalog.json` são relativos a
esta pasta e representam eventos do jogo, não nomes de arquivos espalhados no
código.

O executável carrega este catálogo por meio do `AudioManager`. Os arquivos são
pré-decodificados e mantidos em cache na inicialização, e o jogo dispara apenas
eventos lógicos (por exemplo, `BuildingPlace`), nunca caminhos de arquivos.

O campo `music.Loading` usa uma faixa OGG em uma pista independente com volume
de música. Ela começa durante o carregamento e termina ao fim do arquivo; a
tela de carregamento pode terminar antes da faixa.

`UiClick` tem uma única fonte canônica: o MP3 em `Converter/` convertido para
`ui/mouse_click_002.ogg`. O jogo toca esse efeito uma vez ao pressionar o botão
esquerdo ou direito do mouse, tanto na interface quanto no mapa. O mesmo gesto
não toca outro efeito genérico de seleção, confirmação, abertura ou fechamento
de painel. Erros e efeitos próprios do mundo, como a construção de um prédio,
continuam distintos. Ações de teclado preservam seus próprios sons.
