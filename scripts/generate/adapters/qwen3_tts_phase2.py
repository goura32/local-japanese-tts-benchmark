"""Qwen3-TTS VoiceDesign adapter for Phase 2."""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path
from typing import Any

from _protocol import (
    add_common_arguments,
    load_config,
    load_requests,
    run_requests,
    write_results,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    add_common_arguments(parser)
    parser.add_argument("--model", default=None)
    parser.add_argument("--device", default=None)
    parser.add_argument("--max-new-tokens", type=int, default=2048)
    args = parser.parse_args()
    config = load_config(args.engine_config_json)
    model_id = args.model or os.environ.get("TTS_PHASE2_QWEN_MODEL") or config["model_id"]
    device = args.device or os.environ.get("TTS_PHASE2_QWEN_DEVICE", "cuda:0")

    import soundfile as sf
    import torch
    from qwen_tts import Qwen3TTSModel

    print(f"qwen_model={model_id}", flush=True)
    started = time.perf_counter()
    model = Qwen3TTSModel.from_pretrained(
        model_id,
        device_map=device,
        dtype=torch.bfloat16 if device.startswith("cuda") else torch.float32,
        attn_implementation="sdpa",
    )
    print(f"model_load_sec={time.perf_counter() - started:.6f}", flush=True)

    def generate(request: dict[str, Any], path: Path) -> dict[str, Any]:
        text = str(request["effective_input"])
        instruction = str(request.get("instruction") or "自然で明瞭な日本語で話す。")
        started = time.perf_counter()
        wavs, sample_rate = model.generate_voice_design(
            text=text,
            language="Japanese",
            instruct=instruction,
            max_new_tokens=args.max_new_tokens,
        )
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        sf.write(path, wavs[0], sample_rate)
        return {
            "status": "generated",
            "generation_sec": round(time.perf_counter() - started, 6),
            "speaker": {"mode": "voice_design", "same_speaker_as_neutral": False},
            "mapped_parameters": {"instruction": instruction},
            "native_frontend": False,
        }

    rows = run_requests(
        load_requests(args.requests),
        engine_id=str(config["engine_id"]),
        audio_dir=args.audio_dir,
        generate=generate,
    )
    write_results(args.results, rows)
    print({"generated": sum(row["status"] == "generated" for row in rows), "total": len(rows)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
