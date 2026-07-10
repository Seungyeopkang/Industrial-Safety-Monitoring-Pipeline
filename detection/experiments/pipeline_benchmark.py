"""Reproducible latency comparison for YOLO-only and VLM-assisted pipeline runs.

Run with NOTION_AUTO_EXPORT=0 so the optional report export does not distort
the comparison.  The full path remains detection -> VLM -> RAG -> LLM; its
stage metrics are written by ``api.main._run_pipeline``.
"""
import argparse
import json
import os
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image")
    parser.add_argument("--warm-runs", type=int, default=3)
    parser.add_argument("--pipeline-runs", type=int, default=2)
    parser.add_argument("--output", default="outputs/results/final_pipeline_benchmark.json")
    args = parser.parse_args()

    os.environ["NOTION_AUTO_EXPORT"] = "0"
    from detection.detector import run_detection
    from api.main import RESULTS_DIR, _run_pipeline

    image = str(Path(args.image))
    yolo_runs = []
    yolo_output = None
    for index in range(args.warm_runs + 1):
        started = time.perf_counter()
        yolo_output, _ = run_detection(image)
        yolo_runs.append(round((time.perf_counter() - started) * 1000, 1))

    pipeline_runs = []
    pipeline = None
    for index in range(args.pipeline_runs):
        job_id = f"final_pipeline_benchmark_{index + 1}"
        _run_pipeline(job_id, image, "image")
        pipeline = json.loads((RESULTS_DIR / f"{job_id}.json").read_text(encoding="utf-8"))
        pipeline_runs.append(pipeline["metrics"])
    stages = pipeline_runs[-1].get("stages_ms", {})

    output = {
        "image": image,
        "quality_scope": {
            "yolo": "Detection labels support class-level precision/recall/F1 evaluation.",
            "vlm": "No scene-level ground truth is available, so this run reports contract/decision outputs rather than an invented VLM F1.",
        },
        "yolo_only": {
            "cold_ms": yolo_runs[0],
            "warm_runs_ms": yolo_runs[1:],
            "warm_average_ms": round(sum(yolo_runs[1:]) / max(1, len(yolo_runs) - 1), 1),
            "detections": len(yolo_output["detections"]),
            "vlm_trigger_candidates": sum(bool(item["vlm_trigger"]) for item in yolo_output["detections"]),
            "summary": yolo_output["summary"],
        },
        "vlm_assisted_pipeline": {
            "total_ms": pipeline["metrics"]["total_ms"],
            "stages_ms": stages,
            "runs": pipeline_runs,
            "workers": len((pipeline.get("vlm") or {}).get("parsed", {}).get("workers", [])),
            "immediate_dangers": len((pipeline.get("vlm") or {}).get("parsed", {}).get("immediate_dangers", [])),
            "violations": len((pipeline.get("report") or {}).get("violations", [])),
            "rag_clauses": (pipeline.get("rag") or {}).get("retrieved_count", 0),
        },
        "bottleneck": max(stages, key=stages.get) if stages else None,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
