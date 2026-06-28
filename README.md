# VLM-Based Industrial Safety Monitoring Pipeline

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

```
Image Input (via HTML upload)
        │
        ▼
┌─────────────────────┐
│   PPE Detection     │  ← Pretrained YOLO (helmet, vest, gloves)
│   (Bounding Box)    │
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│   VLM Analysis      │  ← Image + Detection result → Scene description
│   (Scene Context)   │     e.g. "2 out of 3 workers not wearing helmets"
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│   LLM Report        │  ← Classify violations, assess severity, suggest action
│   Generation        │     based on SOP guidelines
└─────────────────────┘
        │
        ▼
┌─────────────────────┐
│   Notion API        │  ← Auto-create report page in Notion DB
│   + JSON Storage    │
└─────────────────────┘
        │
        ▼
   HTML Result Page
```

---

## Tech Stack

- **Detection:** YOLOv8 (PPE pretrained weights)
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

| Sprint | Goal | Duration |
|---|---|---|
| Sprint 1 | PPE Detection pipeline | Week 1 |
| Sprint 2 | VLM + LLM integration & prompt tuning | Week 2 |
| Sprint 3 | FastAPI + HTML frontend | Week 3 |
| Sprint 4 | Notion integration + full pipeline test + docs | Week 4 |

---

## Future Work

- Real-time video stream support
- Multi-camera input handling
- Fine-tuned VLM on industrial safety datasets
- Dashboard with violation trend analytics

---

## License

MIT License