"""Geometria e correção JPEG baseadas nas calibrações reais incluídas no pacote."""

import json
import unittest

import cv2
import numpy as np

from is_viewer.web.vision import (
    calibration,
    project_annotations,
    transform_annotations_2d,
    undistort_jpeg,
)


class VisionTests(unittest.TestCase):
    def test_2d_points_and_bounding_polygon_in_both_pixel_spaces(self):
        width, height = 1280, 720
        sample = {
            "publisher": "detector-1",
            "message": {
                "resolution": {"width": width, "height": height},
                "objects": [
                    {
                        "id": 8,
                        "label": "person",
                        "keypoints": [{"id": 7, "position": {"x": 640, "y": 360}}],
                        "region": {
                            "vertices": [
                                {"x": 600, "y": 300},
                                {"x": 680, "y": 300},
                                {"x": 680, "y": 420},
                                {"x": 600, "y": 420},
                            ]
                        },
                    }
                ],
            },
        }
        result = json.loads(transform_annotations_2d(json.dumps(sample).encode(), 1))
        self.assertEqual(result["publisher"], "detector-1")
        item = result["objects"][0]
        self.assertEqual(item["label"], "person")
        self.assertEqual(len(item["region"]), 4)
        self.assertEqual(item["keypoints"][0]["raw"], [640, 360])
        self.assertTrue(np.isfinite(item["keypoints"][0]["corrected"]).all())
        normalized = {
            **sample,
            "message": {
                **sample["message"],
                "objects": [
                    {
                        **sample["message"]["objects"][0],
                        "keypoints": [{"id": 7, "position": {"x": 0.5, "y": 0.5}}],
                    }
                ],
            },
        }
        normalized_result = json.loads(
            transform_annotations_2d(json.dumps(normalized).encode(), 1, "normalized")
        )
        self.assertEqual(
            normalized_result["objects"][0]["keypoints"][0]["raw"], [640, 360]
        )
        uncalibrated = json.loads(
            transform_annotations_2d(json.dumps(sample).encode(), 5)
        )
        self.assertEqual(uncalibrated["objects"][0]["keypoints"][0]["raw"], [640, 360])
        self.assertEqual(
            uncalibrated["objects"][0]["keypoints"][0]["corrected"], [640, 360]
        )

    def test_project_optical_axis_into_both_image_spaces(self):
        for camera_id in (1, 7):
            with self.subTest(camera_id=camera_id):
                camera = calibration(camera_id)
                point = np.asarray(camera["position"]) + 5 * np.asarray(
                    camera["forward"]
                )
                payload = json.dumps(
                    {
                        "message": {
                            "objects": [
                                {
                                    "id": 42,
                                    "keypoints": [
                                        {
                                            "id": 7,
                                            "position": dict(
                                                zip("xyz", point.tolist())
                                            ),
                                        }
                                    ],
                                }
                            ]
                        }
                    }
                ).encode()
                projected = json.loads(project_annotations(payload, camera_id))
                keypoint = projected["objects"][0]["keypoints"][0]
                self.assertEqual(keypoint["id"], 7)
                intrinsics = camera["intrinsics"]
                np.testing.assert_allclose(
                    keypoint["corrected"],
                    [
                        intrinsics["undistorted"][0][2] - intrinsics["roi_xywh"][0],
                        intrinsics["undistorted"][1][2] - intrinsics["roi_xywh"][1],
                    ],
                    atol=1e-5,
                )
                self.assertTrue(all(np.isfinite(keypoint["raw"])))

    def test_points_behind_camera_are_not_drawn(self):
        camera = calibration(1)
        point = np.asarray(camera["position"]) - np.asarray(camera["forward"])
        payload = json.dumps(
            {
                "objects": [
                    {
                        "id": 3,
                        "keypoints": [
                            {"id": 7, "position": dict(zip("xyz", point.tolist()))}
                        ],
                    }
                ]
            }
        ).encode()
        self.assertEqual(json.loads(project_annotations(payload, 1)), {"objects": []})

    def test_undistorted_jpeg_is_cropped_to_calibration_roi(self):
        image = np.zeros((720, 1280, 3), dtype=np.uint8)
        cv2.circle(image, (300, 300), 70, (255, 255, 255), -1)
        encoded = cv2.imencode(".jpg", image)[1].tobytes()
        output = cv2.imdecode(
            np.frombuffer(undistort_jpeg(encoded, 1), dtype=np.uint8),
            cv2.IMREAD_COLOR,
        )
        x, y, width, height = calibration(1)["intrinsics"]["roi_xywh"]
        self.assertEqual(output.shape, (height, width, 3))
        self.assertGreater(np.count_nonzero(output), 0)
        self.assertFalse(np.array_equal(output, image[y : y + height, x : x + width]))

    def test_invalid_jpeg_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "not a JPEG"):
            undistort_jpeg(b"not an image", 1)
