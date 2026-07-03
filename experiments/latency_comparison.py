"""Pipeline Latency Comparison: YOLO-only vs YOLO+VLM+LLM full pipeline.

Resumable across multiple invocations (each stage saved separately) to stay
within the 30s command timeout and per-minute API quota.
Stages: yolo -> vlm -> llm -> summary
"""
import os, sys, time, json, statistics
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

OUT = PROJECT_ROOT / "outputs" / "results" / "pipeline_latency_comparison.json"
IMG = "datasets/construction-ppe/images/test/image1.jpeg"


def load():
    if OUT.exists():
        return json.loads(OUT.read_text(encoding="utf-8"))
    return {"image": IMG, "runs": []}


def save(d):
    OUT.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


stage = sys.argv[1] if len(sys.argv) > 1 else "yolo"
data = load()

if stage == "yolo":
    from detection.detector import run_detection
    t0 = time.time()
    det_out, _ = run_detection(IMG)
    yolo_ms = (time.time() - t0) * 1000
    run = {"run": len(data["runs"]) + 1, "yolo_ms": round(yolo_ms, 1),
           "n_detections": len(det_out["detections"]),
           "n_triggered": sum(1 for d in det_out["detections"] if d.get("vlm_trigger")),
           "_detections": det_out["detections"]}
    data["runs"].append(run)
    save(data)
    print("YOLO: " + str(round(yolo_ms)) + "ms, " + str(len(det_out["detections"])) + " dets, " + str(run["n_triggered"]) + " triggered")

elif stage == "vlm":
    from google import genai
    from vlm.analyzer import analyze_scene
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    run = data["runs"][-1]
    t0 = time.time()
    vlm_res = analyze_scene(IMG, run["_detections"], prompt_variant="role_constraints", client=client)
    vlm_ms = (time.time() - t0) * 1000
    run["vlm_ms"] = round(vlm_ms, 1)
    run["vlm_tokens"] = str(vlm_res["prompt_tokens"]) + "+" + str(vlm_res["output_tokens"])
    run["_vlm_parsed"] = vlm_res["parsed"].model_dump()
    save(data)
    print("VLM: " + str(round(vlm_ms)) + "ms, tokens " + run["vlm_tokens"])

elif stage == "llm":
    from google import genai
    from vlm.schema import VLMSceneAnalysis
    from llm.reporter import generate_report
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    run = data["runs"][-1]
    vobj = VLMSceneAnalysis.model_validate(run["_vlm_parsed"])
    t0 = time.time()
    llm_res = generate_report(vobj, prompt_variant="default", client=client)
    llm_ms = (time.time() - t0) * 1000
    run["llm_ms"] = round(llm_ms, 1)
    run["llm_tokens"] = str(llm_res["prompt_tokens"]) + "+" + str(llm_res["output_tokens"])
    run["n_violations"] = len(llm_res["parsed"].violations)
    run["n_citations"] = len(llm_res["parsed"].citations)
    run["full_pipeline_ms"] = round(run["yolo_ms"] + run["vlm_ms"] + run["llm_ms"], 1)
    run["vlm_llm_overhead_ms"] = round(run["vlm_ms"] + run["llm_ms"], 1)
    run["overhead_ratio"] = round((run["vlm_ms"] + run["llm_ms"]) / run["full_pipeline_ms"], 3)
    del run["_detections"]
    del run["_vlm_parsed"]
    save(data)
    print("LLM: " + str(round(llm_ms)) + "ms, full=" + str(run["full_pipeline_ms"]) + "ms, overhead=" + str(round(run["overhead_ratio"]*100)) + "%")

elif stage == "summary":
    def avg(key):
        vals = [r[key] for r in data["runs"] if key in r]
        return round(statistics.mean(vals), 1) if vals else 0
    full = avg("full_pipeline_ms")
    data["averages"] = {
        "yolo_ms": avg("yolo_ms"), "vlm_ms": avg("vlm_ms"), "llm_ms": avg("llm_ms"),
        "full_pipeline_ms": full, "vlm_llm_overhead_ms": avg("vlm_llm_overhead_ms"),
        "overhead_ratio": round(avg("overhead_ratio"), 3),
        "yolo_share": round(avg("yolo_ms") / full, 3) if full else 0,
    }
    save(data)
    a = data["averages"]
    print("=== AVERAGES ===")
    print("YOLO only:              " + str(a["yolo_ms"]) + "ms")
    print("VLM (role_constraints): " + str(a["vlm_ms"]) + "ms")
    print("LLM (default):          " + str(a["llm_ms"]) + "ms")
    print("Full pipeline:          " + str(a["full_pipeline_ms"]) + "ms")
    print("VLM+LLM overhead:       " + str(a["vlm_llm_overhead_ms"]) + "ms (" + str(round(a["overhead_ratio"]*100)) + "% of full)")
    print("YOLO share:             " + str(round(a["yolo_share"]*100)) + "% of full pipeline")
