"""Entrega de imagens MJPEG e mensagens JSON por conexão HTTP."""

import asyncio

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse

from ..config import CAMERA_TOPIC
from .pages import messages_html

BOUNDARY = b"--myboundary\r\n"


async def topic_response(request: Request, topic: str, schema_hint=None):
    topic = topic.strip("/")
    if topic.endswith(".Frame"):
        schema_hint = "Image"
    is_image = schema_hint in ("Image", "is.vision.Image")
    try:
        default_history = "1"
        history = int(request.query_params.get("history", default_history))
    except ValueError:
        raise HTTPException(
            status_code=400, detail="history must be an integer"
        ) from None
    if not 1 <= history <= 100:
        raise HTTPException(status_code=400, detail="history must be between 1 and 100")
    hub = request.app.state.hub
    try:
        match = CAMERA_TOPIC.fullmatch(topic)
        if match is not None:
            camera_id = match.group(1)
            request.app.state.cameras.configure_camera(camera_id, request.query_params)
    except (ValueError, TypeError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except (ConnectionError, OSError) as error:
        raise HTTPException(status_code=503, detail="AMQP unavailable") from error

    if (
        not is_image
        and schema_hint not in ("Json", "ObjectAnnotations")
        and request.query_params.get("raw") != "1"
    ):
        raw_url = str(request.url.include_query_params(raw="1"))
        return HTMLResponse(messages_html(raw_url, history))

    loop = asyncio.get_running_loop()
    token, queue = hub.add_client(loop, topic, schema_hint, history)

    async def body():
        try:
            while not await request.is_disconnected():
                kind, payload = await queue.get()
                if kind == "image":
                    yield BOUNDARY
                    yield b"Content-Type: image/jpeg\r\n"
                    yield f"Content-Length: {len(payload)}\r\n\r\n".encode()
                    yield payload
                    yield b"\r\n"
                else:
                    yield payload + b"\n"
        finally:
            hub.remove_client(token)

    media_type = (
        "multipart/x-mixed-replace; boundary=myboundary"
        if is_image
        else "text/plain; charset=utf-8"
    )
    return StreamingResponse(
        body(),
        media_type=media_type,
        headers={"Cache-Control": "no-store", "Connection": "close"},
    )
