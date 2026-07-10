"""Post Sprint 5 VLM contract and prompt revalidation results."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from notion.notion_logger import create_dev_log


TITLE = "2026-07-10 | Sprint 5 - VLM Structured Output contract·가림/조도 프롬프트 재검증"

CONTENT = r"""## 목표와 범위
Sprint 5의 VLM 작업은 단순 schema 변경이 아니라, 운영 프롬프트, `immediate_dangers`의 RAG 경계, 그리고 앞선 합성 Occlusion·조도 평가를 실제 VLM 호출로 회귀 검증하는 작업으로 진행했다.

이번 결과는 **현재 테스트 이미지에 적용한 합성 조건 회귀**다. 실내/실외 일반화 성능을 주장하지 않으며, 새 현장 데이터 수집과 모델 재학습은 범위 밖으로 남긴다.

## 과거 운영 불일치와 결정

과거 prompt 실험 기록에는 `role_constraints`가 채택안으로 남아 있었지만, 실제 `api/main.py`는 variant를 생략하여 `default`를 호출하고 있었다. 또한 과거 `temperature=0.2` 실행에서는 동일 장면에서 `immediate_dangers`가 2건과 0건으로 달라지는 사례가 있었다.

다음과 같이 정리했다.

- 운영 기본 variant: `role_constraints`를 명시 호출
- production temperature: `0.0` 고정
- thinking budget: 지정하지 않아 Gemini 기본 dynamic 유지
- 다른 실험 variant도 공통 출력 계약을 반드시 포함하도록 `USER_OUTPUT_CONTRACT` 추가

## Structured Output 계약

`vlm/schema.py`의 변경:

- `VLMSceneAnalysis.workers`: 빈 목록 허용. Person 미탐지 시 worker를 추정 생성하지 않는다.
- `vlm_confidence`, danger `confidence`: 0.0~1.0 범위 검증.
- Worker: `visibility(clear|partial|occluded|unknown)`, `occlusion_level(none|partial|severe|unknown)` 추가.
- 장면: `analysis_limitations: List[str]` 추가. 저조도, glare, 가림, 탐지 메타데이터 충돌을 명시한다.
- `immediate_dangers`: 자유 문자열 목록에서 `danger_type`, `worker_ids`, `description`, `evidence`, `confidence`를 갖는 구조화 항목으로 변경.
- danger type: `missing_ppe`, `fall_risk`, `danger_zone_access`, `vehicle_strike_risk`, `electrical_risk`, `caught_between_risk`, `fire_risk`, `unknown`만 허용.

가림/충돌 시 PPE 상태는 `unknown`으로 둔다. `unknown`, partial/severe occlusion, 또는 worker-PPE 연결이 불명확한 전역 NO-PPE 탐지에는 `missing_ppe` danger를 만들지 않는다. PPE 미착용 danger는 이미지에서 보이는 구체적 위험 맥락도 있어야 하며, 단순한 시인성 저하나 잠재 노출만으로 생성하지 않도록 프롬프트를 보강했다.

## RAG 계약

기존에는 `str(d) for d in parsed_vlm.immediate_dangers`로 VLM 자유 텍스트를 RAG query 후보에 직접 섞었다. 이제 API는 그 경로를 제거했다.

`rag/danger_contract.py`는 구조화 danger 중 다음 조건을 만족하는 record만 후속 RAG 후보로 반환한다.

- Pydantic/dict 형태의 구조화 항목
- `danger_type != unknown`
- 비어 있지 않은 `evidence`
- `confidence >= 0.5`

이번 단계에서는 이 record를 자유 문자열 검색으로 즉시 변환하지 않는다. 후속 RAG 작업에서 `danger_type + worker/PPE + evidence`의 canonical query를 설계한다. 기존 Notion/UI/CLI 소비처에는 description 추출 호환 처리만 유지했다.

## 실제 VLM 회귀

`vlm/experiments/regression_check.py`로 Construction-PPE 대표 이미지 한 장에 아래 5조건을 적용하고, 각 조건마다 YOLO -> Gemini structured output을 실행했다.

- baseline
- low_light
- glare
- `occlusion_ppe_50`
- `occlusion_person_50`

최종 실행 결과:

| 조건 | Parse | Person/worker 일치 | unknown PPE 필드 | 구조화 danger |
| --- | --- | --- | ---: | --- |
| baseline | 성공 | 1/1 | 2 | 0 |
| low_light | 성공 | 1/1 | 2 | fall_risk 1건 (패널 위 작업이라는 시각 근거) |
| glare | 성공 | 3/3 | 9 | 0 |
| PPE 가림 50% | 성공 | 2/2 | 4 | 0 |
| Person 가림 50% | 성공 | 1/1 | 2 | electrical/fall risk 각 1건 (패널 접촉/고소 구조물 시각 근거) |

모든 structured danger는 canonical type과 비어 있지 않은 evidence를 가졌다. 특히 glare와 PPE 가림 조건에서는 심하게 가려진 worker에 `missing_ppe` danger가 생성되지 않았고, 한계 사항 및 `unknown`으로 표현됐다.

## 회귀 중 발견·수정한 문제

첫 실행에서는 VLM이 이미지와 탐지 메타데이터가 다를 때 "탐지 오류"라고 단정하거나, 심한 가림 상태의 Worker 2/3에 전역 `NO-Safety Vest`를 연결했다. 또한 마스크 미착용만으로 일반적 호흡기 위험을 만들어냈다.

수정 후 프롬프트 계약은 다음을 강제한다.

1. 탐지 class/bbox는 detector fact로 다루고, 충돌을 "탐지 오류"로 단정하지 않는다.
2. 충돌은 `unknown` PPE와 `analysis_limitations`로 표현한다.
3. partial/severe occlusion, unknown PPE, worker association 부재에는 `missing_ppe` danger 금지.
4. `missing_ppe`는 구체적이고 보이는 위험 맥락이 있어야 한다.

최종 회귀에서 위 가림 관련 오탐 위험 항목은 제거됐다. 다만 VLM은 태양광 패널 접촉을 electrical risk로 해석할 수 있으므로, 향후 RAG/LLM 단계에서는 evidence를 포함한 canonical query와 위험 확정/검토 상태를 분리해야 한다.

## 자동 검증

`python -m unittest discover -s tests -p "test_*.py" -v`

- 총 12개 통과.
- no-detection 빈 worker/빈 danger, confidence 경계, partial/severe occlusion 및 `unknown` parsing, typed danger RAG 경계, 모든 prompt variant의 grounding/occlusion 규칙을 검증.
- `python -m py_compile` 및 `git diff --check` 통과.

실제 RAG end-to-end 모듈은 BAAI `bge-m3` Hugging Face adapter 조회가 현재 환경에서 권한/네트워크 오류(`WinError 10013`)로 실패했다. 이는 이번 VLM contract 테스트 실패가 아니라 외부 embedder 초기화 환경 이슈이며, RAG 통합 실행 완료로 표시하지 않는다.

## 후속 범위

- RAG: typed danger에서 canonical query 생성, similarity threshold/parent-child chunking/incremental indexing 검증.
- LLM report schema: Worker 4의 조끼/마스크를 별도 PPE 위반으로 명확히 표시하고, 동일 worker·동일 PPE·동일 근거만 dedupe.
- 실제 실내/실외, 현장 조도, 장기 스트리밍 데이터로 일반화 재검증.
"""


if __name__ == "__main__":
    create_dev_log(
        TITLE,
        CONTENT,
        sprint="Sprint 5",
        categories="VLM,Structured Output,Prompt Engineering,RAG,Occlusion,Robustness,Testing",
    )
