#!/usr/bin/env python3
"""Fail-closed validation for the published benchmark result shape."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from tts_benchmark.benchmark import load_yaml, validate_engine_result

_ALLOWED_STATUS = {"合格", "不合格", "要確認", "対象外"}
_REQUIRED_CASE_FIELDS = {
    "engine_id", "case_id", "raw_input", "effective_input", "requested_style",
    "mapped_style_or_parameters", "audio_path", "duration_sec", "generation_sec",
    "stt_transcript", "cer", "expected_reading", "pronunciation_result",
    "pronunciation_evidence", "mos_estimate", "acoustic_features", "retry_used",
    "error", "human_review_required",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, default=ROOT / "results")
    args = parser.parse_args()
    summary = json.loads((args.results_dir / "summary.json").read_text(encoding="utf-8"))
    configured = load_yaml(ROOT / "config/engines.yaml")["engines"]
    configured_ids = {item["engine_id"] for item in configured}
    actual_ids = {item["engine_id"] for item in summary.get("engines", [])}
    assert actual_ids == configured_ids, f"engine IDs differ: {actual_ids ^ configured_ids}"
    assert summary.get("evaluation_status") == "complete"
    for engine in summary["engines"]:
        validate_engine_result(engine)
        items = [item for item in summary.get("case_results", []) if item["engine_id"] == engine["engine_id"]]
        if engine["install_status"] == "成功":
            assert len(items) == 30, f"{engine['engine_id']} does not have 30 case results"
            assert engine["failed_case_count"] == 0
        for item in items:
            missing = _REQUIRED_CASE_FIELDS - item.keys()
            assert not missing, f"{item['engine_id']}/{item['case_id']} missing {sorted(missing)}"
            assert item["pronunciation_result"] in _ALLOWED_STATUS
    measured = [item for item in summary.get("case_results", []) if item.get("audio_path")]
    assert len(measured) == 60, f"expected 60 generated case records, got {len(measured)}"
    with (args.results_dir / "metrics.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == len(summary.get("case_results", [])), "metrics.csv row count mismatch"
    print(json.dumps({
        "engine_count": len(actual_ids),
        "case_result_count": len(summary.get("case_results", [])),
        "generated_audio_count": len(measured),
        "status": "valid",
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
