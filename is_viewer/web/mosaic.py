"""Monta um único MJPEG com os quadros recentes das câmeras do mosaico."""

import asyncio

import cv2
import numpy as np
from fastapi import Request
from fastapi.responses import StreamingResponse

from .streaming import BOUNDARY

MAX_FRAMES_PER_SECOND = 5
MAX_DECODED_FRAMES_PER_SECOND = 24
FRAME_TIMEOUT_SECONDS = 1.0


def compose_mosaic(
    frames: dict[str, bytes],
    topics: list[str],
    rows: int,
    columns: int,
    width: int,
    height: int,
) -> bytes:
    """Desenha cada JPEG em sua célula, preservando a proporção da imagem."""
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    decoded = {}
    for index, topic in enumerate(topics):
        if topic not in frames:
            continue
        if topic not in decoded:
            decoded[topic] = cv2.imdecode(
                np.frombuffer(frames[topic], dtype=np.uint8), cv2.IMREAD_COLOR
            )
        frame = decoded[topic]
        if frame is None:
            continue

        row, column = divmod(index, columns)
        left, right = column * width // columns, (column + 1) * width // columns
        top, bottom = row * height // rows, (row + 1) * height // rows
        cell_width, cell_height = right - left, bottom - top
        source_height, source_width = frame.shape[:2]
        scale = min(cell_width / source_width, cell_height / source_height)
        resized_width = max(1, round(source_width * scale))
        resized_height = max(1, round(source_height * scale))
        resized = cv2.resize(
            frame, (resized_width, resized_height), interpolation=cv2.INTER_AREA
        )
        x = left + (cell_width - resized_width) // 2
        y = top + (cell_height - resized_height) // 2
        canvas[y : y + resized_height, x : x + resized_width] = resized

    encoded, jpeg = cv2.imencode(".jpg", canvas, [cv2.IMWRITE_JPEG_QUALITY, 75])
    if not encoded:
        raise ValueError("could not encode mosaic frame")
    return jpeg.tobytes()


async def mosaic_response(
    request: Request,
    topics: list[str],
    rows: int,
    columns: int,
    width: int,
    height: int,
) -> StreamingResponse:
    """Compartilha os consumidores existentes e envia uma grade atualizada."""
    hub = request.app.state.hub
    loop = asyncio.get_running_loop()
    subscriptions = {
        topic: hub.add_client(loop, topic, "Image")
        for topic in dict.fromkeys(topics)
        if topic
    }
    latest: dict[str, tuple[float, bytes]] = {}
    fps = min(
        MAX_FRAMES_PER_SECOND,
        MAX_DECODED_FRAMES_PER_SECOND / max(1, len(subscriptions)),
    )

    async def body():
        try:
            while not await request.is_disconnected():
                started = loop.time()
                for topic, (_, queue) in subscriptions.items():
                    while not queue.empty():
                        kind, jpeg = queue.get_nowait()
                        if kind == "image":
                            latest[topic] = (started, jpeg)

                # Uma câmera parada sai da grade, sem congelar o último quadro.
                visible = {
                    topic: jpeg
                    for topic, (received_at, jpeg) in latest.items()
                    if started - received_at < FRAME_TIMEOUT_SECONDS
                }
                jpeg = await asyncio.to_thread(
                    compose_mosaic, visible, topics, rows, columns, width, height
                )
                yield BOUNDARY
                yield b"Content-Type: image/jpeg\r\n"
                yield f"Content-Length: {len(jpeg)}\r\n\r\n".encode()
                yield jpeg
                yield b"\r\n"
                await asyncio.sleep(max(0, 1 / fps - (loop.time() - started)))
        finally:
            for token, _ in subscriptions.values():
                hub.remove_client(token)

    return StreamingResponse(
        body(),
        media_type="multipart/x-mixed-replace; boundary=myboundary",
        headers={"Cache-Control": "no-store", "Connection": "close"},
    )
