import unittest

import numpy as np

from detection.experiments.robustness_evaluate import apply_condition


class RobustnessTransformTests(unittest.TestCase):
    def test_conditions_are_deterministic_and_shape_preserving(self):
        image = np.full((80, 100, 3), 160, dtype=np.uint8)
        labels = [{"class": "helmet", "bbox": [20, 20, 50, 50]}]
        for condition in ("baseline", "low_light", "glare", "high_contrast", "jpeg_artifact", "occlusion_ppe_50"):
            first = apply_condition(image, labels, condition, "case-1")
            second = apply_condition(image, labels, condition, "case-1")
            self.assertEqual(first.shape, image.shape)
            self.assertTrue(np.array_equal(first, second))


if __name__ == "__main__":
    unittest.main()
