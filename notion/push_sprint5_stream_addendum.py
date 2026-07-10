"""Post a short Notion addendum for the live camera stream implementation."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from notion.notion_logger import create_dev_log


if __name__ == "__main__":
    create_dev_log(
        "2026-07-10 | Sprint 5 Addendum - 브라우저 카메라 스트림 입력 연결",
        r"""## 추가 구현
동영상 업로드형 프레임 게이트에 이어, 브라우저 카메라 입력을 같은 정책으로 연결했다.

- `POST /stream/frame/{stream_id}`: JPEG 프레임을 메모리에서 디코딩하고 YOLO + 연속 2프레임 게이트만 실행
- `DELETE /stream/{stream_id}`: 카메라 세션 모델/상태 해제
- `detection/live_stream.py`: 세션당 YOLO 모델 1회 로드, 10초 cooldown 적용
- `frontend/index.html`: 카메라 시작/중지와 2 FPS JPEG 캡처 전송 추가

## 디스크 정책
무탐지, 미확정 후보, cooldown 중인 프레임은 파일로 저장하지 않는다. 연속 후보가 확정된 이벤트만 JPEG 한 장으로 저장하고 기존 YOLO → VLM → RAG → LLM → Notion 작업을 시작한다.

## 현재 경계
이 구현은 단일 브라우저 카메라의 이벤트 게이트다. 다중 카메라 공정성, 작업 큐, GPU semaphore, 백프레셔, 재시작 복구는 후속 큐잉/백프레셔 태스크에서 별도로 다룬다.
""",
        sprint="Sprint 5",
        categories="Streaming,Detection,VLM Trigger,FastAPI,Web UI",
    )
