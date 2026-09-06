#!/usr/bin/env python3
"""Capture non-secret host and dependency metadata for a benchmark run."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import subprocess
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def command(*args: str) -> str | None:
    try:
        completed = subprocess.run(args, capture_output=True, text=True, timeout=20, check=True)
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout.strip()


def json_endpoint(url: str) -> Any:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return json.load(response)
    except (OSError, ValueError):
        return None


def package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "environment")
    parser.add_argument("--kana-checkpoint", type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    gpu_csv = command("nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader")
    gpu = []
    if gpu_csv:
        for line in gpu_csv.splitlines():
            name, memory, driver = [value.strip() for value in line.split(",", 2)]
            gpu.append({"name": name, "memory": memory, "driver": driver})

    hardware = {
        "captured_at": datetime.now(UTC).isoformat(),
        "platform": platform.platform(),
        "python": sys.version,
        "machine": platform.machine(),
        "processor": platform.processor(),
        "gpu": gpu,
        "docker_version": command("docker", "--version"),
        "docker_voicevox_image": command("docker", "image", "inspect", "voicevox/voicevox_engine:latest", "--format", "{{json .RepoDigests}}"),
        "local_services": {
            "aivis_version": json_endpoint("http://127.0.0.1:10101/version"),
            "voicevox_version": json_endpoint("http://127.0.0.1:50021/version"),
        },
    }
    if args.kana_checkpoint and args.kana_checkpoint.exists():
        digest = command("sha256sum", str(args.kana_checkpoint))
        hardware["pronunciation_checkpoint"] = {
            "path": "external cache; not committed",
            "size_bytes": args.kana_checkpoint.stat().st_size,
            "sha256": digest.split()[0] if digest else None,
        }
    (args.output_dir / "hardware.json").write_text(
        json.dumps(hardware, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    versions = {
        "benchmark_python": sys.version.split()[0],
        "numpy": package_version("numpy"),
        "PyYAML": package_version("PyYAML"),
        "psutil": package_version("psutil"),
        "requests": package_version("requests"),
        "soundfile": package_version("soundfile"),
        "faster-whisper": package_version("faster-whisper"),
        "torch": package_version("torch"),
        "torchaudio": package_version("torchaudio"),
        "transformers": package_version("transformers"),
        "pyopenjtalk": package_version("pyopenjtalk"),
        "docker": command("docker", "--version"),
        "ffmpeg": command("ffmpeg", "-version"),
    }
    lines = [f"{key}={value}" for key, value in versions.items()]
    (args.output_dir / "versions.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(hardware, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
