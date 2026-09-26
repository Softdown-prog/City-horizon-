# Áudio de interface e atrações

A biblioteca base contém uma seleção de 15 efeitos OGG do pacote local
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

## Roda-gigante

A fonte audiovisual é `Converter/reflections_under_the_wheel.mp4`. O workflow de
áudio extrai somente a faixa sonora para
`Converter/reflections_under_the_wheel.mp3` e gera a cópia OGG/Vorbis usada pelo
runtime em `attractions/ferris_wheel_running.ogg`.

O catálogo expõe essa faixa como `FerrisWheelRunning`. Ela usa uma pista de
efeito contínuo separada das oito pistas de efeitos curtos de UI. O runtime
mantém duas condições obrigatórias para essa pista: pelo menos uma roda-gigante
deve estar em atividade/giro e o footprint lógico dessa roda deve intersectar a
viewport canônica atual. Assim, a faixa começa no mesmo frame em que uma roda
visível entra em atividade, para no mesmo frame em que a atividade termina e
também é silenciada quando todas as rodas ativas saem da área visível. Se uma
roda continuar girando fora da viewport e voltar a ficar visível, a faixa pode
ser retomada naquele frame.

A checagem de visibilidade reutiliza a câmera/zoom/viewport canônicos registrados
pela camada de projeção; não existe uma câmera paralela apenas para áudio. Esta
regra é um culling específico do áudio da atração. Ela não deve ser confundida
com um gerenciador global de chunks: o renderer geral ainda percorre as entidades
do mundo e um sistema global de spatial/chunk culling deve ser tratado
separadamente quando for implementado.

O MP3 é mantido como derivado de áudio puro para inspeção/reuso; o runtime
continua consumindo OGG/Vorbis.
