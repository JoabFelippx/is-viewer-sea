"""Converte calibrações e mapa locais em JSON portátil para o navegador.

Execute com --help. NumPy só é necessário nesta conversão, não no servidor.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

CAMERA_IDS = (1, 2, 3, 4, 6, 7, 8)


def camera_pose(path: Path, camera_id: int) -> dict:
    with np.load(path, allow_pickle=False) as calibration:
        transform = np.asarray(calibration["rt"], dtype=float)
    if transform.shape not in ((3, 4), (4, 4)) or not np.isfinite(transform).all():
        raise ValueError(f"{path.name}: rt deve ser uma matriz 3x4 ou 4x4 finita")
    rotation, translation = transform[:3, :3], transform[:3, 3]
    if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-5):
        raise ValueError(f"{path.name}: rotação inválida")
    # rt transforma mundo em câmera: o centro no mundo é -Rᵀt.
    position = -rotation.T @ translation
    forward = rotation.T @ np.array([0.0, 0.0, 1.0])
    return {
        "id": camera_id,
        "position": position.tolist(),
        "forward": forward.tolist(),
        "map_only": camera_id in (6, 7, 8),
        "source": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def map_polygons(path: Path, trust_pickle: bool = False) -> list:
    # O NPZ legado guarda listas NumPy como objetos pickle. O opt-in é apenas
    # para conversão offline de um arquivo conhecido, nunca para uploads HTTP.
    with np.load(path, allow_pickle=trust_pickle) as archive:
        polygons = archive["lista"]
        result = []
        for polygon in polygons:
            points = np.asarray(polygon, dtype=float)
            if points.ndim != 2 or points.shape[1] != 3 or len(points) < 3:
                raise ValueError("Cada contorno deve conter pelo menos três pontos XYZ")
            if not np.isfinite(points).all():
                raise ValueError("O mapa contém coordenadas não finitas")
            result.append(points.tolist())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    data_directory = Path(__file__).resolve().parents[1] / "data/world3d"
    parser.add_argument(
        "--calibrations", type=Path, default=data_directory / "calibrations"
    )
    parser.add_argument("--map", type=Path, default=data_directory / "map_B3A1.npz")
    parser.add_argument("--trust-map-pickle", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "is_viewer/web/static/world3d-scene.json",
    )
    args = parser.parse_args()
    scene = {
        "units": "m",
        "coordinate_system": "calibration_world_z_up",
        "cameras": [
            camera_pose(args.calibrations / f"calib_rt{i}.npz", i) for i in CAMERA_IDS
        ],
        "map": {
            "source": args.map.name,
            "sha256": hashlib.sha256(args.map.read_bytes()).hexdigest(),
            "polygons": map_polygons(args.map, args.trust_map_pickle),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(scene, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    print(
        f"{args.output}: {len(scene['cameras'])} câmeras e {len(scene['map']['polygons'])} contornos"
    )


if __name__ == "__main__":
    main()
