# Cenários canônicos

`initial_city.json` é um save V7 para teste visual e funcional. Ele segue a planta original: avenida cívica ao norte, comércio no eixo central, casas voltadas à rua residencial, praça, calçada linear e uma fazenda independente da rede viária. Todo o conteúdo fica no lote inicial, deixando os limites livres para expansão.

Ele não substitui o save pessoal. Para carregá-lo no jogo atual, copie-o para `%LOCALAPPDATA%\CityBuilder\city_save.json` somente depois de preservar, se necessário, o save que já existir; então use F9.

O cenário inicia pausado no dia 18, mês 3, ano 1, com os cinco lotes necessários adquiridos, uma reserva de fundos de teste e inventário agrícola suficiente para demonstrar os bônus locais de cafeteria, padaria e mini mercado.

`coastal_forest_hydroelectric.json` é uma variação gerada pelo Map Forge a
partir desse cenário. Ela preserva a praia existente, posiciona a usina
hidrelétrica no ponto canônico da costa e acrescenta uma floresta esparsa no
limite noroeste, sempre com assets, footprints e limites validados. Gere-a de
novo sem tocar no cenário-base com:

`python -m tools.map_forge.cli generate-coastal-district --asset-root build --scenario assets/scenarios/initial_city.json --output assets/scenarios/coastal_forest_hydroelectric.json`
