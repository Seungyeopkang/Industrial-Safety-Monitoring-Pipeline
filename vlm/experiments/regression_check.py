"""Live VLM regression check for baseline, lighting, and occlusion cases."""
import json
from pathlib import Path

import cv2

from detection.detector import load_model, run_detection_frame
from detection.experiments.robustness_evaluate import apply_condition, load_labels, DATASETS
from vlm.analyzer import analyze_scene


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "outputs" / "vlm_regression"
CONDITIONS = ["baseline", "low_light", "glare", "occlusion_ppe_50", "occlusion_person_50"]


def run_live_regression():
    dataset = DATASETS["construction_ppe"]
    image_path = sorted(dataset["images"].glob("*"))[0]
    image = cv2.imread(str(image_path))
    labels = load_labels(dataset["labels"] / f"{image_path.stem}.txt", image.shape[1], image.shape[0], dataset["label_map"])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    model = load_model()
    results = []

    for condition in CONDITIONS:
        transformed = apply_condition(image, labels, condition, f"vlm-regression/{image_path.name}")
        case_path = OUTPUT_DIR / f"{condition}.jpg"
        cv2.imwrite(str(case_path), transformed)
        detection, _ = run_detection_frame(transformed, model)
        response = analyze_scene(str(case_path), detection["detections"], prompt_variant="role_constraints", temperature=0.0)
        parsed = response["parsed"]
        person_count = sum(item["class_name"] == "Person" for item in detection["detections"])
        grounded_dangers = all(danger.evidence.strip() and danger.danger_type.value != "unknown" for danger in parsed.immediate_dangers)
        results.append({
            "condition": condition,
            "parse_ok": True,
            "detected_persons": person_count,
            "workers": len(parsed.workers),
            "worker_count_matches": len(parsed.workers) == person_count,
            "grounded_dangers": grounded_dangers,
            "danger_records": [
                {
                    "danger_type": danger.danger_type.value,
                    "worker_ids": danger.worker_ids,
                    "description": danger.description,
                    "evidence": danger.evidence,
                    "confidence": danger.confidence,
                }
                for danger in parsed.immediate_dangers
            ],
            "unknown_ppe_fields": sum(
                status.value == "unknown"
                for worker in parsed.workers
                for status in (worker.helmet, worker.vest, worker.mask, worker.gloves)
            ),
            "analysis_limitations": parsed.analysis_limitations,
            "overall_description": parsed.overall_description,
            "latency_ms": response["latency_ms"],
        })

    (OUTPUT_DIR / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return results


if __name__ == "__main__":
    print(json.dumps(run_live_regression(), ensure_ascii=False, indent=2))
