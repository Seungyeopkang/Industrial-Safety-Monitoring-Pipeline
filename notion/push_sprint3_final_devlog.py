"""notion/push_sprint3_final_devlog.py - Sprint 3 최종 마무리 devlog Notion 게시."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from notion.notion_logger import create_dev_log

TITLE = "2026-07-03 | Sprint 3 최종 마무리 - UI 개선, VLM 트리거 실측, 스프린트 완료"

CONTENT = r"""## 개요
Sprint 3(백엔드 및 Web UI 개발)를 최종 마무리. UI 크기 조정(데스크톱 비중 확대), VLM 트리거 로직 실측 검증, UI 스크린샷 레포 저장, Sprint 3 태스크 5개 완료 체크, 후속 스프린트에 실시간 영상/속도 향상 태스크 추가.

## 1. VLM 트리거 로직 실측 검증
"진행할 때마다 매번 VLM 호출하는 게 아니지?" 질문에 대한 실측 답변.

### 실측 (construction-ppe test 15장)
| 단위 | 수치 | 비고 |
|---|---|---|
| 객체 단위 트리거 | 29/99 (29.3%) | 이전 실험 27.9%와 일치 ✓ |
| 이미지 단위 VLM 호출 | 12/15 (80%) | 데이터셋이 위반 사례 위주라 높음 |
| VLM 스킵 이미지 | 3/15 (20%) | conf≥0.60 + 위반 클래스 없음 |
| 트리거 원인 | 위반 클래스 15 + 애매 신뢰도 14 | 안전 최우선 원칙 |

### 결론
- **VLM은 매번 도는 게 아님**: 위반 클래스(NO-Hardhat/NO-Safety Vest/NO-Mask)가 있거나 신뢰도 0.30~0.60 애매 구간일 때만 호출
- conf≥0.60이고 위반 클래스 없으면 VLM·LLM 전부 스킵 (overall_severity: NONE)
- construction-ppe 데이터셋이 위반 사례 위주라 이미지 단위 호출률이 80%로 높지만, 이것은 안전 최우선 설계 의도(위반 누락 방지)이며 버그가 아님
- 실측 샘플: image1.jpeg에서 Hardhat(0.911)·Person(0.761)은 스킵, NO-Mask(0.385)·NO-Safety Vest(0.307)·NO-Mask(0.260)은 트리거

## 2. UI 크기 조정 (데스크톱 비중 확대)
"폰에 맞춰진 듯" 피드백 반영:

| 항목 | before | after |
|---|---|---|
| 컨테이너 너비 | max-w-7xl (1280px) | max-w-screen-2xl (1536px) |
| 좌우 패딩 | px-6 | px-8 |
| 상단 여백 | py-8 | py-10 |
| 그리드 | lg:grid-cols-3, gap-6 | lg:grid-cols-4, gap-8 |
| 결과 대시보드 비중 | col-span-2 (2/3) | col-span-3 (3/4) |
| 업로드 영역 비중 | col-span-1 (1/3) | col-span-1 (1/4) |

결과 대시보드가 화면 3/4 차지하도록 넓히고, 전체 컨테이너 1536px로 확대.

## 3. UI 스크린샷 레포 저장
Playwright 헤드리스 크로미움(113.6MiB 설치)으로 3장 캡처 → frontend/screenshots/ + notion/assets/:
- 01_empty_state.png (36KB) - 초기 빈 상태 화면
- 02_result_dashboard.png (138KB) - 결과 대시보드(목업 데이터)
- 03_progress_skeleton.png (44KB) - 파이프라인 진행 중 스켈레톤 UI

GitHub 푸시 완료 (commit bd2556f). raw URL로 Notion에 임베드.

## 4. Sprint 3 태스크 5개 완료 체크
Notion 스프린트 DB에 Sprint 3 전체 5개 태스크 완료 처리:
- ✅ FastAPI 프로젝트 뼈대 구축 및 의존성 주입 구조 설계
- ✅ FastAPI BackgroundTasks 기반 비동기 파이프라인 처리 및 비차단 API 설계
- ✅ 드래그앤드롭 이미지 업로드 컴포넌트 마크업 및 스타일링 (HTML/CSS)
- ✅ 파이프라인 추론 중 대기 애니메이션(Skeleton UI) 개발
- ✅ 정적 결과 화면 대시보드 UI 개발 (바운딩박스 오버레이 이미지 뷰어 + 리포트 세부 정보 카드)

## 5. 후속 스프린트에 실시간/속도 태스크 추가
**Sprint 5(예외 처리 및 프롬프트 고도화)**에 3개 추가:
- 실시간 영상 처리 기능 - 노트북 웹캠 및 동영상 파일 입력 지원 (프레임 단위 파이프라인)
- 파이프라인 속도 향상 - 단계별 병목 분석 및 최적화 (VLM/LLM 호출 비동기화, 프레임 스킵, 캐싱 등)
- 실시간 처리용 VLM 트리거 임계값 튜닝 - 프레임 단위 호출 빈도 최적화

**Sprint 6(강건성 검증 및 포트폴리오)**에 1개 추가:
- 실시간 데모용 영상 통합 및 성능 벤치마크 (FPS 측정, 지연 시간 시각화)

## 6. 파이프라인 구조 확인 (프로젝트 정체성)
- **목표**: 실시간 탐색 + 문제 발생 시 보고서 자동 생성 (산업 안전 모니터링)
- **현재 상태**: 단발성 이미지 1장 분석 → 보고서 생성 (FastAPI + Web UI로 구현 완료)
- **확장 예정**: 실시간 영상(웹캠/동영상) 프레임 단위 처리는 Sprint 5에서 추가
- **UI 역할**: 보고서 시각화(바운딩박스, 위반, 권고조치, 법령 인용) - 목업이 아닌 실제 파이프라인 결과 표시
- **VLM 호출 최적화**: 매 프레임/이미지마다 도는 게 아니라 위반 의심 시에만 호출 (비용·시간 절감)

## 현재 스프린트 현황
| 스프린트 | 완료/전체 | 상태 |
|---|---|---|
| Sprint 1: 환경 세팅 및 YOLO 탐색 | 7/7 | ✅ 완료 |
| Sprint 2: VLM/LLM 프롬프트 설계 | 5/5 | ✅ 완료 |
| Sprint 3: 백엔드 및 Web UI 개발 | 5/5 | ✅ 완료 (이번 마무리) |
| Sprint 4: Notion 연동 및 통합 | 0/4 | 대기 |
| Sprint 5: 예외 처리 및 프롬프트 고도화 | 1/10 | 실시간/속도 태스크 추가 |
| Sprint 6: 강건성 검증 및 포트폴리오 | 0/5 | 실시간 벤치마크 태스크 추가 |

## 파일 변경 (이번 세션)
- **수정**: frontend/index.html (UI 크기 조정: max-w-screen-2xl, grid-cols-4, col-span-3)
- **신규**: frontend/screenshots/{01_empty_state,02_result_dashboard,03_progress_skeleton}.png
- **복사**: notion/assets/에 스크린샷 3장 (GitHub raw URL용)
- **Git**: commit bd2556f, push to main 완료

## 다음 할 일
- [우선순위 높음] Sprint 5: 실시간 영상 처리(웹캠/동영상 프레임 단위) + 속도 향상 작업
- [우선순위 보통] 503 해소 후 end-to-end 최종 실행 (uvicorn + 브라우저)
- [우선순위 낮음] Sprint 4: Notion 연동 및 통합 테스트
"""

if __name__ == "__main__":
    ok = create_dev_log(
        TITLE,
        CONTENT,
        sprint="Sprint 3",
        categories="UI 개선,VLM 트리거 실측,스크린샷,스프린트 마무리,실시간 영상",
    )
    sys.exit(0 if ok else 1)
