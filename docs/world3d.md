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

`is_viewer/web/static/world3d-scene.json` inclui as calibrações 1–4 e 6–8 e o
mapa `map_B3A1.npz` fornecido. O JSON registra nomes e hashes dos arquivos de
origem e acompanha o pacote/Docker. O servidor não precisa acessar Downloads
ou o projeto de simulação em tempo de execução.

Para atualizar os dados a partir dos originais:

```bash
uv pip install numpy
export CALIBRATIONS=/caminho/para/labsea-simulation/dados/calibracao
export MAP_FILE=/caminho/para/map_B3A1.npz
python scripts/import_world3d.py \
  --calibrations "$CALIBRATIONS" \
  --map "$MAP_FILE" \
  --trust-map-pickle
```

O mapa legado guarda listas de objetos pickle. A opção acima deve ser usada
somente para um arquivo local conhecido. Não há upload ou execução de pickle
pelo servidor; o navegador recebe apenas JSON numérico. Após atualizar,
reconstrua a imagem Docker se aplicável e recarregue a página.

A integração do ambiente sintético ainda não foi implementada. Veja a
[análise do GLB](labsea-glb.md).
