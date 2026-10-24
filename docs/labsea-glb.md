# LabSEA sintético

A visualização opcional está em `/world3d-sintetico/`. Ela usa o mesmo tópico
padrão de `/world3d/`, `SkeletonDetector.3D.Annotations`. Para outro tópico de
`ObjectAnnotations`, abra `/world3d-sintetico/Meu.Topico` ou use o campo no topo.
Há links entre as duas visualizações e para a página de calibração.

## Como usar

1. Inicie o viewer conforme o [README](../README.md#rodar-localmente).
2. Abra `http://localhost:3000/world3d-sintetico/`.
3. Arraste com o botão esquerdo para girar, com o botão central para deslocar e
   use a roda para aproximar ou afastar. **Enquadrar** ajusta a vista às camadas
   visíveis.
4. Marque as camadas desejadas: laboratório, paredes e teto, cadeiras, eixos e
   grade, câmeras 1–4, mapa, câmeras 6–8 e esqueletos.

Esconder **Paredes e teto** oculta os nós `Parede_*`, `Tile_*` e `Ceiling_*` do
GLB para facilitar a inspeção do interior. Os rótulos das câmeras levam a
`/calib/<id>`. O mapa e as câmeras vêm do mesmo JSON usado pelo World3D simples;
os esqueletos vêm do tópico informado e são atualizados sem recarregar o modelo.
Desmarcar **Cadeiras** oculta as 13 raízes `Chair_###` junto com todas as suas
peças; marcar novamente as restaura.

## Arquivos e referencial

O arquivo está em
[`is_viewer/web/static/models/labsea.glb`](../is_viewer/web/static/models/labsea.glb).
Foi copiado de `labsea-simulation/saida/labsea.glb` sem alterar os bytes.
SHA-256: `3424ba7fad0c261e64ceb3e51c5201ea63c5d84893cb5e67c67a09a142870e63`.
São 9.669.972 bytes, 3.917 malhas, cerca de 141.864 triângulos, 27 materiais e
uma textura PNG embutida. O GLB não inclui câmeras ópticas nem animações.

O exportador Blender usa Y para cima. A cena do viewer mantém os dados calibrados
em metros com **Z para cima** e gira somente o GLB em +90° ao redor de X:
`(x_glb, y_glb, z_glb) → (x, -z, y)`. Não há deslocamento nem normalização de
escala. O nó `CameraModel_001` do GLB, após essa rotação, coincide com a posição
da câmera 1 nos NPZ: aproximadamente `(2,737; 3,699; 2,868)` metros.

O navegador carrega Three.js 0.180.0, `GLTFLoader` e `OrbitControls` de arquivos
locais em `is_viewer/web/static/vendor/three/`. A licença MIT correspondente está
em [`LICENSE`](../is_viewer/web/static/vendor/three/LICENSE). O GLB é carregado
somente quando a visualização sintética é aberta. Os arquivos estão incluídos no
pacote Python e na imagem Docker produzida a partir desta branch.

O manifesto Kubernetes ainda aponta para `joabfsl/is-viewer:2.2.0`. Para usar
esta branch no cluster, publique uma imagem com outra tag e atualize o campo
`image` no manifesto da própria branch antes de aplicar o Deployment.

## Limites da integração

A cena permite comparar posição e direção das câmeras, mapa e keypoints com a
geometria sintética. As anotações e o vídeo real são fluxos independentes, sem
sincronização por timestamp. As poses de câmera vêm da calibração estática e não
acompanham PTZ. Os rótulos das câmeras não testam oclusão por paredes.

Os objetos móveis do GLB têm nomes e propriedades, mas não são associados
automaticamente aos IDs recebidos do broker. Essa associação exige uma regra de
rastreamento. A quantidade de malhas pode limitar o desempenho em GPUs fracas;
desligar as paredes reduz a obstrução visual, mas não combina as malhas.
