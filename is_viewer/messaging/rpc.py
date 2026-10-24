"""Chamadas RPC serializadas em uma conexão AMQP dedicada."""

import logging
import threading

from is_wire.core import Channel, Message, StatusCode, Subscription

LOG = logging.getLogger(__name__)


class RpcClient:
    """Evita chamadas concorrentes no canal de comandos da câmera."""

    def __init__(self, uri):
        self.uri = uri
        self.lock = threading.Lock()
        self._connect()

    def _connect(self):
        self.channel = Channel(self.uri, exchange="is")
        self.replies = Subscription(self.channel)

    def _reconnect(self):
        try:
            self.channel.close()
        except (ConnectionError, OSError):
            pass
        self._connect()

    def close(self):
        self.channel.close()

    def publish(self, message: Message, topic: str) -> None:
        """Publica uma configuração sem esperar resposta, no mesmo lock do RPC."""
        with self.lock:
            self.channel.publish(message, topic=topic)

    def call(self, topic, request, reply_type, timeout=3.0):
        with self.lock:
            for attempt in range(2):
                try:
                    message = Message(content=request, reply_to=self.replies)
                    message.timeout = timeout
                    self.channel.publish(message, topic=topic)
                    reply = self.channel.consume(timeout=timeout)
                    if reply.correlation_id != message.correlation_id:
                        raise RuntimeError("RPC response correlation mismatch")
                    if reply.has_status() and reply.status.code is not StatusCode.OK:
                        raise RuntimeError(reply.status.why or reply.status.code.name)
                    return reply.unpack(reply_type)
                except TimeoutError as error:
                    raise TimeoutError(f"RPC timeout on {topic}") from error
                except (ConnectionError, OSError):
                    if attempt:
                        raise
                    LOG.warning("event=rpc_reconnecting topic=%s", topic)
                    self._reconnect()
            raise RuntimeError("unreachable RPC retry state")
