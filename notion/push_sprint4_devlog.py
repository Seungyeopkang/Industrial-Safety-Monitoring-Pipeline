"""notion/push_sprint4_devlog.py - Sprint 4 Notion report export devlog 게시.

실행:
  python -m notion.push_sprint4_devlog
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from notion.notion_logger import create_dev_log


TITLE = "2026-07-04 | Sprint 4 완료 - Notion 안전 보고서 자동 생성, 이미지 업로드, UI 캡처 연동"

CONTENT = r"""## 개요
Sprint 4의 목표는 FastAPI 파이프라인 결과를 Notion에 자동 보고서로 저장하고, 구조화된 LLM SafetyReport를 사람이 읽을 수 있는 Notion 문서 형태로 변환하는 것이었다.

이번 패스에서 단순 텍스트 저장을 넘어서 다음까지 완료했다.
- 파이프라인 완료 시 Notion 안전 보고서 페이지 자동 생성
- Pydantic/JSON SafetyReport를 Notion 블록 구조로 변환
- 현장 포착 원본 이미지 직접 업로드
- Web UI 보고서 본문 캡처를 Notion 이미지 블록으로 추가
- Sprint 4 진행률 체크 완료
- 후속 스프린트에 실시간 스트리밍 확장 및 UI/Notion 포지셔닝 태스크 추가

## 구현 내용

### 1. Notion 보고서 전용 페이지 허브 구성
- 기존 devlog 데이터베이스에 안전 검사 보고서를 섞지 않도록 별도 부모 페이지 `Safety Inspection Reports`를 사용했다.
- `.env`에 `NOTION_REPORT_PARENT_PAGE_ID`를 추가하여 안전 보고서가 새 허브 아래에 누적되도록 구성했다.
- `NOTION_AUTO_EXPORT=1`로 파이프라인 완료 시 보고서 자동 생성이 기본 동작이 되게 했다.

### 2. SafetyReport → Notion 블록 변환
`notion/report_to_notion.py`를 추가하여 LLM 보고서 dict를 Notion 블록으로 변환한다.

변환 구조:
- Callout: 종합 심각도와 검사일
- Paragraph: 요약
- Image: 현장 포착 이미지
- Table: 탐지된 위반 목록
- Bulleted list: 권고 조치
- Quote: RAG 기반 법령 인용
- Paragraph/Callout: VLM 장면 분석 및 즉각 위험
- Table: 파이프라인 메타데이터

Notion API 제한을 고려하여 rich text 길이를 clipping하고, 100개 블록 단위 append 처리를 추가했다.

### 3. Notion Direct File Upload 적용
초기 구현은 `PUBLIC_BASE_URL`이 없으면 로컬 이미지 경로를 안내 문구로만 남겼다. 이 방식은 실제 보고서 관점에서 부적절했다.

수정 후:
- `POST /v1/file_uploads`로 Notion file_upload 객체 생성
- 반환된 `upload_url`로 multipart 파일 업로드
- image block의 `type: file_upload`에 업로드 ID 연결

이제 공개 URL 없이도 로컬 현장 이미지와 UI 캡처가 Notion 내부 파일로 직접 첨부된다.

### 4. 대표 이미지 정책 수정
초기에는 YOLO 바운딩박스 annotated 이미지를 대표 이미지처럼 올렸는데, 실제 보고서에서는 "퍼온 자료" 또는 디버깅 이미지처럼 보였다.

최종 정책:
- Notion 상단 이미지는 사용자가 업로드한 현장 포착 원본 이미지 1장
- YOLO annotated 이미지는 Web UI의 검수/운영 콘솔에서 확인
- Notion에는 원본 이미지와 보고서 본문 캡처만 남김

이렇게 역할을 분리하여 Notion 보고서가 감사/기록 문서처럼 보이도록 조정했다.

### 5. Web UI 캡처 연동
프론트엔드에 `html2canvas`를 적용하고, 결과 렌더링 후 자동으로 보고서 본문을 캡처하도록 했다.

초기에는 전체 `resultDashboard`를 캡처했으나, Notion에는 운영 버튼/성능 로그까지 들어갈 필요가 없다고 판단했다.

최종 캡처 범위:
- 검사 결과 요약
- 탐지된 위반
- 권고 조치
- RAG 법령 인용
- VLM 장면 분석

제외:
- Notion 저장 완료 배너
- annotated 이미지 카드
- 성능 메타데이터
- 새 이미지 분석 버튼

FastAPI에는 `POST /report-screenshot/{job_id}`를 추가했다. 프론트엔드가 base64 PNG를 보내면 서버가 `outputs/report_screenshots/`에 저장하고, 연결된 Notion page_id가 있으면 즉시 이미지 블록으로 append한다.

### 6. 페이지 제목 날짜 수정
Notion 페이지 제목이 LLM이 생성한 `report.date`에 끌려가면서 샘플/모델 출력 날짜가 제목에 섞이는 문제가 있었다.

수정 후:
- 페이지 제목은 보고서 생성일 기준 `YYYY-MM-DD | 안전검사 보고서 {job_id}`로 생성
- 응답 JSON에 실제 `title`을 포함하여 디버깅 가능하게 함
- 본문 내 검사일은 report 내용으로 유지하되, 페이지 관리 날짜는 실행일 기준으로 안정화

### 7. Web UI 포지셔닝 정리
현재 UI는 최종 보고서 산출물이 아니라 업로드 기반 검수 콘솔로 둔다.

후속 방향:
- UI: 실시간 스트리밍 운영 콘솔, 프레임 상태 확인, 트리거/재분석, 운영자 검수
- Notion: 최종 보고서, 감사 로그, 원본 포착 이미지 및 보고서 캡처 아카이브

이 방향은 Sprint 4에 억지로 포함하지 않고 Sprint 5 후속 태스크로 추가했다.

## 변경 파일
- `api/main.py`
  - Notion 자동 export 단계 추가
  - 원본 업로드 이미지를 Notion 보고서 이미지로 전달
  - UI 캡처 업로드 API 추가
  - VLM skip 케이스도 Notion report schema에 맞도록 보강
- `notion/report_to_notion.py`
  - SafetyReport → Notion block 변환
  - Notion page 생성
  - Direct File Upload API 지원
  - UI 캡처 append 지원
  - 페이지 제목 생성일 기준 고정
- `frontend/index.html`
  - 파이프라인 단계에 Notion 추가
  - Notion report link 카드 추가
  - 결과 본문 캡처 및 서버 업로드
  - 캡처 범위를 보고서 본문 영역으로 제한
- `.env.example`
  - Notion report 전용 설정 추가
  - `NOTION_API_VERSION=2026-03-11` 추가
  - `PUBLIC_BASE_URL`은 direct upload fallback 용도로 정리
- `notion/notion_logger.py`, `notion/update_progress.py`
  - `.env` BOM 대응을 위해 `encoding="utf-8-sig"` 적용

## 검증 결과

### 로컬 검증
- `notion/report_to_notion.py`, `api/main.py` compile 통과
- FastAPI 서버 기동 및 `/health` 확인
- Web UI에서 Notion 단계 표시 확인
- 결과 렌더링 후 UI 캡처 업로드 흐름 확인

### Notion 실 업로드 검증
- 현장 포착 원본 이미지 업로드 성공
  - 파일명: `0a06c3cec9b8.jpeg`
  - Notion file_upload ID 발급 확인
- UI 보고서 캡처 업로드 성공
  - 파일명: `sprint4_ui_notion_result.png`
  - `PUBLIC_BASE_URL` 없이도 Notion 이미지 블록으로 렌더링 확인
- 테스트 보고서 페이지 fetch 결과에서 이미지 마크다운 블록 확인

### 스프린트 체크
Sprint 4 기존 남은 항목 완료 처리:
- Pydantic 구조화 데이터를 Notion 블록 구조로 변환하는 모듈 개발
- 분석 이미지 Notion 내 시각적 임베딩/링크 구현

이미 완료되어 있던 항목:
- 노션 API 활용 결과 페이지 자동 생성 연동 구현
- Web frontend - FastAPI - AI engine - Notion 통합 테스트 및 예외 처리

Sprint 4는 4/4 완료 상태가 되었다.

## 코드 리뷰 메모
- YOLO는 업로드마다 항상 1차 실행된다.
- VLM/RAG/LLM은 항상 실행되는 것이 아니라 `vlm_trigger` 기준으로 필요할 때만 호출된다.
- 위반 클래스(`NO-Hardhat`, `NO-Safety Vest`, `NO-Mask`)는 confidence와 무관하게 VLM 검증 대상으로 둔다.
- 일반 객체는 confidence 0.30~0.60 애매 구간에서 VLM 검증, 0.60 이상은 비용 절감을 위해 보통 스킵한다.
- 현재 Notion 이미지 업로드는 Notion API version `2026-03-11`의 File Upload API를 사용한다.

## 남은 주의점
- `html2canvas`는 CDN 의존성이 있으므로 오프라인 데모가 필요하면 vendor 처리 또는 번들링이 필요하다.
- Notion 보고서 본문 캡처는 브라우저 렌더링 결과에 의존하므로, 추후 스트리밍 UI가 들어오면 캡처 영역을 별도 컴포넌트로 분리하는 것이 좋다.
- RAG 벡터스토어 변경분은 이번 Sprint 4 핵심 변경이 아니라 이전 RAG 확장 작업의 산물로 보이며, 별도 커밋/정리 시점에서 재확인 필요하다.

## 후속 스프린트로 넘긴 항목
- 실시간 스트리밍 확장에 맞춘 UI 운영 콘솔 / Notion 보고서 포지셔닝 재정의
  - UI는 실시간 운영/검수 콘솔
  - Notion은 최종 보고서/감사 로그/캡처 아카이브
  - 프레임 단위 VLM 트리거, 호출 빈도 제한, 프레임 스킵/캐싱, 이벤트 기반 캡처 정책과 함께 설계
"""


if __name__ == "__main__":
    ok = create_dev_log(
        TITLE,
        CONTENT,
        sprint="Sprint 4",
        categories="Notion,FastAPI,Web UI,보고서 자동화,통합 테스트,스프린트 관리",
    )
    sys.exit(0 if ok else 1)
