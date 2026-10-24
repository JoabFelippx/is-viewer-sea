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
