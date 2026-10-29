# IS Viewer

Serviço Python que recebe imagens e mensagens do ecossistema IS pelo RabbitMQ e
as disponibiliza no navegador. Inclui streams MJPEG, mosaico de câmeras,
inspeção de protobufs em JSON, visualização de esqueletos 3D e comandos PTZ.

## Rodar localmente

Você precisa de:

- Python 3.10 ou superior e `pip`;
- um RabbitMQ acessível, com o exchange `is` e a infraestrutura de streams
  usada pelo `is-wire-sea`;
- um produtor publicando no tópico que deseja visualizar, como o CameraGateway.

O viewer não captura imagens diretamente da câmera e não inicia o broker ou os
produtores. As conexões com o RabbitMQ são abertas ao iniciar a aplicação.

Na pasta deste projeto:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .

# Substitua pelo endereço, usuário, senha e vhost do seu ambiente.
export IS_URI='amqp://usuario:senha@rabbitmq:5672/vhost'
python server.py
```

Abra **http://localhost:3000/**. Para ver a câmera 1 com os controles disponíveis,
abra **http://localhost:3000/camera/1**.

O comando anterior continua equivalente a:

```bash
python -m uvicorn server:app --host 0.0.0.0 --port 3000
```

Durante o desenvolvimento, acrescente `--reload` ao comando do Uvicorn. Os
mesmos arquivos também podem ser instalados com `python -m pip install .`, sem
modo editável. Não é necessário Node.js nem uma etapa de build da interface.

Se usa `uv`, há um lockfile no repositório:

```bash
uv sync --locked
IS_URI='amqp://usuario:senha@rabbitmq:5672/vhost' uv run server.py
```

## O que abrir no navegador

| URL | Resultado |
| --- | --- |
| `/` | Página inicial com exemplos |
| `/camera/1` | Câmera individual, correção da lente, projeção 3D e PTZ quando disponível |
| `/camera/CameraGateway.1.Frame` | A mesma página usando o tópico completo |
| `/calib` | Visão geral das posições e direções; selecione uma câmera para abrir os parâmetros |
| `/calib/1` | Parâmetros da câmera 1; os IDs 1–4 e 6–8 estão disponíveis |
| `/stream/CameraGateway.1.Frame` | Stream MJPEG direto |
| `/stream/CameraGateway.1.Frame?undistort=1` | MJPEG corrigido pela calibração da câmera 1 |
| `/projection2d/1/SkeletonDetector.1.Detection` | Anotações 2D em pixels originais e corrigidos, em JSON por linha |
| `/CameraGateway.1.Frame` | Atalho para o stream direto, sem painel PTZ |
| `/mosaic/2x3` | Mosaico de 2 linhas e 3 colunas; informe um tópico por célula |
| `/Struct/Some.Struct.Topic` | Página com mensagens protobuf convertidas em JSON |
| `/Struct/Some.Struct.Topic?raw=1` | JSON por linha, sem interface |
| `/world3d/` | Esqueletos do tópico `SkeletonDetector.3D.Annotations` |
| `/world3d/Meu.Topico` | Esqueletos 3D de outro tópico de `ObjectAnnotations` |
| `/world3d-sintetico/` | Laboratório GLB com mapa, câmeras e esqueletos do tópico padrão |
| `/world3d-sintetico/Meu.Topico` | Laboratório GLB com outro tópico de `ObjectAnnotations` |

Os tópicos são exemplos: precisam existir no seu ambiente. O mosaico aceita até
36 células. Streams de outros serviços, como `SkeletonDetector.2.Frame`, também
podem ser abertos em `/stream/<topic>`.

O mosaico entrega a grade inteira em um único MJPEG, até 1600 × 900 e 5 quadros/s,
para reduzir tráfego e diferenças de atraso entre células. Grades maiores usam
uma frequência menor. A captura das câmeras permanece independente; veja os
[limites e controles do mosaico](docs/uso.md#mosaico).

## Capturas das páginas

As capturas foram feitas localmente. As páginas de câmera, mosaico, mensagens,
World3D e LabSEA sintético exibem feeds ou anotações simulados, identificados
na própria imagem.
As telas de calibração usam os NPZ versionados neste projeto.

<table>
  <tr>
    <td align="center"><a href="docs/images/pagina-inicial.png"><strong>Página inicial</strong><br><img src="docs/images/pagina-inicial.png" width="480" alt="Página inicial do IS Viewer"></a></td>
    <td align="center"><a href="docs/images/camera-ptz.png"><strong>Câmera e PTZ</strong><br><img src="docs/images/camera-ptz.png" width="480" alt="Câmera simulada e painel PTZ"></a></td>
  </tr>
  <tr>
    <td align="center"><a href="docs/images/mosaico.png"><strong>Mosaico</strong><br><img src="docs/images/mosaico.png" width="480" alt="Mosaico de quatro feeds simulados"></a></td>
    <td align="center"><a href="docs/images/mensagens-json.png"><strong>Mensagens protobuf em JSON</strong><br><img src="docs/images/mensagens-json.png" width="480" alt="Mensagens simuladas formatadas como JSON"></a></td>
  </tr>
  <tr>
    <td align="center"><a href="docs/images/world3d.png"><strong>World3D</strong><br><img src="docs/images/world3d.png" width="480" alt="World3D com anotações simuladas e câmeras"></a></td>
    <td align="center"><a href="docs/images/calibracoes.png"><strong>Mapa e calibrações</strong><br><img src="docs/images/calibracoes.png" width="480" alt="Visão geral das câmeras e do mapa calibrado"></a></td>
  </tr>
  <tr>
    <td align="center"><a href="docs/images/calibracao-camera-7.png"><strong>Parâmetros da câmera 7</strong><br><img src="docs/images/calibracao-camera-7.png" width="480" alt="Matrizes intrínsecas e extrínsecas da câmera 7"></a></td>
    <td align="center"><a href="docs/images/labsea-sintetico.png"><strong>LabSEA sintético</strong><br><img src="docs/images/labsea-sintetico.png" width="480" alt="Modelo GLB do laboratório com uma anotação simulada"></a></td>
  </tr>
</table>

O [guia World3D](docs/world3d.md) explica o referencial e as matrizes.

Para todos os parâmetros, aliases e exemplos de PTZ, veja o [guia de uso](docs/uso.md).

## Configuração

| Variável | Padrão | Uso |
| --- | --- | --- |
| `IS_URI` | `amqp://localhost` | Conexão com RabbitMQ |
| `IS_PORT` | `3000` | Porta ao executar `python server.py` |
| `CAMERA_TOPICS` | Não definida | Lista separada por vírgulas para o renderizador `dashboard_html()` sem argumentos |
| `CAMERA_IDS` | `1,2,3,4` | Alternativa a `CAMERA_TOPICS` para esse renderizador |

Ao executar Uvicorn diretamente, use `--port`: ele não consulta `IS_PORT`.
As rotas atuais de câmera informam explicitamente o tópico ao renderizador; as
variáveis `CAMERA_TOPICS` e `CAMERA_IDS` não preenchem o mosaico nem alteram a
página inicial. Elas foram mantidas para compatibilidade do renderizador.

O serviço lê o ambiente do processo; não carrega um arquivo `.env` automaticamente.

## Como o código está organizado

```text
server.py                 Entrada curta, compatível com os comandos existentes
is_viewer/
  app.py                  Criação do FastAPI e abertura/fechamento das conexões
  config.py               Variáveis de ambiente e validação de tópicos
  cameras.py              Configuração de câmera, capacidades e movimento PTZ
  messaging/
    hub.py                Clientes HTTP, assinaturas e filas limitadas
    image_stream.py       Consumidor de um tópico de imagem
    rpc.py                Envio de comandos e espera de respostas
    codec.py              Protobuf → imagem ou JSON
  web/
    routes.py             URLs, validação e respostas de erro
    streaming.py          Respostas contínuas MJPEG e JSON por linha
    pages.py              Preenchimento dos templates HTML
    templates/            Estrutura das páginas
    static/               CSS e JavaScript de cada página
tests/                   Testes sem broker ou câmeras reais
docs/                    Guias de arquitetura, uso e implantação
k8s/is-viewer.yaml        Exemplo de implantação no Kubernetes
```

Comece por `server.py`, siga para `is_viewer/app.py` e depois para
`is_viewer/web/routes.py`. O [guia de arquitetura](docs/arquitetura.md) acompanha
uma requisição desde o navegador até o broker e de volta.

## Docker e Kubernetes

```bash
docker build -t is-viewer:local .
docker run --rm -p 3000:3000 \
  -e IS_URI='amqp://usuario:senha@rabbitmq:5672/vhost' \
  is-viewer:local
```

O endereço do broker precisa ser acessível **de dentro do contêiner**.
`localhost` dentro dele aponta para o próprio contêiner.

O [guia de implantação](docs/implantacao.md) explica o Secret, a imagem e as
portas do manifesto Kubernetes, além de como verificar problemas de conexão.

## Testes e manutenção

Depois de instalar o projeto:

```bash
python -m pip install httpx httpx2 numpy
python -m unittest discover -s tests -v
```

Os testes substituem as conexões AMQP por objetos simulados. Cobrem conversão
protobuf, filas de clientes lentos, assinaturas compartilhadas, RPC, templates,
rotas, PTZ, ciclo de vida e enquadramento MJPEG/JSON.

Para executar somente os testes do núcleo, sem FastAPI/httpx:

```bash
python -m unittest discover -s tests -p test_core.py -v
```

Essa seleção ainda precisa de `is-wire-sea` e `is-msgs-sea`. Consulte
[como alterar e validar cada parte](docs/arquitetura.md#onde-alterar-cada-coisa).

## Novidades: PTZ e World3D

O painel PTZ tem **HOME (0, 0, 0)** e leitura da posição atual. O World3D aceita
URLs como `/MeuServico.World3D`, navegação pelo botão central, marcadores das
câmeras 1–4 e a opção de mapa com câmeras 6–8.

As páginas World3D reúnem objetos publicados por vários serviços no mesmo tópico.
Cada mensagem substitui o quadro anterior da origem associada, para que mudanças
de ID ou objetos ausentes não deixem rastros.
Para evitar oscilações e lentidão em fluxos intensos, suas visualizações ignoram
mensagens vazias sem origem identificada e repetições idênticas. A rota genérica
`/ObjectAnnotations/<topic>` não aplica esse filtro. Veja o
[comportamento de múltiplos publicadores](docs/world3d.md#múltiplos-publicadores-no-mesmo-tópico).

- [Uso de HOME e posição PTZ](docs/uso.md#home-e-posição-ptz)
- [Correção da lente e anotações 3D na imagem](docs/uso.md#correção-da-lente-e-anotações-3d-na-imagem)
- [Sobreposição de pontos e bounding boxes 2D](docs/uso.md#sobreposição-de-anotações-2d)
- [World3D e atualização do mapa/calibrações](docs/world3d.md)
- [LabSEA sintético: uso, arquivos e referencial](docs/labsea-glb.md)

`httpx`/`httpx2` atendem às versões do cliente de testes Starlette. NumPy e
OpenCV também são instalados com o projeto para corrigir o MJPEG e projetar as
anotações na imagem. O JSON gerado a partir dos NPZ continua incluído no pacote.
