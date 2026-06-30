# VLM-Based Industrial Safety Monitoring Pipeline

[![Notion Dashboard](https://img.shields.io/badge/Notion-Dashboard-black?logo=notion)](https://fuzzy-wildebeest-406.notion.site/VLM-Safety-Monitor-38d73d4932e0807e9e35df13c2611834?source=copy_link)

> A three-stage AI pipeline (Detection → VLM → LLM) for automated industrial safety monitoring, inspired by real-world solutions in the computer vision AI industry.

---

## Overview

This project implements an end-to-end pipeline that analyzes workplace images to detect PPE (Personal Protective Equipment) violations and automatically generates safety inspection reports.

The pipeline is designed to mirror real-world industrial safety AI systems, with each stage clearly separated by responsibility:

| Stage | Model | Role |
|---|---|---|
| Detection | YOLO (pretrained) | Detect workers and PPE items |
| Understanding | VLM API | Interpret the scene contextually |
| Reporting | LLM API | Generate structured safety reports |
| Storage | Notion API | Auto-save reports to Notion DB |

---

## Pipeline Architecture

The system operates in a hybrid, resource-optimized 6-step process:

**1. Input & Real-Time Monitoring (Detection Model)**
- Image or video frames are fed into the system.
- The local object detection model continuously monitors frames with minimal latency.
- If a potential anomaly or PPE violation is suspected (e.g., a person detected without a helmet or vest), it triggers the heavier VLM/LLM cloud pipeline to save costs.

**2. Metadata Extraction (Detection Model)**
- The detection model detects workers and PPE items, outputting bounding boxes, classes, and confidence scores.
- Rather than cropping the image (which destroys surrounding context), it generates a structured text summary of the detections (e.g., `Worker 1 (helmet: ✗, vest: ✓), Worker 2 (helmet: ✓, vest: ✓)`).

**3. VLM Contextual Analysis (Method 2)**
- Send the **original image** and the **detection model-extracted text metadata** together to the Vision-Language Model (VLM).
- VLM interprets the full scene contextually (e.g., "Worker 1 is standing close to a heavy machinery danger zone without a helmet") while avoiding small-object detection hallucinations by relying on the detection model's pre-filter.

**4. LLM Report Generation**
- Receive VLM scene description as input
- Classify violation types (Missing PPE / Danger zone access / Abnormal behavior)
- Determine severity (High / Medium / Low)
- Generate actionable recommendations based on standard operating procedures (SOP)

**5. Result Storage**
- Save complete pipeline output as a JSON file (detection results + VLM output + LLM report)
- Automatically log results to the connected Notion Database

**6. HTML Result Dashboard**
- Display the processed image with drawn bounding boxes
- Display the VLM situation description
- Display the final LLM report (Violations / Severity / Actions)

---

## Tech Stack

- **Detection:** Pretrained Object Detection Model (YOLO or others)
- **VLM:** Vision Language Model API
- **LLM:** Large Language Model API
- **Backend:** FastAPI
- **Frontend:** HTML (single page)
- **Storage:** Notion API + JSON
- **Language:** Python 3.10+

---

## Project Structure

```
vlm-safety-monitor/
├── detection/
│   ├── detector.py          # YOLO inference & bounding box drawing
│   └── weights/             # Pretrained YOLO weights (PPE)
├── vlm/
│   └── analyzer.py          # VLM API call & scene description
├── llm/
│   └── reporter.py          # LLM API call & report generation
├── notion/
│   └── uploader.py          # Notion API integration
├── api/
│   └── main.py              # FastAPI endpoints
├── frontend/
│   └── index.html           # Single page UI
├── outputs/
│   └── results/             # JSON result storage
├── assets/
│   └── sample_images/       # Test images
├── requirements.txt
└── README.md
```

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/your-username/vlm-safety-monitor.git
cd vlm-safety-monitor
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set environment variables

```bash
cp .env.example .env
```

```env
VLM_API_KEY=your_vlm_api_key
LLM_API_KEY=your_llm_api_key
NOTION_API_KEY=your_notion_api_key
NOTION_DATABASE_ID=your_notion_database_id
```

### 4. Run the server

```bash
uvicorn api.main:app --reload
```

### 5. Open the UI

```
http://localhost:8000
```

---

## Output Example

### Detection Result
```
[Worker 1] helmet: ✗  vest: ✓  gloves: ✗
[Worker 2] helmet: ✓  vest: ✓  gloves: ✓
[Worker 3] helmet: ✗  vest: ✗  gloves: ✗
```

### VLM Scene Description
```
Three workers detected in an industrial zone. 
Worker 1 and Worker 3 are not wearing helmets. 
Worker 3 is also missing a safety vest and approaching a restricted area.
```

### LLM Safety Report
```
[Safety Inspection Report]
- Date: 2026-06-29
- Violations Detected: 3
  · PPE Missing (Helmet): Worker 1, Worker 3
  · PPE Missing (Vest): Worker 3
  · Restricted Area Access: Worker 3
- Severity: HIGH
- Recommended Action:
  · Immediately halt Worker 3's activity
  · Issue PPE to Worker 1 and Worker 3 before resuming work
  · Reference: SOP Section 3.2 - Mandatory PPE Requirements
```

---

## Notion Integration

Each pipeline run automatically creates a new page in the connected Notion database, containing:

- Input image
- Detection summary
- VLM scene description
- Full LLM safety report
- Severity level & timestamp

---

## Design Decisions

**Why separate Detection and VLM?**
YOLO provides fast, precise bounding boxes but lacks contextual understanding. VLM adds scene-level reasoning on top of detection results, enabling nuanced descriptions that rule-based systems cannot produce.

**Why separate VLM and LLM?**
Raw VLM output is descriptive but unstructured. A dedicated LLM step refines this into a structured report with violation classification, severity scoring, and actionable recommendations aligned with SOP guidelines.

**Why Notion over a database?**
For a portfolio-scale project, Notion provides an immediately accessible, visually rich storage layer without requiring infrastructure setup, while demonstrating API integration skills.

---

## Sprints

| Sprint | Goal | Key Tasks |
|---|---|---|
| **Sprint 1** | **환경 세팅 및 탐지 모델 탐색** | - 개발 환경 구성 & Git 연격 저장소 연동<br>- 노션 API 연동용 로깅 스크립트 작성 및 테스트<br>- 사전 학습 객체 탐지 모델 탐색, 선정 및 로컬 가중치 다운로드 (모델 선결정)<br>- 선정된 모델 스펙에 맞춘 Roboflow/HuggingFace 테스트용 PPE 데이터셋 조사 및 다운로드<br>- 단독 탐지 모델 정밀 테스트, 임계값(Confidence) 분석 및 VLM 트리거 조건 수립 (애매한/미착용 감지 시 VLM 호출 조건 정의)<br>- OpenCV 연계 바운딩 박스 라벨 시각화 및 검증 스크립트 완성 |
| **Sprint 2** | **VLM/LLM 프롬프트 설계** | - OpenAI/Claude/Gemini VLM API 호출 모듈 작성<br>- 탐지 모델 메타데이터(클래스, 좌표, confidence) + 원본 이미지 결합 VLM 프롬프트 설계 (방식 2)<br>- VLM 구조적 출력(Structured Outputs/JSON) 적용<br>- 안전 수칙 가이드라인(SOP) 분석 및 LLM 보고서 매핑<br>- LLM 위험도 분류 & 대응조치 프롬프트 설계 |
| **Sprint 3** | **백엔드 및 Web UI 개발** | - FastAPI 뼈대 구축 및 의존성 주입 설계<br>- 탐지 모델 실시간 모니터링 기반 VLM 비동기 트리거링 및 전체 파이프라인 처리 API 개발<br>- 업로드 및 추론 대기 UI 개발 (Skeleton UI)<br>- 탐지 결과 이미지 & LLM 보고서 카드 UI 완성 |
| **Sprint 4** | **Notion 연동 및 통합** | - 노션 API 결과 페이지 생성 연동<br>- 마크다운 보고서 -> 노션 블록 변환기 개발<br>- 분석 이미지 노션 임베딩/링크 구현<br>- 전체 통합 테스트 및 예외 처리 |
| **Sprint 5** | **예외 처리 및 프롬프트 고도화** | - 객체 겹침(Occlusion) 감지 보정 로직<br>- VLM 환각(Hallucination) 방지 가드레일 설계<br>- 조도 변화 등에 따른 파이프라인 강건성 분석<br>- API 제한 초과(Rate Limit) 및 타임아웃 예외 처리 |
| **Sprint 6** | **강건성 검증 및 포트폴리오** | - 산업 현장별(건설, 물류 등) 테스트 데이터셋 확보 (50장 이상)<br>- 파이프라인 일괄 테스트 & 벤치마크 평가<br>- 최종 보고서 작성 & 리팩토링<br>- 포트폴리오용 노션 대시보드 마감 |

---

### Sprint 1: 탐지 모델 & 데이터셋 비교 검증 계획

#### 🔍 객체 탐지 모델 후보 (3종)
| 모델 클래스 | 특징 |
|---|---|
| `keremberke/yolov8m-protective-equipment-detection` | - 클래스: helmet, no_helmet, glove, no_glove, goggles, no_goggles 등 10개<br>- 특징: 착용/미착용 분리형 라벨 구조로 가장 풍부한 메타데이터 획득 가능 |
| `Hansung-Cho/yolov8-ppe-detection` | - 클래스: Hardhat, Safety Vest, Person<br>- 특징: 한국 건설 현장 기반 데이터셋 학습, FastAPI 연동 참고용 가이드 보유 |
| `Tanishjain9/yolov8n-ppe-detection-6classes` | - 클래스: Helmet, Vest, Gloves, Mask, Goggles, Shoes<br>- 특징: 6개 주요 클래스 지원, 리소스가 제한적인 엣지 디바이스용 경량(Nano) 모델 |

#### 📦 테스트 데이터셋 후보 (3종)
| 데이터셋 | 이미지 수 | 특징 |
|---|---|---|
| `Roboflow Hard Hat Workers v10` | 7,035장 | helmet/head/person 클래스를 지원하는 정형화된 클래식 데이터셋 |
| `Ultralytics Construction-PPE` | - | helmet, vest, gloves, boots 착용/미착용 동시 라벨링을 지원하는 2025년 최신 Find Skill.ai 데이터셋 |
| `keremberke/protective-equipment-detection` | - | 10개 클래스를 지원하여 Hugging Face 라이브러리에서 직접 로드 및 빠른 테스트 가능 |

---

### ⚙️ 신뢰도 기반 하이브리드 VLM 트리거 로직
비용 절감과 객체 식별 정확도 극대화를 위해 시스템은 다음과 같은 조건부 트리거링 로직을 수행합니다.

```
이미지 입력 ➔ 탐지 모델 (PPE 감지) ➔ [분기 처리]
  ├─ Confidence가 충분히 높음 (예: > 0.8) ➔ 탐지 결과 자체로 확정 (VLM 호출 스킵, 비용 절감)
  └─ Confidence가 애매하고 낮음 (예: 0.3 ~ 0.8) ➔ 원본 이미지 + 탐지 텍스트 메타데이터 결합 ➔ VLM 재판단
                                                                     ↓
                                                            LLM 리포트 생성
```

---

## Future Work

- Real-time video stream support
- Multi-camera input handling
- Fine-tuned VLM on industrial safety datasets
- Dashboard with violation trend analytics

---

## License

MIT License