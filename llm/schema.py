"""LLM Safety Report Schema (Pydantic) - 구조화 출력 + RAG 기반 인용.

LLM은 VLM 장면 분석을 입력받아 구조화된 안전 검사 보고서를 생성:
위반 분류, 심각도 평가, 실행 가능한 권고 조치, 그리고 RAG로 검색된
한국 안전 규정(산업안전보건법·산안규·KOSHA 가이드) 조항 인용.

※ enum 값(코드값)은 API 호환성을 위해 영어 그대로 유지, 설명은 한국어.
"""
from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field


class ViolationType(str, Enum):
    MISSING_PPE = "missing_ppe"
    DANGER_ZONE_ACCESS = "danger_zone_access"
    ABNORMAL_BEHAVIOR = "abnormal_behavior"
    EQUIPMENT_MISUSE = "equipment_misuse"
    NONE = "none"


class Severity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NONE = "NONE"


class Priority(str, Enum):
    IMMEDIATE = "immediate"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Violation(BaseModel):
    worker_id: str = Field(description="해당 근로자 식별자. 근로자 특정이 아니면 'site-wide'.")
    violation_type: ViolationType = Field(description="위반 유형 분류.")
    severity: Severity = Field(description="해당 위반의 심각도 수준.")
    description: str = Field(description="위반 내용에 대한 사람이 읽기 쉬운 설명(한국어).")


class RecommendedAction(BaseModel):
    action: str = Field(description="상황을 시정하기 위한 구체적 권고 조치(한국어).")
    priority: Priority = Field(description="조치의 긴급도.")
    target: str = Field(description="조치 적용 대상, 예: 'Worker 3' 또는 '전 근로자'.")


class Citation(BaseModel):
    """SOP 인용 - 실제 파이프라인에서는 RAG 검색 결과에서 비롯됨.
    LLM이 검색 컨텍스트에 없는 조항을 지어내지 못하도록 스키마로 추적 가능한 참조를 강제."""
    source: str = Field(description="출처 권위, 예: '산업안전보건법 제98조' 또는 '산안규 제197조' 또는 'KOSHA 가이드'.")
    clause: str = Field(description="구체적 조항/조문 참조, 예: '제98조제1항'.")
    quote: str = Field(description="관련 요건의 짧은 직접 인용문(한국어).")


class SafetyReport(BaseModel):
    """LLM 단계의 최상위 구조화 출력 - 파이프라인 최종 산출물."""
    date: str = Field(description="검사 일자 ISO 날짜 문자열 YYYY-MM-DD.")
    violations: List[Violation] = Field(description="탐지된 모든 위반. 현장이 준수 중이면 빈 리스트(또는 NONE 항목 1개).")
    overall_severity: Severity = Field(description="전체 장면의 종합 심각도.")
    recommended_actions: List[RecommendedAction] = Field(description="우선순위가 부여된 시정 조치.")
    citations: List[Citation] = Field(default_factory=list, description="권고를 뒷받침하는 SOP 인용. 해당 없으면 빈 리스트.")
    summary: str = Field(description="검사 결과에 대한 한 단락 요약(한국어).")

