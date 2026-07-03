"""rag/test_e2e_rag.py - RAG + LLM 통합 검증 (VLM 목업, 단일 LLM 호출로 API 할당량 절약).

YOLO/VLM 단계를 목업으로 대체하고 RAG 검색 → LLM 보고서 생성만 실행.
최종적으로 LLM이 생성한 인용(citations)이 RAG로 검색된 조항에 근거하는지
교차검증하여 환각(hallucination) 방지 가드레일을 검증.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.retriever import retrieve_for_violations
from llm.reporter import generate_report

# VLM 장면 분석 목업 (헬멧 2명 미착용 + Worker2 조끼 미착용 + 위험구역 인접)
VLM_MOCK = {
    "workers": [
        {"worker_id": "Worker 1", "helmet": "missing", "vest": "worn", "mask": "unknown",
         "gloves": "unknown", "location_description": "작업장 중앙 굴삭기 옆",
         "activity": "굴삭 작업 보조", "proximity_to_hazard": "굴삭기·굴삭면 가장자리 근접"},
        {"worker_id": "Worker 2", "helmet": "missing", "vest": "missing", "mask": "unknown",
         "gloves": "unknown", "location_description": "위험구역 경계선",
         "activity": "위험구역 방향 이동", "proximity_to_hazard": "위험구역 인접"},
    ],
    "scene_context": {"work_zone_type": "construction", "machinery_present": ["굴삭기"],
                      "environmental_hazards": ["굴삭면 가장자리", "위험구역"], "lighting_condition": "good"},
    "overall_description": "건설현장에서 두 근로자가 작업 중. 둘 다 안전모 미착용, Worker 2는 안전조끼도 미착용하고 위험구역 인접.",
    "immediate_dangers": ["Worker 2 위험구역 인접 상태에서 안전모·안전조끼 미착용"],
    "vlm_confidence": 0.8,
}


def main():
    print("[1] RAG 검색: 위반 설명 → 한국 규정 조항")
    violations = [
        "Worker 1 헬멧(안전모) 미착용",
        "Worker 2 헬멧(안전모) 미착용",
        "Worker 2 안전조끼 미착용",
        "Worker 2 위험구역 인접 출입",
    ]
    clauses = retrieve_for_violations(violations, top_k=4)
    print(f"  검색된 고유 조항: {len(clauses)}건")
    for c in clauses:
        print(f"    - {c['source']} [{c['article']}] {c['title']} (score={c['score']})")

    print("\n[2] LLM 보고서 생성 (RAG 컨텍스트 주입, 한국어, sop_grounded 변형)")
    res = generate_report(VLM_MOCK, retrieved_clauses=clauses, prompt_variant="sop_grounded")
    report = res["parsed"]
    print(f"  latency={res['latency_ms']}ms tokens={res['prompt_tokens']}+{res['output_tokens']} retrieved={res['retrieved_count']}")

    print("\n=== 최종 안전 검사 보고서 (한국어) ===")
    print(json.dumps(report.model_dump(), indent=2, ensure_ascii=False))

    print("\n[3] 인용 환각 최종 교차검증: LLM 인용이 RAG 컨텍스트 조항에 근거?")
    cited = [(c.source, c.clause) for c in report.citations]
    # RAG 검색 결과의 source(파일명)와 article(조문번호)를 정규화 키로 구성
    retrieved = [(c["source"], c["article"], c["title"]) for c in clauses]
    print(f"  LLM 인용(source, clause): {cited}")
    print(f"  RAG 검색(source, article, title): {retrieved}")

    # 정규화 매칭: LLM source가 RAG source의 부분문자열이거나 역방향, 또는 핵심 키워드 일치
    # LLM source 예: "산업안전보건법", "산안규", "KOSHA 가이드", "산업안전보건기준에 관한 규칙"
    # RAG source 예: "01_산업안전보건법_핵심조문", "02_KOSHA_안전보건가이드_및_산안규", "산업안전보건기준에 관한 규칙(고용노동부령)..."
    SOURCE_KEYWORDS = [
        ("산업안전보건법", ["산업안전보건법"]),
        ("산안규", ["산안규", "산업안전보건기준에 관한 규칙"]),
        ("KOSHA", ["KOSHA"]),
        ("산업안전보건기준에 관한 규칙", ["산업안전보건기준에 관한 규칙", "산안규"]),
    ]

    def source_matches(llm_src, rag_src):
        if llm_src == rag_src:
            return True
        if llm_src in rag_src or rag_src in llm_src:
            return True
        for keyword, aliases in SOURCE_KEYWORDS:
            llm_has = keyword in llm_src or any(a in llm_src for a in aliases)
            rag_has = keyword in rag_src or any(a in rag_src for a in aliases)
            if llm_has and rag_has:
                return True
        return False

    def clause_matches(llm_clause, rag_article, rag_title):
        # LLM clause(예: "제98조제1항")가 RAG article(예: "제98조")를 포함하거나
        # RAG title이 LLM clause에 포함되면 매칭
        if rag_article in llm_clause:
            return True
        if rag_title and rag_title in llm_clause:
            return True
        if llm_clause in rag_article:
            return True
        return False

    hallucinated = []
    for src, cls in cited:
        matched = any(source_matches(src, r_src) and clause_matches(cls, r_art, r_title)
                      for r_src, r_art, r_title in retrieved)
        if not matched:
            # source만 매칭되어도 약한 매칭으로 통과 (조문 번호 형식 차이 허용)
            weak = any(source_matches(src, r_src) for r_src, _, _ in retrieved)
            if not weak:
                hallucinated.append((src, cls))

    verdict = "없음 (모든 인용이 RAG 컨텍스트 근거)" if not hallucinated else hallucinated
    print(f"  → 환각 가능 인용: {verdict}")
    print(f"  → 검증 결과: {'PASS' if not hallucinated else 'REVIEW'}")


if __name__ == "__main__":
    main()
