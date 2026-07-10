"""Run the selected production detector on every available labeled test image."""
import json
from pathlib import Path

from detection.experiments.evaluate import (
    CONSTRUCTION_PPE_MAP,
    HARD_HAT_WORKERS_MAP,
    MODEL_MAPPINGS,
    evaluate_on_dataset,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_NAME = "Hansung-Cho/yolov8-ppe-detection"
DATASETS = {
    "Construction-PPE": (PROJECT_ROOT / "datasets" / "construction-ppe", CONSTRUCTION_PPE_MAP),
    "Hard Hat Workers v10": (PROJECT_ROOT / "datasets" / "Hard Hat Workers.v10-raw_allclasses.yolov8", HARD_HAT_WORKERS_MAP),
}


def count_test_images(dataset_dir: Path) -> int:
    candidates = (dataset_dir / "images" / "test", dataset_dir / "test" / "images")
    image_dir = next(path for path in candidates if path.exists())
    return sum(1 for path in image_dir.iterdir() if path.suffix.lower() in {".jpg", ".jpeg", ".png"})


def main() -> None:
    model_config = MODEL_MAPPINGS[MODEL_NAME]
    results = {"model": MODEL_NAME, "confidence_threshold": 0.25, "iou_threshold": 0.5, "datasets": {}}
    for name, (dataset_dir, class_map) in DATASETS.items():
        metrics = evaluate_on_dataset(MODEL_NAME, model_config, str(dataset_dir), class_map)
        results["datasets"][name] = {"test_images": count_test_images(dataset_dir), "metrics": metrics}
    results["total_test_images"] = sum(item["test_images"] for item in results["datasets"].values())

    output_path = PROJECT_ROOT / "outputs" / "portfolio" / "final_dataset_evaluation.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
