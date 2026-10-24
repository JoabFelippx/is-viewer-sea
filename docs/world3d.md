# World3D: tópicos, navegação, mapa e câmeras

Abra `/MeuServico.World3D` ou `/world3d/MeuServico.World3D`. Qualquer prefixo
terminado em `.World3D` abre o visualizador automaticamente. O campo no topo
permite trocar o tópico. Informe um nome concreto: o `*` da descrição representa
qualquer nome, não uma assinatura simultânea de todos os tópicos do broker.
As rotas antigas continuam funcionando, inclusive `/world3d/`, que preserva
`SkeletonDetector.3D.Annotations` como tópico padrão.

O conteúdo esperado continua sendo protobuf `ObjectAnnotations`, com objetos e
keypoints XYZ no referencial de calibração, em metros. Mudar o nome do tópico
não muda o schema. `/<topic>.World3D?raw=1` entrega os dados sem a página.

- Arrastar com botão esquerdo: girar ao redor do ponto de interesse.
- Arrastar com a roda/botão central pressionado: deslocar o ponto de vista.
- Girar a roda: aproximar/afastar.
- **Enquadrar**: ajustar a visão às câmeras e ao mapa visíveis.
- **Mapa + câmeras 6–8**: mostrar os quatro contornos do mapa e as câmeras extras.

As câmeras 1–4 aparecem por padrão. Os marcadores indicam posição e direção
óptica da calibração; não acompanham movimento PTZ em tempo real. As posições
são calculadas por `C = -Rᵀt`, aceitando os formatos `rt` 3×4 e 4×4 dos arquivos.
O mapa é desenhado no referencial original, sem deslocamento ou mudança de escala.

## Dados incluídos e atualização

`data/world3d/` guarda os NPZ originais das calibrações 1–4 e 6–8 e o mapa
`map_B3A1.npz`, com um inventário e hashes em seu README. O JSON registra os
mesmos hashes e acompanha o pacote/Docker. O servidor não precisa acessar
Downloads ou o projeto de simulação em tempo de execução.

Para atualizar os dados a partir dos originais:

```bash
uv pip install numpy
python scripts/import_world3d.py --trust-map-pickle
```

O mapa legado guarda listas de objetos pickle. Use a opção somente com o mapa
versionado em `data/world3d/map_B3A1.npz`. O servidor não recebe nem executa
pickle; o navegador recebe apenas JSON numérico. Após atualizar,
reconstrua a imagem Docker se aplicável e recarregue a página.

A integração do ambiente sintético ainda não foi implementada. Veja o
[inventário dos NPZ](../data/world3d/README.md) e [análise do GLB](labsea-glb.md).

## Página de calibração

Abra `/calib` para comparar as posições e direções de quatro câmeras no plano
XY. Selecione uma linha ou marcador para abrir `/calib/<id>`, com as matrizes
intrínsecas e extrínsecas, distorção da lente, ROI e hash do NPZ. O seletor
permite navegar pelas sete câmeras; **Incluir mapa e câmeras 6–8** enquadra o
entorno junto com o mapa.

`K` é a matriz intrínseca original; `nK` é a matriz usada com imagens sem
distorção. `rt` transforma do mundo para a câmera e `rt⁻¹` faz o caminho inverso.
O formato original de `rt` (4×4 nas câmeras 1–4; 3×4 nas câmeras 6–8) é
preservado. Tabela e detalhes mostram a posição no mundo e o eixo óptico frontal.

Na página `/camera/<id>`, **Sobrepor 3D** usa essas mesmas extrínsecas para
projetar os keypoints do tópico de anotações sobre a imagem. A opção **Sem
distorção** corrige o JPEG e troca a projeção de `K` para `nK`. Veja o
[guia de uso](uso.md#correção-da-lente-e-anotações-3d-na-imagem).
