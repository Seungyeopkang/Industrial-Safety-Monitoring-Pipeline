"""Post Sprint 5 final integration, RAG architecture, and LLM contract devlog."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from notion.notion_logger import create_dev_log


TITLE = "2026-07-10 | Sprint 5 최종 - Parent/Child RAG·증분 인덱싱·LLM 계약·전체 E2E"

CONTENT = r"""## Sprint 5 완료 범위
이번 마무리는 속도 최적화 태스크를 제외한 Sprint 5의 구현/검증 항목을 정리한 것이다.

- Detection: 이미지/동영상/웹캠 프레임 gate, VLM trigger 정책, queue/backpressure, 합성 Occlusion·조도 평가 완료.
- VLM: structured output, unknown/occlusion/limitations, structured immediate_dangers, role_constraints 운영 계약 완료.
- RAG: canonical query, score/term gate, parent-child metadata, incremental upsert, citation E2E 완료.
- LLM: prompt rule audit, 공통 안전 계약, pipeline 날짜 주입, RAG grounded citation 검증 완료.

`파이프라인 속도 향상 - 단계별 병목 분석 및 최적화`는 사용자 결정에 따라 이번 Sprint 완료 범위에서 제외했다. Cross-encoder reranker도 gold relevance set이 충분히 커진 뒤 재검토하는 backlog로 Sprint에서 제외했다.

## Parent/Child RAG와 증분 인덱싱

### 구조
기존 전역 `c00001` child id를 제거했다. 각 child는 다음 metadata를 가진다.

- `doc_id`: raw file 상대 경로 기반 안정 id
- `parent_id`: 법령 조문/가이드 항목 단위 id
- `child_id`: parent 내부 검색 child id
- `source`, `article`, `title`, `section_path`, `chunk_type`

Chroma는 child text를 embedding/search한다. `rag/vectorstore/parent_documents.json`에는 parent 조문 전체를 별도 보관하고, retrieval 결과에는 child score와 parent 문맥을 함께 반환한다. LLM context는 child text에 필요한 parent 조문 문맥을 최대 1800자로 붙여, 작은 검색 조각만 보고 법령을 오해하는 위험을 줄인다.

### 인덱싱 운영 방식
`rag/build_index.py`는 파일 SHA-256 기반 `index_manifest.json`을 관리한다.

- 신규/수정 파일: 해당 파일의 기존 `doc_id` vector를 삭제 후 child만 embed + `collection.upsert()`.
- 삭제 파일: manifest의 `doc_id`로 Chroma와 parent store에서 제거.
- 변경 없는 파일: load/hash 비교 후 embed 없이 skip.
- `--rebuild`: legacy 전역 id 인덱스에서 한 번만 수행하는 전체 migration/rebuild.

실측:

1. `python -m rag.build_index --rebuild`: raw 4개 문서, child 919개 upsert.
2. 직후 `python -m rag.build_index`: processed=0, skipped=4, upserted=0, deleted=0.
3. 생성 manifest 문서 4개, parent 조문 899개 확인.

즉, 원문 변경이 없을 때 GPU embedding을 다시 수행하지 않는다. 이 구조는 실제 규정 파일이 추가/수정되는 운영 환경에서 전체 재임베딩 비용과 duplicate vector 위험을 줄인다.

## LLM 시스템 규칙·프롬프트 audit

### SYSTEM_INSTRUCTION의 7개 규칙
1. violation type 분류: UI/API enum을 안정적으로 유지하기 위해 필요.
2. severity 판정: 우선순위와 권고 조치의 입력이므로 필요. 단, VLM unknown을 확정 위반으로 키우지 않도록 공통 계약으로 보강.
3. recommended action: 보고서가 탐지 목록에 그치지 않고 행동 가능한 결과가 되게 하므로 필요.
4. RAG context 밖 인용 금지: 법령 hallucination 방지의 핵심이므로 필요.
5. overall severity=max violation: 집계가 임의로 바뀌지 않도록 필요.
6. VLM 사실 기반: 보이지 않는 작업 조건/위반을 추가로 만들지 않도록 필요.
7. 한국어 출력: UI/Notion 계약을 위해 필요.

### REPORT_OUTPUT_CONTRACT
모든 LLM variant 뒤에 붙는 공통 출력 계약을 추가했다.

- VLM `unknown`, analysis_limitations, partial/severe occlusion은 확정 위반이 아니라 재확인 대상으로만 서술.
- 장면 맥락 위험만으로 보이지 않는 작업 조건 또는 법 위반을 단정 금지.
- RAG 조항이 없으면 citations는 빈 목록.
- 날짜는 LLM이 만드는 사실이 아니라 pipeline metadata가 최종 주입.

`default`, `sop_grounded`, `severity_first` 모두 이 계약을 포함한다. 현재 API 운영 variant는 `sop_grounded`, temperature=0.0이다. `default`는 baseline, `severity_first`는 심각도 표현을 비교할 실험용으로 남긴다.

### 날짜 오류 수정
E2E에서 LLM이 2023/2024 날짜를 만들던 문제를 확인했다. `generate_report(..., report_date=...)`가 최종 parsed report.date를 pipeline의 `date.today()` 값으로 덮어쓰도록 변경했다. 이후 실제 E2E report.date는 `2026-07-10`으로 확인됐다.

## 검증

### 자동 테스트
`python -m unittest discover -s tests -p "test_*.py" -v`

- 19개 통과.
- parent-child stable hierarchy, manifest 변경/삭제 계획, query contract/score gate, LLM variant 공통 계약, report date override를 추가 검증.
- 기존 Detection, streaming, VLM contract 회귀 테스트도 모두 통과.

### RAG -> LLM E2E
실제 CUDA bge-m3 + Chroma + Gemini로 canonical query 3개를 실행했다.

- 검색된 고유 조항 4개: PPE 관련 산안규/KOSHA, 위험구역 출입 금지 조항.
- LLM 인용 source/clause와 retrieved clause를 교차검증: PASS.
- parent context가 추가된 뒤에도 prompt tokens 1997, output tokens 1008 수준에서 structured report parse 성공.

### 전체 파이프라인 최종 E2E
`_run_pipeline('sprint5_final_e2e_notion', image1.jpeg, 'image')`로 실행했다.

- YOLO detections: 5
- VLM workers: 1
- canonical RAG queries: 3
- RAG status: complete, retrieved clauses: 7
- LLM overall severity: HIGH, citations: 4
- report.date: 2026-07-10
- 결과 JSON: `outputs/results/sprint5_final_e2e_notion.json`
- Notion report: 생성 성공, 포착 원본 이미지 upload 성공

최초 E2E에서 Notion 저장은 archived parent page를 가리키는 `.env`의 `NOTION_REPORT_PARENT_PAGE_ID` 때문에 400으로 실패했다. 프로젝트 아래에 새 활성 `안전 검사 보고서` parent page를 생성하고 설정을 교체한 뒤 재실행하여 성공했다. 분석/JSON은 Notion 실패와 독립적으로 보존되는 기존 fail-soft 동작도 확인했다.

## Sprint 외로 남긴 것

- 속도 최적화: 단계별 latency/parallelism/caching은 사용자 지시에 따라 제외.
- Cross-encoder reranker: 현재 canonical query + score/term gate의 정량 오류를 더 큰 gold query set으로 축적한 뒤 도입 판단.
- 실제 실내/실외 현장 데이터 기반 일반화, worker-PPE association ground truth, LLM 보고서의 confirmed/review_required/contextual_risk UI 상태 분리는 후속 작업.
"""


if __name__ == "__main__":
    create_dev_log(
        TITLE,
        CONTENT,
        sprint="Sprint 5",
        categories="RAG,Parent Child Chunking,Incremental Indexing,LLM,Prompt Engineering,E2E,Testing,Notion",
    )
