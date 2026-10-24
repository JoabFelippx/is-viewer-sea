"""Regressões do transporte, dos schemas e das páginas, sem broker real."""

import asyncio
import json
import unittest
from html.parser import HTMLParser
from unittest.mock import Mock, patch

from google.protobuf.struct_pb2 import Struct
from is_msgs.image_pb2 import Image
from is_wire.core import Message

from is_viewer.config import Settings, camera_topics, normalize_camera_topic
from is_viewer.messaging.codec import decode_message
from is_viewer.messaging.hub import FrameHub
from is_viewer.messaging.image_stream import ImageStreamWorker
from is_viewer.messaging.rpc import RpcClient
from is_viewer.web.pages import (
    WEB_DIRECTORY,
    dashboard_html,
    home_html,
    messages_html,
    mosaic_html,
    skeleton3d_html,
)


class ConfigTests(unittest.TestCase):
    def test_camera_id_and_full_topic(self):
        for value in ("5", "/CameraGateway.5.Frame/", " 5 "):
            self.assertEqual(normalize_camera_topic(value), "CameraGateway.5.Frame")
        with self.assertRaises(ValueError):
            normalize_camera_topic("SkeletonDetector.5.Frame")

    @patch.dict("os.environ", {}, clear=True)
    def test_defaults(self):
        self.assertEqual(Settings.from_env(), Settings())
        self.assertEqual(len(camera_topics()), 4)

    @patch.dict(
        "os.environ", {"CAMERA_TOPICS": "2, CameraGateway.7.Frame,", "CAMERA_IDS": "1"}
    )
    def test_explicit_topics_override_ids(self):
        self.assertEqual(
            camera_topics(), ["CameraGateway.2.Frame", "CameraGateway.7.Frame"]
        )


class CodecTests(unittest.TestCase):
    def test_image_bytes_are_not_reencoded(self):
        message = Message(content=Image(data=b"jpeg-bytes"))
        for schema in (None, "Image", "is.vision.Image"):
            self.assertEqual(decode_message(message, schema), ("image", b"jpeg-bytes"))

    def test_protobuf_names_and_metadata(self):
        value = Struct()
        value.update({"label": "câmera", "ok": True})
        message = Message(content=value)
        message.topic = "Some.Struct.Topic"
        message.metadata["is-schema"] = "google.protobuf.Struct"
        for schema in (None, "Struct", "google.protobuf.Struct"):
            kind, body = decode_message(message, schema)
            self.assertEqual(kind, "json")
            self.assertEqual(
                json.loads(body),
                {
                    "topic": "Some.Struct.Topic",
                    "schema": "google.protobuf.Struct",
                    "message": {"label": "câmera", "ok": True},
                },
            )

    def test_raw_json_is_passed_through(self):
        message = Message()
        message.body = b'{"value":42}'
        self.assertEqual(decode_message(message, "Json"), ("json", message.body))

    def test_unknown_payload_falls_back_to_base64(self):
        message = Message()
        message.body = b"\xff"
        message.topic = "Unknown.Topic"
        kind, body = decode_message(message, "UnknownSchema")
        self.assertEqual(kind, "json")
        self.assertEqual(json.loads(body)["body_base64"], "/w==")
        self.assertEqual(json.loads(body)["bytes"], 1)


class HubTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        channel_patch = patch("is_viewer.messaging.hub.Channel")
        subscription_patch = patch("is_viewer.messaging.hub.Subscription")
        self.channel = channel_patch.start().return_value
        self.subscription = subscription_patch.start().return_value
        self.addCleanup(channel_patch.stop)
        self.addCleanup(subscription_patch.stop)
        self.hub = FrameHub("amqp://unused")

    async def test_slow_client_keeps_only_latest_messages(self):
        _, queue = self.hub.add_client(asyncio.get_running_loop(), "Topic", "Json", 2)
        for value in (b"1", b"2", b"3"):
            message = Message()
            message.topic = "Topic"
            message.body = value
            self.hub.dispatch(message)
        await asyncio.sleep(0)
        self.assertEqual(queue.qsize(), 2)
        self.assertEqual(queue.get_nowait(), ("json", b"2"))
        self.assertEqual(queue.get_nowait(), ("json", b"3"))

    async def test_other_topics_do_not_receive_deliveries(self):
        token, queue = self.hub.add_client(asyncio.get_running_loop(), "Other", "Json")
        message = Message()
        message.topic = "Topic"
        message.body = b"1"
        self.hub.dispatch(message)
        await asyncio.sleep(0)
        self.assertTrue(queue.empty())
        self.hub.remove_client(token)
        self.hub.remove_client(token)
        self.assertFalse(self.hub.clients)

    async def test_image_worker_shared_until_last_client_leaves(self):
        with patch("is_viewer.messaging.hub.ImageStreamWorker") as worker_type:
            loop = asyncio.get_running_loop()
            first, _ = self.hub.add_client(loop, "CameraGateway.1.Frame", "Image")
            second, _ = self.hub.add_client(loop, "CameraGateway.1.Frame", "Image")
            self.hub._sync_topics()
            worker_type.assert_called_once()
            worker_type.return_value.start.assert_called_once()
            self.subscription.subscribe.assert_not_called()
            self.hub.remove_client(first)
            self.hub._sync_topics()
            worker_type.return_value.stop.assert_not_called()
            self.hub.remove_client(second)
            self.hub._sync_topics()
            worker_type.return_value.stop.assert_called_once()

    async def test_regular_topics_subscribe_and_unsubscribe(self):
        token, _ = self.hub.add_client(
            asyncio.get_running_loop(), "Some.Topic", "Struct"
        )
        self.hub._sync_topics()
        self.subscription.subscribe.assert_called_once_with("Some.Topic")
        self.hub.remove_client(token)
        self.hub._sync_topics()
        self.subscription.unsubscribe.assert_called_once_with("Some.Topic")

    async def test_pending_messages_keep_latest_per_topic(self):
        first = Mock(topic="A")
        other = Mock(topic="B")
        latest = Mock(topic="A")
        self.channel.consume.side_effect = [other, latest, TimeoutError()]
        self.assertEqual(set(self.hub._latest_messages(first)), {latest, other})


class RpcTests(unittest.TestCase):
    def setUp(self):
        channel_patch = patch("is_viewer.messaging.rpc.Channel")
        subscription_patch = patch("is_viewer.messaging.rpc.Subscription")
        self.channel_type = channel_patch.start()
        subscription_patch.start().return_value = "reply-queue"
        self.addCleanup(channel_patch.stop)
        self.addCleanup(subscription_patch.stop)
        self.rpc = RpcClient("amqp://unused")

    def test_reply_correlation(self):
        def reply_for_request(*args, **kwargs):
            sent = self.rpc.channel.publish.call_args.args[0]
            reply = Message(content=Struct())
            reply.correlation_id = sent.correlation_id
            return reply

        self.rpc.channel.consume.side_effect = reply_for_request
        self.assertIsInstance(self.rpc.call("Get", Struct(), Struct), Struct)

    def test_mismatched_reply_is_rejected(self):
        self.rpc.channel.consume.return_value = Message(content=Struct())
        with self.assertRaisesRegex(RuntimeError, "correlation mismatch"):
            self.rpc.call("Get", Struct(), Struct)

    def test_timeout_is_not_retried(self):
        self.rpc.channel.consume.side_effect = TimeoutError()
        with self.assertRaisesRegex(TimeoutError, "RPC timeout on Get"):
            self.rpc.call("Get", Struct(), Struct)
        self.rpc.channel.publish.assert_called_once()

    def test_connection_failure_reconnects_once(self):
        self.rpc.channel.publish.side_effect = OSError("offline")
        with (
            self.assertLogs("is_viewer.messaging.rpc", level="WARNING"),
            self.assertRaises(OSError),
        ):
            self.rpc.call("Get", Struct(), Struct)
        self.assertEqual(self.channel_type.call_count, 2)
        self.rpc.channel.close.assert_called_once()

    def test_publish_does_not_wait_for_reply(self):
        message = Message(content=Struct())
        self.rpc.publish(message, "Set")
        self.rpc.channel.publish.assert_called_once_with(message, topic="Set")
        self.rpc.channel.consume.assert_not_called()


class ImageStreamTests(unittest.TestCase):
    def test_image_topic_without_dots_can_be_subscribed(self):
        with (
            patch("is_viewer.messaging.image_stream.Channel"),
            patch(
                "is_viewer.messaging.image_stream.StreamSubscription"
            ) as subscription,
        ):
            worker = ImageStreamWorker(Mock(uri="amqp://unused"), "Images")
            subscription.return_value.subscribe.assert_called_once_with("Images")
            self.assertEqual(worker.topic, "Images")


class AssetParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in ("src", "href") and value.startswith("/static/"):
                self.assets.append(value.removeprefix("/static/"))


class PageTests(unittest.TestCase):
    def test_all_page_assets_exist(self):
        pages = [
            home_html(),
            dashboard_html(["CameraGateway.1.Frame"]),
            mosaic_html(2, 3),
            skeleton3d_html("Skeleton.3D"),
            messages_html("/raw", 2),
        ]
        for page in pages:
            parser = AssetParser()
            parser.feed(page)
            self.assertTrue(parser.assets)
            for asset in parser.assets:
                self.assertTrue((WEB_DIRECTORY / "static" / asset).is_file(), asset)

    def test_mosaic_layout_and_cell_count(self):
        page = mosaic_html(2, 3)
        self.assertEqual(page.count('class="mosaic-cell"'), 6)
        self.assertIn("--rows: 2; --columns: 3", page)

    def test_untrusted_topic_is_escaped_and_url_encoded(self):
        page = skeleton3d_html("</code><script>alert(1)</script>")
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("%3Cscript%3E", page)

    def test_message_source_cannot_break_attribute(self):
        page = messages_html('/topic?value="<script>&raw=1', 10)
        self.assertIn("&quot;&lt;script&gt;&amp;raw=1", page)
        self.assertIn('data-history="10"', page)


if __name__ == "__main__":
    unittest.main()
