"""VLM Scene Analysis Schema (Pydantic) - Method 2 (이미지 + 탐지 메타데이터).

비전-언어 모델은 원본 이미지와 탐지 모델이 추출한 메타데이터(클래스, 바운딩박스,
신뢰도)를 함께 입력받아 구조화된 장면 이해를 생성. 이는 하위 LLM이 안전 검사
보고서로 정제하는 입력이 됨.

※ enum 값(코드값)은 API 호환성을 위해 영어 그대로 유지, 설명은 한국어.
   자유 텍스트 필드는 한국어 출력을 유도.
"""
from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field


class PPEStatus(str, Enum):
    WORN = "worn"
    MISSING = "missing"
    UNKNOWN = "unknown"


class WorkerAnalysis(BaseModel):
    worker_id: str = Field(description="탐지 요약과 일치하는 식별자, 예: 'Worker 1'.")
    helmet: PPEStatus = Field(description="해당 근로자의 헬멧(안전모) 착용 상태.")
    vest: PPEStatus = Field(description="해당 근로자의 안전조끼 착용 상태.")
    mask: PPEStatus = Field(default=PPEStatus.UNKNOWN, description="마스크 착용 상태, 보이지 않으면 unknown.")
    gloves: PPEStatus = Field(default=PPEStatus.UNKNOWN, description="장갑 착용 상태, 보이지 않으면 unknown.")
    location_description: str = Field(description="장면 내 근로자의 위치(한국어).")
    activity: str = Field(description="근로자가 하는 것으로 보이는 작업(한국어).")
    proximity_to_hazard: str = Field(description="주변 위험/기계와의 거리·관계, 없으면 'none'(한국어).")


class SceneContext(BaseModel):
    work_zone_type: str = Field(description="산업 구역 유형, 예: 'construction', 'warehouse', 'manufacturing', 'outdoor site'.")
    machinery_present: List[str] = Field(default_factory=list, description="주변에서 탐지된 기계/차량/장비.")
    environmental_hazards: List[str] = Field(default_factory=list, description="위험 요소, 예: 'open edge', 'heavy machinery zone', 'restricted area', 'slip risk'.")
    lighting_condition: str = Field(description="조명 상태: 'good', 'poor', 'low-light', 'glare'.")


class VLMSceneAnalysis(BaseModel):
    """VLM 단계의 최상위 구조화 출력."""
    workers: List[WorkerAnalysis] = Field(description="근로자별 분석, 탐지된 인물당 1개 항목.")
    scene_context: SceneContext = Field(description="전체 장면 맥락 및 환경 요인.")
    overall_description: str = Field(description="전체 장면과 안전 우려에 대한 간결한 자연어 설명(한국어).")
    immediate_dangers: List[str] = Field(default_factory=list, description="즉각적 조치가 필요한 긴급 위험(한국어).")
    vlm_confidence: float = Field(description="이 분석에 대한 VLM 자체 신뢰도, 0.0~1.0.")
