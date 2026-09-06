"""Aggregate the Phase 2.1 naturalness-only private review."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from tts_benchmark.phase21 import (
    aggregate_naturalness,
    build_final_recommendation,
    load_review_workbook,
    validate_phase21_identifiers,
    validate_phase21_provenance,
    validate_phase21_recommendation,
    validate_phase21_summary,
    write_public_outputs,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected a JSON object: {path}")
    return value


def _complete_human_summary(
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    source_phase2_commit: str,
    source_phase2_tag: str,
    score_workbook_sha256: str,
) -> dict[str, Any]:
    category_counts = Counter(row["category"] for row in rows)
    engine_ids = {row["engine_id"] for row in summary["engine_aggregates"]}
    summary.update(
        {
            "schema_version": "phase2.1-human-review-summary-1",
            "phase": "phase2.1",
            "status": "complete",
            "blind_map_disclosed_before_aggregation": True,
            "reviewed_dimensions": ["naturalness"],
            "not_evaluated_dimensions": [
                "instruction_match",
                "pronunciation_quality",
                "would_use",
                "reading_issue",
                "note",
            ],
            "review_scope": {
                "sample_count": len(rows),
                "engine_count": len(engine_ids),
                "category_counts": dict(sorted(category_counts.items())),
            },
            "input_artifact": {
                "kind": "private_review_scores_xlsx",
                "sha256": score_workbook_sha256,
                "path_published": False,
            },
            "source_phase2": {
                "commit": source_phase2_commit,
                "tag": source_phase2_tag,
            },
            "private_identity_mapping_published": False,
        }
    )
    return summary


def _complete_recommendation(
    recommendation: dict[str, Any],
    human_summary: dict[str, Any],
    *,
    source_phase2_commit: str,
    source_phase2_tag: str,
) -> dict[str, Any]:
    recommendation.update(
        {
            "schema_version": "phase2.1-final-recommendation-1",
            "phase": "phase2.1",
            "status": "complete",
            "source_phase2": {
                "commit": source_phase2_commit,
                "tag": source_phase2_tag,
            },
            "human_review": {
                "reviewed_dimensions": human_summary["reviewed_dimensions"],
                "not_evaluated_dimensions": human_summary["not_evaluated_dimensions"],
                "aggregation": "engine/case aggregation after applying the private blind map",
                "sample_count": human_summary["sample_count"],
            },
            "private_identity_mapping_published": False,
        }
    )
    return recommendation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores-xlsx", type=Path, required=True)
    parser.add_argument("--blind-map", type=Path, required=True)
    parser.add_argument("--phase2-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-phase2-commit", required=True)
    parser.add_argument("--source-phase2-tag", default="v0.2.0")
    args = parser.parse_args()

    validate_phase21_provenance(args.source_phase2_commit, args.source_phase2_tag)
    rows = load_review_workbook(args.scores_xlsx)
    blind_map = _load_json(args.blind_map)
    blind_items = blind_map.get("items")
    if not isinstance(blind_items, list):
        raise TypeError("blind map must contain an items list")
    validate_phase21_identifiers(blind_items, expected_sample_count=15)
    phase2_summary = _load_json(args.phase2_summary)
    human_summary = _complete_human_summary(
        aggregate_naturalness(rows, blind_items),
        rows,
        source_phase2_commit=args.source_phase2_commit,
        source_phase2_tag=args.source_phase2_tag,
        score_workbook_sha256=_sha256(args.scores_xlsx),
    )
    validate_phase21_summary(human_summary, expected_sample_count=15)
    recommendation = _complete_recommendation(
        build_final_recommendation(phase2_summary, human_summary),
        human_summary,
        source_phase2_commit=args.source_phase2_commit,
        source_phase2_tag=args.source_phase2_tag,
    )
    validate_phase21_recommendation(recommendation)
    write_public_outputs(args.output_dir, human_summary, recommendation)
    print(
        json.dumps(
            {
                "status": "complete",
                "sample_count": human_summary["sample_count"],
                "engine_count": len(human_summary["engine_aggregates"]),
                "engine_case_count": len(human_summary["engine_case_aggregates"]),
                "output_dir": str(args.output_dir),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
