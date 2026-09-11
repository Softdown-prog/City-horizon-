# Áudio de interface

Esta primeira biblioteca contém uma seleção de 15 efeitos OGG do pacote local
`kenney_interfaceSounds`. Os caminhos em `audio_catalog.json` são relativos a
esta pasta e representam eventos do jogo, não nomes de arquivos espalhados no
código.

O executável carrega este catálogo por meio do `AudioManager`. Os arquivos são
pré-decodificados e mantidos em cache na inicialização, e o jogo dispara apenas
eventos lógicos (por exemplo, `BuildingPlace`), nunca caminhos de arquivos.
