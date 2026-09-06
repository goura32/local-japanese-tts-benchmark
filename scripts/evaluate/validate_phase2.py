"""Fail-closed validation for the Phase 2 delta schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tts_benchmark.phase2 import validate_phase2_delta


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--phase1-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    phase1 = json.loads(args.phase1_summary.read_text(encoding="utf-8"))
    validate_phase2_delta(summary)
    errors: list[str] = []
    if phase1.get("schema_version") not in {"1.0", "1.0.0"}:
        errors.append("phase1 baseline schema version is not recognized")
    if not summary.get("phase1_baseline_preserved"):
        errors.append("phase1 baseline is not marked preserved")
    if summary.get("phase1_summary_path") != "results/summary.json":
        errors.append("phase1 summary path is not the preserved public path")
    if errors:
        result = {"status": "invalid", "errors": errors}
        if args.output:
            args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False))
        return 1
    result = {
        "status": "valid",
        "engine_count": len(summary["engines"]),
        "case_result_count": len(summary["case_results"]),
        "reading_variant_count": len(summary["reading_variants"]),
    }
    if args.output:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
