"""VOICEVOX Engine adapter for the Phase 2 JSONL runner."""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from _protocol import (
    add_common_arguments,
    load_config,
    load_requests,
    run_requests,
    write_results,
)


def _request_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, data=b"", method="POST")
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(url: str, payload: dict[str, Any]) -> bytes:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        return response.read()


def main() -> int:
    parser = argparse.ArgumentParser()
    add_common_arguments(parser)
    parser.add_argument("--endpoint", default=None)
    args = parser.parse_args()
    config = load_config(args.engine_config_json)
    endpoint = (args.endpoint or config.get("endpoint") or "http://127.0.0.1:50021").rstrip("/")
    base_speaker = int(config.get("speaker_id", 0))
    style_map = config.get("style_map", {})
    requests = load_requests(args.requests)

    def generate(request: dict[str, Any], path: Path) -> dict[str, Any]:
        requested = str(request.get("requested_style") or request.get("style") or "neutral")
        mapping = style_map.get(requested, style_map.get("neutral", {}))
        speaker_id = int(mapping.get("speaker_id", base_speaker))
        text = str(request["effective_input"])
        query_url = f"{endpoint}/audio_query?{urllib.parse.urlencode({'text': text, 'speaker': speaker_id})}"
        query = _request_json(query_url)
        parameters = mapping.get("parameters", {})
        if isinstance(parameters, dict):
            for key, value in parameters.items():
                if isinstance(value, (int, float)):
                    query[key] = value
        started = time.perf_counter()
        audio = _post_json(f"{endpoint}/synthesis?speaker={speaker_id}", query)
        elapsed = time.perf_counter() - started
        path.write_bytes(audio)
        return {
            "status": "generated",
            "generation_sec": round(elapsed, 6),
            "speaker": {"speaker_id": speaker_id},
            "mapped_parameters": {"requested_style": requested, "parameters": parameters},
            "native_frontend": request["reading_variant"] in {"raw", "engine_native"},
        }

    rows = run_requests(
        requests,
        engine_id=str(config["engine_id"]),
        audio_dir=args.audio_dir,
        generate=generate,
    )
    write_results(args.results, rows)
    print(json.dumps({"generated": sum(row["status"] == "generated" for row in rows), "total": len(rows)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
