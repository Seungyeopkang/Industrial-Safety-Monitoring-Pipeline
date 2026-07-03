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

**1. Image Upload & Async Execution (Detection Model)**
- User uploads an image to the FastAPI backend.
- The local object detection model runs inference. If a potential anomaly or PPE violation is suspected (e.g., a person detected without a helmet or vest, or with ambiguous safety gear status), the system triggers the heavier VLM/LLM cloud pipeline asynchronously to keep the API responsive.

**2. Metadata Extraction (Detection Model)**
- The detection model detects workers and PPE items, outputting bounding boxes, classes, and confidence scores.
- Rather than cropping the image (which destroys surrounding context), it generates a structured text summary of the detections (e.g., `Worker 1 (helmet: ✗, vest: ✓), Worker 2 (helmet: ✓, vest: ✓)`).

**3. VLM Contextual Analysis (Method 2)**
- Send the **original image** and the **detection model-extracted text metadata** together to the Vision-Language Model (VLM).
- VLM interprets the full scene contextually (e.g., "Worker 1 is standing close to a heavy machinery danger zone without a helmet") while avoiding small-object detection hallucinations by relying on the detection model's pre-filter.

**4. LLM Report Generation & Structured Outputs**
- Receive VLM scene description as input.
- Classify violation types (Missing PPE / Danger zone access / Abnormal behavior) and determine severity (High / Medium / Low).
- Enforce strict JSON output format using **Pydantic schemas** (Structured Outputs) to guarantee schema compliance.
- Generate actionable recommendations based on standard operating procedures (SOP) **retrieved via RAG**.
- SOP documents (Korean safety regulations: 산업안전보건법·산업안전보건기준에 관한 규칙·KOSHA 안전보건가이드) are chunked, embedded, and stored in a local vector DB (Chroma). Relevant clauses are retrieved per violation and cited with actual section references, preventing hallucinated citations.

**5. Result Storage**
- Save complete pipeline output as a JSON file (detection results + VLM output + LLM report).
- Automatically log results to the connected Notion Database using structural mapping.

**6. HTML Result Dashboard**
- Display the uploaded image with drawn bounding boxes.
- Display the VLM situation description.
- Display the final structured LLM report (Violations / Severity / Actions).

---

## Tech Stack

- **Detection:** Pretrained Object Detection Model (YOLO or others)
- **VLM:** Vision Language Model API
- **LLM:** Large Language Model API
- **Backend:** FastAPI
- **Frontend:** HTML (single page)
- **RAG:** Local vector DB (Chroma) + bge-m3 (Korean-multilingual embedding) for Korean safety regulation (산업안전보건법·산안규·KOSHA) clause retrieval and citation
- **Storage:** Notion API + JSON
- **Language:** Python 3.10+

---

## Project Structure

```
vlm-safety-monitor/
├── detection/
│   ├── detector.py            # YOLO inference, OpenCV viz, VLM trigger logic
│   ├── vlm_trigger_rules.md   # Confidence-based VLM trigger spec
│   ├── experiments/         # Model benchmarking & evaluations
│   │   ├── benchmark.py
│   │   ├── evaluate.py
│   │   └── generate_report.py
│   └── weights/             # Pretrained YOLO weights (PPE)
├── vlm/
│   ├── analyzer.py            # VLM scene analysis (Method 2: image + detection metadata)
│   └── schema.py              # VLMSceneAnalysis Pydantic schema
├── llm/
│   ├── reporter.py            # LLM safety report generation (Structured Outputs)
│   └── schema.py              # SafetyReport Pydantic schema (with SOP citations)
├── experiments/
│   ├── prompt_optimization.py # VLM/LLM prompt variant comparison
│   └── visualize_prompt_opt.py# Results visualization
├── notion/
│   ├── notion_logger.py       # Notion API integration
│   ├── create_devlog.py     # Programmatic devlog creation
│   ├── update_progress.py   # Notion progress synchronization
│   └── archive/             # Archived/one-off utility scripts
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
NOTION_PAGE_ID=your_notion_page_id
NOTION_SPRINT_DB_ID=your_notion_sprint_db_id
NOTION_PREVIOUS_PAGE_ID=your_notion_previous_page_id
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

**Why RAG for SOP retrieval?**
Hardcoding SOP text in prompts risks fabricated citations (e.g., referencing non-existent sections). Retrieving relevant clauses from a local vector DB built on Korean safety regulations (산업안전보건법·산업안전보건기준에 관한 규칙·KOSHA 안전보건가이드) ensures every recommendation cites a real section, while naturally mitigating LLM hallucination - the LLM is constrained to cite only clauses present in the retrieved RAG context. A multilingual embedding model (bge-m3) is used so Korean-language queries retrieve Korean regulation clauses with high semantic accuracy.

---


## Future Work

- Real-time video stream support
- Multi-camera input handling
- Fine-tuned VLM on industrial safety datasets
- Dashboard with violation trend analytics

---

## License

MIT License