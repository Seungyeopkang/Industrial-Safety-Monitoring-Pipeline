"""VLM Scene Analyzer - Sprint 2 Method 2.

Method 2: send the ORIGINAL image together with detection-model extracted
metadata (classes, bboxes, confidence) to the VLM. The detection pre-filter
supplies precise boxes while the VLM adds scene-level context, avoiding
small-object hallucinations by relying on the detector's pre-filter.

Uses Gemini 2.5 Pro (vision) with Structured Outputs (Pydantic response_schema).
"""
import os
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

from google import genai
from google.genai import types as gtypes
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

_API_KEYS = [k for k in [os.getenv("GEMINI_API_KEY"), os.getenv("GEMINI_API_KEY2")]
             if k and not k.startswith("your_")]
if not _API_KEYS:
    raise RuntimeError("GEMINI_API_KEY not set in .env")

DEFAULT_VLM_MODEL = "gemini-2.5-flash"  # 2.5-pro requires paid tier; flash supports vision + structured outputs on free tier
DEFAULT_PROMPT_VARIANT = "role_constraints"
DEFAULT_TEMPERATURE = 0.0

SYSTEM_INSTRUCTION = (
    "당신은 산업안전 비전 분석가입니다. 작업장 이미지와 함께 YOLO PPE 탐지기가 "
    "생성한 객체 탐지 메타데이터(클래스, 바운딩박스, 신뢰도)를 입력받습니다. "
    "당신의 임무는 장면 수준의 맥락 분석입니다.\n\n"
    "규칙:\n"
    "1. 탐지 메타데이터는 탐지된 객체와 위치의 근거로 사용. 박스를 부정하지 말되, "
    "탐지되지 않은 PPE를 부재로 단정하지 말고 가림·저조도·불명확 시 unknown으로 처리.\n"
    "2. PPE 상태는 오직 worn, missing, unknown만 사용. 가려지거나 불확실하면 추측보다 'unknown' 선호.\n"
    "3. 탐지된 각 인물을 별도 worker 항목으로 기술.\n"
    "4. 간결하고 사실적으로. 보이지 않는 기계나 위험을 지어내지 마세요.\n"
    "5. 이미지 명확도와 메타데이터 일치도에 따라 vlm_confidence를 정직하게 설정. "
    "저조도, glare, 부분/심한 가림, 메타데이터 불일치는 analysis_limitations에 기록.\n"
    "6. 모든 자유 텍스트 필드(location_description, activity, proximity_to_hazard, "
    "overall_description, immediate_dangers 등)는 한국어로 작성.\n"
    "7. immediate_dangers는 danger_type, worker_ids, description, evidence, confidence를 모두 채운 구조화 항목만 생성. "
    "이미지나 메타데이터 근거가 없는 분진, 기계, 낙하물, 위험은 만들지 말고, PPE 미착용은 구체적 위험 맥락이 있을 때만 즉각 위험으로 포함."
)

# A detector/image conflict is uncertainty, not permission to overwrite a
# detector result from visual intuition.  Keep the wording ASCII so it remains
# stable when this module is edited from Windows shells with differing codepages.
SYSTEM_INSTRUCTION += (
    "\n8. Treat detected classes and boxes as detector facts. If the image appears to conflict, "
    "do not call the detection wrong or override it; use unknown PPE status and record the conflict "
    "in analysis_limitations. Set every worker visibility and occlusion_level. "
    "Never create a missing_ppe danger for a worker with unknown PPE, partial/severe occlusion, or no direct worker-PPE association. "
    "A missing_ppe danger requires a visible, specific hazard context; generic visibility or potential exposure is insufficient."
)

# Kept in every user-prompt variant so an experiment cannot accidentally drop
# the schema and grounding rules that production relies on.
USER_OUTPUT_CONTRACT = (
    "\n\n출력 계약:\n"
    "- 가림, 저조도, glare, 또는 근거 부족으로 PPE를 확인할 수 없으면 missing으로 추측하지 말고 unknown을 사용. "
    "그 한계는 analysis_limitations에 기록.\n"
    "- immediate_dangers는 danger_type, worker_ids, description, 근거(evidence), confidence를 갖춘 구조화 항목만 생성. "
    "이미지/탐지 근거 없이 위험을 추측하거나 생성하지 말 것.\n"
    "- Person이 탐지되지 않으면 workers는 빈 목록으로 두고 근로자를 만들어 내지 말 것."
)
USER_OUTPUT_CONTRACT += (
    "\n- Treat detected classes and boxes as detector facts. If image evidence conflicts, do not say "
    "the detector is wrong or override it; use unknown and analysis_limitations instead. "
    "Set visibility and occlusion_level for every worker. "
    "Do not create missing_ppe danger for unknown PPE, partial/severe occlusion, or an unassociated global NO-PPE detection. "
    "Require visible, specific hazard context; generic visibility or potential exposure is not enough."
)


def _load_image_inline(image_path: str) -> gtypes.Part:
    """Load image as inline base64 part (suitable for single small/medium images)."""
    p = Path(image_path)
    ext = p.suffix.lower().lstrip(".")
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "webp": "image/webp", "gif": "image/gif"}.get(ext, "image/jpeg")
    data = p.read_bytes()
    return gtypes.Part.from_bytes(data=data, mime_type=mime)

"json to text"
def _format_detection_metadata(detections: List[Dict[str, Any]]) -> str:
    """Format detector output into a readable metadata block for the prompt."""
    if not detections:
        return "Detector metadata: (no objects detected)"
    lines = ["Detector metadata (YOLO, confidence >= 0.25):"]
    for i, d in enumerate(detections, 1):
        cls = d.get("class_name", "?")
        conf = d.get("confidence", 0)
        bbox = d.get("bbox", [])
        bbox_str = ""
        if len(bbox) == 4:
            bbox_str = f" bbox=[x1={bbox[0]:.0f},y1={bbox[1]:.0f},x2={bbox[2]:.0f},y2={bbox[3]:.0f}]"
        trig = d.get("vlm_trigger", None)
        trig_str = " (flagged for VLM review)" if trig else ""
        lines.append(f"  {i}. {cls} conf={conf:.2f}{bbox_str}{trig_str}")
    return "\n".join(lines)


def _build_user_prompt(prompt_variant: str, metadata_text: str) -> str:
    """선택된 최적화 변형에 대한 사용자 프롬프트(한국어 지시) 반환.
    탐지 메타데이터는 영어 클래스명(helmet/vest 등)을 그대로 포함."""
    if prompt_variant == "default":
        return (
            "이 산업 작업장 이미지를 안전 관점에서 분석하세요. "
            "YOLO 탐지기가 장면을 사전 필터링했으므로, 아래 메타데이터를 객체·위치의 정답으로 사용한 뒤 "
            "탐지기가 볼 수 없는 장면 맥락을 추가하세요.\n\n"
            + metadata_text + "\n\n"
            "각 근로자, 작업 구역, 즉각적 위험을 다루는 구조화된 장면 분석을 생성하세요."
            + USER_OUTPUT_CONTRACT
        )
    if prompt_variant == "role_stepwise":
        return (
            "작업: 산업안전 장면 분석.\n"
            "1단계: 탐지 메타데이터에서 모든 인물을 식별하고 PPE를 기술.\n"
            "2단계: 작업 구역, 기계, 환경 위험을 특성화.\n"
            "3단계: 각 근로자의 위험 근접성을 평가.\n"
            "4단계: 즉각적 위험을 나열.\n"
            "5단계: 전체 장면 설명과 신뢰도 제시.\n\n"
            "탐지 메타데이터(객체/위치의 정답):\n"
            + metadata_text + "\n\n"
            "이에 따라 이미지를 분석하세요."
            + USER_OUTPUT_CONTRACT
        )
    if prompt_variant == "fewshot":
        return (
            "탐지 메타데이터를 정답으로 사용하여 이 산업 작업장 이미지를 안전 관점에서 분석하세요.\n\n"
            "탐지 메타데이터:\n" + metadata_text + "\n\n"
            "예시 추론 스타일(복사하지 말고 이 이미지에 맞게 적용):\n"
            "- Worker 1: helmet worn (Hardhat conf 0.91), vest missing (NO-Safety Vest conf 0.31).\n"
            "- 장면: 야외 건설현장, 굴착기 존재, Worker 1이 굴착면 가장자리 근접.\n"
            "- 즉각적 위험: Worker 1이 보호 없는 가장자리 근처에서 조끼 없이 작업.\n\n"
            "이제 실제 이미지를 분석하여 구조화된 장면 분석을 생성하세요."
            + USER_OUTPUT_CONTRACT
        )
    if prompt_variant == "constraints":
        return (
            "이 산업 작업장 이미지를 안전 관점에서 분석하세요.\n"
            "제약:\n"
            "- 탐지 메타데이터를 정답으로 취급; 탐지기가 착용으로 찾은 PPE를 미착용으로 보고하지 말고 그 반대도 마찬가지.\n"
            "- 탐지되지 않은 PPE는 부재가 아니다. 이미지+메타데이터로 결정할 수 없거나 가려진 PPE는 'unknown' 사용.\n"
            "- 탐지된 Person마다 worker 항목 1개.\n"
            "- 이미지에 보이지 않는 위험은 추측 금지.\n\n"
            "탐지 메타데이터:\n" + metadata_text + "\n\n"
            "구조화된 장면 분석을 생성하세요."
            + USER_OUTPUT_CONTRACT
        )
    if prompt_variant == "role_constraints":
        return (
            "작업: 산업안전 장면 분석.\n"
            "1단계: 탐지 메타데이터에서 모든 인물을 식별하고 PPE를 기술.\n"
            "2단계: 작업 구역, 기계, 환경 위험을 특성화.\n"
            "3단계: 각 근로자의 위험 근접성을 평가.\n"
            "4단계: 즉각적 위험을 나열.\n"
            "5단계: 전체 장면 설명과 신뢰도 제시.\n\n"
            "제약:\n"
            "- 탐지 메타데이터는 탐지된 객체·위치의 근거. 탐지되지 않은 PPE는 부재가 아니며, 가려지거나 불명확하면 'unknown' 사용.\n"
            "- 탐지된 Person마다 worker 항목 1개.\n"
            "- 이미지에 보이지 않는 위험은 추측 금지. 저조도·glare·가림·메타데이터 불일치는 analysis_limitations에 기록.\n"
            "- immediate_dangers는 근거(evidence)가 있는 구조화 위험만 생성. PPE 미착용만으로 보이지 않는 분진·기계·낙하 위험을 만들지 말 것.\n\n"
            "탐지 메타데이터(정답):\n" + metadata_text + "\n\n"
            "이에 따라 이미지를 분석하세요."
            + USER_OUTPUT_CONTRACT
        )
    if prompt_variant == "role_constraints_fewshot":
        return (
            "작업: 산업안전 장면 분석.\n"
            "1-5단계: 인물/PPE 식별, 구역 특성화, 위험 근접성 평가, 위험 나열, 요약.\n\n"
            "제약:\n"
            "- 탐지 메타데이터는 객체/위치의 정답.\n"
            "- 결정 불가능한 PPE는 'unknown'. 탐지된 Person당 worker 1개. 추측 금지.\n\n"
            "예시 추론 스타일(이 이미지에 맞게 적용, 복사 금지):\n"
            "- Worker 1: helmet worn (Hardhat conf 0.91), vest missing (NO-Safety Vest conf 0.31).\n"
            "- 장면: 야외 건설현장, 굴착기 존재, Worker 1이 굴착면 가장자리 근접.\n"
            "- 즉각적 위험: Worker 1이 보호 없는 가장자리 근처에서 조끼 없이 작업.\n\n"
            "탐지 메타데이터:\n" + metadata_text + "\n\n"
            "실제 이미지를 분석하여 구조화된 장면 분석을 생성하세요."
            + USER_OUTPUT_CONTRACT
        )
    if prompt_variant == "safety_first":
        return (
            "안전 최우선 산업 작업장 장면 분석. 이것은 안전-중요 작업입니다: "
            "위험을 놓치면 부상이나 사망을 초래할 수 있습니다. 간결함보다 모든 위험 탐지를 우선하세요. "
            "위험에 대해 불확실할 때 보고하세요(거짓 양성은 허용, 거짓 음성은 불가).\n\n"
            "1단계: 탐지 메타데이터에서 모든 인물과 PPE를 식별.\n"
            "2단계: 작업 구역, 기계, 환경 위험을 특성화.\n"
            "3단계: 각 근로자의 위험 근접성을 평가 - 위험 범위 내의 모든 것에 플래그.\n"
            "4단계: 모든 즉각적 위험을 나열, 저확률 위험도 포함.\n"
            "5단계: 요약하고 신뢰도 제시.\n\n"
            "제약: 탐지 메타데이터는 객체의 정답; 불확실한 PPE는 'unknown'; "
            "탐지된 Person당 worker 1개.\n\n"
            "탐지 메타데이터:\n" + metadata_text + "\n\n"
            "안전을 최우선으로 이미지를 분석하세요."
            + USER_OUTPUT_CONTRACT
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


def analyze_scene(
    image_path: str,
    detections: List[Dict[str, Any]],
    model: str = DEFAULT_VLM_MODEL,
    prompt_variant: str = DEFAULT_PROMPT_VARIANT,
    temperature: float = DEFAULT_TEMPERATURE,
    thinking_budget: Optional[int] = None,
    client: Optional[genai.Client] = None,
) -> Dict[str, Any]:
    """Run VLM scene analysis (Method 2).

    Returns dict: parsed (VLMSceneAnalysis), latency_ms, prompt_tokens,
    output_tokens, prompt_variant, model, raw_text.
    Raises on schema parse failure (caller records as failed attempt).

    thinking_budget: None=dynamic(default), 0=disable thinking (faster, simple tasks),
        >0=cap thinking tokens (complex reasoning). Only for 2.5 series models.
    """
    from vlm.schema import VLMSceneAnalysis

    metadata_text = _format_detection_metadata(detections)
    user_text = _build_user_prompt(prompt_variant, metadata_text)

    # Per Gemini image best practice: place text prompt BEFORE the image.
    contents = [user_text, _load_image_inline(image_path)]

    config_kwargs = {
        "system_instruction": SYSTEM_INSTRUCTION,
        "response_mime_type": "application/json",
        "response_schema": VLMSceneAnalysis,
        "temperature": temperature,
    }
    if thinking_budget is not None:
        config_kwargs["thinking_config"] = gtypes.ThinkingConfig(
            thinking_budget=thinking_budget
        )
    config = gtypes.GenerateContentConfig(**config_kwargs)

    t0 = time.time()
    response = _generate_with_fallback(model, contents, config, client)
    latency_ms = (time.time() - t0) * 1000

    parsed = response.parsed
    usage = response.usage_metadata
    prompt_tokens = getattr(usage, "prompt_token_count", None) or 0
    output_tokens = getattr(usage, "candidates_token_count", None) or 0

    if parsed is None:
        raise ValueError("VLM returned no parsed structured output")

    return {
        "parsed": parsed,
        "latency_ms": round(latency_ms, 1),
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "prompt_variant": prompt_variant,
        "model": model,
        "raw_text": response.text,
    }


if __name__ == "__main__":
    import json
    import sys
    sys.path.insert(0, str(PROJECT_ROOT))
    from detection.detector import run_detection
    img = sys.argv[1] if len(sys.argv) > 1 else "datasets/construction-ppe/images/test/image1.jpeg"
    det_out, _ = run_detection(img)
    res = analyze_scene(img, det_out["detections"])
    print(json.dumps(res["parsed"].model_dump(), indent=2, ensure_ascii=False))
    print(f"\nlatency={res['latency_ms']}ms tokens={res['prompt_tokens']}+{res['output_tokens']}")
