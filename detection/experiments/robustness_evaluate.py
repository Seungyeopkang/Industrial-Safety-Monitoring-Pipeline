"""Reproducible synthetic occlusion and lighting robustness evaluation.

The existing datasets provide labels for helmet/no_helmet/vest, not for every
PPE violation class. Metrics therefore cover those labeled classes while VLM
trigger rate is reported for every detector class.
"""
import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "outputs" / "robustness"
WEIGHTS = ROOT / "detection" / "weights" / "yolov8_hansung.pt"
IOU_THRESHOLD = 0.5
CONF_THRESHOLD = 0.25
TARGET_CLASSES = {"Hardhat": "helmet", "NO-Hardhat": "no_helmet", "Safety Vest": "vest"}
VIOLATION_CLASSES = {"NO-Hardhat", "NO-Safety Vest", "NO-Mask"}

DATASETS = {
    "construction_ppe": {
        "images": ROOT / "datasets" / "construction-ppe" / "images" / "test",
        "labels": ROOT / "datasets" / "construction-ppe" / "labels" / "test",
        "label_map": {0: "helmet", 2: "vest", 7: "no_helmet"},
    },
    "hard_hat_workers": {
        "images": ROOT / "datasets" / "Hard Hat Workers.v10-raw_allclasses.yolov8" / "test" / "images",
        "labels": ROOT / "datasets" / "Hard Hat Workers.v10-raw_allclasses.yolov8" / "test" / "labels",
        "label_map": {0: "no_helmet", 1: "helmet"},
    },
}


def stable_rng(key: str) -> np.random.Generator:
    seed = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16)
    return np.random.default_rng(seed)


def iou(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection
    return intersection / union if union else 0.0


def load_labels(path: Path, width: int, height: int, label_map):
    labels = []
    if not path.exists():
        return labels
    for line in path.read_text(encoding="utf-8").splitlines():
        values = line.split()
        if len(values) < 5 or int(values[0]) not in label_map:
            continue
        cls, cx, cy, bw, bh = int(values[0]), *map(float, values[1:5])
        labels.append({
            "class": label_map[cls],
            "bbox": [(cx - bw / 2) * width, (cy - bh / 2) * height,
                     (cx + bw / 2) * width, (cy + bh / 2) * height],
        })
    return labels


def _mask_box(image, box, fraction, rng, color=(96, 96, 96)):
    x1, y1, x2, y2 = map(int, box)
    width, height = max(1, x2 - x1), max(1, y2 - y1)
    mask_w = max(1, int(width * fraction))
    left = int(rng.integers(x1, max(x1 + 1, x2 - mask_w + 1)))
    image[max(0, y1):min(image.shape[0], y2), max(0, left):min(image.shape[1], left + mask_w)] = color


def apply_condition(image, labels, condition, key):
    """Return a deterministic transformed copy without changing ground truth."""
    transformed = image.copy()
    rng = stable_rng(key + condition)
    height, width = image.shape[:2]
    if condition == "baseline":
        return transformed
    if condition == "low_light":
        return np.clip(transformed.astype(np.float32) * 0.35, 0, 255).astype(np.uint8)
    if condition == "glare":
        overlay = transformed.copy()
        center = (int(width * 0.72), int(height * 0.22))
        cv2.ellipse(overlay, center, (max(20, width // 4), max(20, height // 5)), 0, 0, 360, (255, 255, 255), -1)
        return cv2.addWeighted(overlay, 0.55, transformed, 0.45, 0)
    if condition == "high_contrast":
        return cv2.convertScaleAbs(transformed, alpha=1.8, beta=-55)
    if condition == "jpeg_artifact":
        ok, encoded = cv2.imencode(".jpg", transformed, [cv2.IMWRITE_JPEG_QUALITY, 18])
        return cv2.imdecode(encoded, cv2.IMREAD_COLOR) if ok else transformed

    _, kind, level_text = condition.split("_")
    fraction = {"25": 0.25, "50": 0.50, "75": 0.75}[level_text]
    if kind == "ppe" and labels:
        _mask_box(transformed, labels[int(rng.integers(len(labels)))] ["bbox"], fraction, rng)
    elif kind == "person" and labels:
        box = labels[int(rng.integers(len(labels)))] ["bbox"]
        x1, y1, x2, y2 = map(int, box)
        # A wider foreground rectangle approximates another worker passing in front.
        overlay_w = max(1, int((x2 - x1) * fraction))
        transformed[max(0, y1 - 8):min(height, y2 + 8), max(0, x1):min(width, x1 + overlay_w)] = (72, 72, 72)
    else:  # background: fixed-size occluder placed away from labeled PPE when possible.
        box_w, box_h = max(8, int(width * fraction * 0.22)), max(8, int(height * fraction * 0.22))
        x = int(rng.integers(0, max(1, width - box_w)))
        y = int(rng.integers(0, max(1, height - box_h)))
        transformed[y:y + box_h, x:x + box_w] = (96, 96, 96)
    return transformed


def predict(model, image):
    result = model(image, conf=CONF_THRESHOLD, verbose=False)[0]
    predictions = []
    trigger = False
    for box in result.boxes:
        name = model.names[int(box.cls[0])]
        confidence = float(box.conf[0])
        if name in VIOLATION_CLASSES or 0.30 <= confidence < 0.60:
            trigger = True
        if name in TARGET_CLASSES:
            predictions.append({"class": TARGET_CLASSES[name], "bbox": box.xyxy[0].tolist(), "confidence": confidence})
    return predictions, trigger


def score(labels, predictions):
    stats = {name: {"tp": 0, "fp": 0, "fn": 0} for name in sorted(set(TARGET_CLASSES.values()))}
    failures = []
    for class_name, values in stats.items():
        gts = [item for item in labels if item["class"] == class_name]
        preds = sorted([item for item in predictions if item["class"] == class_name], key=lambda item: item["confidence"], reverse=True)
        matched = set()
        for prediction in preds:
            best_iou, best_index = 0.0, None
            for index, gt in enumerate(gts):
                if index not in matched and iou(prediction["bbox"], gt["bbox"]) > best_iou:
                    best_iou, best_index = iou(prediction["bbox"], gt["bbox"]), index
            if best_iou >= IOU_THRESHOLD:
                stats[class_name]["tp"] += 1
                matched.add(best_index)
            else:
                stats[class_name]["fp"] += 1
                failures.append(("duplicate_detection" if gts else "false_positive", class_name))
        missing = len(gts) - len(matched)
        stats[class_name]["fn"] += missing
        failures.extend(("miss", class_name) for _ in range(missing))
    return stats, failures


def draw_failure(image, labels, predictions, title):
    output = image.copy()
    for item in labels:
        x1, y1, x2, y2 = map(int, item["bbox"])
        cv2.rectangle(output, (x1, y1), (x2, y2), (0, 255, 0), 2)
    for item in predictions:
        x1, y1, x2, y2 = map(int, item["bbox"])
        cv2.rectangle(output, (x1, y1), (x2, y2), (0, 0, 255), 1)
    cv2.putText(output, title, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    return output


def run(max_images=None, conditions=None):
    conditions = conditions or [
        "baseline", "low_light", "glare", "high_contrast", "jpeg_artifact",
        "occlusion_background_25", "occlusion_background_50", "occlusion_background_75",
        "occlusion_ppe_25", "occlusion_ppe_50", "occlusion_ppe_75",
        "occlusion_person_25", "occlusion_person_50", "occlusion_person_75",
    ]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    failure_dir = OUTPUT_DIR / "failure_samples"
    failure_dir.mkdir(exist_ok=True)
    model = YOLO(str(WEIGHTS))
    summary_rows, failure_rows = [], []
    saved_failures = defaultdict(int)

    for dataset_name, dataset in DATASETS.items():
        images = sorted(list(dataset["images"].glob("*.jpg")) + list(dataset["images"].glob("*.jpeg")) + list(dataset["images"].glob("*.png")))
        if max_images:
            images = images[:max_images]
        for condition in conditions:
            aggregate = {name: {"tp": 0, "fp": 0, "fn": 0} for name in sorted(set(TARGET_CLASSES.values()))}
            trigger_count = 0
            for image_path in images:
                image = cv2.imread(str(image_path))
                labels = load_labels(dataset["labels"] / f"{image_path.stem}.txt", image.shape[1], image.shape[0], dataset["label_map"])
                transformed = apply_condition(image, labels, condition, f"{dataset_name}/{image_path.name}")
                predictions, trigger = predict(model, transformed)
                trigger_count += int(trigger)
                stats, failures = score(labels, predictions)
                for cls, values in stats.items():
                    for key, value in values.items():
                        aggregate[cls][key] += value
                for kind, cls in failures:
                    failure_rows.append({"dataset": dataset_name, "condition": condition, "image": image_path.name, "failure_type": kind, "class": cls})
                    sample_key = (dataset_name, condition, kind)
                    if saved_failures[sample_key] < 2:
                        visual = draw_failure(transformed, labels, predictions, f"{condition} | {kind}")
                        cv2.imwrite(str(failure_dir / f"{dataset_name}_{condition}_{kind}_{saved_failures[sample_key]}.jpg"), visual)
                        saved_failures[sample_key] += 1
            for cls, values in aggregate.items():
                precision = values["tp"] / (values["tp"] + values["fp"]) if values["tp"] + values["fp"] else 0.0
                recall = values["tp"] / (values["tp"] + values["fn"]) if values["tp"] + values["fn"] else 0.0
                f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
                summary_rows.append({"dataset": dataset_name, "condition": condition, "class": cls, **values,
                                     "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
                                     "images": len(images), "vlm_trigger_rate": round(trigger_count / len(images), 4) if images else 0.0})

    with (OUTPUT_DIR / "metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=summary_rows[0].keys())
        writer.writeheader(); writer.writerows(summary_rows)
    with (OUTPUT_DIR / "failure_analysis.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["dataset", "condition", "image", "failure_type", "class"])
        writer.writeheader(); writer.writerows(failure_rows)
    (OUTPUT_DIR / "run_manifest.json").write_text(json.dumps({"conditions": conditions, "max_images": max_images,
        "limitations": "Synthetic transformations only; no indoor/outdoor labels or mask/no-vest ground truth."}, indent=2), encoding="utf-8")
    return summary_rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-images", type=int, help="Limit each dataset for a fast smoke run.")
    args = parser.parse_args()
    rows = run(max_images=args.max_images)
    print(f"Wrote {len(rows)} metric rows to {OUTPUT_DIR}")
