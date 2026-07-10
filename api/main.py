"""api/main.py - FastAPI 백엔드 (Sprint 3 Pass 1).

산업 안전 모니터링 파이프라인의 웹 진입점.
- GET  /            : 단일 페이지 UI(frontend/index.html) 서빙
- POST /upload      : 이미지 업로드 → 비동기 파이프라인 즉시 job_id 반환
- GET  /status/{id} : 잡 상태(queued/running/done/failed) 조회
- GET  /results/{id}: 최종 결과 JSON 반환
- GET  /annotated/{id}: 바운딩박스 오버레이 이미지 서빙
- GET  /health      : 헬스체크

파이프라인(BackgroundTasks 비동기):
  YOLO 탐지 → (위반 의심 시) VLM 분석 → RAG 검색 → LLM 보고서 생성 → JSON 저장
"""
import os
import time
import json
import uuid
import traceback
import base64
import asyncio
from datetime import date
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from pydantic import BaseModel
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
from api.schemas import (
    FailedResultResponse, HealthResponse, JobStatusResponse, PendingResultResponse, PipelineResultResponse,
    UploadResponse, public_job_status, public_pipeline_result,
)

# 프로젝트 루트를 sys.path에 추가 (모듈 임포트용)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

app = FastAPI(title="Industrial Safety Monitoring API", version="1.0.0")

# 디렉토리 구조
UPLOAD_DIR = PROJECT_ROOT / "outputs" / "uploads"
RESULTS_DIR = PROJECT_ROOT / "outputs" / "results"
ANNOTATED_DIR = PROJECT_ROOT / "outputs" / "annotated"
REPORT_SCREENSHOT_DIR = PROJECT_ROOT / "outputs" / "report_screenshots"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
NOTION_AUTO_EXPORT = os.getenv("NOTION_AUTO_EXPORT", "1").lower() not in {"0", "false", "no"}
for d in (UPLOAD_DIR, RESULTS_DIR, ANNOTATED_DIR, REPORT_SCREENSHOT_DIR):
    d.mkdir(parents=True, exist_ok=True)

# 메모리 잡 상태 저장 (포트폴리오 규모. 재시작 시 리셋)
JOBS: Dict[str, Dict[str, Any]] = {}
STREAMS: Dict[str, Any] = {}
PIPELINE_QUEUE: asyncio.Queue = asyncio.Queue(maxsize=3)
PIPELINE_WORKER_TASK = None
PIPELINE_METRICS = {"accepted": 0, "dropped": 0, "rejected": 0}


class ReportScreenshotPayload(BaseModel):
    image_data: str


def _set_status(job_id: str, status: str, **extra):
    """잡 상태 업데이트."""
    JOBS.setdefault(job_id, {}).update({"status": status, "updated_at": time.time(), **extra})


async def _pipeline_worker():
    """Run one expensive YOLO/VLM/RAG/LLM job at a time from a bounded queue."""
    while True:
        job_id, image_path, media_type = await PIPELINE_QUEUE.get()
        try:
            _set_status(job_id, "running", stage="dequeued", message="처리 슬롯 확보")
            await asyncio.to_thread(_run_pipeline, job_id, image_path, media_type)
        finally:
            PIPELINE_QUEUE.task_done()


async def _enqueue_pipeline(job_id: str, image_path: str, media_type: str) -> int:
    if PIPELINE_QUEUE.full():
        raise HTTPException(status_code=429, detail="처리 대기열이 가득 찼습니다. 잠시 후 다시 시도하세요.")
    await PIPELINE_QUEUE.put((job_id, image_path, media_type))
    PIPELINE_METRICS["accepted"] += 1
    position = PIPELINE_QUEUE.qsize()
    _set_status(job_id, "queued", stage="queued", message="대기열 등록", queue_position=position)
    return position


@app.on_event("startup")
async def start_pipeline_worker():
    global PIPELINE_WORKER_TASK
    if PIPELINE_WORKER_TASK is None or PIPELINE_WORKER_TASK.done():
        PIPELINE_WORKER_TASK = asyncio.create_task(_pipeline_worker())


def _run_pipeline(job_id: str, image_path: str, media_type: str = "image"):
    """백그라운드 파이프라인: YOLO → VLM → RAG → LLM → 저장.
    잡 상태를 단계별로 갱신하여 프론트엔드가 진행 상황을 표시할 수 있도록 함."""
    started_at = time.perf_counter()
    stage_started_at = started_at
    stages_ms: Dict[str, float] = {}

    def finish_stage(stage: str) -> None:
        nonlocal stage_started_at
        now = time.perf_counter()
        stages_ms[stage] = round((now - stage_started_at) * 1000, 1)
        stage_started_at = now

    result: Dict[str, Any] = {"job_id": job_id}
    video_vlm_confirmed = True
    if media_type == "video":
        # Decode/sample in memory; persist only the one representative frame.
        try:
            from detection.video import select_video_frame
            import cv2
            selection = select_video_frame(image_path)
            representative_path = UPLOAD_DIR / f"{job_id}_selected.jpg"
            cv2.imwrite(str(representative_path), selection["frame"])
            image_path = str(representative_path)
            video_vlm_confirmed = selection["confirmed"]
            result["media"] = {
                "type": "video",
                "representative_frame_path": image_path,
                "representative_frame_index": selection["frame_index"],
                "sampled_frames": selection["sampled_frames"],
                "source_fps": selection["source_fps"],
                "sample_fps": selection["sample_fps"],
                "confirmation_frames": selection["confirmation_frames"],
                "confirmed_candidate": video_vlm_confirmed,
                "selection_reason": selection["selection_reason"],
            }
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"
            _set_status(job_id, "failed", stage="error", message=err)
            (RESULTS_DIR / f"{job_id}.json").write_text(
                json.dumps({"job_id": job_id, "error": err}, ensure_ascii=False), encoding="utf-8"
            )
            return
    else:
        result["media"] = {"type": media_type}
    try:
        # 1) YOLO 탐지
        _set_status(job_id, "running", stage="detection", message="YOLO 객체 탐지 중")
        from detection.detector import run_detection
        det_out, annotated = run_detection(image_path)
        finish_stage("detection")
        detections = det_out["detections"]
        import cv2
        annotated_path = ANNOTATED_DIR / f"{job_id}_annotated.jpg"
        cv2.imwrite(str(annotated_path), annotated)
        result["detection"] = {
            "model": det_out["model"],
            "detections": detections,
            "summary": det_out["summary"],
        }
        _set_status(job_id, "running", stage="detection_done", message=f"탐지 완료: {len(detections)}개 객체")

        # VLM 트리거 여부 판단 (위반 클래스 또는 애매한 신뢰도)
        needs_vlm = any(d.get("vlm_trigger") for d in detections) or len(detections) == 0
        if not needs_vlm:
            classes = {d.get("class_name") for d in detections}
            if classes and classes <= {"Person"}:
                needs_vlm = True

        # Empty frames are expected in video/stream inputs. A VLM event must
        # also have survived the consecutive-frame confirmation gate.
        if media_type == "video":
            needs_vlm = needs_vlm and video_vlm_confirmed
        result["vlm_dispatch"] = {
            "should_dispatch": needs_vlm,
            "reason": (
                "consecutive_candidate_confirmed"
                if media_type == "video" and video_vlm_confirmed and needs_vlm
                else "video_no_confirmed_candidate_skip"
                if media_type == "video" and not video_vlm_confirmed
                else "image_trigger_policy"
            ),
        }

        if not needs_vlm:
            _set_status(job_id, "running", stage="skipped_vlm", message="신뢰도 높음: VLM 스킵")
            result["vlm"] = None
            result["llm"] = None
            result["rag"] = {"retrieved_count": 0, "clauses": []}
            result["report"] = {
                "date": date.today().isoformat(),
                "violations": [],
                "overall_severity": "NONE",
                "recommended_actions": [],
                "citations": [],
                "summary": "명백한 위반 미탐지(VLM 스킵).",
            }
        else:
            # 2) VLM 분석
            _set_status(job_id, "running", stage="vlm", message="VLM 장면 분석 중(Gemini API)")
            from vlm.analyzer import analyze_scene
            vlm_res = analyze_scene(image_path, detections, prompt_variant="role_constraints", temperature=0.0)
            finish_stage("vlm")
            result["vlm"] = {
                "parsed": vlm_res["parsed"].model_dump(),
                "latency_ms": vlm_res["latency_ms"],
                "prompt_tokens": vlm_res["prompt_tokens"],
                "output_tokens": vlm_res["output_tokens"],
            }
            _set_status(job_id, "running", stage="vlm_done", message="VLM 분석 완료")

            # 3) RAG 검색 (위반 설명 → 한국 규정 조항)
            _set_status(job_id, "running", stage="rag", message="RAG 규정 조항 검색 중")
            from rag.retriever import retrieve_for_query_records
            from rag.danger_contract import eligible_danger_records
            from rag.query_builder import build_canonical_queries
            parsed_vlm = vlm_res["parsed"]
            danger_contract = eligible_danger_records(parsed_vlm.immediate_dangers)
            canonical_queries = build_canonical_queries(parsed_vlm.workers, danger_contract)
            try:
                retrieval = retrieve_for_query_records(canonical_queries) if canonical_queries else {
                    "clauses": [], "query_traces": []
                }
                clauses = retrieval["clauses"]
                rag_status = "complete" if clauses else "no_relevant_context"
                result["rag"] = {
                    "status": rag_status,
                    "retrieved_count": len(clauses),
                    "clauses": clauses,
                    "danger_contract": danger_contract,
                    "canonical_queries": canonical_queries,
                    "query_traces": retrieval["query_traces"],
                }
                finish_stage("rag")
                _set_status(job_id, "running", stage="rag_done",
                            message=f"RAG 검색 완료: {len(clauses)}건 ({rag_status})")
            except Exception as rag_exc:
                # The report can still describe the scene, but it must receive no
                # clauses and therefore cannot cite regulations without evidence.
                clauses = []
                result["rag"] = {
                    "status": "unavailable",
                    "retrieved_count": 0,
                    "clauses": [],
                    "danger_contract": danger_contract,
                    "canonical_queries": canonical_queries,
                    "query_traces": [],
                    "error": f"{type(rag_exc).__name__}: {rag_exc}",
                }
                finish_stage("rag")
                _set_status(job_id, "running", stage="rag_unavailable",
                            message="RAG unavailable: 근거 법령 인용 없이 보고서 생성")

            # 4) LLM 보고서 생성
            _set_status(job_id, "running", stage="llm", message="LLM 안전 보고서 생성 중(Gemini API)")
            from llm.reporter import generate_report
            llm_res = generate_report(
                parsed_vlm,
                retrieved_clauses=clauses,
                prompt_variant="sop_grounded",
                temperature=0.0,
                report_date=date.today().isoformat(),
            )
            finish_stage("llm")
            result["llm"] = {
                "parsed": llm_res["parsed"].model_dump(),
                "latency_ms": llm_res["latency_ms"],
                "prompt_tokens": llm_res["prompt_tokens"],
                "output_tokens": llm_res["output_tokens"],
                "retrieved_count": llm_res["retrieved_count"],
            }
            result["report"] = llm_res["parsed"].model_dump()
            _set_status(job_id, "running", stage="llm_done", message="LLM 보고서 완료")

        # 5) Notion 결과 페이지 자동 생성 (실패해도 분석 결과는 유지)
        if result.get("report") and NOTION_AUTO_EXPORT:
            _set_status(job_id, "running", stage="notion", message="Notion 안전 보고서 저장 중")
            try:
                from notion.report_to_notion import create_safety_report_page
                image_url = f"{PUBLIC_BASE_URL}/annotated/{job_id}" if PUBLIC_BASE_URL else None
                result["notion"] = create_safety_report_page(
                    job_id,
                    result,
                    image_url=image_url,
                    image_path=str(image_path),
                )
                finish_stage("notion")
                if result["notion"].get("success"):
                    _set_status(job_id, "running", stage="notion_done", message="Notion 보고서 저장 완료")
                elif result["notion"].get("skipped"):
                    _set_status(job_id, "running", stage="skipped_notion", message="Notion 설정 없음: 저장 스킵")
                else:
                    _set_status(job_id, "running", stage="notion_failed", message="Notion 저장 실패(결과 JSON에는 기록)")
            except Exception as notion_exc:
                result["notion"] = {"success": False, "error": f"{type(notion_exc).__name__}: {notion_exc}"}
                finish_stage("notion")
                _set_status(job_id, "running", stage="notion_failed", message="Notion 저장 실패(결과 JSON에는 기록)")
        else:
            result["notion"] = {"success": False, "skipped": True, "error": "NOTION_AUTO_EXPORT 비활성화 또는 report 없음"}
            _set_status(job_id, "running", stage="skipped_notion", message="Notion 저장 스킵")

        # 6) 결과 저장
        if "notion" not in stages_ms:
            stages_ms["notion"] = 0.0
        for stage in ("vlm", "rag", "llm"):
            stages_ms.setdefault(stage, 0.0)
        result["metrics"] = {
            "total_ms": round((time.perf_counter() - started_at) * 1000, 1),
            "stages_ms": stages_ms,
        }
        result_path = RESULTS_DIR / f"{job_id}.json"
        result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        _set_status(job_id, "done", stage="complete", message="파이프라인 완료",
                    result_path=str(result_path), annotated_path=str(annotated_path))

    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        tb = traceback.format_exc()[:800]
        _set_status(job_id, "failed", stage="error", message=err, traceback=tb)
        try:
            (RESULTS_DIR / f"{job_id}.json").write_text(
                json.dumps({"job_id": job_id, "error": err, "traceback": tb}, indent=2, ensure_ascii=False),
                encoding="utf-8")
        except Exception:
            pass


# --- 엔드포인트 ---

@app.get("/health", response_model=HealthResponse)
async def health():
    return {
        "status": "ok",
        "jobs_active": sum(1 for j in JOBS.values() if j.get("status") in ("queued", "running")),
        "queue": {"pending": PIPELINE_QUEUE.qsize(), "capacity": PIPELINE_QUEUE.maxsize, **PIPELINE_METRICS},
    }


@app.get("/", response_class=HTMLResponse)
async def index():
    """단일 페이지 UI 서빙."""
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        return HTMLResponse("<h1>frontend/index.html not found</h1>", status_code=404)
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


@app.post("/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...)):
    """이미지 업로드 → 비동기 파이프라인 시작 → job_id 즉시 반환."""
    if not file.content_type or not (file.content_type.startswith("image/") or file.content_type.startswith("video/")):
        raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다.")
    job_id = uuid.uuid4().hex[:12]
    media_type = "video" if file.content_type.startswith("video/") else "image"
    max_upload_bytes = 100 * 1024 * 1024 if media_type == "video" else 10 * 1024 * 1024
    if file.size is not None and file.size > max_upload_bytes:
        raise HTTPException(status_code=413, detail="파일 크기 제한을 초과했습니다.")
    ext = Path(file.filename or ("upload.mp4" if media_type == "video" else "upload.jpg")).suffix
    if not ext:
        ext = ".mp4" if media_type == "video" else ".jpg"
    save_path = UPLOAD_DIR / f"{job_id}{ext}"
    save_path.write_bytes(await file.read())
    _set_status(job_id, "queued", stage="queued", message="대기 중",
                filename=file.filename, image_path=str(save_path))
    try:
        queue_position = await _enqueue_pipeline(job_id, str(save_path), media_type)
    except HTTPException:
        save_path.unlink(missing_ok=True)
        PIPELINE_METRICS["rejected"] += 1
        raise
    JOBS[job_id].update(filename=file.filename, image_path=str(save_path))
    return {"job_id": job_id, "status": "queued", "filename": file.filename,
            "media_type": media_type, "queue_position": queue_position}


@app.post("/stream/frame/{stream_id}")
async def process_stream_frame(stream_id: str, file: UploadFile = File(...)):
    """Accept one browser camera frame; only confirmed events enter the pipeline."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="스트림 프레임은 이미지여야 합니다.")
    payload = await file.read()
    if len(payload) > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="스트림 프레임은 2MB 이하여야 합니다.")
    from detection.live_stream import LiveStreamSession
    session = STREAMS.get(stream_id)
    if session is None:
        session = LiveStreamSession()
        STREAMS[stream_id] = session
    frame, _, detection, decision, should_dispatch = await asyncio.to_thread(session.process_jpeg, payload)
    response = {
        "stream_id": stream_id,
        "detections": len(detection["detections"]),
        "vlm_dispatch": should_dispatch,
        "reason": decision.reason,
    }
    if should_dispatch:
        if PIPELINE_QUEUE.full():
            PIPELINE_METRICS["dropped"] += 1
            response.update({"vlm_dispatch": False, "reason": "stream_queue_full_dropped", "dropped": True})
            return response
        import cv2
        job_id = uuid.uuid4().hex[:12]
        frame_path = UPLOAD_DIR / f"{job_id}_stream.jpg"
        cv2.imwrite(str(frame_path), frame)
        _set_status(job_id, "queued", stage="queued", message="스트림 이벤트 분석 대기", image_path=str(frame_path))
        queue_position = await _enqueue_pipeline(job_id, str(frame_path), "stream")
        JOBS[job_id].update(stream_id=stream_id, image_path=str(frame_path))
        response.update({"job_id": job_id, "queue_position": queue_position})
    return response


@app.delete("/stream/{stream_id}")
async def close_stream(stream_id: str):
    STREAMS.pop(stream_id, None)
    return {"stream_id": stream_id, "closed": True}


@app.get("/status/{job_id}", response_model=JobStatusResponse)
async def status(job_id: str):
    """잡 상태 조회."""
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="잡을 찾을 수 없습니다.")
    return public_job_status(job_id, JOBS[job_id])


@app.get("/results/{job_id}", response_model=PipelineResultResponse | PendingResultResponse | FailedResultResponse)
async def results(job_id: str):
    """최종 결과 JSON 반환."""
    result_path = RESULTS_DIR / f"{job_id}.json"
    if not result_path.exists():
        if job_id in JOBS:
            return PendingResultResponse(
                job_id=job_id,
                status=JOBS[job_id].get("status", "failed"),
                message=JOBS[job_id].get("message", ""),
            )
        raise HTTPException(status_code=404, detail="결과를 찾을 수 없습니다.")
    try:
        raw = json.loads(result_path.read_text(encoding="utf-8"))
        if raw.get("error"):
            return FailedResultResponse(job_id=job_id)
        return public_pipeline_result(raw)
    except Exception:
        raise HTTPException(status_code=500, detail="Stored result did not satisfy the public response contract.")


@app.get("/annotated/{job_id}")
async def annotated(job_id: str):
    """바운딩박스 오버레이 이미지 서빙."""
    annotated_path = ANNOTATED_DIR / f"{job_id}_annotated.jpg"
    if not annotated_path.exists():
        raise HTTPException(status_code=404, detail="주석 이미지를 찾을 수 없습니다.")
    return FileResponse(str(annotated_path), media_type="image/jpeg")


@app.get("/report-screenshots/{job_id}")
async def report_screenshot(job_id: str):
    """UI 결과 대시보드 캡처 이미지 서빙."""
    screenshot_path = REPORT_SCREENSHOT_DIR / f"{job_id}_report.png"
    if not screenshot_path.exists():
        raise HTTPException(status_code=404, detail="보고서 캡처 이미지를 찾을 수 없습니다.")
    return FileResponse(str(screenshot_path), media_type="image/png")


@app.post("/report-screenshot/{job_id}")
async def upload_report_screenshot(job_id: str, payload: ReportScreenshotPayload):
    """프론트엔드에서 렌더링된 결과 대시보드 캡처를 저장하고 Notion 보고서에 첨부."""
    result_path = RESULTS_DIR / f"{job_id}.json"
    if not result_path.exists():
        raise HTTPException(status_code=404, detail="결과를 찾을 수 없습니다.")

    prefix = "data:image/png;base64,"
    image_data = payload.image_data
    if image_data.startswith(prefix):
        image_data = image_data[len(prefix):]
    try:
        image_bytes = base64.b64decode(image_data, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"캡처 이미지 디코딩 실패: {exc}")

    screenshot_path = REPORT_SCREENSHOT_DIR / f"{job_id}_report.png"
    screenshot_path.write_bytes(image_bytes)

    result = json.loads(result_path.read_text(encoding="utf-8"))
    screenshot_url = f"{PUBLIC_BASE_URL}/report-screenshots/{job_id}" if PUBLIC_BASE_URL else None
    notion_result = {"success": False, "skipped": True, "error": "Notion page_id 없음"}
    page_id = (result.get("notion") or {}).get("page_id")
    if page_id:
        try:
            from notion.report_to_notion import append_report_screenshot
            notion_result = append_report_screenshot(page_id, screenshot_url, str(screenshot_path))
        except Exception as exc:
            notion_result = {"success": False, "error": f"{type(exc).__name__}: {exc}"}

    result["ui_report_screenshot"] = {
        "local_path": str(screenshot_path),
        "url": screenshot_url,
        "notion": notion_result,
    }
    result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result["ui_report_screenshot"]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=False)
