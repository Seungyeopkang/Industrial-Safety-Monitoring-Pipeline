"""Post Sprint 5 streaming operations and queue completion devlog."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from notion.notion_logger import create_dev_log


TITLE = "2026-07-10 | Sprint 5 - 스트리밍 운영 콘솔 및 bounded queue/backpressure 완성"

CONTENT = r"""## 범위 결정
Sprint 5의 Detection 후속 항목 중 반복 실험이 필요한 Occlusion 보정과 실내/외·조도 강건성 평가는 보류했다. 이번 배치는 구현으로 닫을 수 있는 두 운영 태스크만 대상으로 했다.

- 실시간 스트리밍 확장에 맞춘 UI 운영 콘솔 / Notion 보고서 포지셔닝 재정의
- 연속 요청/실시간 프레임 처리용 큐잉·백프레셔·인메모리 파이프라인 설계

## 1. Bounded Queue 및 Backpressure

기존에는 업로드와 확정 스트림 이벤트가 `BackgroundTasks`로 즉시 실행돼, 연속 요청이 들어오면 YOLO/GPU와 VLM/LLM/Notion 호출이 동시에 겹칠 수 있었다.

`api/main.py`에 크기 3의 `asyncio.Queue`와 단일 worker를 추가했다.

- 업로드 이미지/동영상과 확정된 웹캠 이벤트는 동일 대기열에 등록
- worker는 한 번에 한 job만 `asyncio.to_thread(_run_pipeline, ...)`으로 실행
- 일반 업로드: 큐가 가득 차면 HTTP 429로 즉시 거절하고 저장 직후 파일을 정리
- 스트림 이벤트: 큐가 가득 차면 프레임 파일을 만들지 않고 `stream_queue_full_dropped`로 드롭
- `/health`는 `pending`, `capacity`, `accepted`, `dropped`, `rejected`를 반환
- job 상태는 `queued -> dequeued -> detection -> ... -> complete`로 유지

이 정책은 안전 이벤트의 보고서 생성은 순서대로 보장하면서, 연속 프레임 전체를 쌓아 서버가 멈추는 상황을 막는다. 고속 스트림은 최신 프레임을 계속 보내되, 큐 포화 때에는 미확정 프레임을 저장하지 않고 드롭한다.

## 2. In-memory Stream 처리

웹캠 프레임은 `POST /stream/frame/{stream_id}`에서 JPEG bytes로 받고 메모리에서만 decode한다.

- YOLO 모델은 stream session마다 1회 로드
- 2 FPS 전송, VLM 후보 연속 2프레임 확인
- 10초 cooldown으로 동일 이벤트의 반복 보고서 방지
- 무탐지 프레임은 `stream_no_detection_skip`으로 끝나며 디스크 기록 없음
- 확정 이벤트 한 장만 `outputs/uploads`에 저장한 뒤 queue에 넣음

## 3. UI와 Notion 역할 분리

업로드 화면에 운영 상태를 추가했다.

- 대기열: `pending / capacity`, 드롭 수를 3초마다 `/health`에서 표시
- 스트림 이벤트: 프레임 스킵, 큐 포화 드롭, 보고서 job id를 표시
- 카메라 시작/중지, 영상 업로드 미리보기는 기존 흐름을 유지

Notion은 라이브 화면을 복제하는 곳이 아니라 **확정 이벤트의 최종 안전 보고서, 원본/결과 캡처, 감사 기록**으로 유지한다. 실시간 판단과 대기열 가시성은 Web UI가 담당한다.

## 검증

1. `python -m unittest discover -s tests -p "test_*.py" -v`
   - 총 6개 통과
   - bounded queue가 가득 찬 경우 새 업로드에 429를 반환하는 정책 고정
   - 이미지/스트림 무탐지 정책, 연속 후보, 영상 대표 프레임 선택 회귀 테스트 통과
2. 최신 FastAPI 서버 `/health`
   - `pending=0`, `capacity=3`, accepted/dropped/rejected 지표 반환 확인
3. 무탐지 JPEG를 실제 `/stream/frame/queue-check`에 전송
   - `detections=0`, `vlm_dispatch=false`, `reason=stream_no_detection_skip` 확인
   - 스트림 세션 DELETE 정리 확인

## 제외 및 다음 순서

- `객체 겹침(Occlusion) 상황의 감지 오류 보정 로직 구현`: 라벨 데이터와 오류 사례가 필요한 실험 태스크로 보류
- `실내/외 및 조도 변화에 따른 파이프라인 강건성 분석`: 조건별 평가셋과 반복 측정이 필요한 실험 태스크로 보류

운영 기반을 닫았으므로 다음 코어 파이프라인 작업은 `VLM Structured Output 스키마 재검증 및 스트리밍 확장 대비 contract 정리`다.
"""


if __name__ == "__main__":
    create_dev_log(TITLE, CONTENT, sprint="Sprint 5", categories="Streaming,Queue,Backpressure,FastAPI,Web UI,Notion,Testing")
