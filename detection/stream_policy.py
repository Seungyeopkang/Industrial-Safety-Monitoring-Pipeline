"""Pure VLM dispatch policy shared by video and future live-stream inputs."""
from dataclasses import dataclass
from typing import Iterable, Mapping


PERSON_ONLY_CLASSES = {"Person"}


@dataclass(frozen=True)
class VlmDispatchDecision:
    should_dispatch: bool
    reason: str


def decide_vlm_dispatch(
    detections: Iterable[Mapping[str, object]], *, mode: str = "image"
) -> VlmDispatchDecision:
    """Decide whether a detected frame should enter the VLM stage.

    A still image retains the existing safety-net behavior: a zero-detection
    result may be a detector miss, so it is checked by the VLM. Stream/video
    frames are different: empty frames are expected and must not spend a VLM
    request. A later consecutive-frame gate handles candidate persistence.
    """
    items = list(detections)
    if not items:
        if mode == "image":
            return VlmDispatchDecision(True, "image_no_detection_verify")
        return VlmDispatchDecision(False, "stream_no_detection_skip")

    if any(bool(item.get("vlm_trigger")) for item in items):
        return VlmDispatchDecision(True, "detector_requested_verification")

    classes = {str(item.get("class_name")) for item in items}
    if classes and classes <= PERSON_ONLY_CLASSES:
        return VlmDispatchDecision(True, "person_only_verify")
    return VlmDispatchDecision(False, "high_confidence_detection_skip")


class ConsecutiveFrameGate:
    """Require consecutive candidate frames before a video event is selected."""

    def __init__(self, required_frames: int = 2):
        if required_frames < 1:
            raise ValueError("required_frames must be at least 1")
        self.required_frames = required_frames
        self.candidate_streak = 0

    def observe(self, detections: Iterable[Mapping[str, object]]) -> VlmDispatchDecision:
        decision = decide_vlm_dispatch(detections, mode="stream")
        if not decision.should_dispatch:
            self.candidate_streak = 0
            return decision

        self.candidate_streak += 1
        if self.candidate_streak >= self.required_frames:
            return VlmDispatchDecision(True, "consecutive_candidate_confirmed")
        return VlmDispatchDecision(False, "candidate_waiting_for_confirmation")
