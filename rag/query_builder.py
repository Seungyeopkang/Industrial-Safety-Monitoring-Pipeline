"""Canonical, traceable RAG queries derived from detector/VLM contracts."""
from typing import Any, Dict, Iterable, List


PPE_QUERY_TEMPLATES = {
    "helmet": "안전모 보호구 착용 기준",
    "vest": "안전조끼 보호구 착용 기준",
    "mask": "호흡보호구 마스크 착용 기준",
    "gloves": "보호장갑 착용 기준",
}

PPE_REQUIRED_TERMS = {
    "helmet": ("안전모", "헬멧"),
    "vest": ("안전조끼", "반사조끼", "조끼"),
    "mask": ("마스크", "호흡보호구", "방진"),
    "gloves": ("보호장갑", "장갑"),
}

DANGER_QUERY_TEMPLATES = {
    "fall_risk": "고소 작업 추락 방지 조치",
    "danger_zone_access": "위험구역 출입 금지 조치",
    "vehicle_strike_risk": "건설기계 차량 충돌 방지 조치",
    "electrical_risk": "전기 작업 감전 방지 조치",
    "caught_between_risk": "끼임 협착 사고 방지 조치",
    "fire_risk": "화재 예방 및 소화 설비 조치",
}

DANGER_REQUIRED_TERMS = {
    "fall_risk": ("추락", "고소", "안전대"),
    "danger_zone_access": ("출입", "위험구역"),
    "vehicle_strike_risk": ("차량", "건설기계", "충돌"),
    "electrical_risk": ("전기", "감전", "전로"),
    "caught_between_risk": ("끼임", "협착"),
    "fire_risk": ("화재", "소화"),
}


def _value(item: Any, field: str, default: Any = None) -> Any:
    value = item.get(field, default) if isinstance(item, dict) else getattr(item, field, default)
    return getattr(value, "value", value)


def _append_unique(records: List[Dict[str, Any]], candidate: Dict[str, Any]) -> None:
    """Merge duplicate law queries while retaining every source worker for traceability."""
    for record in records:
        if record["query"] == candidate["query"] and record["origin"] == candidate["origin"]:
            record["worker_ids"] = sorted(set(record["worker_ids"]) | set(candidate["worker_ids"]))
            return
    records.append(candidate)


def build_canonical_queries(workers: Iterable[Any], danger_records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Create law-search queries without treating VLM prose as a search query.

    Missing PPE is sourced from the per-worker structured PPE status because a
    typed ``missing_ppe`` danger does not carry a reliable PPE kind. Contextual
    dangers are mapped only from their controlled ``danger_type``.
    """
    queries: List[Dict[str, Any]] = []

    for worker in workers or []:
        worker_id = str(_value(worker, "worker_id", "site-wide"))
        for ppe_kind, template in PPE_QUERY_TEMPLATES.items():
            if _value(worker, ppe_kind) != "missing":
                continue
            _append_unique(queries, {
                "query": template,
                "origin": "detector_ppe",
                "kind": "missing_ppe",
                "ppe_kind": ppe_kind,
                "worker_ids": [worker_id],
                "danger_type": None,
                "evidence": "VLM structured worker PPE status=missing",
                "confidence": None,
                "required_terms": list(PPE_REQUIRED_TERMS[ppe_kind]),
            })

    for danger in danger_records or []:
        danger_type = str(_value(danger, "danger_type", ""))
        template = DANGER_QUERY_TEMPLATES.get(danger_type)
        if not template:
            # unknown and missing_ppe are intentionally not inferred from prose.
            continue
        _append_unique(queries, {
            "query": template,
            "origin": "vlm_contextual_danger",
            "kind": "contextual_risk",
            "ppe_kind": None,
            "worker_ids": [str(worker_id) for worker_id in (_value(danger, "worker_ids", []) or [])],
            "danger_type": danger_type,
            "evidence": str(_value(danger, "evidence", "")),
            "confidence": _value(danger, "confidence"),
            "required_terms": list(DANGER_REQUIRED_TERMS[danger_type]),
        })

    return queries
