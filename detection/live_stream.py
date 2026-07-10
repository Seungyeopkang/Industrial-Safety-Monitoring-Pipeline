"""In-memory per-camera gate used by the lightweight live-stream endpoint."""
import time

import cv2
import numpy as np

from detection.detector import load_model, run_detection_frame
from detection.stream_policy import ConsecutiveFrameGate


class LiveStreamSession:
    def __init__(self, confirmation_frames: int = 2, cooldown_seconds: float = 10.0):
        self.model = load_model()
        self.gate = ConsecutiveFrameGate(confirmation_frames)
        self.cooldown_seconds = cooldown_seconds
        self.last_dispatch_at = 0.0

    def process_jpeg(self, payload: bytes):
        frame = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("Invalid image frame")
        detection, annotated = run_detection_frame(frame, self.model)
        decision = self.gate.observe(detection["detections"])
        now = time.monotonic()
        should_dispatch = decision.should_dispatch and now - self.last_dispatch_at >= self.cooldown_seconds
        if should_dispatch:
            self.last_dispatch_at = now
            self.gate = ConsecutiveFrameGate(self.gate.required_frames)
        elif decision.should_dispatch:
            decision = type(decision)(False, "stream_cooldown")
        return frame, annotated, detection, decision, should_dispatch
