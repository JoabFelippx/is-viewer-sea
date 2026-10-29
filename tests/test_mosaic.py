"""Composição da grade e descarte de quadros antigos, sem câmeras reais."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import cv2
import numpy as np
from fastapi import HTTPException
from starlette.requests import Request

from is_viewer.web.mosaic import compose_mosaic, mosaic_response
from is_viewer.web.routes import mosaic_stream


def jpeg(color, width=80, height=40):
    pixels = np.full((height, width, 3), color, dtype=np.uint8)
    return cv2.imencode(".jpg", pixels)[1].tobytes()


class MosaicTests(unittest.IsolatedAsyncioTestCase):
    def test_cells_preserve_order_aspect_ratio_and_empty_spaces(self):
        frames = {"red": jpeg((0, 0, 255)), "green": jpeg((0, 255, 0))}
        result = compose_mosaic(frames, ["red", "green", "", "red"], 2, 2, 320, 240)
        pixels = cv2.imdecode(np.frombuffer(result, np.uint8), cv2.IMREAD_COLOR)
        self.assertEqual(pixels.shape, (240, 320, 3))
        for y, x, color in (
            (60, 80, (0, 0, 255)),
            (60, 240, (0, 255, 0)),
            (180, 240, (0, 0, 255)),
            (180, 80, (0, 0, 0)),
            (5, 80, (0, 0, 0)),
        ):
            self.assertTrue(np.allclose(pixels[y, x], color, atol=5))

    def test_invalid_image_does_not_break_other_cells(self):
        result = compose_mosaic({"bad": b"not a JPEG"}, ["bad"], 1, 1, 160, 120)
        pixels = cv2.imdecode(np.frombuffer(result, np.uint8), cv2.IMREAD_COLOR)
        self.assertEqual(int(pixels.max()), 0)

    async def test_stream_expires_frames_and_releases_shared_subscriptions(self):
        queue = asyncio.Queue(maxsize=1)
        queue.put_nowait(("image", b"latest"))
        hub = Mock()
        hub.add_client.return_value = ("token", queue)
        request = SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(hub=hub)),
            is_disconnected=AsyncMock(return_value=False),
        )
        clock = SimpleNamespace(time=Mock(side_effect=[0, 0, 2]))
        with patch("is_viewer.web.mosaic.asyncio.get_running_loop", return_value=clock):
            response = await mosaic_response(
                request, ["Camera", "Camera"], 1, 2, 320, 120
            )
        hub.add_client.assert_called_once()
        with patch(
            "is_viewer.web.mosaic.compose_mosaic", return_value=b"JPEG"
        ) as compose:
            with patch("is_viewer.web.mosaic.asyncio.sleep", new_callable=AsyncMock):
                for _ in range(5):
                    await anext(response.body_iterator)
                self.assertEqual(compose.call_args.args[0], {"Camera": b"latest"})
                await anext(response.body_iterator)
                self.assertEqual(compose.call_args.args[0], {})
                await response.body_iterator.aclose()
        hub.remove_client.assert_called_once_with("token")

    async def test_invalid_stream_parameters_are_rejected(self):
        for query in ("topic=Camera&width=99999", "topic=Bad%23", "topic=A&topic=B"):
            request = Request({"type": "http", "query_string": query.encode()})
            with self.assertRaises(HTTPException) as caught:
                await mosaic_stream(request, "1x1")
            self.assertEqual(caught.exception.status_code, 400)
