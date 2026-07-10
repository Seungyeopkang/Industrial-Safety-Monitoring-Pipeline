"""Compare legacy free-text queries with the canonical RAG query contract."""
import json
from pathlib import Path

from rag.danger_contract import eligible_danger_records
from rag.query_builder import build_canonical_queries
from rag.retriever import retrieve, retrieve_for_query_records


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "rag_evaluation"
THRESHOLDS = (0.45, 0.50, 0.55)

CASES = [
    {
        "name": "missing_helmet_and_fall_risk",
        "workers": [{"worker_id": "Worker 1", "helmet": "missing", "vest": "worn", "mask": "unknown", "gloves": "worn"}],
        "dangers": [{"danger_type": "fall_risk", "worker_ids": ["Worker 1"], "description": "높은 구조물 위에서 작업", "evidence": "작업자가 패널 구조물 위에 있음", "confidence": 0.8}],
        "legacy_queries": ["Worker 1 안전모 미착용 높은 구조물에서 작업 중 추락 위험"],
    },
    {
        "name": "danger_zone_access",
        "workers": [],
        "dangers": [{"danger_type": "danger_zone_access", "worker_ids": ["Worker 2"], "description": "위험구역 출입", "evidence": "출입 제한 표지 인근", "confidence": 0.8}],
        "legacy_queries": ["Worker 2 위험구역 인접 출입 위험"],
    },
    {
        "name": "unknown_danger_must_not_query",
        "workers": [{"worker_id": "Worker 3", "helmet": "unknown", "vest": "unknown", "mask": "unknown", "gloves": "unknown"}],
        "dangers": [{"danger_type": "unknown", "worker_ids": ["Worker 3"], "description": "가림으로 판단 불가", "evidence": "심한 가림", "confidence": 0.7}],
        "legacy_queries": ["가림으로 판단 불가한 위험"],
    },
]


def _summary(results):
    return [{
        "article": item["article"], "title": item["title"], "score": item["score"],
        "query": item.get("query"), "query_origin": item.get("query_origin"),
    } for item in results]


def run_evaluation():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report = []
    for case in CASES:
        dangers = eligible_danger_records(case["dangers"])
        canonical = build_canonical_queries(case["workers"], dangers)
        threshold_results = {}
        for threshold in THRESHOLDS:
            legacy = []
            for query in case["legacy_queries"]:
                legacy.extend(retrieve(query, top_k=4, min_score=threshold))
            canonical_result = retrieve_for_query_records(canonical, min_score=threshold)
            threshold_results[str(threshold)] = {
                "legacy_result_count": len(legacy),
                "legacy_top": _summary(legacy[:3]),
                "canonical_result_count": len(canonical_result["clauses"]),
                "canonical_top": _summary(canonical_result["clauses"][:3]),
                "canonical_query_traces": canonical_result["query_traces"],
            }
        report.append({"case": case["name"], "canonical_queries": canonical, "thresholds": threshold_results})
    path = OUTPUT_DIR / "retrieval_quality.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report, path


if __name__ == "__main__":
    rows, output_path = run_evaluation()
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    print(f"saved: {output_path}")
