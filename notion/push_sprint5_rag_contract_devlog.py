"""Post Sprint 5 canonical RAG query and quality-gate results."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from notion.notion_logger import create_dev_log


TITLE = "2026-07-10 | Sprint 5 - Canonical RAG Query·유사도/근거 Gate·E2E 인용 검증"

CONTENT = r"""## 목표
VLM의 자유로운 `immediate_dangers` 문장이 법령 검색어로 직접 들어가던 경로를 제거하고, detector/VLM structured output을 제한된 canonical query로 변환했다. 또한 Chroma가 top-k 결과를 무조건 반환하는 특성 때문에 관련 없는 법령이 LLM context에 들어가는 문제를 score/용어 gate로 차단했다.

## 시작점과 위험

기존 `retrieve(query, top_k=5)`는 cosine score를 계산했지만 임계값 없이 반환했다. 즉, DB에 무관한 문서만 있어도 상대적으로 가까운 top-k가 LLM에 주입될 수 있었다.

또한 VLM `immediate_dangers`는 이전에 자유 문자열이었으므로, 문체와 추측성 설명이 검색 품질을 흔들 수 있었다. VLM contract 개선 이후에는 typed danger가 생겼지만, `danger_contract`는 결과 JSON에 보관만 되고 실제 검색에는 아직 쓰이지 않았다.

## 구현

### 1. Canonical query builder
`rag/query_builder.py`를 추가했다.

- worker PPE 상태가 `missing`인 경우에만 PPE별 고정 검색어를 생성한다.
  - helmet -> `안전모 보호구 착용 기준`
  - vest -> `안전조끼 보호구 착용 기준`
  - mask/gloves도 동일한 보호구 유형 템플릿 사용
- eligible typed VLM danger만 danger_type 템플릿으로 변환한다.
  - fall_risk -> `고소 작업 추락 방지 조치`
  - danger_zone_access -> `위험구역 출입 금지 조치`
  - electrical/vehicle/caught-between/fire도 제한된 템플릿 보유
- `unknown`과 `missing_ppe` typed danger는 VLM description/evidence를 파싱해 PPE 종류를 추측하지 않는다. PPE 법령 검색은 worker의 구조화 PPE status를 사용한다.
- query마다 origin, kind, worker_ids, danger_type, evidence, confidence, required_terms를 trace metadata로 남긴다.

따라서 VLM의 자유 description은 보고서 설명용으로만 남고 RAG query가 되지 않는다.

### 2. Retrieval quality gate
`rag/retriever.py`를 보강했다.

- `DEFAULT_MIN_SCORE=0.55`
- query당 `DEFAULT_TOP_K_PER_QUERY=3`
- 전체 LLM context 최대 8개
- score 미달 결과 제외
- controlled danger/PPE query의 required_terms가 제목 또는 본문에 하나도 없으면 제외
- query마다 returned_count, rejected_by_term_gate, status(match/no_relevant_context)를 결과 JSON에 기록
- 결과가 없으면 `no_relevant_context`; embedder/Chroma 오류면 API가 `rag.status=unavailable`과 error를 기록하고 빈 clause로 LLM을 호출한다. LLM prompt는 빈 RAG context일 때 citations를 비우도록 이미 계약되어 있다.

API는 이제 `danger_contract -> build_canonical_queries -> retrieve_for_query_records` 경로를 사용한다. raw VLM danger 문자열을 검색에 넣지 않는다.

## 실제 검색 품질 실험

`python -m rag.experiments.evaluate_retrieval`을 RTX 4060 CUDA의 실제 bge-m3 + 기존 Chroma 인덱스로 실행했다. 산출물은 `outputs/rag_evaluation/retrieval_quality.json`이다.

### threshold 후보: 0.45 / 0.50 / 0.55

- 안전모 미착용 + 추락 위험: 0.55에서도 `산안규 제197조 보호구의 지급 및 사용`, `KOSHA 건설현장 개인보호구 착용 기준`, `고소작업대 설치 등의 조치` 등 관련 결과 유지.
- 위험구역 출입: 0.55에서도 `KOSHA 위험구역 출입 통제`, `제569조/제457조 출입의 금지` 유지.
- unknown 가림 위험의 legacy 자유문장 검색: 0.45에서 4건, 0.50에서 3건의 무관 법령 반환. 0.55에서야 0건.
- 같은 unknown 위험은 canonical builder가 query를 만들지 않으므로 모든 threshold에서 0건.

0.55는 대표 관련 query를 보존하면서 observed ambiguous query의 forced top-k를 차단했으므로 기본값으로 채택했다. 다만 이 값은 현재 소규모 gold case 기준이며, 새 법령/현장 데이터가 추가되면 재측정한다.

### term gate 발견과 보정

처음에는 위험구역 query에 `통제`라는 넓은 표현을 사용해 이산화탄소 소화설비 조항이 섞였다. query를 `위험구역 출입 금지 조치`로 좁히고, danger_type/PPE별 required_terms gate를 추가했다. 추락 query에서는 후보 1건이 이 gate에서 제외됐고, 위험구역 결과는 출입 관련 조항만 유지됐다.

## 실제 RAG -> LLM E2E

`python -m rag.test_e2e_rag`를 새 운영 경로로 실행했다.

- 입력 canonical query 3개: 안전모 보호구, 안전조끼 보호구, 위험구역 출입 금지
- 모든 query trace: `matched`
- 최종 LLM context: 4개 고유 조항
  - 산안규 제197조 보호구의 지급 및 사용 (0.6764)
  - KOSHA 건설현장 개인보호구 착용 기준 (0.6396)
  - 제569조/제457조 출입의 금지
- Gemini LLM 인용: 산안규 제197조제1호, KOSHA 건설현장 개인보호구 착용 기준
- citation source/clause와 retrieved clause를 교차검증한 결과: `PASS`, RAG context 밖 인용 0건

실행 중 첫 Gemini key가 429/503 상태여서 기존 key fallback이 동작했고, 다음 key로 보고서가 생성됐다.

## 자동 검증

`python -m unittest discover -s tests -p "test_*.py" -v`

- 총 15개 통과.
- canonical builder가 controlled template만 쓰고 unknown/free text를 건너뛰는지 검증.
- forced top-k mock 결과에서 min_score가 낮은 score를 제거하는지 검증.
- required_terms와 no_relevant_context trace가 작동하는지 검증.
- 기존 detection, streaming, VLM contract 테스트도 회귀 없이 통과.
- `py_compile`, `git diff --check` 통과.

## 범위와 남은 작업

이번 완료 범위는 query contract, score/term gate, trace, API 연결, 검색 품질 실험, RAG->LLM citation E2E다.

다음 RAG 작업은 아직 완료 처리하지 않는다.

- parent-child chunking 및 parent citation metadata 재설계
- 파일 hash manifest 기반 incremental indexing/upsert/delete
- 더 넓은 gold query set과 실제 현장 위험 질의를 통한 threshold 재튜닝

또한 LLM이 생성하는 report.date는 이번 RAG E2E에서도 과거 날짜를 만들 수 있었다. 날짜는 LLM 결과가 아니라 pipeline metadata로 고정하는 후속 LLM report schema 작업에서 처리한다.
"""


if __name__ == "__main__":
    create_dev_log(
        TITLE,
        CONTENT,
        sprint="Sprint 5",
        categories="RAG,Chroma,bge-m3,Retrieval,Prompt Contract,Testing,E2E",
    )
