"""API HTTP dos comandos de câmera e leitura da posição PTZ."""

from contextlib import contextmanager

from fastapi import APIRouter, HTTPException, Request

from ..cameras import PositionUnavailable, PtzStep

router = APIRouter(prefix="/api/cameras")


@contextmanager
def camera_errors():
    """Traduz falhas do broker para o mesmo contrato HTTP em todas as operações."""
    try:
        yield
    except PositionUnavailable as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except TimeoutError as error:
        raise HTTPException(status_code=504, detail=str(error)) from error
    except (ConnectionError, OSError) as error:
        raise HTTPException(status_code=503, detail="AMQP unavailable") from error
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


def require_capability(cameras, camera_id: int, capability: str):
    capabilities = cameras.camera_capabilities(camera_id)
    if capabilities.get("state") != "available" or not capabilities.get(capability):
        raise HTTPException(
            status_code=409, detail=f"camera does not support {capability}"
        )


@router.get("/{camera_id}/capabilities")
def camera_capabilities(request: Request, camera_id: int):
    with camera_errors():
        return request.app.state.cameras.camera_capabilities(camera_id)


@router.get("/{camera_id}/ptz")
def camera_position(request: Request, camera_id: int):
    with camera_errors():
        return request.app.state.cameras.camera_position(camera_id)


@router.post("/{camera_id}/ptz/home")
def home_camera(request: Request, camera_id: int):
    with camera_errors():
        cameras = request.app.state.cameras
        require_capability(cameras, camera_id, "ptz_absolute")
        cameras.home_camera(camera_id)
        return {"ok": True}


@router.post("/{camera_id}/ptz")
def move_camera(request: Request, camera_id: int, step: PtzStep):
    values = (step.pan, step.tilt, step.zoom)
    if not any(values) or any(value not in (-1, 0, 1) for value in values):
        raise HTTPException(
            status_code=400, detail="PTZ step values must be -1, 0 or 1"
        )
    if not 0.5 <= step.step_degrees <= 45:
        raise HTTPException(
            status_code=400, detail="PTZ step must be between 0.5 and 45 degrees"
        )
    with camera_errors():
        cameras = request.app.state.cameras
        require_capability(cameras, camera_id, "ptz_step")
        cameras.move_camera(camera_id, step)
        return {"ok": True}
