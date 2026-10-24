"""Endpoints de páginas, streams e comandos de câmera.

As rotas genéricas ficam por último para não capturar /api, /stream e /world3d.
"""

import re
from functools import partial

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..config import CAMERA_TOPIC, normalize_camera_topic
from .pages import (
    calibration_html,
    dashboard_html,
    home_html,
    mosaic_html,
    skeleton3d_html,
)
from .streaming import projection_response, topic_response
from .vision import calibration, undistort_jpeg

router = APIRouter()


@router.get("/")
async def default_view():
    return HTMLResponse(home_html())


@router.get("/calib")
@router.get("/calib/")
async def calibration_overview():
    return HTMLResponse(calibration_html())


@router.get("/calib/{camera_id}")
async def camera_calibration(camera_id: int):
    if camera_id not in (1, 2, 3, 4, 6, 7, 8):
        raise HTTPException(status_code=404, detail="calibration not found")
    return HTMLResponse(calibration_html(camera_id))


@router.get("/stream/{topic:path}")
async def camera_stream(request: Request, topic: str):
    # O stream também é usado pelo mosaico para imagens produzidas por
    # outros serviços, por exemplo SkeletonDetector.<id>.Frame. A validação
    # específica de CameraGateway permanece apenas nas rotas de PTZ.
    topic = topic.strip("/").strip()
    if not topic or "/" in topic or len(topic) > 255:
        raise HTTPException(status_code=400, detail="invalid image topic")
    image_transform = None
    if request.query_params.get("undistort") == "1":
        match = CAMERA_TOPIC.fullmatch(topic)
        if match is None:
            raise HTTPException(
                status_code=400, detail="undistortion needs a camera topic"
            )
        camera_id = int(match.group(1))
        calibration(camera_id)
        image_transform = partial(undistort_jpeg, camera_id=camera_id)
    return await topic_response(request, topic, "Image", image_transform)


@router.get("/projection/{camera_id}/{topic:path}")
async def camera_projection(request: Request, camera_id: int, topic: str):
    topic = topic.strip("/").strip()
    if not topic or "/" in topic or len(topic) > 255 or any(c in topic for c in "*#"):
        raise HTTPException(status_code=400, detail="invalid 3D topic")
    calibration(camera_id)
    return await projection_response(request, camera_id, topic)


@router.get("/camera/{topic:path}")
async def camera_view(topic: str):
    try:
        topic = normalize_camera_topic(topic)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return HTMLResponse(dashboard_html([topic]))


@router.get("/mosaic/{layout}")
async def mosaic_view(layout: str):
    match = re.fullmatch(r"([1-9][0-9]*)x([1-9][0-9]*)", layout)
    if match is None:
        raise HTTPException(status_code=400, detail="layout must be ROWSxCOLUMNS")
    rows, columns = (int(value) for value in match.groups())
    if rows * columns > 36:
        raise HTTPException(status_code=400, detail="mosaic cannot exceed 36 cells")
    return HTMLResponse(mosaic_html(rows, columns))


@router.get("/skeleton3d/{topic:path}")
async def skeleton3d_view(topic: str):
    return RedirectResponse(f"/world3d/{topic.strip('/')}", status_code=308)


@router.get("/world3d/")
async def world3d_default_view():
    return HTMLResponse(skeleton3d_html("SkeletonDetector.3D.Annotations"))


@router.get("/world3d/{topic:path}")
async def world3d_view(topic: str):
    return HTMLResponse(skeleton3d_html(topic.strip("/")))


@router.get("/skeleton3d-data/{topic:path}")
async def skeleton3d_data(request: Request, topic: str):
    return await topic_response(request, topic.strip("/"), "ObjectAnnotations")


@router.get("/topic/{schema}/{topic:path}")
async def explicit_topic_view(request: Request, schema: str, topic: str):
    return await topic_response(request, topic, schema)


@router.get("/{topic:path}/Image")
async def image_suffix_view(request: Request, topic: str):
    return await topic_response(request, topic, "Image")


@router.get("/{schema}/{topic:path}")
async def schema_prefix_view(request: Request, schema: str, topic: str):
    return await topic_response(request, topic, schema)


@router.get("/{topic:path}")
async def automatic_view(request: Request, topic: str):
    if topic.strip("/").endswith(".World3D") and request.query_params.get("raw") != "1":
        return HTMLResponse(skeleton3d_html(topic.strip("/")))
    if topic.strip("/").endswith(".World3D"):
        return await topic_response(request, topic, "ObjectAnnotations")
    return await topic_response(request, topic)
