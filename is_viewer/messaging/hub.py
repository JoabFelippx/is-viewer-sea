"""Liga os consumidores AMQP às filas limitadas dos clientes HTTP."""

import asyncio
import logging
import threading
import uuid
from dataclasses import dataclass

from amqp.exceptions import ConnectionError as AMQPConnectionError
from is_wire.core import Channel, Message, Subscription

from .codec import decode_message
from .image_stream import ImageStreamWorker

LOG = logging.getLogger(__name__)
Payload = tuple[str, bytes]


@dataclass(frozen=True)
class Client:
    """Uma assinatura HTTP e o event loop que pode escrever na sua fila."""

    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[Payload]
    topic: str
    schema_hint: str | None

    @property
    def wants_images(self) -> bool:
        return self.schema_hint in ("Image", "is.vision.Image") or (
            self.schema_hint is None and self.topic.endswith(".Frame")
        )


class FrameHub:
    """Compartilha consumidores por tópico e limita o histórico de cada cliente."""

    def __init__(self, uri: str):
        self.uri = uri
        self.channel = Channel(uri, exchange="is")
        self.subscription = Subscription(
            self.channel, name=f"is-viewer-{uuid.uuid4().hex}"
        )
        self.stop_event = threading.Event()
        self.active_topics: set[str] = set()
        self.stream_workers: dict[str, ImageStreamWorker] = {}
        self.thread = threading.Thread(target=self._consume, name="amqp-consumer")
        self.lock = threading.RLock()
        self.clients: dict[object, Client] = {}

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.channel.close()
        if self.thread.ident is not None:
            self.thread.join(timeout=5)
        for worker in tuple(self.stream_workers.values()):
            worker.stop()

    def _clients_snapshot(self) -> tuple[Client, ...]:
        with self.lock:
            return tuple(self.clients.values())

    def _consume(self) -> None:
        while not self.stop_event.is_set():
            try:
                self._sync_topics()
                message = self.channel.consume(timeout=0.2)
                latest = self._latest_messages(message)
            except TimeoutError:
                continue
            except (AMQPConnectionError, ConnectionError, OSError):
                if not self.stop_event.is_set():
                    LOG.exception("event=amqp_consumer_failed")
                return
            clients = self._clients_snapshot()
            for current in latest:
                self._dispatch(current, clients)

    def _latest_messages(self, first: Message) -> tuple[Message, ...]:
        """Descarta entregas antigas já pendentes, mantendo a última por tópico."""
        latest = {first.topic: first}
        while True:
            try:
                pending = self.channel.consume(timeout=0.0)
            except TimeoutError:
                return tuple(latest.values())
            latest[pending.topic] = pending

    def _sync_topics(self) -> None:
        """Abre assinaturas ao primeiro cliente e fecha ao sair o último."""
        clients = self._clients_snapshot()
        message_topics = {client.topic for client in clients if not client.wants_images}
        image_topics = {client.topic for client in clients if client.wants_images}

        for topic in message_topics - self.active_topics:
            self.subscription.subscribe(topic)
            self.active_topics.add(topic)
        for topic in self.active_topics - message_topics:
            self.subscription.unsubscribe(topic)
            self.active_topics.remove(topic)
        for topic in image_topics - self.stream_workers.keys():
            worker = ImageStreamWorker(self, topic)
            self.stream_workers[topic] = worker
            worker.start()
        for topic in self.stream_workers.keys() - image_topics:
            self.stream_workers.pop(topic).stop()

    def dispatch(self, message: Message) -> None:
        self._dispatch(message, self._clients_snapshot())

    def _dispatch(self, message: Message, clients: tuple[Client, ...]) -> None:
        for client in clients:
            if message.topic != client.topic:
                continue
            try:
                payload = decode_message(message, client.schema_hint)
                # asyncio.Queue não é thread-safe: a escrita ocorre no loop HTTP.
                client.loop.call_soon_threadsafe(self._offer, client.queue, payload)
            except Exception:
                LOG.exception("event=invalid_message topic=%r", message.topic)

    @staticmethod
    def _offer(queue: asyncio.Queue[Payload], payload: Payload) -> None:
        """Um navegador lento perde a mensagem mais antiga, sem bloquear os demais."""
        if queue.full():
            queue.get_nowait()
        queue.put_nowait(payload)

    def add_client(
        self,
        loop: asyncio.AbstractEventLoop,
        topic: str,
        schema_hint: str | None = None,
        history: int = 1,
    ) -> tuple[object, asyncio.Queue[Payload]]:
        queue: asyncio.Queue[Payload] = asyncio.Queue(maxsize=history)
        token = object()
        with self.lock:
            self.clients[token] = Client(loop, queue, topic, schema_hint)
        return token, queue

    def remove_client(self, token: object) -> None:
        with self.lock:
            self.clients.pop(token, None)
