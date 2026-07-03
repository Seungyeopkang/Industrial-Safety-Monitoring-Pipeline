"""VLM Trigger Threshold Experiment - Sprint 2.

Empirically determine the confidence threshold line for triggering VLM.
The base is YOLO; VLM only runs when detection confidence is ambiguous or
when violation classes (NO-Hardhat etc.) appear. This experiment sweeps
candidate thresholds across a sample of images and measures:
  - how many detections would trigger VLM (cost)
  - how many violation-class detections exist (safety-critical, must trigger)
  - the confidence distribution to pick a data-driven threshold line.

Safety-first principle: violation classes ALWAYS trigger VLM regardless of
confidence, because the no_helmet F1 was 0.08-0.22 (unreliable alone).
"""
import os
import sys
import json
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from detection.detector import determine_vlm_trigger
from ultralytics import YOLO

WEIGHTS = PROJECT_ROOT / "detection" / "weights" / "yolov8_hansung.pt"

OUT_DIR = PROJECT_ROOT / "outputs" / "results"
OUT_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_JSON = OUT_DIR / "trigger_threshold_experiment.json"
LOG_FILE = OUT_DIR / "_trigger_log.txt"

# Diverse sample: 30 test images to get a confidence distribution
import glob
TEST_DIR = PROJECT_ROOT / "datasets" / "construction-ppe" / "images" / "test"
SAMPLE_IMAGES = sorted(glob.glob(str(TEST_DIR / "*.jp*")))[:10]

# Candidate threshold lines to evaluate
CANDIDATE_LINES = [
    (0.75, 0.30),  # current
    (0.70, 0.25),
    (0.65, 0.25),
    (0.60, 0.30),
    (0.80, 0.35),
]

VIOLATION_CLASSES = {"NO-Hardhat", "NO-Safety Vest", "NO-Mask"}


def log(msg):
    print(msg, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n"); f.flush()


def run_threshold_experiment():
    log("=== TRIGGER THRESHOLD EXPERIMENT START ===")
    log("Loading YOLO model once...")
    model = YOLO(str(WEIGHTS))
    log("Model loaded. Running batch inference on %d images..." % len(SAMPLE_IMAGES))
    all_detections = []
    batch_results = model(SAMPLE_IMAGES, conf=0.25, verbose=False)
    for r in batch_results:
        img_name = Path(r.path).name
        for box in r.boxes:
            cls_id = int(box.cls[0])
            cls_name = model.names[cls_id]
            conf = float(box.conf[0])
            bbox = box.xyxy[0].tolist()
            all_detections.append({"class_name": cls_name, "confidence": conf, "bbox": bbox, "image": img_name})
    log(f"Batch done. Total detections: {len(all_detections)}")

    log(f"\nTotal detections across {len(SAMPLE_IMAGES)} images: {len(all_detections)}")
    class_counts = Counter(d["class_name"] for d in all_detections)
    log("Class distribution: " + str(dict(class_counts)))

    confs = [d["confidence"] for d in all_detections]
    if confs:
        import statistics
        log(f"Confidence stats: min={min(confs):.3f} max={max(confs):.3f} "
            f"mean={statistics.mean(confs):.3f} median={statistics.median(confs):.3f}")

    # Evaluate each candidate threshold line
    results = {"total_detections": len(all_detections), "class_distribution": dict(class_counts),
               "n_images": len(SAMPLE_IMAGES), "confidence_stats": {}, "lines": []}
    if confs:
        import statistics
        results["confidence_stats"] = {"min": min(confs), "max": max(confs),
                                        "mean": statistics.mean(confs), "median": statistics.median(confs)}

    n_violation = sum(1 for d in all_detections if d["class_name"] in VIOLATION_CLASSES)
    log(f"Violation-class detections (always-trigger): {n_violation}")

    for high, low in CANDIDATE_LINES:
        # Simulate trigger with this line (violation classes always trigger)
        n_trigger = 0
        n_skip = 0
        n_noise = 0
        n_violation_triggered = 0
        for d in all_detections:
            cls = d["class_name"]
            conf = d["confidence"]
            if cls in VIOLATION_CLASSES:
                n_trigger += 1
                n_violation_triggered += 1
            elif conf >= high:
                n_skip += 1
            elif conf >= low:
                n_trigger += 1
            else:
                n_noise += 1
        trigger_rate = n_trigger / len(all_detections) if all_detections else 0
        line_result = {"high": high, "low": low, "trigger": n_trigger, "skip": n_skip,
                        "noise_dropped": n_noise, "violation_triggered": n_violation_triggered,
                        "trigger_rate": round(trigger_rate, 3)}
        results["lines"].append(line_result)
        log(f"Line (skip>={high}, trigger {low}-{high}, noise<{low}): "
            f"trigger={n_trigger} ({trigger_rate:.1%}) skip={n_skip} noise={n_noise} "
            f"violation_always={n_violation_triggered}")

    # Safety-first recommendation: pick the line that keeps ALL violations triggering
    # while minimizing non-essential triggers. Prefer the line with lowest trigger_rate
    # that still has violation_triggered == n_violation (guaranteed by construction).
    valid = [l for l in results["lines"] if l["violation_triggered"] == n_violation]
    if valid:
        best = min(valid, key=lambda x: x["trigger_rate"])
        results["recommended"] = best
        log(f"\nRECOMMENDED LINE: high={best['high']} low={best['low']} "
            f"trigger_rate={best['trigger_rate']:.1%} (safety-first: all violations trigger)")

    RESULTS_JSON.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"=== END results saved to {RESULTS_JSON} ===")


if __name__ == "__main__":
    run_threshold_experiment()
