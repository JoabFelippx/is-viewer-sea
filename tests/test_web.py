"""Rotas, ciclo de vida e streaming; precisa de FastAPI e httpx, sem RabbitMQ."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from is_msgs.camera_pb2 import CameraConfig
from starlette.requests import Request

from is_viewer.app import create_app
from is_viewer.cameras import CameraService, PositionUnavailable, PtzStep
from is_viewer.config import Settings
from is_viewer.web.streaming import topic_response


class RouteTests(unittest.TestCase):
    def setUp(self):
        hub_patch = patch("is_viewer.app.FrameHub")
        rpc_patch = patch("is_viewer.app.RpcClient")
        self.hub = hub_patch.start().return_value
        self.rpc = rpc_patch.start().return_value
        self.addCleanup(hub_patch.stop)
        self.addCleanup(rpc_patch.stop)
        self.app = create_app(Settings(broker_uri="amqp://unused"))
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.cameras = Mock()
        self.app.state.cameras = self.cameras

    def test_pages_and_static_assets(self):
        for path in (
            "/",
            "/camera/5",
            "/mosaic/2x3",
            "/world3d/",
            "/world3d/Custom.Topic",
            "/world3d-sintetico/",
            "/world3d-sintetico/Custom.Topic",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn("text/html", response.headers["content-type"])
        response = self.client.get("/static/camera.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn("setupCamera", response.text)
        self.assertEqual(self.client.get("/static/missing.js").status_code, 404)

    def test_synthetic_view_preserves_topic_without_subscribing_on_page_load(self):
        response = self.client.get("/world3d-sintetico/Tracking.World3D")
        self.assertEqual(response.status_code, 200)
        self.assertIn("/skeleton3d-data/Tracking.World3D", response.text)
        self.assertIn(
            "/static/models/labsea.glb",
            self.client.get("/static/world3d-synthetic.js").text,
        )
        self.assertEqual(
            self.client.get("/static/models/labsea.glb").content[:4], b"glTF"
        )
        self.assertEqual(
            self.client.get("/static/vendor/three/three.core.js").status_code, 200
        )
        self.hub.add_client.assert_not_called()

    def test_invalid_camera_and_mosaic(self):
        for path in (
            "/camera/not-a-camera",
            "/mosaic/0x2",
            "/mosaic/7x6",
            "/mosaic/abc",
        ):
            self.assertEqual(self.client.get(path).status_code, 400)

    def test_undistortion_requires_a_calibrated_camera(self):
        self.assertEqual(
            self.client.get("/stream/SkeletonDetector.2.Frame?undistort=1").status_code,
            400,
        )
        self.assertEqual(
            self.client.get("/stream/CameraGateway.5.Frame?undistort=1").status_code,
            404,
        )

    def test_history_validation_happens_before_subscription(self):
        for history in ("0", "101", "abc"):
            response = self.client.get("/Struct/Some.Topic?history=" + history)
            self.assertEqual(response.status_code, 400)
        self.hub.add_client.assert_not_called()

    def test_json_page_reuses_query_in_raw_url(self):
        response = self.client.get("/Struct/Some.Topic?history=3")
        self.assertEqual(response.status_code, 200)
        self.assertIn('data-history="3"', response.text)
        self.assertIn("raw=1", response.text)
        self.hub.add_client.assert_not_called()

    def test_legacy_3d_redirect(self):
        response = self.client.get("/skeleton3d/Custom.Topic", follow_redirects=False)
        self.assertEqual(response.status_code, 308)
        self.assertEqual(response.headers["location"], "/world3d/Custom.Topic")

    def test_topic_aliases_preserve_schema_and_topic(self):
        paths = [
            ("/stream/SkeletonDetector.2.Frame", "SkeletonDetector.2.Frame", "Image"),
            ("/topic/Struct/Some.Topic", "Some.Topic", "Struct"),
            ("/Image/CameraGateway.1.Frame", "CameraGateway.1.Frame", "Image"),
            ("/CameraGateway.1.Frame/Image", "CameraGateway.1.Frame", "Image"),
            ("/CameraGateway.1.Frame", "CameraGateway.1.Frame", None),
            ("/skeleton3d-data/Some.Topic", "Some.Topic", "ObjectAnnotations"),
        ]
        with patch(
            "is_viewer.web.routes.topic_response", new_callable=AsyncMock
        ) as view:
            view.return_value = JSONResponse({"ok": True})
            for path, topic, schema in paths:
                self.assertEqual(self.client.get(path).status_code, 200)
                args = view.call_args.args
                self.assertEqual(args[1], topic)
                self.assertEqual(args[2] if len(args) > 2 else None, schema)

    def test_ptz_validation_and_capabilities(self):
        for payload in ({}, {"pan": 2}, {"pan": 1, "step_degrees": 46}):
            self.assertEqual(
                self.client.post("/api/cameras/5/ptz", json=payload).status_code, 400
            )
        self.cameras.move_camera.assert_not_called()
        self.cameras.camera_capabilities.return_value = {
            "state": "available",
            "ptz_step": False,
        }
        self.assertEqual(
            self.client.post("/api/cameras/5/ptz", json={"pan": 1}).status_code, 409
        )
        self.cameras.camera_capabilities.return_value["ptz_step"] = True
        self.assertEqual(
            self.client.post("/api/cameras/5/ptz", json={"pan": 1}).json(), {"ok": True}
        )
        self.cameras.move_camera.assert_called_once()

    def test_broker_errors_map_to_http_status(self):
        for error, status in (
            (TimeoutError("late"), 504),
            (OSError("offline"), 503),
            (RuntimeError("bad reply"), 502),
        ):
            self.cameras.camera_capabilities.side_effect = error
            self.assertEqual(
                self.client.get("/api/cameras/5/capabilities").status_code, status
            )

    def test_world3d_suffix_opens_viewer_for_any_prefix(self):
        for topic in ("SkeletonDetector.World3D", "Tracking.Floor.2.World3D"):
            response = self.client.get("/" + topic)
            self.assertEqual(response.status_code, 200)
            self.assertIn("/skeleton3d-data/" + topic, response.text)
            self.assertIn('id="show-map"', response.text)
        self.hub.add_client.assert_not_called()

    def test_world3d_raw_preserves_data_access(self):
        with patch(
            "is_viewer.web.routes.topic_response", new_callable=AsyncMock
        ) as view:
            view.return_value = JSONResponse({"ok": True})
            self.client.get("/Tracking.World3D?raw=1")
            self.assertEqual(
                view.call_args.args[1:], ("Tracking.World3D", "ObjectAnnotations")
            )

    def test_home_requires_absolute_capability(self):
        self.cameras.camera_capabilities.return_value = {
            "state": "available",
            "ptz_absolute": False,
        }
        self.assertEqual(self.client.post("/api/cameras/5/ptz/home").status_code, 409)
        self.cameras.home_camera.assert_not_called()
        self.cameras.camera_capabilities.return_value["ptz_absolute"] = True
        self.assertEqual(
            self.client.post("/api/cameras/5/ptz/home").json(), {"ok": True}
        )
        self.cameras.home_camera.assert_called_once_with(5)

    def test_current_position_and_unavailable_reading(self):
        position = {"pan": 3576, "tilt": 40, "zoom": 10, "units": "camera_native"}
        self.cameras.camera_position.return_value = position
        self.assertEqual(self.client.get("/api/cameras/5/ptz").json(), position)
        self.cameras.camera_position.side_effect = PositionUnavailable("no position")
        self.assertEqual(self.client.get("/api/cameras/5/ptz").status_code, 409)

    def test_new_ptz_endpoints_report_timeouts(self):
        self.cameras.camera_capabilities.return_value = {
            "state": "available",
            "ptz_absolute": True,
        }
        self.cameras.camera_position.side_effect = TimeoutError("late")
        self.cameras.home_camera.side_effect = TimeoutError("late")
        self.assertEqual(self.client.get("/api/cameras/5/ptz").status_code, 504)
        self.assertEqual(self.client.post("/api/cameras/5/ptz/home").status_code, 504)

    def test_scene_json_is_packaged_and_served(self):
        response = self.client.get("/static/world3d-scene.json")
        self.assertEqual(response.status_code, 200)
        scene = response.json()
        self.assertEqual(
            [camera["id"] for camera in scene["cameras"]], [1, 2, 3, 4, 6, 7, 8]
        )
        self.assertEqual(len(scene["map"]["polygons"]), 4)

    def test_lifespan_closes_connections(self):
        with (
            patch("is_viewer.app.FrameHub") as hub,
            patch("is_viewer.app.RpcClient") as rpc,
        ):
            with TestClient(create_app(Settings())):
                hub.return_value.start.assert_called_once()
            hub.return_value.stop.assert_called_once()
            rpc.return_value.close.assert_called_once()


class CameraTests(unittest.TestCase):
    def test_ptz_scales_all_axes(self):
        rpc = Mock()
        CameraService(rpc).move_camera(
            5, PtzStep(pan=1, tilt=-1, zoom=1, step_degrees=10)
        )
        topic, config, _ = rpc.call.call_args.args
        self.assertEqual(topic, "CameraGateway.5.SetConfig")
        self.assertEqual(
            (
                config.ptzcontrol.step.x,
                config.ptzcontrol.step.y,
                config.ptzcontrol.step.z,
            ),
            (2, -2, 2),
        )

    def test_home_serialization_preserves_absolute_zero_command(self):
        rpc = Mock()
        CameraService(rpc).home_camera(5)
        topic, config, _ = rpc.call.call_args.args
        restored = CameraConfig.FromString(config.SerializeToString())
        self.assertEqual(topic, "CameraGateway.5.SetConfig")
        self.assertTrue(restored.ptzcontrol.HasField("absolute"))
        self.assertFalse(restored.ptzcontrol.HasField("step"))
        self.assertEqual(
            (
                restored.ptzcontrol.absolute.x,
                restored.ptzcontrol.absolute.y,
                restored.ptzcontrol.absolute.z,
            ),
            (0, 0, 0),
        )

    def test_position_comes_from_getconfig_including_zero_fields(self):
        rpc = Mock()
        config = CameraConfig()
        config.ptzcontrol.absolute.y = 40
        config.ptzcontrol.absolute.z = 10
        rpc.call.return_value = config
        position = CameraService(rpc).camera_position(5)
        self.assertEqual(rpc.call.call_args.args[0], "CameraGateway.5.GetConfig")
        self.assertEqual(
            position, {"pan": 0, "tilt": 40, "zoom": 10, "units": "camera_native"}
        )
        rpc.call.return_value = CameraConfig()
        with self.assertRaises(PositionUnavailable):
            CameraService(rpc).camera_position(5)

    def test_configuration_publishes_only_when_requested(self):
        rpc = Mock()
        cameras = CameraService(rpc)
        cameras.configure_camera(5, {})
        rpc.publish.assert_not_called()
        cameras.configure_camera(5, {"fps": "10", "color": "gray"})
        rpc.publish.assert_called_once()
        with self.assertRaises(ValueError):
            cameras.configure_camera(5, {"color": "invalid"})


class StreamTests(unittest.IsolatedAsyncioTestCase):
    async def response(self, schema, payload):
        queue = asyncio.Queue()
        queue.put_nowait(payload)
        hub = Mock()
        hub.add_client.return_value = ("token", queue)
        app = SimpleNamespace(state=SimpleNamespace(hub=hub))
        request = Request(
            {"type": "http", "app": app, "query_string": b"raw=1", "headers": []}
        )
        request.is_disconnected = AsyncMock(side_effect=[False, True])
        return await topic_response(request, "Some.Topic", schema), hub

    async def test_mjpeg_boundary_and_client_cleanup(self):
        response, hub = await self.response("Image", ("image", b"jpeg"))
        body = b"".join([part async for part in response.body_iterator])
        self.assertEqual(
            body,
            b"--myboundary\r\nContent-Type: image/jpeg\r\nContent-Length: 4\r\n\r\njpeg\r\n",
        )
        hub.remove_client.assert_called_once_with("token")

    async def test_json_is_delimited_by_newlines(self):
        response, hub = await self.response("Struct", ("json", b'{"ok":true}'))
        body = b"".join([part async for part in response.body_iterator])
        self.assertEqual(body, b'{"ok":true}\n')
        hub.remove_client.assert_called_once_with("token")

    async def test_cancelled_stream_removes_client(self):
        response, hub = await self.response("Image", ("image", b"jpeg"))
        await anext(response.body_iterator)
        await response.body_iterator.aclose()
        hub.remove_client.assert_called_once_with("token")
