"""Geometria e correção JPEG baseadas nas calibrações reais incluídas no pacote."""

import json
import unittest

import cv2
import numpy as np

from is_viewer.web.vision import calibration, project_annotations, undistort_jpeg


class VisionTests(unittest.TestCase):
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
