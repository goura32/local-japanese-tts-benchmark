"""Fixture and result-schema helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_REQUIRED_ENGINE_FIELDS = {
    "engine_id",
    "engine_name",
    "version",
    "source_url",
    "license",
    "local_inference",
    "japanese_support",
    "install_status",
    "install_notes",
    "model_size_gb",
    "peak_vram_gb",
    "peak_ram_gb",
    "generation_rtf",
    "automation_score",
    "pronunciation_control_score",
    "expression_score",
    "naturalness_score",
    "content_accuracy_score",
    "overall_notes",
    "human_review_required_count",
}


def load_yaml(path: str | Path) -> Any:
    with Path(path).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_cases(path: str | Path) -> list[dict[str, Any]]:
    cases = load_yaml(path)
    if not isinstance(cases, list):
        raise TypeError("case fixture must be a YAML list")
    seen: set[str] = set()
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str):
            raise TypeError("every case must have a string id")
        if case["id"] in seen:
            raise ValueError(f"duplicate case id: {case['id']}")
        seen.add(case["id"])
        if not isinstance(case.get("text"), str) or not case["text"]:
            raise ValueError(f"case {case['id']} must have non-empty text")
        if case.get("type") == "pronunciation":
            for field in ("target_span", "expected_reading"):
                if not isinstance(case.get(field), str) or not case[field]:
                    raise ValueError(f"pronunciation case {case['id']} missing {field}")
    return cases


def validate_engine_result(result: dict[str, Any]) -> None:
    missing = sorted(_REQUIRED_ENGINE_FIELDS - result.keys())
    if missing:
        raise ValueError(f"engine result missing required fields: {', '.join(missing)}")
    for field in (
        "automation_score",
        "pronunciation_control_score",
        "expression_score",
        "naturalness_score",
        "content_accuracy_score",
    ):
        value = result[field]
        if value is not None and not isinstance(value, (int, float)):
            raise ValueError(f"{field} must be numeric or null")
        if value is not None and not 0 <= value <= 5:
            raise ValueError(f"{field} must be between 0 and 5")
