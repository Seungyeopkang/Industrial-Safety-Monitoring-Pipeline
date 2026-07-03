"""notion/push_rag_devlog_v2.py - 한국 RAG 시스템 확장 및 전면 검증 devlog Notion 게시.

공식 법령 PDF 추가, API 키 폴백, 인덱스 919청크 확장, RAG→LLM 통합 검증,
한국어화 전면 점검 결과를 상세히 기록.
실행: python -m notion.push_rag_devlog_v2
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from notion.notion_logger import create_dev_log

TITLE = "2026-07-03 | 한국 RAG 시스템 확장·전면 검증 (공식 PDF 919청크 + API 폴백 + 한국어 보고서 생성)"

CONTENT = r"""## 개요
1차 RAG 구축(16청크 샘플)에 이어, 공식 법령 PDF 2종을 추가하여 인덱스를 919청크로 대폭 확장. Gemini API 키 폴백(429/503 자동 전환)을 구현하여 할당량 한계를 극복, RAG→LLM 통합으로 한국어 안전 검사 보고서+법령 인용 생성을 최종 검증함. 한국어화 전면 점검 완료.

## 환경 (재확인)
- GPU: RTX 4060 8GB, CUDA 11.8, torch 2.7.1+cu118 → bge-m3 임베딩 GPU(cuda) 가속
- sentence-transformers 5.6.0, chromadb 1.5.9, pypdf 6.5.0, google-genai 2.10.0
- API 키: GEMINI_API_KEY + GEMINI_API_KEY2 (할당량 폴백용 2개)

## 진행 상황 (상세)

### 1. 공식 법령 PDF 추가 및 청커 업그레이드
- **PDF 다운로드**: datasets/sop_korean/raw/에 공식 법령본문 PDF 2종 추가
  - 산업안전보건법(법률)(제21374호)(20260601).pdf — 304KB, 103,364자
  - 산업안전보건기준에 관한 규칙(고용노동부령)(제00450호)(20260302).pdf — 748KB, 225,813자
- **청커 업그레이드 (rag/chunker.py)**: 공식 PDF의 조문 형식 `제NN조(제목) 본문` 인식 추가 (기존 `[제NN조]` 괄호 형식과 함께 2개 패턴 지원). PDF 페이지 헤더 "법제처 N" 노이즈 필터링 추가.
- **ID 충돌 수정**: 조문 번호 중복(본문 참조에서 헤더로 오인)으로 인한 Chroma DuplicateIDError → 전역 카운터로 고유 ID 재할당하여 해결
- **청킹 결과**: 919청크 (산안규 703, 산업안전보건법 200, 샘플 TXT 16) — 기존 16청크 대비 57배 확장

### 2. 인덱스 재빌드
- bge-m3 임베딩: shape=(919, 1024), device=cuda (RTX 4060 GPU 가속)
- Chroma 컬렉션 'korean_safety_sop': 919건 저장, 889개 고유 (source, article) 쌍
- 빌드 시간: 모델 캐시 후 임베딩 포함 약 30초 (GPU)

### 3. Gemini API 키 폴백 구현
- llm/reporter.py, vlm/analyzer.py에 `_generate_with_fallback()` 헬퍼 추가
- GEMINI_API_KEY → GEMINI_API_KEY2 순회, 429(RESOURCE_EXHAUSTED)/503(UNAVAILABLE) 시 자동 전환
- .env.example에 GEMINI_API_KEY2 추가, 실제 키를 placeholder로 교체

### 4. RAG→LLM 통합 테스트 성공 (목업 VLM + 실제 LLM)
- RAG 검색 5건: 안전모 미착용의 위험성(0.653), 제98조 보호구(0.59), 제20조 출입의 금지 등(0.5831), 제639조 사고 시의 대피 등(0.5693), 산안규 제197조(0.5656)
- API 키 폴백 작동: KEY1 429 → KEY2 자동 전환 → LLM 호출 성공 (latency=16344ms, tokens=3185+1392)
- **한국어 안전 검사 보고서 생성 완료**:
  - 위반 4건: Worker1 헬멧미착용(HIGH), Worker2 헬멧미착용(HIGH), Worker2 안전조끼미착용(MEDIUM), Worker2 위험구역접근(HIGH)
  - overall_severity: HIGH
  - 권고조치 4건: 즉각 작업중단+보호구착용(immediate), 전 근로자 교육(high), 위험구역 통제 강화(high), 관리감독자 점검(medium)
  - 인용 6건: 산업안전보건법 제98조제1항/제2항, 산안규 제197조제1호, KOSHA 가이드 안전모 미착용의 위험성, 산안규 제20조제12호/제18호 — 모두 RAG 컨텍스트에서 추출
  - 한국어 summary: "금일 건설현장 검사 결과, 두 명의 근로자가 안전모를 착용하지 않았으며..."

### 5. 전체 파이프라인 테스트 (YOLO→VLM→RAG→LLM)
- YOLO 탐지 성공 → VLM API 호출에서 KEY1 429 → KEY2 폴백 전환 확인 → KEY2 503 UNAVAILABLE(Gemini 서버 일시적 과부하)로 실패
- 503 처리 로직 추가(429+503 모두 폴백 대상) — 일시적 서버 문제이며 코드 정상 작동 확인

## 검증 결과 (상세 성능 지표)

### RAG 검색 품질 (919청크 인덱스, test_retriever.py)
| 쿼리 | top-1 결과 | score | 기대 키워드 | 통과 |
|---|---|---|---|---|
| 헬멧(안전모) 미착용 | KOSHA 가이드 건설현장 PPE 착용기준 | 0.6005 | 제98조/안전모/보호구 | ✓ |
| 안전조끼 미착용 | KOSHA 가이드 안전조끼 착용기준 | 0.6887 | 안전조끼/보호구 | ✓ |
| 추락 위험 | 산안규 제62조 추락방지조치 | 0.6628 | 산안규62조/추락 | ✓ |
| 위험구역 출입 | KOSHA 가이드 위험구역 출입 통제 | 0.6628 | 위험구역/KOSHA | ✓ |
| 보호구 미지급 | 제98조 보호구 | 0.6589 | 제98조/보호구/벌칙 | ✓ |

- **top-1 관련성: 5/5 통과**
- **인용 환각 방지: 검색 결과 15건 출처 전부 DB 존재 True**
- 공식 PDF 조문이 정확히 검색됨: 제624조 안전대 등, 제45조 지붕 위 위험방지, 제20조 출입금지, 제654조 보호구 지급, 제639조 사고 시 대피 등

### RAG→LLM 통합 검증 (test_e2e_rag.py)
- RAG 검색: 5건 (목업 위반 4개 → 5개 고유 조항)
- LLM 보고서: 한국어 구조화 출력 정상 생성 (Pydantic 스키마 준수)
- 인용 환각 교차검증: LLM 인용 6건 중 전부 RAG 컨텍스트에 근거 (source 이름 정규화 매칭으로 검증)
- API 키 폴백: 429 → KEY2 전환 → 성공 (실제 작동 확인)

### 임베딩 성능
- 모델: BAAI/bge-m3 (1024차원, 다국어)
- 디바이스: CUDA (RTX 4060)
- 919청크 임베딩: 약 30초 (모델 로드 포함, GPU 가속)
- 가중치 로드: 391 weights, <1초 (캐시 후)

## 한국어화 전면 점검 결과
| 파일 | 점검 항목 | 결과 |
|---|---|---|
| llm/reporter.py | SYSTEM_INSTRUCTION | 한국어 ✓ (환각 방지 규칙 7개 포함) |
| llm/reporter.py | _build_llm_prompt (3개 변형) | 한국어 ✓ (default/sop_grounded/severity_first) |
| llm/reporter.py | RAG 컨텍스트 블록 | 한국어 ✓ |
| llm/schema.py | 모든 Field description | 한국어 ✓ (enum값은 영어 유지, API 호환) |
| vlm/analyzer.py | SYSTEM_INSTRUCTION | 한국어 ✓ (6개 규칙) |
| vlm/analyzer.py | _build_user_prompt (7개 변형) | 한국어 ✓ (default/role_stepwise/fewshot/constraints/role_constraints/role_constraints_fewshot/safety_first) |
| vlm/schema.py | 모든 Field description | 한국어 ✓ (enum값은 영어 유지) |
- **enum 코드값(missing_ppe, HIGH, immediate 등)은 API 호환성을 위해 영어 유지** — 이는 의도된 설계 결정이며 Gemini Structured Outputs와 호환됨

## 다음 할 일 (이전 devlog 항목 완료 상태)
- [완료] Gemini 할당량 리셋 후 RAG→LLM 통합 테스트 → API 키 폴백으로 극복, 한국어 보고서+법령 인용 생성 확인
- [완료] KOSHA/법령 원문 PDF 추가 후 인덱스 재빌드 → 919청크 확장, 공식 PDF 조문 검색 정상
- [검토 완료] cross-encoder 재순위 모델 도입 검토 → 현재 top-1 관련성 5/5로 충분. 데이터 확장 시 재순위 필요성 재평가 권장
- [검토 완료] RAG top-k·유사도 임세값 튜닝 → 현재 top_k=5, 유사도 임계값 없음. 검색 품질 양호. 데이터 추가 시 임계값(예: 0.5) 도입 검토

## 문제 & 해결 (상세)
1. **공식 PDF 조문 형식 불일치**: 기존 청커는 `[제NN조]` 괄호 형식만 인식. 공식 PDF는 `제NN조(제목) 본문` 형식. → LAW_HEADER_RE 정규식 추가로 2개 패턴 동시 지원
2. **Chroma DuplicateIDError**: 조문 번호 중복(본문에서 "제6조" 참조가 헤더로 오인)으로 ID 해시 충돌 (10개 중복). → chunk_documents에서 전역 카운터로 고유 ID 재할당
3. **PDF 페이지 헤더 노이즈**: "법제처 1" 등이 청크 본문에 섞임. → NOISE_RE로 "법제처" + 페이지 번호 라인 필터링
4. **Gemini 429 RESOURCE_EXHAUSTED**: 무료 tier 일일 20회 한도. → GEMINI_API_KEY2 폴백 구현, 429 시 자동 전환
5. **Gemini 503 UNAVAILABLE**: 서버 일시적 과부하. → 503도 폴백 대상에 추가 (429+503 모두 자동 전환)
6. **인용 교차검증 거짓 양성**: RAG source(파일명)와 LLM 인용 source(단축명) 불일치. → SOURCE_KEYWORDS 정규화 매칭 로직으로 해결 (산업안전보건법/산안규/KOSHA 키워드 기준 매칭)

## 한계/주의
- 법령 PDF는 2026.06.01(법률)/2026.03.02(산안규) 시행 기준. 조문 번호가 이전 버전과 상이할 수 있음 (예: 제98조가 보호구→안전검사로 변경된 버전 존재)
- Gemini 무료 tier 할당량(키당 20회/일) 제한. 2개 키로 일일 40회까지 커버 가능하나 대량 테스트 시 유료 전환 필요
- 503 UNAVAILABLE은 일시적 서버 문제 — 재시도 또는 시간차 실행으로 해결 가능

## 다음 할 일 (신규)
- [우선순위 높음] 503 해소 후 전체 파이프라인 end-to-end 최종 실행 (YOLO→VLM→RAG→LLM 한국어 보고서)
- [우선순위 보통] 데이터 추가 시 cross-encoder 재순위 + 유사도 임계값(0.5) 도입 검토
- [우선순위 낮음] API 키 3개 이상으로 확장 또는 유료 tier 전환 검토
"""

if __name__ == "__main__":
    ok = create_dev_log(
        TITLE,
        CONTENT,
        sprint="Sprint 4",
        categories="RAG,데이터 파이프라인,한국어 NLP,벡터DB,API 폴백,검증",
    )
    sys.exit(0 if ok else 1)
