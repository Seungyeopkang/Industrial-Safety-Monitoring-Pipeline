"""Post final portfolio and verification completion record for Sprint 6."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from notion.notion_logger import create_dev_log


TITLE = "2026-07-10 | Sprint 6 - 포트폴리오 증적·전체 데이터셋 평가·최종 아카이브"

CONTENT = r"""## Sprint 6 마감 범위
Sprint 1~5에서 구현한 파이프라인을 포트폴리오에서 검증 가능한 형태로 정리했다. 이번 작업은 기능을 새로 과장하는 마무리가 아니라, 실제 UI/보고서/검증 지표를 Git과 Notion에 고정하고 한계를 명시하는 데 초점을 두었다.

## 1. 기존 라벨 데이터셋 전체 재평가
운영 모델 `Hansung-Cho/yolov8-ppe-detection`을 confidence 0.25, IoU 0.50 기준으로 현재 보유한 두 test split 전체에 다시 실행했다.

| 데이터셋 | test 이미지 | helmet F1 | no-helmet F1 | vest F1 |
| --- | ---: | ---: | ---: | ---: |
| Construction-PPE | 141 | 0.793 | 0.217 | 0.698 |
| Hard Hat Workers v10 | 706 | 0.496 | 0.086 | N/A |

총 847장이다. no-helmet 성능이 낮다는 결과를 숨기지 않았고, 이것이 위반 후보를 최종 판정으로 바로 쓰지 않고 VLM review path로 전달하는 근거임을 README에 명시했다.

`outputs/portfolio/final_dataset_evaluation.json`과 `detection/experiments/final_dataset_evaluation.py`로 재현 가능하게 남겼다.

## 2. Git 포트폴리오 증적 고정
`assets/portfolio/`에 다음 실제 산출물을 버전 관리용 자산으로 추가했다.

- `ui-live-empty-state.png`: 로컬 FastAPI 서버에서 캡처한 운영 콘솔 실제 화면.
- `ui-result-dashboard.png`: 실제 안전 결과 대시보드.
- `ui-report-capture.png`: 프론트엔드 렌더 결과를 html2canvas로 캡처한 보고서 이미지.
- `annotated-detection.jpg`: 실제 YOLO bounding-box 결과.
- `model-evaluation.png`: 모델 비교/평가 시각화.

README는 이 화면을 직접 보여 주고, 아키텍처, API 경계, 성능, 실행 방법, 한계와 재현 명령을 한 페이지에서 확인할 수 있도록 전면 정리했다.

## 3. Notion 최종 보존 확인
기존 실제 job `6ad7a272eb59`를 확인했다.

- 원본 감지 이미지: Notion file upload 성공.
- 렌더된 UI 보고서 PNG: Notion page append 및 file upload 성공.
- Notion report page는 source image와 사람이 읽는 보고서 캡처를 함께 보존한다.

최종 pipeline 결과의 public API는 내부 local path, traceback, RAG 원문/parent text, canonical query trace, Notion internal id를 노출하지 않는 typed response로 유지된다.

## 4. 성능 정리
동일 프로세스 warm 상태에서 YOLO는 평균 약 19.3ms, RAG는 26.44초 cold start에서 34.8ms warm 상태로 감소했다. VLM/LLM 외부 API는 약 15~18초로 이후의 주된 지연이다. VLM -> RAG -> LLM은 근거 의존 관계라 병렬 호출하지 않는다.

## 완료/보류 판단
- 완료: 포트폴리오용 Notion 보드/문서 아카이브, 최종 보고서/저장소 정리, 확보된 데이터셋 전체 평가.
- 보류: `산업 현장별(건설, 물류 등) 테스트 데이터셋 확보 (50장 이상)`.

현재 로컬에는 Construction-PPE와 Hard Hat Workers PPE 데이터가 총 8,451장 있지만, 물류/제조 등 별도 산업군을 대표하는 출처 검증 데이터는 없다. 따라서 이를 완료로 표시하지 않았으며, 도메인 일반화 성능을 주장하지 않는다.

## 최종 검증
- 전체 labeled test images 평가: 847장 완료.
- `python -m unittest discover -s tests -p "test_*.py" -v`: 22/22 PASS.
- FastAPI `/docs` response schema 및 public result filter test PASS.
- Git README의 버전 관리 자산 경로와 실제 이미지 렌더링 확인.
"""


if __name__ == "__main__":
    create_dev_log(
        TITLE,
        CONTENT,
        sprint="Sprint 6",
        categories="Portfolio,Documentation,Evaluation,YOLO,FastAPI,Notion,Testing",
    )
