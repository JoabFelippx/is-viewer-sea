"""Um consumidor de stream por tópico de imagem ativo."""

import logging
import threading

from amqp.exceptions import ConnectionError as AMQPConnectionError
from is_wire.core import Channel, StreamSubscription

LOG = logging.getLogger(__name__)


class ImageStreamWorker:
    """Consome um tópico de imagem e confirma cada entrega após o despacho."""

    def __init__(self, hub, topic):
        self.hub = hub
        self.topic = topic
        self._connect()
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, name=f"stream-{topic}")

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self._close_channel()
        if self.thread.ident is not None:
            self.thread.join(timeout=5)

    def _connect(self):
        self.channel = Channel(self.hub.uri, exchange="is")
        parts = self.topic.split(".")
        camera_id = parts[1] if len(parts) > 1 else self.topic
        self.subscription = StreamSubscription(
            self.channel, group=f"cameras-visualizer.camera-{camera_id}"
        )
        self.subscription.subscribe(self.topic)

    def _close_channel(self):
        try:
            self.channel.close()
        except (AMQPConnectionError, ConnectionError, OSError):
            # Uma conexão que perdeu o alinhamento dos frames pode falhar
            # também durante close. Isso não deve encerrar a thread do worker.
            LOG.debug("event=stream_close_failed topic=%s", self.topic, exc_info=True)

    def _reconnect(self, error):
        LOG.warning(
            "event=stream_reconnecting topic=%s error=%s",
            self.topic,
            error,
        )
        self._close_channel()
        if self.stop_event.wait(0.5):
            return False
        try:
            self._connect()
        except (AMQPConnectionError, ConnectionError, OSError):
            LOG.exception("event=stream_reconnect_failed topic=%s", self.topic)
        return True

    def _run(self):
        while not self.stop_event.is_set():
            try:
                message = self.subscription.consume(timeout=0.5)
            except TimeoutError:
                continue
            except (AMQPConnectionError, ConnectionError, OSError) as error:
                if not self._reconnect(error):
                    return
                continue
            try:
                self.hub.dispatch(message)
                message.ack()
            except (AMQPConnectionError, ConnectionError, OSError) as error:
                # ack/reject também usam o socket AMQP. Uma falha aqui indica
                # que esta conexão não pode ser usada para outra entrega.
                if not self._reconnect(error):
                    return
            except Exception:
                try:
                    message.reject(requeue=False)
                except (AMQPConnectionError, ConnectionError, OSError) as error:
                    if not self._reconnect(error):
                        return
                LOG.exception("event=stream_dispatch_failed topic=%s", self.topic)
