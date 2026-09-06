"""Shared JSONL protocol for Phase 2 engine adapters."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--audio-dir", type=Path, required=True)
    parser.add_argument("--engine-config-json", required=True)


def load_requests(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_config(raw: str) -> dict[str, Any]:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise TypeError("engine config must be a JSON object")
    return value


def audio_path(audio_dir: Path, engine_id: str, request_id: str) -> Path:
    path = audio_dir / engine_id / f"{request_id}.wav"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def write_results(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def run_requests(
    requests: list[dict[str, Any]],
    *,
    engine_id: str,
    audio_dir: Path,
    generate: Callable[[dict[str, Any], Path], dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for request in requests:
        path = audio_path(audio_dir, engine_id, request["request_id"])
        try:
            row = generate(request, path)
            row.setdefault("status", "generated")
            row["request_id"] = request["request_id"]
            row["audio_path"] = str(path) if row["status"] == "generated" else None
        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
            row = {
                "request_id": request["request_id"],
                "status": "unavailable",
                "error": f"{type(exc).__name__}: {exc}",
                "audio_path": None,
                "generation_sec": None,
            }
        rows.append(row)
    return rows
