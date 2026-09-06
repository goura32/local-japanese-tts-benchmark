"""IndexTTS-2.5 adapter with explicit reference/emotion controls."""

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

EMOTION_VECTORS = {
    "neutral": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    "cheerful": [0.8, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    "angry": [0.0, 0.8, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    "sad": [0.0, 0.0, 0.8, 0.0, 0.0, 0.0, 0.0, 0.0],
    "suspenseful": [0.0, 0.0, 0.0, 0.8, 0.0, 0.0, 0.0, 0.0],
    "tired": [0.0, 0.0, 0.0, 0.0, 0.0, 0.7, 0.0, 0.0],
    "calm": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.8],
    "punctuation_performance": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.8, 0.0],
    "restrained_emotion": [0.0, 0.0, 0.35, 0.0, 0.0, 0.0, 0.0, 0.15],
}


def main() -> int:
    parser = argparse.ArgumentParser()
    add_common_arguments(parser)
    parser.add_argument("--model-dir", default=None)
    parser.add_argument("--cfg-path", default=None)
    parser.add_argument("--reference-audio", default=None)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--use-bf16", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()
    config = load_config(args.engine_config_json)
    model_dir = args.model_dir or os.environ.get("TTS_PHASE2_INDEX_MODEL_DIR")
    reference_audio = args.reference_audio or os.environ.get("TTS_PHASE2_INDEX_REFERENCE_AUDIO")
    if not model_dir or not reference_audio:
        raise SystemExit("IndexTTS-2.5 requires --model-dir and --reference-audio")

    from indextts.infer_v2_5 import IndexTTS2

    cfg_path = args.cfg_path or str(Path(model_dir) / "config.yaml")
    started = time.perf_counter()
    tts = IndexTTS2(
        cfg_path=cfg_path,
        model_dir=model_dir,
        use_bf16=args.use_bf16,
        device=args.device,
        use_cuda_kernel=False,
        use_qwen_emo=False,
    )
    print(f"indextts_model_load_sec={time.perf_counter() - started:.6f}", flush=True)

    def generate(request: dict[str, Any], path: Path) -> dict[str, Any]:
        requested = str(request.get("requested_style") or "neutral")
        vector = EMOTION_VECTORS.get(requested, EMOTION_VECTORS["neutral"])
        duration_factor = 1.0
        if requested in {"calm", "tired"}:
            duration_factor = 1.15
        elif requested in {"cheerful", "punctuation_performance"}:
            duration_factor = 0.95
        started = time.perf_counter()
        result = tts.infer(
            spk_audio_prompt=reference_audio,
            text=str(request["effective_input"]),
            output_path=str(path),
            lang="ja",
            emo_vector=vector,
            duration_factor=duration_factor,
            text_normalization=request["reading_variant"] != "external_preprocessed",
            verbose=False,
        )
        if result is None or not path.exists():
            raise RuntimeError("IndexTTS returned no audio file")
        return {
            "status": "generated",
            "generation_sec": round(time.perf_counter() - started, 6),
            "speaker": {"reference_audio": "official-public-reference-only", "same_speaker_as_neutral": True},
            "mapped_parameters": {"requested_style": requested, "emo_vector": vector, "duration_factor": duration_factor},
            "native_frontend": request["reading_variant"] in {"raw", "engine_native"},
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
