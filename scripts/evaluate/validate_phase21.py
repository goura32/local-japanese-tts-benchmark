"""Validate the public Phase 2.1 review outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tts_benchmark.phase21 import (
    PUBLIC_CASE_IDS,
    PUBLIC_CATEGORIES,
    PUBLIC_ENGINE_IDS,
    validate_phase21_recommendation,
    validate_phase21_summary,
)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected a JSON object: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--recommendation", type=Path, required=True)
    parser.add_argument("--expected-sample-count", type=int, default=15)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    summary = _load(args.summary)
    recommendation = _load(args.recommendation)
    validate_phase21_summary(
        summary,
        expected_sample_count=args.expected_sample_count,
        allowed_engine_ids=PUBLIC_ENGINE_IDS,
        allowed_case_ids=PUBLIC_CASE_IDS,
        allowed_categories=PUBLIC_CATEGORIES,
    )
    validate_phase21_recommendation(recommendation)
    if recommendation.get("schema_version") != "phase2.1-final-recommendation-1":
        raise ValueError("invalid Phase 2.1 recommendation schema version")
    if (
        recommendation.get("phase") != "phase2.1"
        or recommendation.get("status") != "complete"
    ):
        raise ValueError("Phase 2.1 recommendation is not complete")
    if (
        recommendation.get("machine_human_comparison", {}).get("single_score")
        is not False
    ):
        raise ValueError("Phase 2.1 recommendation must not define a single score")
    for row in recommendation.get("comparison", []):
        other = row.get("human_other_dimensions", {})
        if any(value is not None for value in other.values()):
            raise ValueError("unassessed human dimensions must remain null")
    if recommendation.get("private_identity_mapping_published") is not False:
        raise ValueError("private identity mapping must not be published")

    result = {
        "status": "valid",
        "sample_count": summary["sample_count"],
        "engine_count": len(summary["engine_aggregates"]),
        "engine_case_count": len(summary["engine_case_aggregates"]),
        "reviewed_dimensions": summary["reviewed_dimensions"],
        "not_evaluated_dimensions": summary["not_evaluated_dimensions"],
        "single_score": recommendation["machine_human_comparison"]["single_score"],
    }
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
