import unittest

from detection.stream_policy import ConsecutiveFrameGate, decide_vlm_dispatch


class StreamPolicyTests(unittest.TestCase):
    def test_still_image_keeps_no_detection_safety_net(self):
        decision = decide_vlm_dispatch([], mode="image")
        self.assertTrue(decision.should_dispatch)
        self.assertEqual(decision.reason, "image_no_detection_verify")

    def test_stream_skips_empty_frame(self):
        decision = decide_vlm_dispatch([], mode="stream")
        self.assertFalse(decision.should_dispatch)
        self.assertEqual(decision.reason, "stream_no_detection_skip")

    def test_stream_requires_two_consecutive_candidates(self):
        gate = ConsecutiveFrameGate(required_frames=2)
        candidate = [{"class_name": "NO-Hardhat", "vlm_trigger": True}]
        self.assertFalse(gate.observe(candidate).should_dispatch)
        self.assertTrue(gate.observe(candidate).should_dispatch)

    def test_empty_frame_resets_candidate_streak(self):
        gate = ConsecutiveFrameGate(required_frames=2)
        candidate = [{"class_name": "NO-Hardhat", "vlm_trigger": True}]
        gate.observe(candidate)
        gate.observe([])
        self.assertFalse(gate.observe(candidate).should_dispatch)


if __name__ == "__main__":
    unittest.main()
