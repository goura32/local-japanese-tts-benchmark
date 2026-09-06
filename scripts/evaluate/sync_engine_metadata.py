#!/usr/bin/env python3
"""Synchronize immutable source metadata into measured result artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from tts_benchmark.benchmark import load_yaml


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, default=ROOT / "results")
    parser.add_argument("--aivis-model-size", type=float)
    parser.add_argument("--voicevox-image-size", type=float)
    args = parser.parse_args()
    result_dir = args.results_dir
    summary_path = result_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    config = {item["engine_id"]: item for item in load_yaml(ROOT / "config/engines.yaml")["engines"]}
    for engine in summary["engines"]:
        source = config[engine["engine_id"]]
        for key in ("engine_name", "version", "source_url", "license", "japanese_support"):
            engine[key] = source[key]
        if engine["engine_id"] == "aivis" and args.aivis_model_size is not None:
            engine["model_size_gb"] = args.aivis_model_size
            note = " Model footprint is the downloaded AIVMX file size, not committed."
            if note.strip() not in engine["install_notes"]:
                engine["install_notes"] += note
        if engine["engine_id"] == "voicevox" and args.voicevox_image_size is not None:
            engine["model_size_gb"] = args.voicevox_image_size
            note = " This value is the pinned Docker image footprint, not an isolated speaker model."
            if note.strip() not in engine["install_notes"]:
                engine["install_notes"] += note
        items = [item for item in summary.get("case_results", []) if item["engine_id"] == engine["engine_id"]]
        payload = {"engine": engine, "case_results": items}
        (result_dir / "engine_results" / f"{engine['engine_id']}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "synchronized", "engine_count": len(summary["engines"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
