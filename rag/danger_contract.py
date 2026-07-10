"""Typed VLM danger records accepted by the future canonical RAG query builder."""
from typing import Iterable, List


def eligible_danger_records(dangers: Iterable[object]) -> List[dict]:
    """Keep only grounded, non-ambiguous danger records; never accept free text."""
    records = []
    for danger in dangers or []:
        if hasattr(danger, "model_dump"):
            danger = danger.model_dump()
        if not isinstance(danger, dict):
            continue
        danger_type = danger.get("danger_type")
        if hasattr(danger_type, "value"):
            danger_type = danger_type.value
        evidence = str(danger.get("evidence", "")).strip()
        confidence = float(danger.get("confidence", 0.0))
        if not danger_type or danger_type == "unknown" or not evidence or confidence < 0.5:
            continue
        records.append({
            "danger_type": str(danger_type),
            "worker_ids": list(danger.get("worker_ids") or []),
            "description": str(danger.get("description", "")),
            "evidence": evidence,
            "confidence": confidence,
        })
    return records
