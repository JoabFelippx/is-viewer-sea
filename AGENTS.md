# Orientações para agentes neste repositório

Este arquivo se aplica ao repositório inteiro. Escreva código e documentação em
português claro quando estiver explicando o comportamento da aplicação. Prefira
funções pequenas, nomes descritivos e comentários que expliquem decisões ou
limites reais. Preserve a legibilidade para quem dará manutenção depois.

## O que é esta aplicação

O IS Viewer é um serviço FastAPI que recebe imagens e mensagens do ecossistema
IS pelo RabbitMQ e as apresenta no navegador. Ele oferece MJPEG, mosaico de
câmeras, visualização de mensagens protobuf, projeções 2D e 3D, World3D e PTZ.
O viewer não captura imagens diretamente nem inicia o broker ou os produtores.

Leia primeiro o [README.md](README.md). Para detalhes de funcionamento, consulte
[docs/arquitetura.md](docs/arquitetura.md); para a interface e os tópicos,
[docs/uso.md](docs/uso.md); para publicação,
[docs/implantacao.md](docs/implantacao.md). Os guias
[docs/world3d.md](docs/world3d.md) e [docs/labsea-glb.md](docs/labsea-glb.md)
descrevem os dois mundos 3D.

## Mapa do código

- `server.py` é a entrada; `is_viewer/app.py` cria o FastAPI e gerencia o ciclo de
  vida das conexões. Importar módulos não deve abrir conexões com o broker.
- `is_viewer/config.py` lê configurações e valida tópicos.
- `is_viewer/messaging/` contém o hub de assinaturas, consumidores de imagens,
  decodificação protobuf e RPC. `FrameHub` compartilha consumidores por tópico e
  entrega mensagens a filas limitadas de cada cliente HTTP.
- `is_viewer/cameras.py` e `is_viewer/web/camera_api.py` implementam o contrato
  PTZ e as rotas de câmera.
- `is_viewer/web/routes.py` define páginas e streams; `streaming.py` gera MJPEG e
  JSON por linha; `mosaic.py` compõe a grade de câmeras; `vision.py` trata
  calibração, correção de lente e projeção.
- `is_viewer/web/pages.py` preenche os arquivos em `templates/`. A interação e o
  desenho no navegador ficam em `static/`. `annotation-state.js` mantém o estado
  visual das anotações. O diretório `static/vendor/` contém código de terceiros.
- `tests/` contém testes com broker simulado; `k8s/` contém os manifestos.

## Cuidados ao alterar o comportamento

- Registre rotas específicas antes das rotas genéricas `/{schema}/{topic:path}`
  e `/{topic:path}` em `routes.py`.
- Preserve o compartilhamento de consumidores por tópico e o limite das filas.
  Clientes lentos não devem bloquear outros clientes. Uma resposta de streaming
  precisa liberar suas assinaturas quando a conexão termina ou é cancelada.
- O consumidor AMQP roda em threads e as filas HTTP pertencem ao event loop.
  Entregue dados a `asyncio.Queue` pelo loop do cliente, como faz `FrameHub`.
- `ObjectAnnotations` pode receber mensagens de vários serviços no mesmo tópico.
  Não presuma que `id`, `label` ou `frame_id` identifiquem o publicador. Consulte
  `docs/world3d.md` antes de alterar a associação e a expiração dos objetos.
  Um lote novo substitui o anterior de sua origem para não deixar rastros.
- As coordenadas 2D usuais são pixels da imagem original. Se alterar correção de
  lente ou sobreposição, valide a transformação para o tamanho efetivo exibido.
- O mosaico usa um único MJPEG composto, com quadros recentes de cada câmera.
  Ele limita a saída a 1600 × 900 e até 5 quadros/s; não sincroniza capturas por
  timestamp. Câmera sem quadro recente deve deixar de mostrar a imagem antiga.
- Arquivos HTML são carregados em cache por processo. Reinicie o servidor ao
  verificar alterações de template. O projeto não requer build de frontend.
- Mantenha os arquivos de `static/vendor/` e o modelo GLB fora de refatorações
  gerais, salvo quando a tarefa envolver esses recursos.

## Desenvolvimento e verificação

Requer Python 3.10 ou superior. Com as dependências instaladas, os comandos
usuais são:

```bash
python3 -m unittest discover -s tests -v
ruff check is_viewer tests
git diff --check
```

Os testes de unidade não precisam de RabbitMQ real. Para executar a aplicação,
configure `IS_URI` e use `python3 server.py`; veja o README para instalação e
exemplos. Adicione testes que verifiquem o comportamento alterado, especialmente
liberação de assinaturas, múltiplos publicadores, streams e transformações de
imagem. Evite testes que apenas repitam a implementação.

Ao mudar uma funcionalidade visível, atualize o README e os guias afetados no
mesmo trabalho. Documente limites observados e comandos que ainda funcionem.

## Docker e Kubernetes

O `Dockerfile` instala o pacote Python e serve a aplicação na porta 3000. O
manifesto `k8s/is-viewer-sintetico.yaml` corresponde ao serviço da porta 30300;
`k8s/is-viewer.yaml` é outro exemplo de implantação. Não confunda os dois ao
alterar a imagem.

A instalação ativa usa a tag `joabfsl/is-viewer:world-multi-2d` fixada por digest.
Publicar novamente a mesma tag não atualiza o pod por si só: obtenha o digest
novo, atualize o manifesto correto, confira `kubectl diff`, aplique e acompanhe
o rollout. Verifique a imagem efetiva do pod e a rota alterada. O Deployment
ativo está marcado como gerenciado por Helm; uma atualização por Helm pode
substituir uma imagem aplicada diretamente com `kubectl` se os valores do release
divergirem. Consulte `docs/implantacao.md` antes de implantar.

Não registre URI, usuário, senha ou conteúdo de Secrets em código, testes,
documentação ou saídas compartilhadas.
