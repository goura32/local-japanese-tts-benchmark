#!/usr/bin/env python3
"""Refresh stored WAV features after an evaluator implementation change."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from tts_benchmark.audio import analyze_wave


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, default=ROOT / "results")
    args = parser.parse_args()
    summary_path = args.results_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    for item in summary.get("case_results", []):
        path_value = item.get("audio_path")
        if not path_value:
            continue
        path = Path(path_value)
        if not path.is_absolute():
            path = ROOT / path
        if path.exists():
            item["acoustic_features"] = analyze_wave(path)
    by_engine: dict[str, list[dict]] = {}
    for item in summary.get("case_results", []):
        by_engine.setdefault(item["engine_id"], []).append(item)
    for engine in summary.get("engines", []):
        payload_path = args.results_dir / "engine_results" / f"{engine['engine_id']}.json"
        if payload_path.exists():
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload["case_results"] = by_engine.get(engine["engine_id"], [])
            payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fields = [
        "engine_id", "case_id", "requested_style", "duration_sec", "generation_sec",
        "generation_rtf", "stt_transcript", "cer", "expected_reading", "pronunciation_result",
        "retry_used", "human_review_required", "silence_ratio", "rms_dbfs", "estimated_f0_hz",
        "anomaly_flags", "error",
    ]
    with (args.results_dir / "metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for item in summary.get("case_results", []):
            features = item.get("acoustic_features") or {}
            writer.writerow({
                "engine_id": item.get("engine_id"),
                "case_id": item.get("case_id"),
                "requested_style": item.get("requested_style"),
                "duration_sec": item.get("duration_sec"),
                "generation_sec": item.get("generation_sec"),
                "generation_rtf": round(item["generation_sec"] / item["duration_sec"], 6)
                if item.get("generation_sec") and item.get("duration_sec") else None,
                "stt_transcript": item.get("stt_transcript"),
                "cer": item.get("cer"),
                "expected_reading": item.get("expected_reading"),
                "pronunciation_result": item.get("pronunciation_result"),
                "retry_used": item.get("retry_used"),
                "human_review_required": item.get("human_review_required"),
                "silence_ratio": features.get("silence_ratio"),
                "rms_dbfs": features.get("rms_dbfs"),
                "estimated_f0_hz": features.get("estimated_f0_hz"),
                "anomaly_flags": ";".join(features.get("anomaly_flags", [])),
                "error": item.get("error"),
            })
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("updated", sum(bool(item.get("audio_path")) for item in summary.get("case_results", [])), "audio records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
