"""notion/push_rag_devlog.py - 한국 안전 규정 RAG 시스템 구축 devlog Notion 게시.

notion_logger.create_dev_log 를 직접 호출하여 상세 마크다운 devlog를 Notion DB에 생성.
실행: python -m notion.push_rag_devlog
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from notion.notion_logger import create_dev_log

TITLE = "2026-07-03 | 한국 안전 규정 RAG 시스템 구축 (bge-m3 + Chroma)"

CONTENT = r"""## 개요
기존 OSHA(미국) 기반 SOP 인용 계획을 한국 안전 규정(산업안전보건법·산업안전보건기준에 관한 규칙·KOSHA 안전보건가이드) 기반 RAG로 전환. 로컬 bge-m3 다국어 임베딩 + Chroma 벡터DB로 한국어 의미 검색·인용 시스템을 구축하고 검증.

## 환경
- GPU: RTX 4060 8GB, CUDA 11.8, torch 2.7.1+cu118 (CUDA 인식 OK)
- 이미 설치: chromadb 1.5.9, google-genai 2.10.0, pypdf 6.5.0, pydantic 2.13.4, transformers 5.5.0
- 추가 설치: sentence-transformers 5.6.0 (1종만 추가)

## 진행 상황 (Phase별)
- **Phase 1 - 의존성/디렉토리**: sentence-transformers 설치, rag/·datasets/sop_korean/raw/·rag/vectorstore/ 생성
- **Phase 2 - 데이터/청킹**: 산업안전보건법 핵심조문(제5/24/94/98/99/100/101/102/119조) + KOSHA/산안규(제62/197조, PPE/위험구역/안전모/조끼/시정 권고) 샘플 2파일 구성. rag/loader.py(PDF/TXT), rag/chunker.py(조문 단위 의미 청킹) → 청크 16개
- **Phase 3 - 임베딩/인덱스**: rag/embedder.py(bge-m3, CUDA), rag/build_index.py → bge-m3 shape=(16,1024), Chroma 컬렉션 'korean_safety_sop' 16건 저장
- **Phase 4 - 검색**: rag/retriever.py(top-k 검색, retrieve_for_violations 병합, format_context)
- **Phase 5 - LLM 한국어화+RAG 연결**: llm/reporter.py 시스템 프롬프트/프롬프트 변형 한국어화, generate_report에 retrieved_clauses 파라미터 추가, RAG 컨텍스트 주입 + "검색 컨텍스트에 없는 조항 인용 금지" 환각 방지 규칙. llm/schema.py Citation.source를 한국 법령 예시로 변경
- **Phase 6 - VLM 한국어화**: vlm/analyzer.py(7개 변형 전부), vlm/schema.py description 한국어화(enum값은 유지)
- **Phase 7 - 검증**: rag/test_retriever.py + rag/test_e2e_rag.py

## 기술 결정 사항
- **임베딩: bge-m3 로컬** 선택. 한국어 품질 우수·오프라인·무료. RTX 4060 GPU 가속으로 임베딩 빠름. torch 의존성 이미 존재.
- **벡터DB: Chroma** (README 계획 일관, 로컬 영속, cosine 거리)
- **청킹: 조문 단위 의미 청킹** ([제NN조] 헤더 인식, 메타데이터 source/article/title 부착 → 인용 추적 가능)
- **언어 일관성**: VLM/LLM/스키마 description 전부 한국어화, enum 코드값은 API 호환성 유지
- **인용 환각 방지**: LLM 프롬프트에 RAG 검색 컨텍스트 주입 + "컨텍스트에 없는 조항 인용 금지" 규칙 + 스키마 Citation으로 추적 강제

## RAG 구축 단계 (재설명)
1. 문서 수집 - datasets/sop_korean/raw/ 에 한국 규정 원문(PDF/TXT/MD)
2. 전처리 - rag/loader.py 가 PDF(pypdf)/TXT 추출
3. 청킹 - rag/chunker.py 가 조문 단위 분할 + 메타데이터 부착
4. 임베딩 - rag/embedder.py 가 bge-m3로 청크→1024차원 벡터
5. 인덱싱 - rag/build_index.py 가 Chroma에 임베딩+메타데이터 저장
6. 검색 - rag/retriever.py 가 위반 쿼리→top-k 조항 검색
7. 증강/생성 - llm/reporter.py 가 검색 컨텍스트를 프롬프트에 주입→한국어 보고서+법령 인용

## 검증 결과
- 인덱스: 16청크, 12개 고유 (source,article) 쌍
- 단일 쿼리 5개(헬멧/조끼/추락/위험구역/보호구미지급) 의미 검색 정확 (예: 안전조끼→안전조끼착용기준 0.6887, 추락→산안규62조 0.6628, 보호구미지급→제98조 0.6589 + 제119조 벌칙 0.6442)
- 인용 환각 방지: 검색 결과 15건 출처 전부 DB 존재 True
- top-1 관련성 기대치 교차: 5/5 통과
- 통합(RAG→LLM 목업): RAG 4건 검색 정상(안전모위험성 0.653, 제98조 0.59, 산안규197조 0.5656, 산안규62조 0.5293)

## 문제 & 해결
1. **bge-m3 다운로드로 run_commands 30초 타임아웃**: Start-Process 백그라운드 + 파일 리다이렉트로 해결, 로그 폴링으로 완료 확인
2. **Start-Process 동기 대기 / Start-Job 세션 격리**: -PassThru 변수 할당 + -WindowStyle Hidden, Get-Process PID 폴링으로 회피
3. **README editor 멀티라인 매칭 실패**: CRLF 라인엔딩 → 단일 라인 교체로 해결
4. **Gemini API 429 RESOURCE_EXHAUSTED**: 무료 tier 일일 20회 한도 초과 (코드 문제 아님). YOLO→VLM 호출까지 정상 도달 확인됨. 할당량 리셋 후 LLM 보고서 생성 예정

## 한계/주의
- 법령 데이터는 law.go.kr 동적 페이지 페치 불가로 공개 법령 핵심 조문을 샘플 발췌본으로 구성(출처 표기). 최신·전체 본문은 원문 PDF로 datasets/sop_korean/raw/ 교체 후 `python -m rag.build_index --rebuild` 재실행
- LLM 보고서 생성은 Gemini 무료 tier 일일 한도(20회) 초과로 보류. 할당량 리셋 후 `python -m rag.test_e2e_rag` 또는 `python -m llm.reporter` 실행

## 다음 할 일
- [우선순위 높음] Gemini 할당량 리셋 후 RAG→LLM 통합 테스트로 한국어 보고서+법령 인용 최종 확인
- [우선순위 보통] KOSHA/법령 원문 PDF 추가 후 인덱스 재빌드(청크 확장)
- [우선순위 보통] cross-encoder 재순위 모델 도입 검토
- [우선순위 낮음] RAG 검색 top-k·유사도 임계값 튜닝
"""

if __name__ == "__main__":
    ok = create_dev_log(
        TITLE,
        CONTENT,
        sprint="Sprint 4",
        categories="RAG,데이터 파이프라인,한국어 NLP,벡터DB",
    )
    sys.exit(0 if ok else 1)
