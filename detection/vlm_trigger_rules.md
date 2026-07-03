# VLM Trigger Rules (Confidence-Based Hybrid Pipeline)

## 설계 원칙: 안전 최우선 (Safety-First)
이 파이프라인은 산업 안전 모니터링이므로 **안전이 최우선**이다. 위반 가능성이 있는 경우에는 비용을 들여서라도 VLM으로 보정한다. 거짓 긍정(false positive)은 감내하되, 거짓 부정(false negative, 위반 누락)은 절대 허용하지 않는다.

## 기본 구조
- 베이스는 YOLO 1차 탐지 (빠르고 저렴, 로컬)
- 1차 탐지 신뢰도가 충분히 높으면 VLM 호출을 스킵해 비용 절감
- 신뢰도가 애매하면 VLM API로 맥락 보정
- **위반 클래스(NO-Hardhat/NO-Safety Vest/NO-Mask)는 신뢰도와 무관하게 항상 VLM 호출**

## 실험적 근거 (experiments/trigger_threshold_experiment.py)
- 샘플: Construction-PPE test 10장, 총 68개 탐지
- confidence 분포: min 0.257 / median 0.785 / mean 0.703 / max 0.939
- 위반 클래스 탐지: NO-Mask 8, NO-Hardhat 1, NO-Safety Vest 1 = 10개 (항상 트리거)

## 트리거 규칙 (실험 기반 확정)

| 신뢰도(confidence) 구간 | 동작 | 이유 |
|---|---|---|
| conf 0.60 이상 | VLM 호출 스킵 | 1차 탐지 신뢰도 충분, 비용 절감 |
| conf 0.30 ~ 0.60 | VLM API 호출 (원본 이미지 + 메타데이터) | 애매한 구간, VLM으로 맥락 보정 |
| conf 0.30 미만 | 해당 박스 무시 (노이즈) | 신뢰도 너무 낮아 false positive 위험 |

## 항상 트리거 조건 (안전 최우선)
- NO-Hardhat / NO-Safety Vest / NO-Mask 클래스가 감지된 경우: conf와 무관하게 **항상 VLM 호출**
  - 근거: 단독 탐지 모델의 no_helmet F1이 0.08 ~ 0.22로 극도로 낮아 신뢰할 수 없음
- Person 클래스만 감지되고 PPE 클래스가 전혀 없는 경우: VLM 호출 (PPE 상태 불명확)

## 임계값 선정 근거
| 후보 선 (high/low) | 트리거율 | 위반 트리거 | 비고 |
|---|---|---|---|
| 0.80 / 0.35 | 48.5% | 100% | 가장 보수적, 비용 높음 |
| 0.75 / 0.30 | 39.7% | 100% | 초기 설계값 |
| 0.70 / 0.25 | 36.8% | 100% | |
| 0.65 / 0.25 | 33.8% | 100% | |
| **0.60 / 0.30** | **27.9%** | **100%** | **채택: 위한 100% 유지하면서 비용 최소** |

모든 후보 선이 위반 100% 트리거를 유지하므로, 안전을 보장하면서 트리거율이 가장 낮은 0.60/0.30을 채택. (주의: high가 낮아질수록 일반 탐지의 VLM 검증 기회가 줄어드는 트레이드오프가 있으나, 위반 클래스는 무조건 트리거 규칙이 이를 보완함.)

## 출력 스키마
각 워커별: worker_id, bbox, classes, confidence, vlm_trigger (bool), trigger_reason (str)
