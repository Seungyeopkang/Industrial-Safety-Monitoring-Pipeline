import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from detection.video import select_video_frame


class VideoSelectionTests(unittest.TestCase):
    def test_empty_video_frames_do_not_confirm_vlm_candidate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "empty.avi"
            writer = cv2.VideoWriter(
                str(path), cv2.VideoWriter_fourcc(*"MJPG"), 4.0, (32, 32)
            )
            for value in (20, 60, 100, 140):
                writer.write(np.full((32, 32, 3), value, dtype=np.uint8))
            writer.release()

            empty_output = {"model": "fake", "detections": [], "summary": []}
            with patch("detection.video.load_model", return_value=object()), patch(
                "detection.video.run_detection_frame",
                side_effect=lambda frame, model: (empty_output, frame.copy()),
            ):
                result = select_video_frame(str(path), sample_fps=2.0)

        self.assertFalse(result["confirmed"])
        self.assertEqual(result["selection_reason"], "no_consecutive_vlm_candidate")
        self.assertGreaterEqual(result["sampled_frames"], 2)


if __name__ == "__main__":
    unittest.main()
