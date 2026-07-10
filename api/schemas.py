"""Public FastAPI request/response contracts and response allow-lists."""
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class QueueInfo(APIModel):
    pending: int = Field(ge=0)
    capacity: int = Field(ge=1)
    accepted: int = Field(ge=0)
    dropped: int = Field(ge=0)
    rejected: int = Field(ge=0)


class HealthResponse(APIModel):
    status: Literal["ok"]
    jobs_active: int = Field(ge=0)
    queue: QueueInfo


class UploadResponse(APIModel):
    job_id: str
    status: Literal["queued"]
    filename: Optional[str] = None
    media_type: Literal["image", "video"]
    queue_position: int = Field(ge=0)


class JobStatusResponse(APIModel):
    job_id: str
    status: Literal["queued", "running", "done", "failed"]
    stage: str
    message: str
    queue_position: Optional[int] = Field(default=None, ge=0)
    updated_at: float = Field(ge=0)


class DetectionItem(APIModel):
    class_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: List[float] = Field(min_length=4, max_length=4)
    vlm_trigger: bool
    trigger_reason: str


class DetectionResult(APIModel):
    model: str
    detections: List[DetectionItem]
    summary: List[str]


class MediaResult(APIModel):
    type: Literal["image", "video", "stream"]
    representative_frame_index: Optional[int] = None
    sampled_frames: Optional[int] = Field(default=None, ge=0)
    source_fps: Optional[float] = Field(default=None, ge=0)
    sample_fps: Optional[float] = Field(default=None, gt=0)
    confirmation_frames: Optional[int] = Field(default=None, ge=1)
    confirmed_candidate: Optional[bool] = None
    selection_reason: Optional[str] = None


class VLMDispatch(APIModel):
    should_dispatch: bool
    reason: str


class WorkerResult(APIModel):
    worker_id: str
    helmet: Literal["worn", "missing", "unknown"]
    vest: Literal["worn", "missing", "unknown"]
    mask: Literal["worn", "missing", "unknown"]
    gloves: Literal["worn", "missing", "unknown"]
    location_description: str
    activity: str
    proximity_to_hazard: str
    visibility: Literal["clear", "partial", "occluded", "unknown"]
    occlusion_level: Literal["none", "partial", "severe", "unknown"]


class DangerResult(APIModel):
    danger_type: Literal["missing_ppe", "fall_risk", "danger_zone_access", "vehicle_strike_risk", "electrical_risk", "caught_between_risk", "fire_risk", "unknown"]
    worker_ids: List[str]
    description: str
    evidence: str
    confidence: float = Field(ge=0.0, le=1.0)


class SceneContextResult(APIModel):
    work_zone_type: str
    machinery_present: List[str]
    environmental_hazards: List[str]
    lighting_condition: str


class VLMParsedResult(APIModel):
    workers: List[WorkerResult]
    scene_context: SceneContextResult
    overall_description: str
    immediate_dangers: List[DangerResult]
    analysis_limitations: List[str]
    vlm_confidence: float = Field(ge=0.0, le=1.0)


class VLMResult(APIModel):
    parsed: VLMParsedResult
    latency_ms: float = Field(ge=0)
    prompt_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class ClauseResult(APIModel):
    source: str
    article: str
    title: str
    score: float = Field(ge=0.0, le=1.0)


class RAGResult(APIModel):
    status: Literal["complete", "no_relevant_context", "unavailable"]
    retrieved_count: int = Field(ge=0)
    clauses: List[ClauseResult]


class ViolationResult(APIModel):
    worker_id: str
    violation_type: str
    severity: Literal["HIGH", "MEDIUM", "LOW", "NONE"]
    description: str


class ActionResult(APIModel):
    action: str
    priority: Literal["immediate", "high", "medium", "low"]
    target: str


class CitationResult(APIModel):
    source: str
    clause: str
    quote: str


class ReportResult(APIModel):
    date: str
    violations: List[ViolationResult]
    overall_severity: Literal["HIGH", "MEDIUM", "LOW", "NONE"]
    recommended_actions: List[ActionResult]
    citations: List[CitationResult]
    summary: str


class LLMResult(APIModel):
    latency_ms: float = Field(ge=0)
    prompt_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    retrieved_count: int = Field(ge=0)


class PipelineMetrics(APIModel):
    total_ms: float = Field(ge=0)
    stages_ms: Dict[str, float]


class NotionResult(APIModel):
    success: bool
    skipped: bool = False
    page_url: Optional[str] = None


class PipelineResultResponse(APIModel):
    job_id: str
    media: MediaResult
    detection: DetectionResult
    vlm_dispatch: VLMDispatch
    vlm: Optional[VLMResult] = None
    rag: RAGResult
    llm: Optional[LLMResult] = None
    report: ReportResult
    notion: NotionResult
    metrics: PipelineMetrics


class PendingResultResponse(APIModel):
    job_id: str
    status: Literal["queued", "running", "failed"]
    message: str


class FailedResultResponse(APIModel):
    job_id: str
    status: Literal["failed"] = "failed"
    message: str = "Pipeline failed. Inspect server logs for details."


def public_job_status(job_id: str, job: Dict[str, Any]) -> JobStatusResponse:
    """Allow-list transient state; local paths and tracebacks remain internal."""
    return JobStatusResponse(job_id=job_id, status=job.get("status", "failed"),
                             stage=job.get("stage", "unknown"), message=job.get("message", ""),
                             queue_position=job.get("queue_position"), updated_at=job.get("updated_at", 0.0))


def public_pipeline_result(raw: Dict[str, Any]) -> PipelineResultResponse:
    """Validate and reduce a persisted internal result to the public contract."""
    media = dict(raw.get("media") or {})
    media.pop("representative_frame_path", None)
    rag = raw.get("rag") or {}
    clauses = [{key: item.get(key, "") for key in ("source", "article", "title", "score")}
               for item in rag.get("clauses", [])]
    llm = raw.get("llm")
    return PipelineResultResponse.model_validate({
        "job_id": raw.get("job_id"), "media": media, "detection": raw.get("detection"),
        "vlm_dispatch": raw.get("vlm_dispatch"),
        "vlm": ({key: value for key, value in (raw.get("vlm") or {}).items()
                 if key in {"parsed", "latency_ms", "prompt_tokens", "output_tokens"}} if raw.get("vlm") else None),
        "rag": {"status": rag.get("status", "unavailable"), "retrieved_count": rag.get("retrieved_count", 0), "clauses": clauses},
        "llm": ({key: value for key, value in llm.items()
                 if key in {"latency_ms", "prompt_tokens", "output_tokens", "retrieved_count"}} if llm else None),
        "report": raw.get("report"),
        "notion": {key: value for key, value in (raw.get("notion") or {}).items()
                   if key in {"success", "skipped", "page_url"}},
        "metrics": raw.get("metrics"),
    })
