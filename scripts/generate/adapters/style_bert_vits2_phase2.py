"""Style-Bert-VITS2 adapter using a fixed JP-Extra checkpoint speaker."""

from __future__ import annotations

import argparse
import os
import re
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


def _split_long_text(text: str, max_chars: int = 80) -> str:
    """Give the upstream frontend bounded segments for the long common case."""
    if len(text) <= max_chars:
        return text
    sentences = [part for part in re.split(r"(?<=[。！？!?])", text) if part]
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if current and len(current) + len(sentence) > max_chars:
            chunks.append(current)
            current = ""
        current += sentence
    if current:
        chunks.append(current)
    return "\n".join(chunks)


def main() -> int:
    parser = argparse.ArgumentParser()
    add_common_arguments(parser)
    parser.add_argument("--model-root", default=None)
    parser.add_argument("--model-name", default="jvnv-F1-jp")
    parser.add_argument("--bert-model", default="ku-nlp/deberta-v2-large-japanese-char-wwm")
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()
    config = load_config(args.engine_config_json)
    model_root = Path(args.model_root or os.environ.get("TTS_PHASE2_STYLE_MODEL_ROOT", ""))
    if not model_root:
        raise SystemExit("Style-Bert-VITS2 requires --model-root or TTS_PHASE2_STYLE_MODEL_ROOT")
    model_dir = model_root / args.model_name
    config_path = model_dir / "config.json"
    model_files = list(model_dir.glob("*.safetensors"))
    style_vec_path = model_dir / "style_vectors.npy"
    if len(model_files) != 1 or not config_path.exists() or not style_vec_path.exists():
        raise SystemExit(f"incomplete Style-Bert-VITS2 model directory: {model_dir}")

    import soundfile as sf
    from style_bert_vits2.constants import Languages
    from style_bert_vits2.models.hyper_parameters import HyperParameters
    from style_bert_vits2.nlp import bert_models
    from style_bert_vits2.tts_model import TTSModel

    bert_models.load_model(Languages.JP, args.bert_model)
    bert_models.load_tokenizer(Languages.JP, args.bert_model)
    HyperParameters.load_from_json(config_path)
    tts = TTSModel(
        model_path=model_files[0],
        config_path=config_path,
        style_vec_path=style_vec_path,
        device=args.device,
        onnx_providers=[],
    )
    style_map = config.get("style_map", {})
    style_map = style_map if isinstance(style_map, dict) else {}
    fallback = "Neutral"

    def generate(request: dict[str, Any], path: Path) -> dict[str, Any]:
        requested = str(request.get("requested_style") or "neutral")
        style = str(style_map.get(requested, fallback))
        length = 1.0
        intonation = 1.0
        if requested in {"calm", "tired", "slow_explanatory"}:
            length = 1.1 if requested != "tired" else 1.16
        if requested in {"angry", "cheerful", "suspenseful"}:
            intonation = 1.15
        model_text = _split_long_text(str(request["effective_input"]))
        started = time.perf_counter()
        sample_rate, audio = tts.infer(
            model_text,
            language=Languages.JP,
            style=style,
            length=length,
            intonation_scale=intonation,
            line_split="\n" in model_text,
            split_interval=0.08,
        )
        sf.write(path, audio, sample_rate, subtype="PCM_16")
        return {
            "status": "generated",
            "generation_sec": round(time.perf_counter() - started, 6),
            "speaker": {"model_name": args.model_name, "style": style, "same_speaker_as_neutral": True},
            "mapped_parameters": {"requested_style": requested, "style": style, "length": length, "intonation_scale": intonation},
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
