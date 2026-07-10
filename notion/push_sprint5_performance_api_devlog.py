"""Post Sprint 5 latency/API-contract completion devlog to Notion."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from notion.notion_logger import create_dev_log


TITLE = "2026-07-10 | Sprint 5 최종 - YOLO/VLM 성능·병목 실측 및 FastAPI 공개 계약"

CONTENT = r"""## 완료 범위
Sprint 5의 마지막 두 항목을 실제 동일 이미지와 실제 Gemini/RAG 경로로 검증했다.

1. `파이프라인 속도 향상 - 단계별 병목 분석 및 최적화`
2. `FastAPI /docs 응답 스키마 명세 및 결과 JSON 검증·필터링 강화`

## YOLO-only vs VLM-assisted 최종 점검
실험 이미지: `datasets/construction-ppe/images/test/image1.jpeg`.

### 품질 비교의 경계
- YOLO: 테스트 라벨이 있으므로 클래스별 Precision/Recall/F1로 평가할 수 있다. 기존 Hansung 모델 결과에서 helmet F1=0.793, no-helmet F1=0.217, vest F1=0.698이며, 약한 위반 클래스는 VLM 검토 대상으로 유지한다.
- VLM 결합 경로: 현재 데이터셋에는 장면 이해/worker-PPE 연결/위험 판단의 정답 라벨이 없다. 따라서 VLM F1을 임의로 만들지 않았다. 대신 구조화 파싱, worker 수, `unknown`/가림 계약, 위험 근거, 최종 보고서 생성 여부를 기능 품질 지표로 기록했다.

이번 실험에서 YOLO는 5개 객체를 탐지했고 그중 3개가 VLM 검토 후보였다. VLM 결합 경로는 worker, structured danger, RAG 조항, SafetyReport를 모두 생성했다. 이 결과는 VLM이 YOLO box F1을 높였다는 뜻이 아니라, YOLO의 불확실한 위반 후보를 장면 맥락·근거·보고서로 확장하는 별도 역할을 수행한다는 확인이다.

## 단계별 병목 실험
`python -m detection.experiments.pipeline_benchmark datasets/construction-ppe/images/test/image1.jpeg --warm-runs 3 --pipeline-runs 2`

| 구간 | 1회차 cold | 2회차 warm | 결론 |
| --- | ---: | ---: | --- |
| YOLO 모델 로드+첫 추론 | 644.8 ms | - | 가중치 로드 비용 |
| YOLO warm 추론 평균 | - | 19.3 ms | 실제 프레임 처리 기준 |
| Detection | 19.0 ms | 24.2 ms | 전체 지연의 비지배 항목 |
| VLM Gemini | 14.69 s | 14.91 s | 외부 API 지연 |
| RAG | 26.44 s | 34.8 ms | bge-m3/Chroma cold start가 원인 |
| LLM Gemini | 19.32 s | 18.10 s | warm 상태 최대 병목 |
| 전체 | 60.47 s | 33.07 s | warm 서버 기준 약 45% 감소 |

### 적용한 개선
1. `detection.detector.load_model()`을 `lru_cache(maxsize=2)`로 변경했다. 같은 weight 파일은 프로세스 생명주기 동안 재사용된다. 실측상 cold 644.8 ms에서 warm 평균 19.3 ms로, 요청마다 불필요했던 모델 초기화를 제거했다.
2. `api.main._run_pipeline()`에 `metrics.total_ms`, `metrics.stages_ms`를 저장했다. 이후 결과 JSON과 `/results`에서 단계별 지연을 확인할 수 있다.
3. RAG의 embedder, Chroma collection, parent store는 기존 프로세스 전역 캐시를 그대로 활용한다. 실험에서 첫 검색 26.44초가 두 번째 검색 34.8ms로 감소했다. 운영 배포에서는 worker startup warm-up으로 이 cold start를 첫 사용자 요청에서 분리하는 것이 다음 우선순위다.
4. 스트림은 이미 2개 연속 후보 프레임 gate, 10초 cooldown, bounded queue(3), queue-full drop을 적용한다. 빈 프레임과 일시적인 후보는 VLM/LLM까지 보내지 않는다.

### 비동기화 판단
`VLM -> RAG -> LLM`은 데이터 의존성이 있다. LLM은 VLM 분석과 그로부터 만든 canonical RAG query/근거 조항을 받아야 하므로, VLM과 LLM을 병렬 호출하면 grounded citation 계약이 깨진다. 현재는 queue worker가 `asyncio.to_thread`로 동기 파이프라인을 event loop 밖에서 실행하므로 API 상태 조회와 업로드는 막지 않는다.

다음 최적화 후보는 (a) 앱 시작 시 YOLO/RAG warm-up, (b) provider별 rate-limit backoff/재시도 지표, (c) 실제 운영 부하에서 duplicate image 결과 캐시, (d) 스트림 FPS/confirmation/cooldown 재튜닝이다. 지금 단계에서 VLM/LLM을 무조건 병렬화하거나 RAG context를 무근거로 줄이지는 않는다.

## FastAPI 공개 응답 계약
`api/schemas.py`에 Pydantic response model을 추가하고 `/docs`에 다음 구조를 명시했다.

- `GET /health`: queue 용량과 accepted/dropped/rejected 운영 지표
- `POST /upload`: job id, media type, queue position
- `GET /status/{job_id}`: public job status
- `GET /results/{job_id}`: Detection/VLM/RAG/LLM/Report/Notion/metrics의 typed response

`/results`는 저장된 내부 JSON을 그대로 반환하지 않는다. allow-list + Pydantic validation을 거쳐 다음을 차단한다.

- 로컬 `image_path`, representative-frame path, result path
- traceback과 provider 내부 오류 문자열
- RAG `text`, `parent_text`, `doc_id`, canonical query/query trace 등 내부 검색 세부 정보
- Notion page id 등 불필요한 내부 식별자

저장된 결과가 public contract를 만족하지 않으면 generic 500을 반환하며, 실패 job은 서버 로그/trace 대신 일반화된 failed response만 반환한다. 이는 클라이언트가 깨진 JSON을 받는 문제와 경로/로그 노출 위험을 함께 줄인다.

## 검증
- `python -m unittest discover -s tests -p "test_*.py" -v`: 22/22 PASS.
- 신규 API contract 테스트: OpenAPI에 result/status schema가 노출되는지, public response에서 path/traceback/RAG 원문/page id가 제외되는지 확인.
- `python -m compileall api detection/experiments/pipeline_benchmark.py`: PASS.
- `git diff --check`: PASS.

## 산출물
- `outputs/results/final_pipeline_benchmark.json`: cold/warm YOLO 및 두 full pipeline run의 stage timing.
- `outputs/results/final_pipeline_benchmark_1.json`, `_2.json`: 각 실험의 원본 내부 결과와 stage metrics.
- `api/schemas.py`, `tests/test_api_contract.py`, `detection/experiments/pipeline_benchmark.py`.
"""


if __name__ == "__main__":
    create_dev_log(
        TITLE,
        CONTENT,
        sprint="Sprint 5",
        categories="Performance,Bottleneck,YOLO,VLM,RAG,LLM,FastAPI,OpenAPI,Security,Testing",
    )
