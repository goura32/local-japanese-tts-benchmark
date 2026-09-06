#!/usr/bin/env python3
"""Evaluate generated audio with local STT, kana CTC, and acoustic checks."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from tts_benchmark.alignment import observed_for_reference_span
from tts_benchmark.benchmark import load_cases
from tts_benchmark.metrics import (
    assess_pronunciation,
    cer,
    normalize_text,
)

KANA_MODEL_ID = "sakasegawa/japanese-wav2vec2-large-hiragana-ctc"
KANA_REPO_ROOT = Path(os.environ.get("TTS_BENCHMARK_KANA_REPO", str(ROOT / "external/hiragana-asr")))


def _load_runner_module():
    path = ROOT / "scripts/generate/run_benchmark.py"
    spec = importlib.util.spec_from_file_location("benchmark_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load generation runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _to_hiragana(text: str) -> str:
    """Use pyopenjtalk only for a reference context, never as audio evidence."""
    import pyopenjtalk

    katakana = pyopenjtalk.g2p(text, kana=True)
    katakana = katakana.replace("<sp>", "").replace(" ", "")
    chars: list[str] = []
    for char in katakana:
        codepoint = ord(char)
        if 0x30A1 <= codepoint <= 0x30F6:
            chars.append(chr(codepoint - 0x60))
        elif char in "、。？！,.!?「」『』（）()［］[]{}・…:;\"'`":
            continue
        else:
            chars.append(char)
    return normalize_text("".join(chars))


def _resolve_audio(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    path = Path(path_value)
    if path.is_absolute():
        return path
    return ROOT / path


def _load_stt(model_name: str, cache_dir: Path):
    import torch
    from faster_whisper import WhisperModel

    if torch.cuda.is_available():
        device, compute_type = "cuda", "float16"
    else:
        device, compute_type = "cpu", "int8"
    return WhisperModel(model_name, device=device, compute_type=compute_type, download_root=str(cache_dir)), {
        "model": model_name,
        "device": device,
        "compute_type": compute_type,
    }


def _transcribe(model: Any, audio_path: Path) -> tuple[str, dict[str, Any]]:
    segments, info = model.transcribe(
        str(audio_path),
        language="ja",
        task="transcribe",
        beam_size=5,
        condition_on_previous_text=False,
        vad_filter=False,
    )
    segment_list = list(segments)
    text = "".join(segment.text for segment in segment_list).strip()
    return text, {
        "language": getattr(info, "language", None),
        "language_probability": getattr(info, "language_probability", None),
        "segment_count": len(segment_list),
    }


class KanaRecognizer:
    """Wrapper around the published dual-CTC kana/phoneme checkpoint."""

    def __init__(self, checkpoint: Path, device: str | None = None, repo_root: Path | None = None):
        repo_root = repo_root or KANA_REPO_ROOT
        if not repo_root.exists():
            raise FileNotFoundError(f"kana recognizer source is missing: {repo_root}")
        sys.path.insert(0, str(repo_root))
        import soundfile as sf
        import torch
        import torchaudio
        from src.asr.kana_vocab import KanaVocab
        from src.asr.model import load_checkpoint
        from src.asr.phoneme_vocab import PhonemeVocab
        from transformers import Wav2Vec2FeatureExtractor

        self.torch = torch
        self.torchaudio = torchaudio
        self.sf = sf
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.model = load_checkpoint(str(checkpoint))
        self.model.to(self.device)
        self.model.eval()
        self.feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(
            "reazon-research/japanese-wav2vec2-large"
        )
        self.kana_vocab = KanaVocab()
        self.phoneme_vocab = PhonemeVocab()

    def recognize(self, audio_path: Path) -> dict[str, Any]:
        samples, sample_rate = self.sf.read(str(audio_path), dtype="float32", always_2d=True)
        waveform = self.torch.from_numpy(samples.T.copy())
        if sample_rate != 16_000:
            waveform = self.torchaudio.transforms.Resample(sample_rate, 16_000)(waveform)
            sample_rate = 16_000
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)
        audio = waveform.squeeze(0).numpy()
        inputs = self.feature_extractor(
            audio,
            sampling_rate=sample_rate,
            return_tensors="pt",
            return_attention_mask=True,
        )
        with self.torch.inference_mode():
            outputs = self.model(
                inputs.input_values.to(self.device),
                attention_mask=inputs.attention_mask.to(self.device),
            )
        kana_ids = outputs["kana_logits"].squeeze(0).argmax(dim=-1).tolist()
        phoneme_ids = outputs["phoneme_logits"].squeeze(0).argmax(dim=-1).tolist()
        return {
            "kana": self.kana_vocab.decode(kana_ids),
            "phonemes": self.phoneme_vocab.decode(phoneme_ids),
            "evaluator": KANA_MODEL_ID,
            "device": str(self.device),
        }


def _pronunciation_reference(case: dict[str, Any]) -> tuple[str, tuple[int, int]]:
    text = case["text"]
    target = case["target_span"]
    start = text.index(target)
    end = start + len(target)
    prefix = _to_hiragana(text[:start])
    suffix = _to_hiragana(text[end:])
    reference = prefix + normalize_text(case["expected_reading"]) + suffix
    return reference, (len(prefix), len(prefix) + len(normalize_text(case["expected_reading"])))


def _assess_case_pronunciation(
    case: dict[str, Any], kana_result: dict[str, Any] | None
) -> tuple[Any, dict[str, Any]]:
    if kana_result is None:
        assessment = assess_pronunciation(case["expected_reading"], None, "hiragana_ctc")
        return assessment, {"status": "kana_evaluator_unavailable"}
    reference, (start, end) = _pronunciation_reference(case)
    full_kana = normalize_text(kana_result.get("kana", ""))
    observed = observed_for_reference_span(reference, full_kana, start, end) if full_kana else None
    assessment = assess_pronunciation(case["expected_reading"], observed, "hiragana_ctc")
    evidence = {
        "status": "acoustic_alignment",
        "evaluator": kana_result.get("evaluator"),
        "phoneme_ctc_output": kana_result.get("phonemes"),
        "full_kana_output": full_kana,
        "reference_context_kana": reference,
        "target_span_indices": [start, end],
        "target_observed_kana": observed,
        "target_error_rate": assessment.error_rate,
    }
    return assessment, evidence


def _retry_case(
    runner: Any,
    engine: dict[str, Any],
    case: dict[str, Any],
    audio_root: Path,
) -> tuple[dict[str, Any], str]:
    effective = case["text"].replace(case["target_span"], case["expected_reading"], 1)
    retry_case = dict(case)
    retry_case["text"] = effective
    retry_result = runner._generate_one(runner.requests.Session(), engine, retry_case, audio_root / "retry")
    return retry_result, effective


def _score_engine(engine_result: dict[str, Any], case_results: list[dict[str, Any]]) -> None:
    content_cers = [item["cer"] for item in case_results if isinstance(item.get("cer"), (int, float))]
    pronunciation = [item for item in case_results if item.get("expected_reading")]
    checked_pronunciation = [item for item in pronunciation if item.get("pronunciation_result") in {"合格", "不合格"}]
    if content_cers:
        engine_result["content_accuracy_score"] = round(max(0.0, min(5.0, 5 * (1 - mean(content_cers)))), 3)
    if checked_pronunciation:
        passed = sum(item["pronunciation_result"] == "合格" for item in checked_pronunciation)
        engine_result["pronunciation_control_score"] = round(5 * passed / len(checked_pronunciation), 3)
    engine_result["human_review_required_count"] = sum(
        bool(item.get("human_review_required")) for item in case_results
    )
    engine_result["retry_count"] = sum(bool(item.get("retry_used")) for item in case_results)
    clean = sum(
        bool(item.get("acoustic_features")) and not item["acoustic_features"].get("anomaly_flags")
        for item in case_results
    )
    engine_result["overall_notes"] = (
        f"The local run generated {engine_result.get('successful_case_count', 0)} of "
        f"{engine_result.get('case_count', len(case_results))} common cases through the recorded HTTP endpoint. "
        "Round-trip content accuracy was computed from the local faster-whisper transcript and normalized CER; "
        "this is not a human listening score and may hide pronunciation errors through language-model context. "
        "Ambiguous readings were evaluated with a separate dual-CTC hiragana/phoneme recognizer when its checkpoint "
        "was available. The engine-provided reading metadata is retained as provenance but is not treated as acoustic "
        "proof. One retry, replacing only the target span with its expected kana, is recorded after an unambiguous "
        "acoustic mismatch. Automatic naturalness/MOS was not asserted because no validated local MOS estimator was "
        "available in this run; WAV format, duration, silence, level, pitch proxy, and anomaly flags are retained. "
        f"{clean}/{len(case_results)} successful cases had no simple acoustic anomaly flags."
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, default=ROOT / "results")
    parser.add_argument("--cases", type=Path, default=ROOT / "tests/cases.yaml")
    parser.add_argument("--audio-dir", type=Path, default=ROOT / "tmp/audio")
    parser.add_argument("--stt-model", default="small")
    parser.add_argument("--stt-cache", type=Path, default=Path("/tmp/tts-local-benchmark/model-cache/stt"))
    parser.add_argument("--kana-checkpoint", type=Path)
    parser.add_argument("--kana-repo", type=Path, default=KANA_REPO_ROOT)
    parser.add_argument("--skip-stt", action="store_true")
    parser.add_argument("--skip-kana", action="store_true")
    parser.add_argument("--case-limit", type=int)
    args = parser.parse_args()

    summary_path = args.results_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    cases = load_cases(args.cases)
    case_by_id = {case["id"]: case for case in cases}
    if args.case_limit is not None:
        case_ids = {case["id"] for case in cases[: args.case_limit]}
    else:
        case_ids = set(case_by_id)

    stt_model = None
    stt_info: dict[str, Any] = {"status": "skipped" if args.skip_stt else "pending"}
    if not args.skip_stt:
        try:
            args.stt_cache.mkdir(parents=True, exist_ok=True)
            stt_model, stt_info = _load_stt(args.stt_model, args.stt_cache)
            stt_info["status"] = "loaded"
        except Exception as exc:  # noqa: BLE001 - model availability is an explicit measured outcome
            stt_info = {"status": "unavailable", "error": f"{type(exc).__name__}: {exc}"}

    kana_model = None
    kana_info: dict[str, Any] = {"status": "skipped" if args.skip_kana else "pending"}
    if not args.skip_kana:
        checkpoint = args.kana_checkpoint
        if checkpoint is None:
            raise SystemExit("--kana-checkpoint is required unless --skip-kana is used")
        try:
            kana_model = KanaRecognizer(checkpoint, repo_root=args.kana_repo)
            kana_info = {"status": "loaded", "model": KANA_MODEL_ID, "device": str(kana_model.device)}
        except Exception as exc:  # noqa: BLE001 - optional evaluator failures are recorded
            kana_info = {"status": "unavailable", "model": KANA_MODEL_ID, "error": f"{type(exc).__name__}: {exc}"}
    engines_config = yaml.safe_load((ROOT / "config/engines.yaml").read_text(encoding="utf-8"))["engines"]
    engine_config_by_id = {engine["engine_id"]: engine for engine in engines_config}
    runner = _load_runner_module()
    engine_files = {}
    for engine_result in summary["engines"]:
        path = args.results_dir / "engine_results" / f"{engine_result['engine_id']}.json"
        if path.exists():
            engine_files[engine_result["engine_id"]] = json.loads(path.read_text(encoding="utf-8"))

    stt_cache: dict[str, tuple[str, dict[str, Any]]] = {}
    evaluated = 0
    retry_count = 0
    for case_result in summary.get("case_results", []):
        if case_result.get("case_id") not in case_ids or not case_result.get("audio_path"):
            continue
        evaluated += 1
        case = case_by_id[case_result["case_id"]]
        audio_path = _resolve_audio(case_result["audio_path"])
        if audio_path is None or not audio_path.exists():
            case_result["error"] = "audio file missing at evaluation time"
            case_result["human_review_required"] = True
            continue
        if stt_model is not None:
            key = str(audio_path)
            if key not in stt_cache:
                stt_cache[key] = _transcribe(stt_model, audio_path)
            transcript, transcript_info = stt_cache[key]
            case_result["stt_transcript"] = transcript
            case_result["cer"] = round(cer(case_result["raw_input"], transcript), 6)
            case_result["pronunciation_evidence"] = {
                **(case_result.get("pronunciation_evidence") or {}),
                "stt": {"system": "faster-whisper", **transcript_info},
            }
        kana_result = None
        if kana_model is not None and case.get("type") == "pronunciation":
            kana_result = kana_model.recognize(audio_path)
        if case.get("type") == "pronunciation":
            assessment, evidence = _assess_case_pronunciation(case, kana_result)
            case_result["pronunciation_result"] = assessment.result
            case_result["pronunciation_evidence"] = {
                **(case_result.get("pronunciation_evidence") or {}),
                **evidence,
            }
            case_result["human_review_required"] = assessment.result == "要確認"
            if assessment.result == "不合格" and kana_model is not None:
                first_attempt = {
                    "effective_input": case_result.get("effective_input"),
                    "audio_path": case_result.get("audio_path"),
                    "duration_sec": case_result.get("duration_sec"),
                    "generation_sec": case_result.get("generation_sec"),
                    "acoustic_features": case_result.get("acoustic_features"),
                    "pronunciation_result": assessment.result,
                    "pronunciation_evidence": dict(case_result.get("pronunciation_evidence") or {}),
                    "stt_transcript": case_result.get("stt_transcript"),
                    "cer": case_result.get("cer"),
                }
                case_result["first_attempt"] = first_attempt
                engine = engine_config_by_id[case_result["engine_id"]]
                try:
                    retry_result, effective = _retry_case(runner, engine, case, args.audio_dir)
                    retry_audio = _resolve_audio(retry_result["audio_path"])
                    retry_kana = kana_model.recognize(retry_audio) if retry_audio else None
                    retry_assessment, retry_evidence = _assess_case_pronunciation(case, retry_kana)
                    retry_payload = {
                        "effective_input": effective,
                        "audio_path": retry_result["audio_path"],
                        "duration_sec": retry_result["duration_sec"],
                        "generation_sec": retry_result["generation_sec"],
                        "acoustic_features": retry_result.get("acoustic_features"),
                        "pronunciation_result": retry_assessment.result,
                        "pronunciation_evidence": retry_evidence,
                        "stt_transcript": None,
                        "cer": None,
                        "error": retry_result.get("error"),
                    }
                    case_result["retry_attempt"] = retry_payload
                    case_result["retry_used"] = True
                    retry_count += 1
                    if retry_audio and stt_model is not None:
                        retry_key = str(retry_audio)
                        if retry_key not in stt_cache:
                            stt_cache[retry_key] = _transcribe(stt_model, retry_audio)
                        retry_text, _ = stt_cache[retry_key]
                        retry_payload["stt_transcript"] = retry_text
                        retry_payload["cer"] = round(cer(case_result["raw_input"], retry_text), 6)
                    case_result.update({
                        "effective_input": effective,
                        "audio_path": retry_result["audio_path"],
                        "duration_sec": retry_result["duration_sec"],
                        "generation_sec": retry_result["generation_sec"],
                        "acoustic_features": retry_result.get("acoustic_features"),
                        "pronunciation_result": retry_assessment.result,
                        "pronunciation_evidence": {
                            **(case_result.get("pronunciation_evidence") or {}),
                            "retry": retry_payload,
                        },
                        "human_review_required": retry_assessment.result == "要確認",
                    })
                    if retry_payload["stt_transcript"] is not None:
                        case_result["stt_transcript"] = retry_payload["stt_transcript"]
                        case_result["cer"] = retry_payload["cer"]
                except Exception as exc:  # noqa: BLE001 - one retry must not abort the batch
                    case_result["retry_attempt"] = {"error": f"{type(exc).__name__}: {exc}"}
                    case_result["retry_used"] = True
                    retry_count += 1

    # Keep per-engine files and the top-level summary in sync.
    summary_cases_by_engine = {}
    for item in summary.get("case_results", []):
        summary_cases_by_engine.setdefault(item["engine_id"], []).append(item)
    for engine_result in summary["engines"]:
        items = summary_cases_by_engine.get(engine_result["engine_id"], [])
        if items:
            _score_engine(engine_result, items)
        payload = engine_files.get(engine_result["engine_id"])
        if payload is not None:
            payload["engine"] = engine_result
            payload["case_results"] = items
            (args.results_dir / "engine_results" / f"{engine_result['engine_id']}.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )

    rows = []
    for item in summary.get("case_results", []):
        features = item.get("acoustic_features") or {}
        rows.append({
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
    with (args.results_dir / "metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]) if rows else ["engine_id", "case_id"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)

    summary["evaluation_status"] = "complete"
    total_retry_count = sum(bool(item.get("retry_used")) for item in summary.get("case_results", []))
    summary["evaluation"] = {
        "completed_at": datetime.now(UTC).isoformat(),
        "evaluated_audio_count": evaluated,
        "retry_count": total_retry_count,
        "stt": stt_info,
        "pronunciation": kana_info,
        "naturalness": {
            "mos_estimator": None,
            "status": "not_available",
            "acoustic_anomaly_checks": "completed_for_generated_wav",
        },
        "notes": "A faster-whisper round-trip is context-sensitive; the hiragana/phoneme CTC result is the pronunciation evidence. Null scores remain null when a local evaluator was unavailable.",
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "evaluated_audio_count": evaluated,
        "retry_count": total_retry_count,
        "stt": stt_info,
        "pronunciation": kana_info,
        "metrics": str(args.results_dir / "metrics.csv"),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
