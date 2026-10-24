"""Correção da lente e projeção de anotações 3D usando as calibrações NPZ importadas.

O JSON é gerado por scripts/import_world3d.py e incluído no pacote. Assim, o
servidor não precisa abrir NPZ ou pickle enquanto atende aos streams.
"""

import json
from functools import cache

import cv2
import numpy as np
from fastapi import HTTPException

from .pages import WEB_DIRECTORY

SCENE_PATH = WEB_DIRECTORY / "static/world3d-scene.json"
DEFAULT_IMAGE_SIZE = (1280, 720)


@cache
def calibration(camera_id: int) -> dict:
    scene = json.loads(SCENE_PATH.read_text(encoding="utf-8"))
    for camera in scene["cameras"]:
        if camera["id"] == camera_id:
            return camera
    raise HTTPException(status_code=404, detail="camera calibration not found")


def image_size(camera: dict) -> tuple[int, int]:
    recorded = camera["intrinsics"]["image_size"]
    if recorded:
        return recorded["width"], recorded["height"]
    # Os NPZ das câmeras 6–8 guardam ROI, mas não o tamanho da imagem original.
    return DEFAULT_IMAGE_SIZE


def scaled_roi(camera_id: int, width: int, height: int) -> tuple[int, int, int, int]:
    camera = calibration(camera_id)
    original_width, original_height = image_size(camera)
    scale_x, scale_y = width / original_width, height / original_height
    x, y, roi_width, roi_height = camera["intrinsics"]["roi_xywh"]
    return (
        round(x * scale_x),
        round(y * scale_y),
        round(roi_width * scale_x),
        round(roi_height * scale_y),
    )


@cache
def undistortion_maps(camera_id: int, width: int, height: int):
    camera = calibration(camera_id)
    original_width, original_height = image_size(camera)
    scale = np.diag([width / original_width, height / original_height, 1.0])
    intrinsics = camera["intrinsics"]
    raw = scale @ np.asarray(intrinsics["raw"], dtype=np.float64)
    corrected = scale @ np.asarray(intrinsics["undistorted"], dtype=np.float64)
    distortion = np.asarray(intrinsics["distortion"], dtype=np.float64)
    return cv2.initUndistortRectifyMap(
        raw, distortion, None, corrected, (width, height), cv2.CV_16SC2
    )


def undistort_jpeg(payload: bytes, camera_id: int) -> bytes:
    image = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("camera frame is not a JPEG image")
    height, width = image.shape[:2]
    map_x, map_y = undistortion_maps(camera_id, width, height)
    corrected = cv2.remap(image, map_x, map_y, interpolation=cv2.INTER_LINEAR)
    x, y, roi_width, roi_height = scaled_roi(camera_id, width, height)
    if (
        roi_width <= 0
        or roi_height <= 0
        or x + roi_width > width
        or y + roi_height > height
    ):
        raise ValueError("calibration ROI is outside the camera image")
    corrected = corrected[y : y + roi_height, x : x + roi_width]
    encoded, output = cv2.imencode(".jpg", corrected, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not encoded:
        raise ValueError("could not encode undistorted frame")
    return output.tobytes()


def project_annotations(payload: bytes, camera_id: int) -> bytes:
    """Retorna pixels brutos e corrigidos para cada keypoint visível."""
    camera = calibration(camera_id)
    intrinsics = camera["intrinsics"]
    transform = np.asarray(camera["world_to_camera"], dtype=np.float64)[:3]
    rotation, translation = transform[:, :3], transform[:, 3]
    rotation_vector = cv2.Rodrigues(rotation)[0]
    raw = np.asarray(intrinsics["raw"], dtype=np.float64)
    corrected = np.asarray(intrinsics["undistorted"], dtype=np.float64)
    distortion = np.asarray(intrinsics["distortion"], dtype=np.float64)
    roi_x, roi_y, _, _ = intrinsics["roi_xywh"]
    value = json.loads(payload)
    message = value.get("message", value)
    objects = []
    for item in message.get("objects", []):
        points = []
        ids = []
        for point in item.get("keypoints", []):
            position = point.get("position") or {}
            xyz = np.asarray(
                [position.get(axis, 0.0) for axis in ("x", "y", "z")],
                dtype=np.float64,
            )
            if np.isfinite(xyz).all() and (rotation @ xyz + translation)[2] > 0:
                points.append(xyz)
                ids.append(point.get("id"))
        if not points:
            continue
        world_points = np.asarray(points, dtype=np.float64)
        raw_pixels = cv2.projectPoints(
            world_points, rotation_vector, translation, raw, distortion
        )[0].reshape(-1, 2)
        corrected_pixels = cv2.projectPoints(
            world_points, rotation_vector, translation, corrected, None
        )[0].reshape(-1, 2)
        corrected_pixels -= np.asarray([roi_x, roi_y], dtype=np.float64)
        keypoints = [
            {
                "id": point_id,
                "raw": raw_pixel.tolist(),
                "corrected": corrected_pixel.tolist(),
            }
            for point_id, raw_pixel, corrected_pixel in zip(
                ids, raw_pixels, corrected_pixels
            )
            if np.isfinite(raw_pixel).all() and np.isfinite(corrected_pixel).all()
        ]
        if keypoints:
            objects.append({"id": item.get("id"), "keypoints": keypoints})
    return json.dumps({"objects": objects}, separators=(",", ":")).encode()
