"""Prompt Optimization Experiment - Sprint 2.

Runs VLM and LLM across multiple prompt variants on sample images, records
latency, token usage, schema-compliance, and qualitative rubric scores.
ALL attempts (including failures) are logged for the DevLog.

Outputs:
  outputs/results/prompt_optimization_results.json  (structured results)
  outputs/results/_experiment_log.txt                (live progress log)
"""
import os
import sys
import time
import json
import traceback
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from google import genai
from vlm.analyzer import analyze_scene
from llm.reporter import generate_report
from detection.detector import run_detection

OUT_DIR = PROJECT_ROOT / "outputs" / "results"
OUT_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_JSON = OUT_DIR / "prompt_optimization_results.json"
LOG_FILE = OUT_DIR / "_experiment_log.txt"

TEST_IMAGES = [
    "datasets/construction-ppe/images/test/image1.jpeg",
    "datasets/construction-ppe/images/test/image1003.jpg",
]

VLM_VARIANTS = ["default", "role_stepwise", "fewshot", "constraints", "role_constraints", "role_constraints_fewshot", "safety_first"]
LLM_VARIANTS = ["default", "sop_grounded", "severity_first"]
CONSISTENCY_REPEATS = 2
RATE_LIMIT_SLEEP = 2  # seconds between calls to avoid 429
SOFT_DEADLINE = 28  # stop before run_commands 30s timeout, save and exit for resume


def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()


def _load_results():
    if RESULTS_JSON.exists():
        try:
            return json.loads(RESULTS_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"start": datetime.now().isoformat(), "vlm": [], "llm": [], "consistency": [], "failures": [], "done_tasks": []}


def _save_results(results):
    RESULTS_JSON.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")


def rubric_score_vlm(parsed) -> dict:
    """Qualitative rubric for VLM output (0-3 each)."""
    s = {"worker_coverage": 0, "ppe_specificity": 0, "context_richness": 0, "danger_awareness": 0}
    try:
        workers = parsed.workers
        s["worker_coverage"] = min(3, len(workers))
        ppe_filled = sum(
            1 for w in workers
            if w.helmet.value != "unknown" or w.vest.value != "unknown"
        )
        s["ppe_specificity"] = min(3, ppe_filled)
        ctx = parsed.scene_context
        s["context_richness"] = min(3, len(ctx.machinery_present) + len(ctx.environmental_hazards))
        s["danger_awareness"] = min(3, len(parsed.immediate_dangers))
    except Exception:
        pass
    s["total"] = sum(s.values())
    return s


def rubric_score_llm(parsed) -> dict:
    """Qualitative rubric for LLM report (0-3 each)."""
    s = {"violation_count": 0, "action_quality": 0, "citation_quality": 0, "severity_specificity": 0}
    try:
        s["violation_count"] = min(3, len(parsed.violations))
        s["action_quality"] = min(3, len(parsed.recommended_actions))
        s["citation_quality"] = min(3, len(parsed.citations))
        sev_set = {v.severity.value for v in parsed.violations if v.severity.value != "NONE"}
        s["severity_specificity"] = min(3, len(sev_set))
    except Exception:
        pass
    s["total"] = sum(s.values())
    return s


def run_experiment_resumable():
    """Soft-deadline resumable experiment - re-run to continue from where it stopped."""
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    results = _load_results()
    done = set(results.get("done_tasks", []))
    start_t = time.time()
    def time_left():
        return SOFT_DEADLINE - (time.time() - start_t)
    def save():
        results["done_tasks"] = sorted(done)
        _save_results(results)
    det_cache = results.get("det_cache", {})
    vlm_cache = {}
    from vlm.schema import VLMSceneAnalysis
    for v in results.get("vlm", []):
        if v.get("variant") == "default" and v.get("image") == TEST_IMAGES[0]:
            vlm_cache[TEST_IMAGES[0]] = VLMSceneAnalysis.model_validate(v["parsed"])
    log("resume done=%d vlm=%d llm=%d cons=%d fails=%d" % (len(done), len(results["vlm"]), len(results["llm"]), len(results["consistency"]), len(results["failures"])))
    for img in TEST_IMAGES:
        tid = "det:" + img
        if tid in done: continue
        if time_left() < 8: save(); log("pause-det"); return
        log("det " + Path(img).name); det_out, _ = run_detection(img); det_cache[img] = det_out["detections"]; results["det_cache"] = det_cache; done.add(tid); save()
    for variant in VLM_VARIANTS:
        tid = "vlm:" + variant + ":" + TEST_IMAGES[0]
        if tid in done: continue
        if time_left() < 22: save(); log("pause-" + tid); return
        img = TEST_IMAGES[0]; log("VLM " + variant); time.sleep(RATE_LIMIT_SLEEP)
        try:
            res = analyze_scene(img, det_cache[img], prompt_variant=variant, client=client)
            entry = {"stage": "vlm", "variant": variant, "image": img, "latency_ms": res["latency_ms"], "prompt_tokens": res["prompt_tokens"], "output_tokens": res["output_tokens"], "model": res["model"], "schema_ok": True, "rubric": rubric_score_vlm(res["parsed"]), "parsed": res["parsed"].model_dump()}
            results["vlm"].append(entry)
            if variant == "default": vlm_cache[img] = res["parsed"]
            done.add(tid); save(); log("  OK lat=" + str(res["latency_ms"]) + " rub=" + str(entry["rubric"]["total"]) + "/12")
        except Exception as e:
            results["failures"].append({"stage": "vlm", "variant": variant, "image": img, "error": str(e)[:300], "tb": traceback.format_exc()[:500]}); done.add(tid); save(); log("  FAIL " + str(e)[:120])
    if vlm_cache.get(TEST_IMAGES[0]):
        for variant in LLM_VARIANTS:
            tid = "llm:" + variant
            if tid in done: continue
            if time_left() < 12: save(); log("pause-" + tid); return
            log("LLM " + variant); time.sleep(RATE_LIMIT_SLEEP)
            try:
                res = generate_report(vlm_cache[TEST_IMAGES[0]], prompt_variant=variant, client=client)
                entry = {"stage": "llm", "variant": variant, "latency_ms": res["latency_ms"], "prompt_tokens": res["prompt_tokens"], "output_tokens": res["output_tokens"], "model": res["model"], "schema_ok": True, "rubric": rubric_score_llm(res["parsed"]), "parsed": res["parsed"].model_dump()}
                results["llm"].append(entry); done.add(tid); save(); log("  OK lat=" + str(res["latency_ms"]) + " rub=" + str(entry["rubric"]["total"]) + "/12 viol=" + str(len(entry["parsed"]["violations"])) + " cite=" + str(len(entry["parsed"]["citations"])))
            except Exception as e:
                results["failures"].append({"stage": "llm", "variant": variant, "error": str(e)[:300], "tb": traceback.format_exc()[:500]}); done.add(tid); save(); log("  FAIL " + str(e)[:120])
    for i in range(CONSISTENCY_REPEATS):
        tid = "cons:" + str(i+1)
        if tid in done: continue
        if time_left() < 20: save(); log("pause-" + tid); return
        log("cons " + str(i+1)); time.sleep(RATE_LIMIT_SLEEP)
        try:
            res = analyze_scene(TEST_IMAGES[0], det_cache[TEST_IMAGES[0]], prompt_variant="default", client=client)
            entry = {"run": i+1, "latency_ms": res["latency_ms"], "vlm_confidence": res["parsed"].vlm_confidence, "n_workers": len(res["parsed"].workers), "n_dangers": len(res["parsed"].immediate_dangers)}
            results["consistency"].append(entry); done.add(tid); save(); log("  OK conf=" + str(entry["vlm_confidence"]))
        except Exception as e:
            results["failures"].append({"stage": "consistency", "run": i+1, "error": str(e)[:300]}); done.add(tid); save(); log("  FAIL " + str(e)[:120])
    tid = "e2e_vlm:" + TEST_IMAGES[1]
    if tid not in done:
        if time_left() < 20: save(); log("pause-e2e_vlm"); return
        img2 = TEST_IMAGES[1]; log("E2E_VLM " + Path(img2).name); time.sleep(RATE_LIMIT_SLEEP)
        try:
            vres = analyze_scene(img2, det_cache[img2], prompt_variant="default", client=client)
            results["e2e_vlm_parsed"] = vres["parsed"].model_dump(); results["e2e_vlm_latency"] = vres["latency_ms"]
            done.add(tid); save(); log("  OK e2e_vlm conf=" + str(vres["parsed"].vlm_confidence))
        except Exception as e:
            results["failures"].append({"stage": "e2e_vlm", "error": str(e)[:300], "tb": traceback.format_exc()[:500]}); done.add(tid); save(); log("  FAIL " + str(e)[:120])
    tid2 = "e2e_llm"
    if tid2 not in done and results.get("e2e_vlm_parsed"):
        if time_left() < 12: save(); log("pause-e2e_llm"); return
        log("E2E_LLM"); time.sleep(RATE_LIMIT_SLEEP)
        try:
            from vlm.schema import VLMSceneAnalysis as _VA
            vobj = _VA.model_validate(results["e2e_vlm_parsed"])
            lres = generate_report(vobj, prompt_variant="default", client=client)
            results["e2e_image2"] = {"vlm": results["e2e_vlm_parsed"], "llm": lres["parsed"].model_dump(), "vlm_latency": results.get("e2e_vlm_latency"), "llm_latency": lres["latency_ms"]}
            done.add(tid2); save(); log("  OK e2e_llm viol=" + str(len(lres["parsed"].violations)) + " cite=" + str(len(lres["parsed"].citations)))
        except Exception as e:
            results["failures"].append({"stage": "e2e_llm", "error": str(e)[:300], "tb": traceback.format_exc()[:500]}); done.add(tid2); save(); log("  FAIL " + str(e)[:120])
    results["end"] = datetime.now().isoformat(); save()
    log("=== COMPLETE === vlm=" + str(len(results["vlm"])) + " llm=" + str(len(results["llm"])) + " cons=" + str(len(results["consistency"])) + " fails=" + str(len(results["failures"])))



def run_experiment():
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    results = {"start": datetime.now().isoformat(), "vlm": [], "llm": [], "consistency": [], "failures": []}
    log("=== EXPERIMENT START ===")

    vlm_cache = {}
    det_cache = {}
    for img in TEST_IMAGES:
        log(f"Running detection on {img}")
        det_out, _ = run_detection(img)
        det_cache[img] = det_out["detections"]

    for variant in VLM_VARIANTS:
        img = TEST_IMAGES[0]
        log(f"VLM variant={variant} image={Path(img).name}")
        time.sleep(RATE_LIMIT_SLEEP)
        try:
            res = analyze_scene(img, det_cache[img], prompt_variant=variant, client=client)
            entry = {
                "stage": "vlm", "variant": variant, "image": img,
                "latency_ms": res["latency_ms"], "prompt_tokens": res["prompt_tokens"],
                "output_tokens": res["output_tokens"], "model": res["model"],
                "schema_ok": True, "rubric": rubric_score_vlm(res["parsed"]),
                "parsed": res["parsed"].model_dump(),
            }
            results["vlm"].append(entry)
            if variant == "default":
                vlm_cache[img] = res["parsed"]
            log(f"  OK latency={res['latency_ms']}ms tokens={res['prompt_tokens']}+{res['output_tokens']} rubric={entry['rubric']['total']}/12")
        except Exception as e:
            results["failures"].append({"stage": "vlm", "variant": variant, "image": img, "error": str(e)[:300], "tb": traceback.format_exc()[:500]})
            log(f"  FAIL: {str(e)[:150]}")

    if vlm_cache.get(TEST_IMAGES[0]):
        for variant in LLM_VARIANTS:
            log(f"LLM variant={variant}")
            time.sleep(RATE_LIMIT_SLEEP)
            try:
                res = generate_report(vlm_cache[TEST_IMAGES[0]], prompt_variant=variant, client=client)
                entry = {
                    "stage": "llm", "variant": variant,
                    "latency_ms": res["latency_ms"], "prompt_tokens": res["prompt_tokens"],
                    "output_tokens": res["output_tokens"], "model": res["model"],
                    "schema_ok": True, "rubric": rubric_score_llm(res["parsed"]),
                    "parsed": res["parsed"].model_dump(),
                }
                results["llm"].append(entry)
                log(f"  OK latency={res['latency_ms']}ms rubric={entry['rubric']['total']}/12 violations={len(entry['parsed']['violations'])} citations={len(entry['parsed']['citations'])}")
            except Exception as e:
                results["failures"].append({"stage": "llm", "variant": variant, "error": str(e)[:300], "tb": traceback.format_exc()[:500]})
                log(f"  FAIL: {str(e)[:150]}")

    for i in range(CONSISTENCY_REPEATS):
        img = TEST_IMAGES[0]
        log(f"Consistency run {i+1}/{CONSISTENCY_REPEATS} VLM default")
        time.sleep(RATE_LIMIT_SLEEP)
        try:
            res = analyze_scene(img, det_cache[img], prompt_variant="default", client=client)
            entry = {"run": i+1, "latency_ms": res["latency_ms"], "vlm_confidence": res["parsed"].vlm_confidence,
                     "n_workers": len(res["parsed"].workers), "n_dangers": len(res["parsed"].immediate_dangers)}
            results["consistency"].append(entry)
            log(f"  OK conf={entry['vlm_confidence']} workers={entry['n_workers']} dangers={entry['n_dangers']}")
        except Exception as e:
            results["failures"].append({"stage": "consistency", "run": i+1, "error": str(e)[:300]})
            log(f"  FAIL: {str(e)[:150]}")

    img2 = TEST_IMAGES[1]
    log(f"E2E image2 {Path(img2).name} VLM default")
    time.sleep(RATE_LIMIT_SLEEP)
    try:
        vres = analyze_scene(img2, det_cache[img2], prompt_variant="default", client=client)
        log(f"  VLM OK conf={vres['parsed'].vlm_confidence}")
        time.sleep(RATE_LIMIT_SLEEP)
        lres = generate_report(vres["parsed"], prompt_variant="default", client=client)
        results["e2e_image2"] = {"vlm": vres["parsed"].model_dump(), "llm": lres["parsed"].model_dump(),
                                  "vlm_latency": vres["latency_ms"], "llm_latency": lres["latency_ms"]}
        log(f"  LLM OK violations={len(lres['parsed'].violations)}")
    except Exception as e:
        results["failures"].append({"stage": "e2e_image2", "error": str(e)[:300], "tb": traceback.format_exc()[:500]})
        log(f"  FAIL: {str(e)[:150]}")

    results["end"] = datetime.now().isoformat()
    RESULTS_JSON.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"=== EXPERIMENT END results saved to {RESULTS_JSON} ===")
    log(f"VLM runs: {len(results['vlm'])}, LLM runs: {len(results['llm'])}, consistency: {len(results['consistency'])}, failures: {len(results['failures'])}")


if __name__ == "__main__":
    run_experiment_resumable()
