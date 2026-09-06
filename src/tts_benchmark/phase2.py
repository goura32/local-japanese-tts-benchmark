"""Phase 2 fixture, control-mapping, and delta-schema helpers."""

from __future__ import annotations

import math
import wave
from pathlib import Path
from typing import Any

import numpy as np

from .benchmark import load_yaml

PHASE2_READING_VARIANTS = ("raw", "engine_native", "external_preprocessed")
PHASE2_MEASUREMENT_STATUSES = ("実測完了", "一部実測", "対象外")
INSTRUCTION_CONTROL_TYPES = (
    "自然言語",
    "公式style/emotion",
    "speaker/style embedding",
    "prosody parameter",
    "単純近似",
    "なし",
)


def load_phase2_cases(path: str | Path) -> list[dict[str, Any]]:
    """Load the explicitly expanded Phase 2 cases, including x06 style rows."""
    cases = load_yaml(path)
    if not isinstance(cases, list):
        raise TypeError("Phase 2 case fixture must be a YAML list")

    seen: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise TypeError("each Phase 2 case must be a mapping")
        case_id = case.get("id")
        text = case.get("text")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("Phase 2 case id must be a non-empty string")
        if case_id in seen:
            raise ValueError(f"duplicate Phase 2 case id: {case_id}")
        if not isinstance(text, str) or not text:
            raise ValueError(f"Phase 2 case {case_id} must contain text")
        if case_id.startswith("x06_") and case.get("group_id") != "x06":
            raise ValueError(f"same-text style case {case_id} must use group_id=x06")
        seen.add(case_id)
    return cases


def map_instruction(intent: str, capabilities: dict[str, Any]) -> dict[str, Any]:
    """Map a shared intent through the strongest capability the engine exposes."""
    layers = (
        ("natural_language", "自然言語"),
        ("official_style", "公式style/emotion"),
        ("speaker_style_embedding", "speaker/style embedding"),
        ("prosody_parameter", "prosody parameter"),
        ("simple_approximation", "単純近似"),
    )
    control_type = "なし"
    capability_key = None
    for key, label in layers:
        if capabilities.get(key) is True:
            control_type = label
            capability_key = key
            break

    same_speaker = capabilities.get("same_speaker_multi_style")
    if not isinstance(same_speaker, bool):
        same_speaker = None
    return {
        "control_type": control_type,
        "mapped_parameters": {
            "intent": intent,
            "capability": capability_key,
        },
        "same_speaker_as_neutral": same_speaker,
    }


def build_reading_variant(
    *,
    engine_id: str,
    case_id: str,
    variant: str,
    raw_input: str,
    effective_input: str,
    correction_method: str,
    output_audio_path: str | None,
    stt_transcript: str | None,
    cer: float | None,
    kana_or_phoneme_result: dict[str, Any] | None,
    pronunciation_result: str,
    evaluator_confidence: float | None,
    human_review_required: bool,
    expected_reading: str | None = None,
    expected_kana: str | None = None,
    expected_phonemes: str | None = None,
) -> dict[str, Any]:
    """Build one explicit raw/native/external pronunciation observation."""
    if variant not in PHASE2_READING_VARIANTS:
        raise ValueError(f"unknown Phase 2 reading variant: {variant}")
    if not isinstance(human_review_required, bool):
        raise TypeError("human_review_required must be boolean")
    return {
        "engine_id": engine_id,
        "case_id": case_id,
        "variant": variant,
        "raw_input": raw_input,
        "effective_input": effective_input,
        "correction_method": correction_method,
        "output_audio_path": output_audio_path,
        "stt_transcript": stt_transcript,
        "cer": cer,
        "kana_or_phoneme_result": kana_or_phoneme_result,
        "pronunciation_result": pronunciation_result,
        "evaluator_confidence": evaluator_confidence,
        "human_review_required": human_review_required,
        "expected_reading": expected_reading,
        "expected_kana": expected_kana,
        "expected_phonemes": expected_phonemes,
    }


def build_phase2_requests(
    phase1_cases: list[dict[str, Any]], phase2_cases: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Combine the Phase 1 fixture with Phase 2 cases without rewriting either."""
    requests: list[dict[str, Any]] = []
    for phase, cases in (("phase1", phase1_cases), ("phase2", phase2_cases)):
        for case in cases:
            raw_input = str(case["text"])
            variants = (
                PHASE2_READING_VARIANTS
                if phase == "phase1" and case.get("type") == "pronunciation"
                else ("raw",)
            )
            for variant in variants:
                effective_input = raw_input
                correction_method = "none"
                if variant == "external_preprocessed":
                    target_span = case.get("target_span")
                    expected_reading = case.get("expected_reading")
                    if not target_span or not expected_reading or target_span not in raw_input:
                        raise ValueError(
                            f"{case.get('id')} lacks target_span/expected_reading for external reading"
                        )
                    effective_input = raw_input.replace(target_span, expected_reading, 1)
                    correction_method = "expected_reading_substitution"
                elif variant == "engine_native":
                    correction_method = "engine_native"
                requests.append(
                    {
                        "phase": phase,
                        "case_id": case["id"],
                        "raw_input": raw_input,
                        "effective_input": effective_input,
                        "reading_variant": variant,
                        "correction_method": correction_method,
                        "expected_reading": case.get("expected_reading"),
                        "target_span": case.get("target_span"),
                        "instruction": case.get("instruction"),
                        "requested_style": case.get("requested_style", case.get("style")),
                        "group_id": case.get("group_id", case["id"]),
                    }
                )
    return requests


def build_expression_result(
    *,
    engine_id: str,
    case_id: str,
    requested_instruction: str,
    control_type: str,
    mapped_parameters: dict[str, Any],
    same_speaker_as_neutral: bool | None,
    acoustic_features: dict[str, Any],
    evaluator_score: float | None,
    human_review_required: bool,
) -> dict[str, Any]:
    """Build an expression observation without confusing proxies with MOS."""
    if control_type not in INSTRUCTION_CONTROL_TYPES:
        raise ValueError(f"unknown instruction control type: {control_type}")
    evaluator = {
        "status": "loaded" if evaluator_score is not None else "not_available",
        "name": "phase2_style_evaluator" if evaluator_score is not None else None,
        "score": evaluator_score,
        "interpretation": "automatic proxy; not human naturalness MOS",
    }
    return {
        "engine_id": engine_id,
        "case_id": case_id,
        "requested_instruction": requested_instruction,
        "control_type": control_type,
        "mapped_parameters": mapped_parameters,
        "same_speaker_as_neutral": same_speaker_as_neutral,
        "acoustic_features": acoustic_features,
        "emotion_or_style_evaluator": evaluator,
        "evaluator_score": evaluator_score,
        "mos_estimate": None,
        "human_review_required": human_review_required,
    }


def select_human_review(
    candidates: list[dict[str, Any]], *, max_total: int = 15, max_per_engine: int = 5
) -> list[dict[str, Any]]:
    """Select a deterministic, bounded review queue from automatic flags."""
    if max_total < 0 or max_per_engine < 0:
        raise ValueError("human review limits must be non-negative")
    ordered = sorted(
        candidates,
        key=lambda item: (
            -float(item.get("priority", 0)),
            str(item.get("engine_id", "")),
            str(item.get("case_id", "")),
        ),
    )
    selected: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    per_engine: dict[str, int] = {}

    def add_candidate(candidate: dict[str, Any]) -> bool:
        engine_id = str(candidate.get("engine_id", ""))
        case_id = str(candidate.get("case_id", ""))
        key = (engine_id, case_id)
        if not engine_id or not case_id or key in seen:
            return False
        if per_engine.get(engine_id, 0) >= max_per_engine:
            return False
        if len(selected) >= max_total:
            return False
        item = dict(candidate)
        item.pop("priority", None)
        item["public_audio"] = False
        item["private_drive_saved"] = bool(item.get("private_drive_saved", False))
        seen.add(key)
        per_engine[engine_id] = per_engine.get(engine_id, 0) + 1
        selected.append(item)
        return True

    # Reserve one slot per available review category and engine before filling
    # remaining capacity by priority. This keeps a large pronunciation failure
    # set from hiding every expression example.
    for category in ("expression", "pronunciation"):
        for engine_id in sorted({str(item.get("engine_id", "")) for item in ordered}):
            candidate = next(
                (
                    item
                    for item in ordered
                    if str(item.get("engine_id", "")) == engine_id
                    and item.get("review_category") == category
                ),
                None,
            )
            if candidate is not None:
                add_candidate(candidate)
    for candidate in ordered:
        add_candidate(candidate)
    return selected


def validate_phase2_delta(delta: dict[str, Any]) -> None:
    """Fail closed on the public Phase 2 delta contract."""
    required = {
        "schema_version",
        "phase",
        "baseline_schema_version",
        "engines",
        "reading_variants",
        "expression_results",
        "human_review_manifest",
    }
    missing = sorted(required - delta.keys())
    if missing:
        raise ValueError(f"Phase 2 delta missing required fields: {', '.join(missing)}")
    if delta["schema_version"] != "2.0" or delta["phase"] != "phase2":
        raise ValueError("Phase 2 delta must use schema_version=2.0 and phase=phase2")
    if delta["baseline_schema_version"] != "1.0":
        raise ValueError("Phase 2 baseline_schema_version must remain 1.0")

    engines = delta["engines"]
    if not isinstance(engines, list):
        raise TypeError("Phase 2 engines must be a list")
    engine_ids: set[str] = set()
    for engine in engines:
        if not isinstance(engine, dict) or not isinstance(engine.get("engine_id"), str):
            raise TypeError("each Phase 2 engine must contain engine_id")
        engine_id = engine["engine_id"]
        if engine_id in engine_ids:
            raise ValueError(f"duplicate Phase 2 engine: {engine_id}")
        engine_ids.add(engine_id)
        attempts = engine.get("install_attempts")
        if not isinstance(attempts, list) or not 1 <= len(attempts) <= 5:
            raise ValueError(f"{engine_id} must have 1-5 install_attempts")
        status = engine.get("phase2_measurement_status")
        if status not in PHASE2_MEASUREMENT_STATUSES:
            raise ValueError(f"{engine_id} has invalid phase2_measurement_status")
        if status == "対象外" and not str(engine.get("phase2_exclusion_reason", "")).strip():
            raise ValueError(f"{engine_id}対象外 requires phase2_exclusion_reason")
        if status == "対象外" and any(
            engine.get(field) is not None
            for field in ("content_cer_mean", "generation_rtf_mean", "evaluator_score")
        ):
            raise ValueError(f"target-out engine {engine_id} cannot have measured scores")

    reading_variants = delta["reading_variants"]
    if not isinstance(reading_variants, list):
        raise TypeError("Phase 2 reading_variants must be a list")
    reading_keys: set[tuple[str, str, str]] = set()
    for result in reading_variants:
        if not isinstance(result, dict):
            raise TypeError("each reading variant must be a mapping")
        key = (result.get("engine_id"), result.get("case_id"), result.get("variant"))
        if key in reading_keys:
            raise ValueError(f"duplicate reading variant: {key}")
        reading_keys.add(key)
        if result.get("variant") not in PHASE2_READING_VARIANTS:
            raise ValueError(f"invalid reading variant: {result.get('variant')}")
        for field in (
            "raw_input",
            "effective_input",
            "correction_method",
            "output_audio_path",
            "stt_transcript",
            "cer",
            "kana_or_phoneme_result",
            "pronunciation_result",
            "evaluator_confidence",
            "human_review_required",
        ):
            if field not in result:
                raise ValueError(f"reading variant missing {field}")
        if not isinstance(result["human_review_required"], bool):
            raise TypeError("reading variant human_review_required must be boolean")

    expression_results = delta["expression_results"]
    if not isinstance(expression_results, list):
        raise TypeError("Phase 2 expression_results must be a list")
    for result in expression_results:
        if not isinstance(result, dict):
            raise TypeError("each expression result must be a mapping")
        for field in (
            "engine_id",
            "case_id",
            "requested_instruction",
            "control_type",
            "mapped_parameters",
            "same_speaker_as_neutral",
            "acoustic_features",
            "emotion_or_style_evaluator",
            "evaluator_score",
            "mos_estimate",
            "human_review_required",
        ):
            if field not in result:
                raise ValueError(f"expression result missing {field}")
        if result["control_type"] not in INSTRUCTION_CONTROL_TYPES:
            raise ValueError("expression result has invalid control_type")
        if not isinstance(result["human_review_required"], bool):
            raise TypeError("expression human_review_required must be boolean")
        evaluator = result["emotion_or_style_evaluator"]
        if not isinstance(evaluator, dict) or evaluator.get("score") != result["evaluator_score"]:
            raise ValueError("expression evaluator score is inconsistent")
        if result["evaluator_score"] is None and result["mos_estimate"] is not None:
            raise ValueError("automatic proxy cannot be recorded as MOS")

    manifest = delta["human_review_manifest"]
    if not isinstance(manifest, list):
        raise TypeError("human_review_manifest must be a list")
    if len(manifest) > 15:
        raise ValueError("human review manifest exceeds 15 items")
    per_engine: dict[str, int] = {}
    for item in manifest:
        if not isinstance(item, dict):
            raise TypeError("human review item must be a mapping")
        for field in (
            "engine_id",
            "case_id",
            "reason",
            "public_audio",
            "private_drive_saved",
            "regeneration_command",
            "license_note",
        ):
            if field not in item:
                raise ValueError(f"human review item missing {field}")
        if item["public_audio"] is not False:
            raise ValueError("human review audio must not be public")
        if not isinstance(item["private_drive_saved"], bool):
            raise TypeError("private_drive_saved must be boolean")
        engine_id = str(item["engine_id"])
        per_engine[engine_id] = per_engine.get(engine_id, 0) + 1
    if per_engine and max(per_engine.values()) > 5:
        raise ValueError("human review manifest exceeds five items per engine")


def _frame_f0(frame: np.ndarray, sample_rate: int) -> float | None:
    """Estimate one voiced-frame F0 with a bounded autocorrelation search."""
    centered = frame.astype(np.float64) - float(np.mean(frame))
    if centered.size < 16 or float(np.sqrt(np.mean(centered**2))) <= 1e-5:
        return None
    windowed = centered * np.hanning(centered.size)
    correlation = np.correlate(windowed, windowed, mode="full")[centered.size - 1 :]
    min_lag = max(1, int(sample_rate / 500))
    max_lag = min(correlation.size - 1, int(sample_rate / 50))
    if max_lag <= min_lag:
        return None
    lag = min_lag + int(np.argmax(correlation[min_lag:max_lag]))
    if correlation[lag] <= 0:
        return None
    return sample_rate / lag


def extract_expression_features(
    path: str | Path, text: str | None = None
) -> dict[str, float | None]:
    """Extract reproducible acoustic proxies for the Phase 2 expression report."""
    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        sample_width = handle.getsampwidth()
        sample_rate = handle.getframerate()
        raw = handle.readframes(handle.getnframes())
    if sample_width == 2:
        samples = np.frombuffer(raw, dtype="<i2").astype(np.float64)
        scale = 32768.0
    elif sample_width == 4:
        samples = np.frombuffer(raw, dtype="<i4").astype(np.float64)
        scale = 2147483648.0
    else:
        raise ValueError(f"unsupported WAV sample width: {sample_width}")
    if channels > 1 and samples.size:
        samples = samples.reshape(-1, channels).mean(axis=1)
    normalized = samples / scale if scale else samples
    rms = float(np.sqrt(np.mean(normalized**2))) if normalized.size else 0.0
    frame_len = max(1, int(sample_rate * 0.04))
    frames = [normalized[i : i + frame_len] for i in range(0, normalized.size, frame_len)]
    frame_rms = [
        float(np.sqrt(np.mean(frame**2))) for frame in frames if frame.size
    ]
    threshold = max(10 ** (-55 / 20), rms * 0.05)
    voiced = [frame for frame in frames if frame.size and np.sqrt(np.mean(frame**2)) >= threshold]
    f0_values = [
        value
        for frame in voiced
        if (value := _frame_f0(frame, sample_rate)) is not None
    ]
    duration = len(normalized) / sample_rate if sample_rate else 0.0
    voiced_duration = len(voiced) * frame_len / sample_rate if sample_rate else 0.0
    characters = (
        sum(not char.isspace() and char not in "、。！？!?.,，．…「」『』（）()" for char in text)
        if text
        else 0
    )
    return {
        "f0_mean_hz": float(np.mean(f0_values)) if f0_values else None,
        "f0_range_hz": float(max(f0_values) - min(f0_values)) if f0_values else None,
        "energy_rms_dbfs": 20 * math.log10(max(rms, 1e-12)),
        "pause_ratio": 1 - (len(voiced) / len(frame_rms) if frame_rms else 0.0),
        "speaking_rate_proxy": characters / voiced_duration
        if characters and voiced_duration > 0
        else None,
        "duration_sec": duration,
    }


__all__ = [
    "INSTRUCTION_CONTROL_TYPES",
    "PHASE2_MEASUREMENT_STATUSES",
    "PHASE2_READING_VARIANTS",
    "build_expression_result",
    "build_phase2_requests",
    "build_reading_variant",
    "extract_expression_features",
    "load_phase2_cases",
    "map_instruction",
    "select_human_review",
    "validate_phase2_delta",
]
