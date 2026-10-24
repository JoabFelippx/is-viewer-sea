"""Importação de geometria: mundo Z-up e formatos NPZ de todas as câmeras."""

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from is_viewer.web.pages import WEB_DIRECTORY
from scripts.import_world3d import camera_pose, map_polygons


class SceneTests(unittest.TestCase):
    def test_camera_center_uses_inverse_extrinsics_in_both_shapes(self):
        rotation = np.array([[0.0, -1, 0], [1, 0, 0], [0, 0, 1]])
        center = np.array([3.0, 4, 2])
        transform = np.eye(4)
        transform[:3, :3] = rotation
        transform[:3, 3] = -rotation @ center
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "camera.npz"
            for shape in (transform, transform[:3]):
                np.savez(
                    path,
                    rt=shape,
                    K=np.eye(3),
                    nK=np.eye(3),
                    dist=np.zeros((1, 5)),
                    roi=np.array([0, 0, 1280, 720]),
                )
                camera = camera_pose(path, 6)
                np.testing.assert_allclose(camera["position"], center)
                np.testing.assert_allclose(camera["forward"], rotation.T @ [0, 0, 1])
                self.assertTrue(camera["map_only"])

    def test_map_requires_explicit_trust_and_preserves_coordinates(self):
        polygons = np.empty(1, dtype=object)
        polygons[0] = [[1.0, 2, 0], [3.0, 4, 0], [5.0, 6, 0]]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "map.npz"
            np.savez(path, lista=polygons)
            with self.assertRaises(ValueError):
                map_polygons(path)
            self.assertEqual(map_polygons(path, True), polygons.tolist())

    def test_nonfinite_map_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "map.npz"
            np.savez(path, lista=[[[float("nan"), 0, 0], [1, 0, 0], [0, 1, 0]]])
            with self.assertRaises(ValueError):
                map_polygons(path)

    def test_supplied_scene_contains_seven_calibrations_and_original_map(self):
        scene = json.loads((WEB_DIRECTORY / "static/world3d-scene.json").read_text())
        self.assertEqual(scene["units"], "m")
        cameras = {row["id"]: row for row in scene["cameras"]}
        self.assertEqual(set(cameras), {1, 2, 3, 4, 6, 7, 8})
        np.testing.assert_allclose(
            cameras[1]["position"], [2.7367904119, 3.6985051546, 2.8676400254]
        )
        self.assertEqual(
            [i for i, row in cameras.items() if row["map_only"]], [6, 7, 8]
        )
        self.assertEqual([len(p) for p in scene["map"]["polygons"]], [146, 65, 71, 36])
