"""LLM Safety Report Generator - Sprint 2 Structured Outputs.

Receives the VLM scene analysis and produces a structured safety inspection
report: violation classification, severity scoring, prioritized actions, and
SOP citations. Uses Gemini Structured Outputs with a Pydantic response_schema.

NOTE: citations are currently produced from the model's general knowledge of
OSHA references. The production pipeline replaces this with RAG-retrieved
clauses (Sprint 2 follow-up) - the schema is already defined to accept them.
"""
import os
import time
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

from google import genai
from google.genai import types as gtypes
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

_API_KEYS = [k for k in [os.getenv("GEMINI_API_KEY"), os.getenv("GEMINI_API_KEY2")]
             if k and not k.startswith("your_")]
if not _API_KEYS:
    raise RuntimeError("GEMINI_API_KEY not set in .env")

DEFAULT_LLM_MODEL = "gemini-2.5-flash"  # 2.5-pro requires paid tier; flash supports structured outputs on free tier

SYSTEM_INSTRUCTION = (
    "당신은 인증받은 산업안전 검사관으로서 검사 보고서를 작성합니다. "
    "비전-언어 모델(VLM)이 제공한 장면 분석을 입력받아 공식 안전 검사 보고서로 변환합니다.\n\n"
    "규칙:\n"
    "1. 각 문제를 violation_type으로 분류: missing_ppe, danger_zone_access, "
    "abnormal_behavior, equipment_misuse, 또는 none.\n"
    "2. 부상 위험도와 규정 가중치에 따라 위반별 심각도 HIGH/MEDIUM/LOW 부여.\n"
    "3. 위반에 연결된 구체적이고 우선순위가 부여된 recommended_actions 제시.\n"
    "4. 인용(citations)은 반드시 제공된 '관련 규정 조항(RAG 검색 결과)'에서만 추출. "
    "검색 컨텍스트에 없는 조항·조문번호·출처는 절대 인용하지 마세요(환각 방지). "
    "관련 조항이 없으면 citations를 비워두세요. 인용은 한국 법령(산업안전보건법·산업안전보건기준에 관한 규칙·KOSHA 가이드)을 기준.\n"
    "5. overall_severity는 위반 중 최악 값(준수 시 NONE).\n"
    "6. 제공된 장면 분석에 근거해 사실 기반으로 작성. 위반을 지어내지 마세요.\n"
    "7. 모든 텍스트 필드(설명·조치·인용 quote·summary)는 한국어로 작성."
)


def _build_llm_prompt(prompt_variant: str, vlm_analysis_json: str, rag_context: str = "") -> str:
    # RAG 검색 컨텍스트 블록 구성 (인용은 이 컨텍스트에서만 허용 → 환각 방지)
    if rag_context and rag_context.strip() and not rag_context.strip().startswith("(검색된 관련 조항 없음)"):
        ctx_block = (
            "\n\n[관련 규정 조항 (RAG 검색 결과 - 인용은 이 컨텍스트에서만)]\n"
            + rag_context + "\n"
            "위 검색된 조항 중 위반과 직접 관련된 것만 citations에 인용하세요. "
            "이 컨텍스트에 없는 조항·조문번호·출처는 절대 인용하지 마세요.\n"
        )
    else:
        ctx_block = "\n\n[관련 규정 조항] 검색된 관련 조항이 없습니다. citations를 비워두세요.\n"

    if prompt_variant == "default":
        return (
            "다음 VLM 장면 분석을 구조화된 안전 검사 보고서로 변환하세요.\n\n"
            "VLM 장면 분석(JSON):\n" + vlm_analysis_json + ctx_block + "\n"
            "위반, 심각도, 권고 조치, 인용을 생성하세요."
        )
    if prompt_variant == "sop_grounded":
        return (
            "한국 안전 규정에 근거한 안전 검사 보고서를 작성하세요.\n"
            "각 위반에 대해 가장 관련성 높은 규정 조항을 식별하고 인용(quote)하세요.\n\n"
            "VLM 장면 분석(JSON):\n" + vlm_analysis_json + ctx_block + "\n"
            "인용은 반드시 위 [관련 규정 조항] 컨텍스트에서 추출하고, "
            "탐지된 위반과 직접 관련된 조항만 인용하세요."
        )
    if prompt_variant == "severity_first":
        return (
            "먼저 전체 장면의 심각도를 결정한 뒤, 위반과 조치를 나열하세요.\n\n"
            "VLM 장면 분석(JSON):\n" + vlm_analysis_json + ctx_block + "\n"
            "추론 순서:\n"
            "1. overall_severity 결정(즉각적 위험이나 위험 근처 핵심 PPE 누락 시 HIGH).\n"
            "2. 각 위반을 자체 심각도와 함께 나열.\n"
            "3. 우선순위가 부여된 조치 제시(즉각 조치 우선).\n"
            "4. 직접 관련된 규정 조항 인용(컨텍스트에서만)."
        )
    raise ValueError(f"Unknown prompt_variant: {prompt_variant}")


def _generate_with_fallback(model, contents, config, client=None):
    """generate_content with API key rotation on 429 RESOURCE_EXHAUSTED.
    client가 제공되면 그대로 사용; None이면 _API_KEYS를 순회하며 429 시 다음 키로 전환."""
    if client is not None:
        return client.models.generate_content(model=model, contents=contents, config=config)
    last_err = None
    for key in _API_KEYS:
        try:
            c = genai.Client(api_key=key)
            return c.models.generate_content(model=model, contents=contents, config=config)
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e) or "503" in str(e) or "UNAVAILABLE" in str(e):
                last_err = e
                print("  [API 키 폴백] 일시적 오류(429/503), 다음 키로 전환...")
                continue
            raise
    if last_err:
        raise last_err


def generate_report(
    vlm_analysis,
    model: str = DEFAULT_LLM_MODEL,
    prompt_variant: str = "default",
    temperature: float = 0.2,
    client: Optional[genai.Client] = None,
    retrieved_clauses: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """VLM 장면 분석으로부터 구조화된 안전 검사 보고서 생성.

    vlm_analysis: VLMSceneAnalysis pydantic 인스턴스(또는 dict).
    retrieved_clauses: RAG 검색 결과(rag.retriever.retrieve_for_violations 출력).
        제공되면 각 조항이 LLM 프롬프트 컨텍스트로 주입되어 인용 근거로 사용됨.
        None이면 RAG 컨텍스트 없이 실행(이전 동작 호환).
    반환 dict: parsed(SafetyReport), latency_ms, prompt_tokens,
    output_tokens, prompt_variant, model, raw_text, retrieved_count.
    """
    from llm.schema import SafetyReport
    from rag.retriever import format_context

    # Accept either a pydantic instance or a dict.
    if hasattr(vlm_analysis, "model_dump"):
        vlm_json = vlm_analysis.model_dump_json(indent=2)
    elif isinstance(vlm_analysis, dict):
        vlm_json = json.dumps(vlm_analysis, indent=2, ensure_ascii=False)
    else:
        vlm_json = str(vlm_analysis)

    # RAG 검색 컨텍스트 구성 (인용은 이 컨텍스트에서만 허용)
    rag_context = format_context(retrieved_clauses) if retrieved_clauses else ""

    user_text = _build_llm_prompt(prompt_variant, vlm_json, rag_context=rag_context)

    config = gtypes.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=SafetyReport,
        temperature=temperature,
    )

    t0 = time.time()
    response = _generate_with_fallback(model, user_text, config, client)
    latency_ms = (time.time() - t0) * 1000

    parsed = response.parsed
    usage = response.usage_metadata
    prompt_tokens = getattr(usage, "prompt_token_count", None) or 0
    output_tokens = getattr(usage, "candidates_token_count", None) or 0

    if parsed is None:
        raise ValueError("LLM returned no parsed structured output")

    return {
        "parsed": parsed,
        "latency_ms": round(latency_ms, 1),
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "prompt_variant": prompt_variant,
        "model": model,
        "raw_text": response.text,
        "retrieved_count": len(retrieved_clauses) if retrieved_clauses else 0,
    }


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(PROJECT_ROOT))
    from vlm.analyzer import analyze_scene
    from detection.detector import run_detection
    from rag.retriever import retrieve_for_violations
    img = sys.argv[1] if len(sys.argv) > 1 else "datasets/construction-ppe/images/test/image1.jpeg"
    det_out, _ = run_detection(img)
    vlm_res = analyze_scene(img, det_out["detections"])
    print("=== VLM done, running LLM ===")
    # VLM 분석에서 위반 설명 추출 → RAG 검색
    violation_texts = []
    parsed_vlm = vlm_res["parsed"]
    for w in parsed_vlm.workers:
        if getattr(w.helmet, "value", None) == "missing":
            violation_texts.append(f"{w.worker_id} 헬멧(안전모) 미착용")
        if getattr(w.vest, "value", None) == "missing":
            violation_texts.append(f"{w.worker_id} 안전조끼 미착용")
    violation_texts.extend([str(d) for d in parsed_vlm.immediate_dangers if d])
    clauses = retrieve_for_violations(violation_texts) if violation_texts else []
    print(f"=== RAG retrieved {len(clauses)} clauses ===")
    for c in clauses:
        print(f"  - {c['source']} [{c['article']}] {c['title']} (score={c['score']})")
    llm_res = generate_report(vlm_res["parsed"], retrieved_clauses=clauses)
    print(json.dumps(llm_res["parsed"].model_dump(), indent=2, ensure_ascii=False))
    print(f"\nllm latency={llm_res['latency_ms']}ms tokens={llm_res['prompt_tokens']}+{llm_res['output_tokens']} retrieved={llm_res['retrieved_count']}")

