"""Memory-only representative-frame selection for uploaded videos.

Only the final selected frame is written by the API layer. Decoded frames and
the short confirmation window remain in memory, preventing per-frame disk I/O.
"""
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2

from detection.detector import load_model, run_detection_frame
from detection.stream_policy import ConsecutiveFrameGate

VIDEO_SAMPLE_FPS = 2.0
VIDEO_CONFIRMATION_FRAMES = 2


def _sharpness_score(frame) -> float:
    return float(cv2.Laplacian(frame, cv2.CV_64F).var())


def select_video_frame(
    video_path: str,
    *,
    sample_fps: float = VIDEO_SAMPLE_FPS,
    confirmation_frames: int = VIDEO_CONFIRMATION_FRAMES,
) -> Dict[str, Any]:
    """Return a confirmed VLM candidate or the sharpest sampled fallback.

    The caller always receives a displayable representative frame. `confirmed`
    says whether it is eligible to invoke VLM/RAG/LLM.
    """
    if sample_fps <= 0:
        raise ValueError("sample_fps must be positive")

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"Unable to open video: {Path(video_path).name}")

    source_fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_interval = max(1, round(source_fps / sample_fps)) if source_fps else 1
    model = load_model()
    gate = ConsecutiveFrameGate(confirmation_frames)
    candidate_window: List[Tuple[float, Any, Dict[str, Any], Any, int]] = []
    fallback = None
    sampled_frames = 0
    frame_index = -1

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            frame_index += 1
            if frame_index % frame_interval:
                continue

            sampled_frames += 1
            det_out, annotated = run_detection_frame(frame, model)
            sharpness = _sharpness_score(frame)
            if fallback is None or sharpness > fallback[0]:
                fallback = (sharpness, frame.copy(), det_out, annotated, frame_index)

            decision = gate.observe(det_out["detections"])
            if decision.should_dispatch:
                candidate_window.append((sharpness, frame.copy(), det_out, annotated, frame_index))
                selected = max(candidate_window, key=lambda item: item[0])
                return {
                    "confirmed": True,
                    "frame": selected[1],
                    "detection": selected[2],
                    "annotated": selected[3],
                    "frame_index": selected[4],
                    "sampled_frames": sampled_frames,
                    "source_fps": source_fps,
                    "sample_fps": sample_fps,
                    "confirmation_frames": confirmation_frames,
                    "selection_reason": decision.reason,
                }

            if decision.reason == "candidate_waiting_for_confirmation":
                candidate_window.append((sharpness, frame.copy(), det_out, annotated, frame_index))
            else:
                candidate_window.clear()
    finally:
        capture.release()

    if fallback is None:
        raise ValueError("Video contains no decodable frames")
    return {
        "confirmed": False,
        "frame": fallback[1],
        "detection": fallback[2],
        "annotated": fallback[3],
        "frame_index": fallback[4],
        "sampled_frames": sampled_frames,
        "source_fps": source_fps,
        "sample_fps": sample_fps,
        "confirmation_frames": confirmation_frames,
        "selection_reason": "no_consecutive_vlm_candidate",
    }
