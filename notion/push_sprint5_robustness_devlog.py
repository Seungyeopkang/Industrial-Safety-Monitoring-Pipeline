"""Post synthetic occlusion and lighting robustness evaluation results."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from notion.notion_logger import create_dev_log


TITLE = "2026-07-10 | Sprint 5 - 합성 Occlusion·조도 강건성 평가 및 보정 판단"

CONTENT = r"""## 목표와 범위
기존 YOLO 모델을 재학습하지 않고, 현재 보유한 두 테스트셋의 원본 이미지와 정답 라벨에 합성 변형을 적용해 PPE 탐지의 강건성을 평가했다.

- Construction-PPE test: 141장
- Hard Hat Workers test: 706장
- 총 847장, 14개 조건, 3개 라벨 클래스, 84개 metric 행 생성

이 결과는 **합성 조건 강건성 평가**다. 현재 데이터에는 실내/실외 정답 메타데이터가 없으므로 실제 환경 일반화 성능으로 해석하지 않는다.

## 실험 설계

### Occlusion
- background / PPE 직접 가림 / 사람 전경 가림 3종
- 각 가림 유형에 25%, 50%, 75% 수준 적용
- 고정 SHA-256 기반 seed로 이미지와 조건마다 동일한 변형을 재현

### 조도·열화
- baseline, low_light, glare, high_contrast, jpeg_artifact
- 변형 전후 라벨은 동일하게 유지
- class별 Precision/Recall/F1과 VLM trigger rate 기록

## 라벨 범위와 한계
현재 데이터셋의 정답 라벨은 `helmet`, `no_helmet`, `vest`에 한정된다. 따라서 `NO-Mask`, `NO-Safety Vest`의 재현율은 직접 계산할 수 없다.

- 라벨 지원 클래스: F1/Recall/Precision 정량 평가
- 미지원 위반 클래스: detector/VLM trigger 빈도와 대표 실패 사례만 추적
- worker-PPE 연결 오류: 데이터에 person-PPE association 정답이 없어 자동 분류 불가

이 제한은 숨기지 않고 결과 manifest에 명시했다.

## 핵심 결과

### Construction-PPE
- baseline 평균 F1: 0.5578
- low_light: -0.0115p, glare: -0.0329p, high_contrast: -0.0356p, jpeg_artifact: -0.0027p
- PPE 직접 가림 50%: -0.1751p
- 사람 전경 가림 50%: -0.2072p
- 심한 사람 가림에서 helmet Recall: 0.7604 -> 0.4740

### Hard Hat Workers
- baseline 평균 F1: 0.2914 (도메인/클래스 매핑 차이를 포함한 낮은 기준선)
- low_light/glare는 큰 하락이 없었음
- JPEG artifact: -0.0647p
- PPE 직접 가림 25~75%: 약 -0.0706~-0.0753p
- 사람 전경 가림 50~75%: 약 -0.0880~-0.0889p

### VLM 호출 영향
Occlusion이 커질수록 Construction-PPE VLM trigger rate는 baseline 0.7943에서 PPE 가림 50% 0.9220, 사람 가림 75% 0.9007까지 상승했다. 탐지 불확실성이 커질수록 VLM 검증 경로가 더 자주 선택되는 현재 정책이 실제로 작동함을 확인했다.

## 오류 유형 및 보정 판단

실패 분석 CSV에는 `miss`, `duplicate_detection`, `false_positive`를 기록했다. 가장 큰 반복 오류는 Hard Hat Workers의 helmet miss와 duplicate detection, 그리고 Construction-PPE의 사람/PPE 직접 가림 조건에서의 miss였다.

**이번 단계에서는 heuristic 보정 로직을 추가하지 않는다.**

근거:
- 가림 문제는 특정 bbox 규칙 하나로 안정적으로 복구할 수 있는 오류가 아니라 시각 정보 자체가 사라지는 경우가 많음
- 잘못된 worker-PPE 연결은 현재 데이터에 association 정답이 없어 자동 보정 규칙을 검증할 수 없음
- 대신 심한 가림/낮은 confidence는 기존 VLM trigger 경로로 보내고, 향후 VLM schema에서 `unknown`과 occlusion metadata를 명시적으로 표현하는 것이 더 안전함

## 산출물

- `detection/experiments/robustness_evaluate.py`: 전체 평가 재실행 스크립트
- `outputs/robustness/metrics.csv`: 84개 class-condition metric
- `outputs/robustness/failure_analysis.csv`: image-level 실패 유형
- `outputs/robustness/failure_samples/`: 원본 변형+GT/pred 대표 이미지 168장
- `outputs/robustness/run_manifest.json`: 조건과 한계

## Worker 4 보고서 표현
Worker 4의 두 PPE 카드는 중복이 아니라 안전조끼 미착용과 마스크 미착용이라는 서로 다른 위반이다. 현재 `Violation` 스키마가 PPE 종류를 구조화하지 않아 UI가 모두 "PPE 미착용"으로 표시한다. 이 표현 개선은 다음 VLM/LLM report contract 태스크에서 `ppe_items`와 동일 worker·동일 PPE 중복 제거 규칙으로 처리한다.
"""


if __name__ == "__main__":
    create_dev_log(TITLE, CONTENT, sprint="Sprint 5", categories="Detection,Occlusion,Robustness,Computer Vision,Testing")
