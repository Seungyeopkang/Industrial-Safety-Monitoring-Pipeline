"""Post the Sprint 5 detection/video dispatch devlog to Notion."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from notion.notion_logger import create_dev_log


TITLE = "2026-07-10 | Sprint 5 - 동영상 프레임 게이트 및 VLM 호출 정책 검증"

CONTENT = r"""## 개요
Sprint 5의 첫 작업인 `실시간 처리용 VLM 트리거 임계값 튜닝 - 프레임 단위 호출 빈도 최적화`를 Detection → VLM 경계부터 진행했다.

핵심 문제는 기존 단건 이미지 정책을 스트리밍에 그대로 적용할 경우, **YOLO가 아무것도 탐지하지 못한 프레임도 즉시 VLM으로 전송**된다는 점이었다. 영상 스트림에는 작업자가 없는 프레임과 장면 전환이 정상적으로 반복되므로, 이 동작은 VLM API 비용과 지연을 불필요하게 늘린다.

이번 작업은 confidence 값을 새 데이터 없이 재튜닝하지 않았다. 기존 `0.60 / 0.30` 임계값과 PPE 위반 클래스 우선 규칙은 유지하고, 그 위에 **입력 매체별 VLM 호출 정책과 연속 프레임 확인 게이트**를 추가했다.

## 결정 사항

### 1. 이미지와 스트리밍의 무탐지 정책을 분리

| 입력 | YOLO 탐지 0건 | VLM 처리 | 이유 |
| --- | --- | --- | --- |
| 정지 이미지 | VLM 호출 | 유지 | 한 장뿐인 입력에서는 YOLO miss를 한 번 더 확인하는 안전망이 필요 |
| 동영상/향후 스트림 | VLM 스킵 | 신규 | 빈 프레임은 일반적인 정상 상태이며 매 프레임 API 호출의 근거가 되지 않음 |

`detection/stream_policy.py`의 `decide_vlm_dispatch`가 이 계약을 가진다. 결과 JSON에는 `vlm_dispatch.should_dispatch`와 `reason`도 남겨, 왜 스킵/호출됐는지 외부에서 확인할 수 있게 했다.

### 2. 동영상 후보 프레임은 연속 2회 확인 후 확정

- 샘플링: 기본 2 FPS
- 후보 조건: YOLO의 기존 `vlm_trigger=True` 또는 `Person`만 탐지된 PPE 상태 불명확 프레임
- 확정 조건: 후보가 연속 2개 샘플 프레임에서 관찰될 것
- 대표 프레임: 확정 창 안에서 Laplacian variance가 가장 큰, 즉 상대적으로 선명한 프레임 1장
- 무탐지/비후보 프레임: 후보 streak를 초기화하고 VLM 호출하지 않음

2 FPS에서 연속 2프레임은 약 1초 수준의 확인 창이다. 안전 위반 클래스를 버리는 필터가 아니라, 일시적 노이즈·장면 전환에 VLM이 반복 호출되는 것을 막는 호출 게이트다.

### 3. 디스크 병목을 피하는 처리 방식

`detection/video.py`는 OpenCV로 영상을 순차 디코딩하되, 샘플 프레임과 후보 창을 메모리에서만 유지한다. 프레임별 JPG/PNG는 생성하지 않는다. API가 저장하는 것은 업로드한 원본 동영상과, 최종 보고서/대시보드에 쓸 대표 프레임 1장뿐이다.

## 구현 변경

- `detection/stream_policy.py`
  - 이미지/스트림별 VLM dispatch 판단
  - `ConsecutiveFrameGate(required_frames=2)`
- `detection/video.py`
  - 2 FPS 샘플링, 모델 1회 로드, 연속 후보 확인, 대표 프레임 선택
- `detection/detector.py`
  - `load_model`, `run_detection_frame` 분리
  - 동영상 한 건 안에서 YOLO 모델을 프레임마다 재로딩하지 않도록 개선
- `api/main.py`
  - `POST /upload`이 이미지와 video MIME을 모두 수락
  - video 입력은 대표 프레임을 후속 VLM → RAG → LLM 파이프라인에 전달
  - 무탐지/미확정 동영상은 VLM/RAG/LLM을 모두 스킵하고 `NONE` 보고서를 생성
  - 영상 최대 100MB, 이미지 최대 10MB 제한
- `frontend/index.html`
  - MP4/WEBM/MOV 선택과 video 미리보기 지원

## 검증

### 단위 테스트

`python -m unittest discover -s tests -p "test_*.py" -v`

- 이미지 무탐지: 기존 안전망대로 VLM 호출
- 스트림 무탐지: `stream_no_detection_skip`
- 후보 2개 연속: 두 번째 후보에서만 VLM 이벤트 확정
- 중간 무탐지: candidate streak 초기화
- 4 FPS 합성 무탐지 동영상: 2 FPS로 4장 샘플링, 확정 후보 없음

결과: 5개 테스트 통과.

### API 통합 확인

Notion 자동 저장을 끈 별도 로컬 서버에서 4 FPS, 8프레임 무탐지 AVI를 업로드했다.

결과 JSON:

```json
{
  "media": {
    "type": "video",
    "sampled_frames": 4,
    "sample_fps": 2.0,
    "confirmation_frames": 2,
    "confirmed_candidate": false
  },
  "vlm_dispatch": {
    "should_dispatch": false,
    "reason": "video_no_confirmed_candidate_skip"
  }
}
```

검증 결과, 대표 프레임 1장만 저장됐고 VLM/RAG/LLM 호출 없이 `NONE` 보고서로 종료됐다.

## 범위와 다음 점검

- 이번 구현은 업로드형 동영상 분석과 실시간 스트림에서 재사용할 수 있는 정책/게이트를 제공한다.
- 웹캠 RTSP/WebSocket 연결, 큐잉, cooldown, 다중 카메라, backpressure는 아직 구현하지 않았다. 이는 별도 Sprint 5의 `연속 요청/실시간 프레임 처리용 큐잉·백프레셔·인메모리 파이프라인 설계` 태스크에서 처리한다.
- confidence 임계값은 추가 라벨 데이터와 동영상 평가셋이 생긴 뒤 재실험한다. 현재는 임계값을 임의로 바꾸지 않고 호출 빈도만 정책으로 제어했다.
- 다음 순서는 `VLM Structured Output 스키마 재검증 및 스트리밍 확장 대비 contract 정리`다. 여기서 VLM의 `immediate_dangers` 자유 텍스트와 RAG 쿼리 계약을 함께 정리한다.
"""


if __name__ == "__main__":
    create_dev_log(
        TITLE,
        CONTENT,
        sprint="Sprint 5",
        categories="Detection,Video Processing,VLM Trigger,FastAPI,Testing",
    )
