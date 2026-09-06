"""Irodori-TTS VoiceDesign adapter for Phase 2."""

from __future__ import annotations

import argparse
import hashlib
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
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--model-device", default=None)
    parser.add_argument("--model-precision", default="bf16")
    parser.add_argument("--codec-device", default="cuda")
    parser.add_argument("--codec-precision", default="bf16")
    parser.add_argument("--seconds", type=float, default=None)
    parser.add_argument("--max-seconds", type=float, default=30.0)
    parser.add_argument("--num-steps", type=int, default=20)
    args = parser.parse_args()
    config = load_config(args.engine_config_json)
    checkpoint = args.checkpoint or os.environ.get("TTS_PHASE2_IRODORI_CHECKPOINT")
    if not checkpoint:
        raise SystemExit("Irodori adapter requires --checkpoint or TTS_PHASE2_IRODORI_CHECKPOINT")

    import torch
    from irodori_tts.inference_runtime import (
        InferenceRuntime,
        RuntimeKey,
        SamplingRequest,
        save_wav,
    )

    model_device = args.model_device or os.environ.get("TTS_PHASE2_IRODORI_MODEL_DEVICE", "cuda")
    key = RuntimeKey(
        checkpoint=checkpoint,
        model_device=model_device,
        model_precision=args.model_precision,
        codec_device=args.codec_device,
        codec_precision=args.codec_precision,
    )
    started = time.perf_counter()
    runtime = InferenceRuntime.from_key(key)
    print(f"irodori_model_load_sec={time.perf_counter() - started:.6f}", flush=True)

    def generate(request: dict[str, Any], path: Path) -> dict[str, Any]:
        seed = int(hashlib.sha256(request["request_id"].encode()).hexdigest()[:8], 16)
        text = str(request["effective_input"])
        caption = str(request.get("instruction") or "自然で明瞭な日本語で話す。")
        sampling = SamplingRequest(
            text=text,
            caption=caption,
            no_ref=True,
            seconds=args.seconds,
            max_seconds=args.max_seconds,
            num_steps=args.num_steps,
            seed=seed,
        )
        started = time.perf_counter()
        result = runtime.synthesize(sampling)
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        save_wav(path, result.audio, result.sample_rate)
        return {
            "status": "generated",
            "generation_sec": round(time.perf_counter() - started, 6),
            "speaker": {"mode": "caption_controlled_no_reference", "same_speaker_as_neutral": False},
            "mapped_parameters": {"caption": caption, "seed": result.used_seed},
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
