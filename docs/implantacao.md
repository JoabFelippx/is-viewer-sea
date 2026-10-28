# Implantação e diagnóstico

## Docker

Na raiz do projeto:

```bash
docker build -t is-viewer:local .
docker run --rm --name is-viewer -p 3000:3000 \
  -e IS_URI='amqp://usuario:senha@rabbitmq:5672/vhost' \
  is-viewer:local
```

O Dockerfile instala o pacote com os templates e arquivos estáticos e executa
Uvicorn com usuário sem privilégios. O comando padrão usa a porta interna 3000.
Para acessar por outra porta no host, use, por exemplo, `-p 8080:3000`.

O nome `rabbitmq` é um exemplo. Use um hostname/IP alcançável pelo contêiner, ou
coloque viewer e broker na mesma rede Docker e use o nome do serviço do broker.
O projeto não provisiona o RabbitMQ nem os produtores.

## Kubernetes, passo a passo

O exemplo está em [`../k8s/is-viewer.yaml`](../k8s/is-viewer.yaml).

1. Construa uma imagem com este código e publique no registry do seu ambiente:

   ```bash
   docker build -t joabfsl/is-viewer:labsea-sintetico .
   docker login -u joabfsl
   docker push joabfsl/is-viewer:labsea-sintetico
   ```

2. O manifesto desta branch aponta para a imagem sintética publicada, fixada
   pelo digest. Se reconstruir e publicar outra imagem, atualize o digest no
   campo `image` antes de aplicar o YAML.

3. Crie o Secret esperado pelo Deployment, no mesmo namespace:

   ```bash
   kubectl create secret generic rabbitmq-new-uri \
     --from-literal=uri='amqp://usuario:senha@rabbitmq:5672/vhost'
   ```

   Se esse Secret já existe e aponta para o broker correto, use-o. O manifesto
   lê a chave `uri` de `rabbitmq-new-uri`.

4. Aplique e acompanhe a inicialização:

   ```bash
   kubectl apply -f k8s/is-viewer.yaml
   kubectl rollout status deployment/is-viewer
   kubectl logs deployment/is-viewer
   ```

5. Para acessar localmente:

   ```bash
   kubectl port-forward service/is-viewer 3000:3000
   ```

   Abra `http://localhost:3000/`. O Service desse manifesto define **NodePort 30400**:
   quando a rede permite, use `http://IP_DO_NODE:30400/`.

### Instalação ativa na porta 30300

O arquivo `k8s/is-viewer-sintetico.yaml` corresponde ao Deployment atualmente
usado na porta 30300. Ele usa o Secret `rabbitmq-uri` e a tag
`joabfsl/is-viewer:world-multi-2d`, fixada por digest. Para publicar alterações
feitas neste repositório mantendo a tag:

```bash
docker build -t joabfsl/is-viewer:world-multi-2d .
docker push joabfsl/is-viewer:world-multi-2d
```

Depois do push, obtenha o novo digest no registry, atualize o campo `image` em
`k8s/is-viewer-sintetico.yaml` e aplique esse arquivo:

```bash
kubectl diff -f k8s/is-viewer-sintetico.yaml
kubectl apply -f k8s/is-viewer-sintetico.yaml
kubectl rollout status deployment/is-viewer
```

Uma nova publicação com a mesma tag não altera o pod enquanto o Deployment
continuar apontando para o digest anterior.

Use `-n SEU_NAMESPACE` nos comandos se estiver fora do namespace padrão. O
manifesto usa uma réplica e probes TCP. Elas verificam a porta HTTP, sem garantir
que o broker ou uma câmera estejam entregando dados.

A variável `CAMERA_TOPICS` presente no manifesto é compatibilidade do renderizador;
não preenche as células do mosaico. O comando do Deployment fixa `--port 3000`.

## Problemas comuns

| Sintoma | O que conferir |
| --- | --- |
| `No module named fastapi` ou `uvicorn` | Ative o ambiente virtual e execute `python -m pip install -e .` |
| Aplicação falha durante o startup | URI, DNS, porta, credenciais, vhost e acesso ao RabbitMQ |
| Página abre, mas imagem não aparece | Produtor ativo, tópico correto, infraestrutura de stream e JPEG no campo `Image.data` |
| Tópico abre como dados inesperados | Informe o schema explicitamente em `/<schema>/<topic>` |
| JSON funciona, mas PTZ retorna `504` | CameraGateway precisa implementar e responder aos tópicos RPC |
| PTZ retorna `409` | Verifique `state` e `ptz_step` em `/api/cameras/<id>/capabilities` |
| Erro em `/camera/Meu.Topico` | Essa rota só aceita ID ou `CameraGateway.<id>.Frame`; use `/stream/Meu.Topico` para outras imagens |
| Alterações no Kubernetes não aparecem | Publique a nova imagem e atualize a referência completa no Deployment |
| CSS/JS retorna `404` | Reinstale/reconstrua o pacote com `is_viewer/web/static` incluído |
| HTML editado não mudou | Reinicie o processo; os templates são guardados em cache |
| Stream de imagem parou após `UnexpectedFrame` ou queda do broker | O consumidor de imagem fecha a conexão corrompida, espera meio segundo e tenta reconectar. Confira os logs `stream_reconnecting` e `stream_reconnect_failed` e verifique se `IS_URI` aponta para o listener AMQP (geralmente porta 5672 ou NodePort configurado), não para uma porta HTTP. |
| Mensagens comuns pararam após erro AMQP | Confira `amqp_consumer_failed`; a assinatura comum encerra a thread e pode exigir reiniciar o viewer. |

O consumo de streams registra eventos como `stream_reconnecting` e
`stream_reconnect_failed`. O consumidor comum registra `amqp_consumer_failed`.
O RPC registra `rpc_reconnecting`. Esses eventos indicam qual parte da
comunicação precisa ser investigada.
