# Análise: integrar o LabSEA sintético ao IS Viewer

Esta integração **não foi implementada**. A análise usa o arquivo
`labsea-simulation/saida/labsea.glb` e o script original
`scripts/blender/exportar_glb.py` desse projeto.

## O que existe no arquivo

| Item | Valor inspecionado |
| --- | --- |
| Formato | glTF 2.0 binário (GLB) |
| Tamanho | 9.669.972 bytes, aproximadamente 9,7 MB |
| Nós / malhas | 3.991 / 3.917 |
| Triângulos | 141.864, somando os índices das primitivas |
| Materiais | 27 |
| Imagens | Uma textura PNG embutida, `LabSEA_Terrazzo_1m` |
| Câmeras ópticas / animações | Não incluídas |

O arquivo preserva nomes, hierarquias e propriedades `extras`. Por exemplo,
`Chair_001` e `Chair_013` têm `dynamic=true`, `trackable=true`, tipo de objeto,
dimensões e confiança. Isso permite identificar e mover uma cadeira completa,
sem alterar individualmente seus componentes. As poses ópticas continuam nos NPZ.

## Caminho recomendado

Migrar o desenho do World3D de Canvas 2D para uma cena Three.js e carregar o
arquivo com `GLTFLoader`. O loader suporta glTF 2.0 e as extensões de materiais
presentes neste arquivo: transmissão, índice de refração e intensidade emissiva.
[Documentação oficial do GLTFLoader](https://threejs.org/docs/pages/GLTFLoader.html).

Manter quatro grupos independentes na cena: ambiente sintético, mapa, câmeras
calibradas e dados recebidos do broker. Assim é possível ligar/desligar cada
camada e atualizar as detecções sem recarregar o laboratório. Servir o GLB pelo
próprio viewer, com carregamento sob demanda e cache; usar arquivos JavaScript
locais com versão fixada para não depender de CDN no laboratório.

`OrbitControls` oferece órbita, deslocamento e zoom; sua configuração de botões
pode manter a interação atual, com botão central para deslocar.
[Documentação oficial do OrbitControls](https://threejs.org/docs/pages/OrbitControls.html).

## Alinhamento: o ponto mais importante

As calibrações e o mapa usam metros com **Z para cima**. O exportador usa
`export_yup=True`: `(X, Y, Z)` do laboratório vira `(X, Z, -Y)` no GLB.

Recomendo manter os dados do viewer em Z-up e aplicar ao grupo raiz do GLB uma
rotação de **+90° em X**. A conversão inversa é
`(x_glb, y_glb, z_glb) → (x_glb, -z_glb, y_glb)`. Isso mantém as mensagens e os
NPZ no referencial original. É necessário validar piso, origem e posições das
câmeras antes de sobrepor pessoas ou móveis. Não recentralizar automaticamente
o GLB nem normalizar sua escala.

Para uma visão correspondente à câmera real, reconstruir a pose usando `rt`
e a projeção usando `K` ou `nK`, respeitando resolução e ROI. Um simples
`lookAt` com campo de visão aproximado não reproduz a calibração. A comparação
com imagens corrigidas deve usar `nK`; não aplicar distorção novamente.

## Como aproveitar o laboratório sintético

- **Contexto espacial:** mostrar pessoas/esqueletos entre mesas, paredes e portas.
- **Localização de objetos:** associar IDs estáveis do rastreamento às raízes,
  como `Chair_001`, e atualizar posição/orientação. Essa associação ainda precisa
  de uma regra; os IDs de detecção não equivalem automaticamente aos IDs do GLB.
- **Validação da reconstrução:** identificar pontos flutuando, pessoas sob o
  piso, erros de escala ou trajetórias atravessando paredes.
- **Visões das câmeras:** oferecer atalhos para posições calibradas e comparar
  a vista sintética com o vídeo real, usando a projeção correta.
- **Experimentos reproduzíveis:** reproduzir trajetórias gravadas, avaliar
  cobertura, oclusões e regiões de interesse, e usar renders do projeto Blender
  como dados sintéticos. O viewer apresenta os resultados; não gera sozinho
  uma simulação física nem um conjunto de treinamento.

Para ver dentro do laboratório, será útil esconder teto e certas paredes ou
aplicar transparência. O projeto de simulação informa medidas estimadas e
incertezas: a geometria não deve ser tratada como medição exata de todos os móveis.

## Desempenho e etapas

O tamanho do arquivo e a quantidade de triângulos são administráveis, mas as
3.917 malhas podem resultar em muitas chamadas de desenho. Antes de acrescentar
sombras e efeitos, medir tempo de carregamento, memória e FPS na máquina-alvo.
Agrupar geometria estática por material e usar instâncias para peças repetidas,
preservando as raízes dos objetos móveis. `InstancedMesh` reduz chamadas de
desenho para geometria/material repetidos.
[Documentação oficial do InstancedMesh](https://threejs.org/docs/pages/InstancedMesh.html).

Sequência sugerida:

1. Carregar GLB e validar eixos, escala e pontos de referência.
2. Sobrepor mapa e as sete câmeras; acrescentar visões calibradas.
3. Sobrepor o fluxo de esqueletos e objetos com controles de camadas.
4. Associar objetos rastreados aos IDs do cenário e adicionar reprodução temporal.
5. Otimizar malhas, materiais, iluminação e cache com medições reais.

Para o entorno, o projeto já descreve `ifes.glb` (mundo combinado) e
`entorno.glb` (expansão). Usar `ifes.glb` sozinho ou `labsea.glb` + `entorno.glb`;
carregar o combinado junto com o laboratório duplicaria a geometria.
