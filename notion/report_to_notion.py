"""notion/report_to_notion.py - SafetyReport Pydantic → 노션 블록 변환 + 자동 페이지 생성.

Sprint 4 태스크 2: 구조화 데이터를 노션 블록(Heading, Table, Paragraph, Quote, Callout)으로 변환.
Sprint 4 태스크 1: 파이프라인 완료 시 결과 페이지 자동 생성 연동.

변환 구조:
  Callout: 종합 심각도 + 검사일자
  Paragraph: 요약
  Heading 3 + Image: 바운딩박스 이미지(있을 경우)
  Heading 2: 탐지된 위반 → Table(근로자/위반유형/심각도/설명)
  Heading 2: 권고 조치 → Bulleted list
  Heading 2: 법령 인용(RAG) → Quote 블록들
  Heading 2: VLM 장면 분석 → Paragraph + Callout(즉각위험)
  Heading 2: 파이프라인 메타데이터 → Table(단계/지연/토큰/모델)
"""
import os
import mimetypes
import requests
from datetime import date as current_date
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=True, encoding="utf-8-sig")

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_REPORT_PARENT_PAGE_ID = os.getenv("NOTION_REPORT_PARENT_PAGE_ID")
NOTION_REPORT_DATABASE_ID = os.getenv("NOTION_REPORT_DATABASE_ID")
NOTION_TITLE_PROPERTY = os.getenv("NOTION_REPORT_TITLE_PROPERTY", "Name")
NOTION_DATE_PROPERTY = os.getenv("NOTION_REPORT_DATE_PROPERTY", "Date")
HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": os.getenv("NOTION_API_VERSION", "2026-03-11"),
}

SEVERITY_COLOR = {"HIGH": "red_background", "MEDIUM": "yellow_background",
                  "LOW": "blue_background", "NONE": "green_background"}
VIOLATION_TYPE_LABEL = {"missing_ppe": "PPE 미착용", "danger_zone_access": "위험구역 출입",
                        "abnormal_behavior": "이상 행동", "equipment_misuse": "장비 오용", "none": "이상 없음"}
PRIORITY_LABEL = {"immediate": "즉시", "high": "높음", "medium": "보통", "low": "낮음"}
MAX_RICH_TEXT_LEN = 1900
MAX_BLOCKS_PER_REQUEST = 100


def _clip(content: Any, limit: int = MAX_RICH_TEXT_LEN) -> str:
    text = "" if content is None else str(content)
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _text(content: str) -> dict:
    return {"type": "text", "text": {"content": _clip(content)}}


def _bold_text(content: str) -> dict:
    return {"type": "text", "text": {"content": _clip(content)}, "annotations": {"bold": True}}


def _heading2(text: str) -> dict:
    return {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [_text(text)]}}


def _heading3(text: str) -> dict:
    return {"object": "block", "type": "heading_3", "heading_3": {"rich_text": [_text(text)]}}


def _paragraph(rich_texts: List[dict]) -> dict:
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": rich_texts}}


def _bulleted(rich_texts: List[dict]) -> dict:
    return {"object": "block", "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": rich_texts}}


def _quote(rich_texts: List[dict]) -> dict:
    return {"object": "block", "type": "quote", "quote": {"rich_text": rich_texts}}


def _callout(rich_texts: List[dict], color: str = "blue_background", emoji: str = "⚠️") -> dict:
    return {"object": "block", "type": "callout",
            "callout": {"rich_text": rich_texts, "color": color,
                        "icon": {"type": "emoji", "emoji": emoji}}}


def _table_block(headers: List[str], rows: List[List[str]]) -> dict:
    """테이블 블록 (create_devlog.py make_table_block 패턴 재사용)."""
    cells = [{"object": "block", "type": "table_row",
              "table_row": {"cells": [[_text(h)] for h in headers]}}]
    for row in rows:
        cells.append({"object": "block", "type": "table_row",
                      "table_row": {"cells": [[_text(str(c))] for c in row]}})
    return {"object": "block", "type": "table",
            "table": {"table_width": len(headers), "has_column_header": True,
                      "has_row_header": False, "children": cells}}


def _image_block(url: str, caption: str = "") -> dict:
    """external 이미지 블록 (바운딩박스 이미지 임베딩용 - 태스크 3)."""
    block = {"object": "block", "type": "image",
             "image": {"type": "external", "external": {"url": url}}}
    if caption:
        block["image"]["caption"] = [_text(caption)]
    return block


def _uploaded_image_block(file_upload_id: str, caption: str = "") -> dict:
    block = {"object": "block", "type": "image",
             "image": {"type": "file_upload", "file_upload": {"id": file_upload_id}}}
    if caption:
        block["image"]["caption"] = [_text(caption)]
    return block


def upload_file_to_notion(file_path: str) -> Dict[str, Any]:
    """Upload a local file to Notion-managed storage and return the file_upload id."""
    path = Path(file_path)
    if not path.exists():
        return {"success": False, "error": f"파일 없음: {file_path}"}
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"

    try:
        create_res = requests.post(
            "https://api.notion.com/v1/file_uploads",
            json={},
            headers=HEADERS,
            timeout=30,
        )
        if create_res.status_code != 200:
            return {"success": False, "error": f"Create file upload {create_res.status_code}: {create_res.text[:300]}"}
        upload = create_res.json()
        upload_url = upload.get("upload_url")
        upload_id = upload.get("id")
        if not upload_url or not upload_id:
            return {"success": False, "error": "Notion file_upload 응답에 upload_url/id 없음"}

        with path.open("rb") as fh:
            send_headers = {
                "Authorization": f"Bearer {NOTION_API_KEY}",
                "Notion-Version": HEADERS["Notion-Version"],
            }
            send_res = requests.post(
                upload_url,
                headers=send_headers,
                files={"file": (path.name, fh, mime_type)},
                timeout=60,
            )
        if send_res.status_code != 200:
            return {"success": False, "error": f"Send file upload {send_res.status_code}: {send_res.text[:300]}"}
        sent = send_res.json()
        if sent.get("status") != "uploaded":
            return {"success": False, "error": f"File upload status={sent.get('status')}"}
        return {"success": True, "file_upload_id": upload_id, "filename": path.name, "content_type": mime_type}
    except requests.RequestException as exc:
        return {"success": False, "error": f"Notion file upload failed: {exc}"}


def _divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def _enum_value(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return getattr(value, "value", str(value))


def report_to_blocks(report: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None,
                     image_url: Optional[str] = None,
                     image_file_upload_id: Optional[str] = None) -> List[dict]:
    """SafetyReport(dict) + 메타데이터 → 노션 블록 리스트 변환."""
    blocks: List[dict] = []
    date = report.get("date", "")
    severity = _enum_value(report.get("overall_severity", "NONE"), "NONE")
    summary = report.get("summary", "요약 없음")
    violations = report.get("violations", [])
    actions = report.get("recommended_actions", [])
    citations = report.get("citations", [])

    # 1. 종합 심각도 + 요약 (Callout)
    color = SEVERITY_COLOR.get(severity, "gray_background")
    emoji = "🚨" if severity == "HIGH" else ("⚠️" if severity in ("MEDIUM", "LOW") else "✅")
    blocks.append(_callout(
        [_bold_text(f"종합 심각도: {severity}"), _text(f"  |  검사 일자: {date}")],
        color=color, emoji=emoji))
    blocks.append(_paragraph([_text(summary)]))

    # 2. 현장 포착 원본 이미지 (있을 경우)
    if image_file_upload_id or image_url:
        blocks.append(_heading3("📷 현장 포착 이미지"))
        if image_file_upload_id:
            blocks.append(_uploaded_image_block(image_file_upload_id, "현장 포착 원본 이미지"))
        else:
            blocks.append(_image_block(image_url, "현장 포착 이미지"))

    # 3. 탐지된 위반 (테이블)
    if violations:
        blocks.append(_heading2("탐지된 위반"))
        rows = [[v.get("worker_id", "-"),
                 VIOLATION_TYPE_LABEL.get(_enum_value(v.get("violation_type")), _enum_value(v.get("violation_type"), "-")),
                 _enum_value(v.get("severity", "-"), "-"),
                 v.get("description", "-")[:200]] for v in violations]
        blocks.append(_table_block(["근로자", "위반 유형", "심각도", "설명"], rows))

    # 4. 권고 조치 (불릿 리스트)
    if actions:
        blocks.append(_heading2("권고 조치"))
        for a in actions:
            prio = PRIORITY_LABEL.get(_enum_value(a.get("priority")), _enum_value(a.get("priority", "-"), "-"))
            blocks.append(_bulleted([
                _bold_text(f"[{prio}] "), _text(f"{a.get('action', '')} "),
                _text(f"(대상: {a.get('target', '-')})")]))

    # 5. 법령 인용 (Quote 블록들)
    if citations:
        blocks.append(_heading2("법령 인용 (RAG 기반)"))
        blocks.append(_paragraph([_text("환각 방지: 검색된 규정 조항에서만 인용")]))
        for c in citations:
            blocks.append(_quote([
                _bold_text(f"{c.get('source', '')} · {c.get('clause', '')}\n"),
                _text(f'"{c.get("quote", "")}"')]))

    # 6. VLM 장면 분석 (있을 경우)
    vlm = metadata.get("vlm") if metadata else None
    if vlm and vlm.get("parsed"):
        parsed = vlm["parsed"]
        blocks.append(_heading2("VLM 장면 분석"))
        blocks.append(_paragraph([_text(parsed.get("overall_description", ""))]))
        from vlm.schema import danger_descriptions
        dangers = danger_descriptions(parsed.get("immediate_dangers", []))
        if dangers:
            blocks.append(_callout([_bold_text("즉각 위험: "), _text(", ".join(dangers))],
                                   color="red_background", emoji="🚨"))

    # 7. 파이프라인 메타데이터 (테이블)
    if metadata:
        blocks.append(_heading2("파이프라인 메타데이터"))
        meta_rows = [["YOLO 탐지", "-", f"{len(metadata.get('detection', {}).get('detections', []))}개 객체", "-"]]
        if vlm:
            meta_rows.append(["VLM 분석", f"{vlm.get('latency_ms', '-')}ms",
                              f"{vlm.get('prompt_tokens', 0)}+{vlm.get('output_tokens', 0)} 토큰", "Gemini 2.5"])
        else:
            meta_rows.append(["VLM 분석", "스킵", "-", "-"])
        llm = metadata.get("llm")
        if llm:
            meta_rows.append(["LLM 보고서", f"{llm.get('latency_ms', '-')}ms",
                              f"{llm.get('prompt_tokens', 0)}+{llm.get('output_tokens', 0)} 토큰", "Gemini 2.5"])
        rag = metadata.get("rag")
        if rag:
            meta_rows.append(["RAG 검색", "-", f"{rag.get('retrieved_count', 0)}건", "bge-m3+Chroma"])
        blocks.append(_table_block(["단계", "지연 시간", "토큰/건수", "모델"], meta_rows))

    return blocks


def _append_blocks(page_id: str, blocks: List[dict]) -> Optional[str]:
    for start in range(0, len(blocks), MAX_BLOCKS_PER_REQUEST):
        chunk = blocks[start:start + MAX_BLOCKS_PER_REQUEST]
        res = requests.patch(
            f"https://api.notion.com/v1/blocks/{page_id}/children",
            json={"children": chunk},
            headers=HEADERS,
            timeout=20,
        )
        if res.status_code != 200:
            return f"Notion append API {res.status_code}: {res.text[:300]}"
    return None


def create_safety_report_page(job_id: str, result: Dict[str, Any],
                              image_url: Optional[str] = None,
                              image_path: Optional[str] = None) -> Dict[str, Any]:
    """파이프라인 완료 시 노션에 안전 검사 보고서 페이지 자동 생성 (태스크 1).

    result: api/main.py 파이프라인 결과 dict (report/detection/vlm/llm/rag 포함)
    image_url: 바운딩박스 이미지 GitHub raw URL (있을 경우)
    반환: {"success": bool, "page_url": str, "page_id": str} 또는 {"success": False, "error": str}
    """
    if not NOTION_API_KEY:
        return {"success": False, "skipped": True, "error": "NOTION_API_KEY 미설정"}
    if not NOTION_REPORT_PARENT_PAGE_ID and not NOTION_REPORT_DATABASE_ID:
        return {"success": False, "skipped": True, "error": "NOTION_REPORT_PARENT_PAGE_ID 또는 NOTION_REPORT_DATABASE_ID 미설정"}

    report = result.get("report", {})
    if not report:
        return {"success": False, "error": "결과에 report 필드 없음"}

    metadata = {
        "detection": result.get("detection"),
        "vlm": result.get("vlm"),
        "llm": result.get("llm"),
        "rag": result.get("rag"),
    }
    image_upload = None
    if image_path:
        image_upload = upload_file_to_notion(image_path)
    image_file_upload_id = image_upload.get("file_upload_id") if image_upload and image_upload.get("success") else None
    blocks = report_to_blocks(
        report,
        metadata=metadata,
        image_url=image_url,
        image_file_upload_id=image_file_upload_id,
    )
    if image_upload and not image_upload.get("success"):
        blocks.insert(2, _paragraph([_text(f"포착 이미지 업로드 실패: {image_upload.get('error')}")]))

    generated_date = current_date.today().isoformat()
    title = f"{generated_date} | 안전검사 보고서 {job_id}"

    if NOTION_REPORT_PARENT_PAGE_ID:
        payload = {
            "parent": {"page_id": NOTION_REPORT_PARENT_PAGE_ID},
            "properties": {"title": {"title": [{"text": {"content": title}}]}},
            "children": blocks[:MAX_BLOCKS_PER_REQUEST],
        }
    else:
        payload = {
            "parent": {"database_id": NOTION_REPORT_DATABASE_ID},
            "properties": {NOTION_TITLE_PROPERTY: {"title": [{"text": {"content": title}}]}},
            "children": blocks[:MAX_BLOCKS_PER_REQUEST],
        }

    if NOTION_REPORT_DATABASE_ID and not NOTION_REPORT_PARENT_PAGE_ID:
        payload["properties"][NOTION_DATE_PROPERTY] = {"date": {"start": generated_date}}

    try:
        res = requests.post("https://api.notion.com/v1/pages", json=payload, headers=HEADERS, timeout=30)
    except requests.RequestException as exc:
        return {"success": False, "error": f"Notion request failed: {exc}"}

    if res.status_code == 200:
        data = res.json()
        append_error = _append_blocks(data["id"], blocks[MAX_BLOCKS_PER_REQUEST:])
        if append_error:
            return {"success": False, "page_url": data.get("url", ""), "page_id": data["id"], "error": append_error}
        response = {"success": True, "page_url": data.get("url", ""), "page_id": data["id"], "title": title}
        if image_upload:
            response["captured_image_upload"] = image_upload
        return response
    return {"success": False, "error": f"Notion API {res.status_code}: {res.text[:300]}"}


def append_report_screenshot(page_id: str, screenshot_url: Optional[str], local_path: str) -> Dict[str, Any]:
    """Append a rendered UI report screenshot reference to an existing Notion report page."""
    if not NOTION_API_KEY:
        return {"success": False, "skipped": True, "error": "NOTION_API_KEY 미설정"}
    if not page_id:
        return {"success": False, "skipped": True, "error": "Notion page_id 없음"}

    blocks = [_divider(), _heading2("UI 보고서 캡처")]
    upload = upload_file_to_notion(local_path) if local_path else {"success": False, "error": "local_path 없음"}
    if upload.get("success"):
        blocks.append(_uploaded_image_block(upload["file_upload_id"], "Web UI 결과 대시보드 캡처"))
    elif screenshot_url:
        blocks.append(_image_block(screenshot_url, "Web UI 결과 대시보드 캡처"))
        blocks.append(_paragraph([_text(f"Screenshot URL: {screenshot_url}")]))
    else:
        blocks.append(_paragraph([
            _text(f"UI 캡처 이미지 업로드 실패: {upload.get('error')}")
        ]))

    error = _append_blocks(page_id, blocks)
    if error:
        return {"success": False, "error": error}
    return {"success": True, "screenshot_url": screenshot_url, "local_path": local_path, "file_upload": upload}


if __name__ == "__main__":
    # 단위 테스트: 목업 report로 블록 변환 + 페이지 생성
    import json
    mock = {
        "report": {
            "date": "2026-07-03",
            "overall_severity": "HIGH",
            "summary": "건설현장 검사 결과, Worker 2가 안전모·안전조끼 미착용 상태로 위험구역에 인접.",
            "violations": [
                {"worker_id": "Worker 1", "violation_type": "missing_ppe", "severity": "HIGH",
                 "description": "굴삭기 옆에서 안전모 미착용 상태로 작업 중."},
                {"worker_id": "Worker 2", "violation_type": "danger_zone_access", "severity": "HIGH",
                 "description": "위험구역 경계선 인접 이동."},
            ],
            "recommended_actions": [
                {"action": "Worker 2의 위험구역 진입 즉시 중단, 보호구 착용 지시.", "priority": "immediate", "target": "Worker 2"},
                {"action": "전 근로자 보호구 상시 착용 교육.", "priority": "high", "target": "전 근로자"},
            ],
            "citations": [
                {"source": "산업안전보건법", "clause": "제98조제1항",
                 "quote": "사업주는 근로자에게 보호구를 지급하고 사용하게 하여야 한다."},
            ],
        },
        "detection": {"detections": [{"class_name": "Person"}, {"class_name": "NO-Hardhat"}]},
        "vlm": {"parsed": {"overall_description": "건설현장에서 두 근로자가 작업 중.",
                           "immediate_dangers": ["Worker 2 위험구역 인접"]},
                "latency_ms": 4200, "prompt_tokens": 850, "output_tokens": 320},
        "llm": {"latency_ms": 16344, "prompt_tokens": 3185, "output_tokens": 1392},
        "rag": {"retrieved_count": 5},
    }
    result = create_safety_report_page("test_job_001", mock)
    print(json.dumps(result, indent=2, ensure_ascii=False))
