# Usando as páginas e a API

Os exemplos usam `http://localhost:3000` e câmera `1`. Substitua os tópicos e IDs
pelos do seu ambiente.

## Câmera individual

Abra `http://localhost:3000/camera/1`. A página inicia o stream da câmera e consulta
`/api/cameras/1/capabilities`. O botão PTZ aparece quando a resposta informa
`state: available` e `ptz`. Para mover, a API também exige `ptz_step`.

As opções de passo e inversão de pan/tilt ficam salvas no `localStorage` do
navegador, separadamente por tópico. Uma falha nos controles não impede a
exibição das imagens.

Para usar apenas o vídeo, sem a interface:

```text
/stream/CameraGateway.1.Frame
/CameraGateway.1.Frame
/CameraGateway.1.Frame/Image
/Image/CameraGateway.1.Frame
```

`/1` não é um atalho de câmera. Use `/camera/1` para a página ou o tópico completo
para o stream.

## Correção da lente e anotações 3D na imagem

Em `/camera/1`, **Sem distorção** troca o MJPEG pelo stream corrigido com `K`,
`nK` e os coeficientes `dist` da calibração. **Imagem original** volta ao stream
sem correção. O resultado é recortado para o ROI armazenado no NPZ. Para obter
só o vídeo corrigido:

```text
/stream/CameraGateway.1.Frame?undistort=1
```

**Sobrepor 3D** projeta na imagem os mesmos keypoints e conexões usados pelo
World3D. O campo **Tópico 3D** começa em `SkeletonDetector.3D.Annotations` e
aceita outro tópico concreto de `ObjectAnnotations`, inclusive nomes terminados
em `.World3D`. Ao alternar a correção da lente, os pontos passam a usar a matriz
intrínseca correspondente, sem perder o fluxo de anotações. Na imagem corrigida,
as coordenadas projetadas são deslocadas pela origem do ROI para permanecerem
alinhadas com o recorte.

Os controles aparecem para as câmeras com calibração incluída (1–4 e 6–8).
As matrizes foram importadas dos NPZ em `data/world3d/calibrations/`; o servidor
lê o JSON numérico gerado por `scripts/import_world3d.py`. A projeção usa a pose
registrada na calibração e pode deixar de alinhar após movimentar o PTZ. Imagem
e anotações são streams independentes, sem sincronização por timestamp.

Os desenhos 3D são removidos após 3 segundos sem atualização da origem, mesmo
se a conexão HTTP continuar aberta. Se vários serviços publicam no mesmo tópico,
o viewer mantém o último conjunto de objetos de cada origem. Para distinguir
objetos com o mesmo ID e rótulo com certeza, cada publicador pode enviar um
identificador estável em `Message.metadata["source"]` (também são aceitos
`publisher`, `service`, `producer` e `is-source`). Os publicadores atuais não
enviam esse campo. Nesse caso, o viewer associa mensagens recentes pelo rótulo
e proximidade espacial dos pontos ou da caixa. Cada mensagem substitui o quadro
anterior da origem inferida, removendo imediatamente objetos que sumiram desse
quadro. IDs que mudam entre quadros não deixam pontos antigos desenhados. Para
objetos sem posição, o ID é usado como apoio. Observações sobrepostas de serviços
diferentes não podem ser atribuídas com segurança.
Mensagens 3D vazias sem origem identificada são ignoradas, e publicações idênticas
são reduzidas a uma por segundo nas visualizações. As posições novas continuam
passando imediatamente. Use `/ObjectAnnotations/<topic>` para inspecionar o fluxo
sem esse filtro.

## Sobreposição de anotações 2D

Em `/camera/1`, **Sobrepor 2D** lê por padrão
`SkeletonDetector.1.Detection`. O campo **Tópico 2D** aceita qualquer tópico
concreto que publique `ObjectAnnotations`; altere-o para o produtor da câmera.
O viewer desenha `keypoints[].position` e o polígono `region.vertices`, incluindo
bounding boxes de dois cantos ou quatro vértices. O `label` aparece junto ao objeto.

Por padrão, as coordenadas são pixels na resolução indicada em
`ObjectAnnotations.resolution`. Se o produtor usa valores entre 0 e 1, selecione
**0–1**. Quando `resolution` não está presente, usa-se a resolução da calibração
(1280 × 720 para as câmeras 6–8). A opção **Sem distorção** transforma também os
pontos e os vértices para a imagem corrigida e recortada. Os desenhos expiram
após 3 segundos sem publicação. A sobreposição 2D pode ser usada junto com a 3D.
Ela também funciona em câmeras sem calibração cadastrada, sobre a imagem original.
Cada mensagem 2D substitui o desenho anterior; quadros antigos não se acumulam.

Para abrir a página já com um tópico 2D selecionado, use
`/camera/1?annotations2d=Meu.Topico`. A saída numérica para outros clientes está
em `/projection2d/1/Meu.Topico`; adicione `?coordinates=normalized` quando
necessário.

## Configurar frequência e cor

Os parâmetros são aplicados quando se abre o stream de um tópico CameraGateway:

```text
/stream/CameraGateway.1.Frame?fps=10&color=gray
```

`fps` é convertido em número e `color` é procurado no enum `ColorSpaces`, sem
diferenciar maiúsculas de minúsculas. Exemplos: `gray` e `rgb`. A alteração é
enviada para a câmera compartilhada; pode afetar outros consumidores desse
produtor. A publicação não espera confirmação de aplicação da configuração.

Os parâmetros da página `/camera/1` não são repassados ao `<img>`; para configurar
via query string, use a URL de stream acima.

Para gravar um stream JPEG com FFmpeg instalado:

```bash
ffmpeg -use_wallclock_as_timestamps 1 -f mjpeg \
  -i 'http://localhost:3000/stream/CameraGateway.1.Frame' \
  -c copy output.mkv
```

## Mosaico

1. Abra `/mosaic/2x2`, `/mosaic/2x3` ou outro layout de até 36 células.
2. Digite o tópico completo em cada célula, como `CameraGateway.1.Frame`.
3. Clique em **Abrir**.
4. Passe o mouse sobre a imagem para mostrar o campo novamente e trocar o tópico.

As células aceitam imagens de outros produtores, como `SkeletonDetector.2.Frame`.
A escolha dos tópicos não é persistida ao recarregar a página.

O mosaico recebe um único MJPEG composto no servidor, usando o quadro mais
recente de cada tópico. A saída acompanha a proporção da janela, até 1600 × 900,
com JPEG de qualidade 75 e até 5 quadros/s. Acima de quatro tópicos, a frequência
é limitada também pelo orçamento de 24 decodificações por segundo. Isso reduz
o volume transferido e evita que cada célula acumule um atraso diferente no
navegador. A frequência de publicação das câmeras não é alterada.

As células aparecem no mesmo quadro de saída, mas a captura das câmeras continua
independente: não há alinhamento por timestamp. Uma câmera sem novos quadros por
um segundo fica preta. Para remover uma câmera, limpe seu campo e clique em
**Abrir**. A rota `/stream/<topic>` continua oferecendo a imagem individual na
resolução e frequência originais.

## Mensagens protobuf e JSON

Prefira informar o schema explicitamente:

```text
/Struct/Some.Struct.Topic
/topic/Struct/Some.Struct.Topic
/ObjectAnnotations/SkeletonDetector.2.Detection
```

Também são aceitos nomes completos, como `google.protobuf.Struct`. O registro
inclui os tipos dos módulos `camera_pb2`, `common_pb2`, `image_pb2`, `power_pb2`,
`robot_pb2`, `ros_pb2` e `google.protobuf.Struct`.

Para a página JSON, `history` controla quantas mensagens recentes ficam visíveis:

```text
/Struct/Some.Struct.Topic?history=10
```

O padrão é `1`; o intervalo aceito é de `1` a `100`. Para consumir JSON por linha:

```bash
curl -N 'http://localhost:3000/Struct/Some.Struct.Topic?raw=1'
```

Cada linha normalmente tem esta estrutura:

```json
{"topic":"Some.Struct.Topic","schema":"google.protobuf.Struct","message":{"ok":true}}
```

`/Json/Meu.Topico` encaminha o corpo original, que deve conter JSON válido para
ser interpretado como JSON pelo cliente. Por compatibilidade, o schema curto
`ObjectAnnotations` também retorna dados diretamente sem exigir `raw=1`.
O schema completo desse protobuf pode ser usado para obter a página de inspeção.

O endereço `/<topic>` sem schema depende da metadata `is-schema` ou da tentativa
de decodificação como imagem. Um schema explícito evita essa ambiguidade.

## HOME e posição PTZ

Em `/camera/5`, abra o painel **PTZ**. **HOME** solicita a posição absoluta
`(0, 0, 0)` usando `CameraConfig.ptzcontrol.absolute`, desde que a câmera anuncie
`ptz_absolute`. Não é o preset HOME configurável do fabricante. O firmware pode
limitar valores, especialmente o zoom: o indicador mostra a posição reportada,
sem assumir que o comando terminou ou que todos os eixos chegaram a zero.

O painel consulta a posição a cada 1,5 segundo enquanto estiver aberto e a aba
estiver visível. Pan, tilt e zoom estão em **unidades nativas do gateway**, sem
conversão presumida para graus. Em falhas de leitura, os valores são substituídos
por `—`. A API usa `GetConfig` e exige o campo `ptzcontrol.absolute` presente.

```text
GET  /api/cameras/5/ptz       → posição atual
POST /api/cameras/5/ptz/home  → solicitar (0, 0, 0)
```

## Esqueletos 3D

Abra `/world3d/` para consumir `SkeletonDetector.3D.Annotations`, ou
`/world3d/Meu.Topico` para outro tópico. O produtor deve enviar `ObjectAnnotations`
com `objects`, `keypoints` e posições tridimensionais.

- Arraste com o botão esquerdo para girar a visão.
- Arraste com o botão central pressionado para deslocar a visão.
- Use a roda do mouse para aproximar ou afastar.
- Marque ou desmarque X, Y e Z para controlar os eixos visíveis.

Tópicos terminados em `.World3D` também abrem diretamente em `/<topic>`.
A opção **Mapa + câmeras 6–8** adiciona o mapa ao cenário; as câmeras 1–4
já aparecem por padrão. Veja o [guia World3D](world3d.md).

A grade representa intervalos de 1 metro. A visualização pressupõe coordenadas
em metros. `/skeleton3d/<topic>` continua redirecionando para `/world3d/<topic>`.
`/skeleton3d-data/<topic>` entrega os dados que alimentam a página.

## API de câmera

Consulta de capacidades:

```bash
curl 'http://localhost:3000/api/cameras/1/capabilities'
```

Movimento relativo:

```bash
curl -X POST 'http://localhost:3000/api/cameras/1/ptz' \
  -H 'Content-Type: application/json' \
  -d '{"pan":1,"tilt":0,"zoom":0,"step_degrees":5}'
```

`pan`, `tilt` e `zoom` aceitam `-1`, `0` ou `1`, e pelo menos um precisa ser
diferente de zero. `step_degrees` aceita de `0.5` a `45`. O valor `5` corresponde
a um passo padrão do contrato legado. A resposta de sucesso é `{"ok":true}`.

| Status | Significado |
| --- | --- |
| `400` | Parâmetro, layout, tópico de câmera ou passo inválido |
| `409` | Câmera não oferece movimento PTZ por passo |
| `422` | Corpo ou parâmetro incompatível com o tipo esperado pelo FastAPI |
| `502` | Resposta RPC com erro ou correlação inesperada |
| `503` | Erro de conexão AMQP durante a operação |
| `504` | Timeout ao aguardar resposta RPC |
