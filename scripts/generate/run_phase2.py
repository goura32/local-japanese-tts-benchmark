"""Generate Phase 2 requests through auditable engine adapter subprocesses."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from tts_benchmark.benchmark import load_yaml
from tts_benchmark.phase2 import build_phase2_requests, load_phase2_cases

ROOT = Path(__file__).resolve().parents[2]


def _jsonl_write(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _jsonl_read(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _request_rows(
    phase1_cases: list[dict[str, Any]], phase2_cases: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = build_phase2_requests(phase1_cases, phase2_cases)
    for index, row in enumerate(rows):
        row["request_id"] = f"{row['case_id']}__{row['reading_variant']}__{index:03d}"
    return rows


def _unavailable_rows(requests: list[dict[str, Any]], error: str) -> list[dict[str, Any]]:
    return [
        {
            "request_id": request["request_id"],
            "status": "unavailable",
            "error": error,
            "audio_path": None,
            "generation_sec": None,
        }
        for request in requests
    ]


def run_engine(
    engine: dict[str, Any], requests: list[dict[str, Any]], output_dir: Path, audio_dir: Path
) -> dict[str, Any]:
    engine_id = str(engine["engine_id"])
    request_path = output_dir / "requests" / f"{engine_id}.jsonl"
    result_path = output_dir / "generated" / f"{engine_id}.jsonl"
    _jsonl_write(request_path, requests)
    result_path.parent.mkdir(parents=True, exist_ok=True)
    adapter = ROOT / str(engine["adapter_script"])
    command = [
        sys.executable,
        str(adapter),
        "--requests",
        str(request_path),
        "--results",
        str(result_path),
        "--audio-dir",
        str(audio_dir),
        "--engine-config-json",
        json.dumps(engine, ensure_ascii=False),
    ]
    started = time.perf_counter()
    completed = subprocess.run(command, cwd=ROOT, check=False, text=True, capture_output=True)
    elapsed = time.perf_counter() - started
    stdout_path = output_dir / "logs" / f"{engine_id}.stdout.log"
    stderr_path = output_dir / "logs" / f"{engine_id}.stderr.log"
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    rows = _jsonl_read(result_path)
    if completed.returncode != 0 or not rows:
        error = (
            f"adapter_exit={completed.returncode}; "
            f"stderr_log={stderr_path.as_posix()}"
        )
        rows = _unavailable_rows(requests, error)
        _jsonl_write(result_path, rows)
    return {
        "engine_id": engine_id,
        "adapter_script": str(adapter.relative_to(ROOT)),
        "request_path": str(request_path),
        "result_path": str(result_path),
        "stdout_log": str(stdout_path),
        "stderr_log": str(stderr_path),
        "exit_code": completed.returncode,
        "elapsed_sec": round(elapsed, 6),
        "generated_rows": sum(row.get("status") == "generated" for row in rows),
        "unavailable_rows": sum(row.get("status") != "generated" for row in rows),
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine-config", type=Path, default=ROOT / "config/phase2_engines.yaml")
    parser.add_argument("--cases", type=Path, default=ROOT / "tests/cases.yaml")
    parser.add_argument("--phase2-cases", type=Path, default=ROOT / "tests/phase2_cases.yaml")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--audio-dir", type=Path, required=True)
    parser.add_argument("--engines", default="all", help="comma-separated engine IDs or all")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_yaml(args.engine_config)
    all_engines = config.get("engines", [])
    selected = set(all_engines if args.engines == "all" else args.engines.split(","))
    engines = [engine for engine in all_engines if engine.get("engine_id") in selected]
    unknown = selected - {engine.get("engine_id") for engine in engines}
    if unknown:
        raise SystemExit(f"unknown engine IDs: {', '.join(sorted(unknown))}")
    phase1_cases = load_yaml(args.cases)
    phase2_cases = load_phase2_cases(args.phase2_cases)
    requests = _request_rows(phase1_cases, phase2_cases)
    runs = [run_engine(engine, requests, args.output_dir, args.audio_dir) for engine in engines]
    manifest = {
        "manifest_schema_version": "2.0",
        "phase": "phase2",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repository_root": str(ROOT),
        "requests": requests,
        "engine_runs": runs,
        "audio_dir": str(args.audio_dir),
        "environment": {
            "pid": os.getpid(),
            "python": sys.executable,
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "phase2_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "manifest": str(args.output_dir / "phase2_manifest.json"),
                "engine_count": len(runs),
                "request_count": len(requests),
                "generated_rows": sum(run["generated_rows"] for run in runs),
                "unavailable_rows": sum(run["unavailable_rows"] for run in runs),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
