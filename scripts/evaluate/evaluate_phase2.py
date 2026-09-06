"""Evaluate Phase 2 manifests and emit a public-safe delta result."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from tts_benchmark.audio import analyze_wave
from tts_benchmark.metrics import cer
from tts_benchmark.phase2 import (
    build_expression_result,
    build_reading_variant,
    extract_expression_features,
    map_instruction,
    select_human_review,
    validate_phase2_delta,
)


def _load_phase1_evaluator():
    path = ROOT / "scripts/evaluate/evaluate_results.py"
    spec = importlib.util.spec_from_file_location("phase1_evaluator", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import Phase 1 evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _public_adapter_metadata(row: dict[str, Any]) -> dict[str, Any]:
    """Keep useful adapter fields while removing temporary paths and logs."""
    metadata: dict[str, Any] = {}
    for key, value in row.items():
        if key in {"audio_path", "request_id", "generation_sec", "status"}:
            continue
        if "path" in key.lower() or "log" in key.lower():
            continue
        if key == "error":
            metadata[key] = "adapter failed; stderr output was retained outside the repository"
        else:
            metadata[key] = value
    return metadata


def _load_manifests(paths: list[Path]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    loaded: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for path in paths:
        manifest = _read_json(path)
        if manifest.get("phase") != "phase2":
            raise ValueError(f"not a Phase 2 manifest: {path}")
        requests = {row["request_id"]: row for row in manifest.get("requests", [])}
        for run in manifest.get("engine_runs", []):
            loaded.append((run, requests))
    return loaded


def _case_id_map(paths: list[Path]) -> dict[str, dict[str, Any]]:
    cases: dict[str, dict[str, Any]] = {}
    for path in paths:
        for case in yaml.safe_load(path.read_text(encoding="utf-8")):
            cases[case["id"]] = case
    return cases


def _safe_audio_features(path: Path, text: str) -> tuple[dict[str, Any], dict[str, Any]]:
    return analyze_wave(path), extract_expression_features(path, text)


def _expected_phonemes(reading: str | None) -> str | None:
    if not reading:
        return None
    try:
        import pyopenjtalk

        return str(pyopenjtalk.g2p(reading, kana=False)).strip()
    except Exception:  # noqa: BLE001 - optional phoneme frontend
        return None


def _audio_reference(path: Path | None, root: Path) -> str | None:
    if path is None:
        return None
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return None


def _write_metrics(path: Path, records: list[dict[str, Any]]) -> None:
    fields = [
        "engine_id",
        "phase",
        "case_id",
        "reading_variant",
        "status",
        "duration_sec",
        "generation_sec",
        "rtf",
        "cer",
        "f0_mean_hz",
        "f0_range_hz",
        "energy_rms_dbfs",
        "pause_ratio",
        "speaking_rate_proxy",
        "pronunciation_result",
        "human_review_required",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for record in records:
            acoustic = record.get("expression_features", {})
            writer.writerow(
                {
                    field: record.get(field)
                    for field in fields[:9]
                }
                | {
                    "f0_mean_hz": acoustic.get("f0_mean_hz"),
                    "f0_range_hz": acoustic.get("f0_range_hz"),
                    "energy_rms_dbfs": acoustic.get("energy_rms_dbfs"),
                    "pause_ratio": acoustic.get("pause_ratio"),
                    "speaking_rate_proxy": acoustic.get("speaking_rate_proxy"),
                    "pronunciation_result": record.get("pronunciation_result"),
                    "human_review_required": record.get("human_review_required", False),
                }
            )


def _install_matrix(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"installation matrix is missing: {path}")
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise TypeError("installation matrix must be a YAML list")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, action="append", required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--phase1-summary", type=Path, default=ROOT / "results/summary.json")
    parser.add_argument("--cases", type=Path, default=ROOT / "tests/cases.yaml")
    parser.add_argument("--phase2-cases", type=Path, default=ROOT / "tests/phase2_cases.yaml")
    parser.add_argument("--engine-config", type=Path, default=ROOT / "config/phase2_engines.yaml")
    parser.add_argument("--installation-matrix", type=Path, default=ROOT / "config/phase2_installation_matrix.yaml")
    parser.add_argument("--stt-model", default="small")
    parser.add_argument("--stt-cache", type=Path, default=Path(tempfile.gettempdir()) / "tts-phase2/model-cache/stt")
    parser.add_argument("--kana-checkpoint", type=Path)
    parser.add_argument("--kana-repo", type=Path)
    parser.add_argument("--skip-stt", action="store_true")
    parser.add_argument("--skip-kana", action="store_true")
    args = parser.parse_args()

    engine_config = yaml.safe_load(args.engine_config.read_text(encoding="utf-8"))
    configs = {item["engine_id"]: item for item in engine_config["engines"]}
    phase1_cases = yaml.safe_load(args.cases.read_text(encoding="utf-8"))
    phase2_cases = yaml.safe_load(args.phase2_cases.read_text(encoding="utf-8"))
    cases = _case_id_map([args.cases, args.phase2_cases])
    phase2_ids = {case["id"] for case in phase2_cases}
    pronunciation_ids = {case["id"] for case in phase1_cases if case.get("type") == "pronunciation"}

    evaluator = _load_phase1_evaluator()
    stt_model = None
    stt_info: dict[str, Any] = {"status": "skipped" if args.skip_stt else "pending"}
    if not args.skip_stt:
        try:
            stt_model, stt_info = evaluator._load_stt(args.stt_model, args.stt_cache)
            stt_info["status"] = "loaded"
        except Exception as exc:  # noqa: BLE001 - availability is a measured result
            stt_info = {"status": "unavailable", "error": f"{type(exc).__name__}: {exc}"}

    kana_model = None
    kana_info: dict[str, Any] = {"status": "skipped" if args.skip_kana else "pending"}
    if not args.skip_kana:
        if args.kana_checkpoint is None or args.kana_repo is None:
            kana_info = {"status": "unavailable", "error": "checkpoint and repo are required"}
        else:
            try:
                kana_model = evaluator.KanaRecognizer(
                    args.kana_checkpoint,
                    device="cuda" if _cuda_available() else "cpu",
                    repo_root=args.kana_repo,
                )
                kana_info = {
                    "status": "loaded",
                    "model": evaluator.KANA_MODEL_ID,
                    "device": str(kana_model.device),
                }
            except Exception as exc:  # noqa: BLE001 - availability is a measured result
                kana_info = {"status": "unavailable", "error": f"{type(exc).__name__}: {exc}"}

    output_records: list[dict[str, Any]] = []
    reading_variants: list[dict[str, Any]] = []
    expression_results: list[dict[str, Any]] = []
    engine_results: list[dict[str, Any]] = []
    human_candidates: list[dict[str, Any]] = []

    for run, request_map in _load_manifests(args.manifest):
        engine_id = str(run["engine_id"])
        config = configs[engine_id]
        rows = {row["request_id"]: row for row in run.get("rows", [])}
        engine_records: list[dict[str, Any]] = []
        for request_id, request in request_map.items():
            if request_id not in rows:
                continue
            row = rows[request_id]
            case_id = str(request["case_id"])
            case = cases[case_id]
            audio_path = Path(row["audio_path"]) if row.get("status") == "generated" and row.get("audio_path") else None
            audio_features: dict[str, Any] = {}
            expression_features: dict[str, Any] = {}
            transcript: str | None = None
            transcript_info: dict[str, Any] | None = None
            content_cer: float | None = None
            if audio_path is not None and audio_path.exists():
                audio_features, expression_features = _safe_audio_features(audio_path, request["raw_input"])
                if stt_model is not None:
                    transcript, transcript_info = evaluator._transcribe(stt_model, audio_path)
                    content_cer = cer(request["raw_input"], transcript)
                else:
                    transcript_info = {"status": stt_info["status"]}
            elif row.get("status") != "generated":
                transcript_info = {"status": "not_generated"}

            result = {
                "engine_id": engine_id,
                "phase": request["phase"],
                "case_id": case_id,
                "group_id": request["group_id"],
                "reading_variant": request["reading_variant"],
                "status": row.get("status", "unavailable"),
                "raw_input": request["raw_input"],
                "effective_input": request["effective_input"],
                "requested_instruction": request.get("instruction"),
                "requested_style": request.get("requested_style"),
                "expected_reading": request.get("expected_reading"),
                "expected_kana": request.get("expected_reading"),
                "expected_phonemes": _expected_phonemes(request.get("expected_reading")),
                "target_span": request.get("target_span"),
                "audio_path": _audio_reference(audio_path, ROOT),
                "duration_sec": audio_features.get("duration_sec"),
                "generation_sec": row.get("generation_sec"),
                "rtf": (
                    row.get("generation_sec") / audio_features["duration_sec"]
                    if row.get("generation_sec") is not None and audio_features.get("duration_sec")
                    else None
                ),
                "acoustic_features": audio_features,
                "expression_features": expression_features,
                "stt_transcript": transcript,
                "stt_info": transcript_info,
                "cer": content_cer,
                "adapter_metadata": _public_adapter_metadata(row),
                "pronunciation_result": "not_applicable",
                "human_review_required": False,
            }
            if case_id in pronunciation_ids:
                if kana_model is not None and audio_path is not None and audio_path.exists():
                    kana_result = kana_model.recognize(audio_path)
                    assessment, evidence = evaluator._assess_case_pronunciation(case, kana_result)
                    result["pronunciation_result"] = assessment.result
                    result["pronunciation_evidence"] = evidence
                    pronunciation_evidence = evidence
                    pronunciation_confidence = None
                else:
                    result["pronunciation_result"] = "要確認" if audio_path else "対象外"
                    pronunciation_evidence = {
                        "status": kana_info["status"],
                        "note": kana_info.get("error"),
                        "kana_ctc_alignment": None,
                        "phoneme_ctc_alignment": None,
                        "alignment_timing": None,
                    }
                    result["pronunciation_evidence"] = pronunciation_evidence
                    pronunciation_confidence = None
                reading = build_reading_variant(
                    engine_id=engine_id,
                    case_id=case_id,
                    variant=request["reading_variant"],
                    raw_input=request["raw_input"],
                    effective_input=request["effective_input"],
                    correction_method=request["correction_method"],
                    output_audio_path=None,
                    stt_transcript=transcript,
                    cer=content_cer,
                    kana_or_phoneme_result=pronunciation_evidence,
                    pronunciation_result=result["pronunciation_result"],
                    evaluator_confidence=pronunciation_confidence,
                    human_review_required=False,
                    expected_reading=request.get("expected_reading"),
                    expected_kana=request.get("expected_reading"),
                    expected_phonemes=_expected_phonemes(request.get("expected_reading")),
                )
                reading_variants.append(reading)
            output_records.append(result)
            engine_records.append(result)
            if case_id in phase2_ids and request["reading_variant"] == "raw":
                mapped = map_instruction(
                    str(request.get("requested_style") or "neutral"),
                    config.get("instruction_control", {}),
                )
                expression = build_expression_result(
                    engine_id=engine_id,
                    case_id=case_id,
                    requested_instruction=str(request.get("instruction") or ""),
                    control_type=mapped["control_type"],
                    mapped_parameters={**mapped["mapped_parameters"], **row.get("mapped_parameters", {})},
                    same_speaker_as_neutral=mapped["same_speaker_as_neutral"],
                    acoustic_features=expression_features,
                    evaluator_score=None,
                    human_review_required=False,
                )
                expression["status"] = result["status"]
                expression_results.append(expression)
                if result["status"] == "generated":
                    priority = 40
                    reason = "expression output requires representative listening because no validated style evaluator is installed"
                    if audio_features.get("anomaly_flags"):
                        priority = 100
                        reason = "automatic acoustic anomaly flag"
                    human_candidates.append(
                        {
                            "engine_id": engine_id,
                            "case_id": case_id,
                            "review_category": "expression",
                            "reason": reason,
                            "priority": priority,
                            "regeneration_command": "use the recorded phase2_manifest request with the engine-specific adapter",
                            "license_note": "private review only; generated audio is not included in the public repository",
                        }
                    )
            if case_id in pronunciation_ids and result["pronunciation_result"] in {"不合格", "要確認"}:
                human_candidates.append(
                    {
                        "engine_id": engine_id,
                        "case_id": case_id,
                        "review_category": "pronunciation",
                        "reason": "pronunciation recognizer requires human confirmation",
                        "priority": 90,
                        "regeneration_command": "use the recorded phase2_manifest request with the engine-specific adapter",
                        "license_note": "private review only; generated audio is not included in the public repository",
                    }
                )

        generated_raw = [
            item for item in engine_records if item["reading_variant"] == "raw" and item["status"] == "generated"
        ]
        raw_cers = [item["cer"] for item in generated_raw if isinstance(item.get("cer"), (int, float))]
        raw_rtf = [item["rtf"] for item in generated_raw if isinstance(item.get("rtf"), (int, float))]
        phase2_raw = [item for item in generated_raw if item["phase"] == "phase2"]
        engine_results.append(
            {
                "engine_id": engine_id,
                "model": config.get("model_id"),
                "model_snapshot": config.get("model_snapshot"),
                "model_file_sha256": config.get("model_file_sha256"),
                "codec_id": config.get("codec_id"),
                "speaker": config.get("speaker_id", config.get("reference_policy")),
                "reference": config.get("reference_policy"),
                "install_attempts": [],
                "phase2_measurement_status": "実測完了" if generated_raw else "対象外",
                "phase2_exclusion_reason": None if generated_raw else "adapter did not produce any audio; see installation matrix",
                "case_count": len({item["case_id"] for item in engine_records if item["reading_variant"] == "raw"}),
                "successful_case_count": len(generated_raw),
                "phase2_expression_case_count": len(phase2_raw),
                "phase2_expression_generated_count": len(phase2_raw),
                "reading_variant_count": sum(item["engine_id"] == engine_id for item in reading_variants),
                "content_cer_mean": round(mean(raw_cers), 6) if raw_cers else None,
                "generation_rtf_mean": round(mean(raw_rtf), 6) if raw_rtf else None,
                "same_speaker_multi_style": config.get("instruction_control", {}).get("same_speaker_multi_style"),
                "instruction_control": config.get("instruction_control", {}),
                "naturalness_mos": None,
                "human_review_required_count": 0,
            }
        )

    matrix = _install_matrix(args.installation_matrix)
    matrix_by_engine = {item["engine_id"]: item["attempts"] for item in matrix}
    for engine in engine_results:
        engine["install_attempts"] = matrix_by_engine.get(engine["engine_id"], [])
        if not any(item["status"] == "generated" for item in output_records if item["engine_id"] == engine["engine_id"]):
            engine["phase2_measurement_status"] = "対象外"
            engine["phase2_exclusion_reason"] = engine["phase2_exclusion_reason"] or "no generated output"

    human_review = select_human_review(human_candidates, max_total=15, max_per_engine=5)
    selected_keys = {(item["engine_id"], item["case_id"]) for item in human_review}
    for item in output_records:
        item["human_review_required"] = (item["engine_id"], item["case_id"]) in selected_keys
    for item in reading_variants + expression_results:
        item["human_review_required"] = (item["engine_id"], item["case_id"]) in selected_keys
    for engine in engine_results:
        engine["human_review_required_count"] = sum(
            item["engine_id"] == engine["engine_id"] and item["human_review_required"]
            for item in output_records
        )

    for item in reading_variants:
        item["output_audio_path"] = None
    summary = {
        "schema_version": "2.0",
        "phase": "phase2",
        "baseline_schema_version": "1.0",
        "created_at": datetime.now(UTC).isoformat(),
        "phase1_summary_path": "results/summary.json",
        "phase1_baseline_preserved": args.phase1_summary.exists(),
        "specification": {
            "runbook": "Google Drive/00_ChatGPT/Projects/音声AI・音声処理基盤/TTSローカル音声合成ベンチマーク/Phase2_表現力・読み制御拡張/00_RUNBOOK_PHASE2_TTS_BENCHMARK.docx",
            "additional_cases": "Google Drive/00_ChatGPT/Projects/音声AI・音声処理基盤/TTSローカル音声合成ベンチマーク/Phase2_表現力・読み制御拡張/01_TEST_CASES_PHASE2_EXPRESSIVE.docx",
            "delta_schema": "Google Drive/00_ChatGPT/Projects/音声AI・音声処理基盤/TTSローカル音声合成ベンチマーク/02_PHASE2_RESULT_DELTA_SCHEMA.docx",
        },
        "evaluation": {
            "stt": stt_info,
            "pronunciation": kana_info,
            "naturalness_mos": {"status": "not_measured", "value": None},
            "expression": {
                "status": "acoustic_proxies_only",
                "style_evaluator": None,
                "mos_estimate": None,
                "features": ["f0_mean_hz", "f0_range_hz", "energy_rms_dbfs", "pause_ratio", "speaking_rate_proxy"],
            },
        },
        "engines": engine_results,
        "case_results": output_records,
        "reading_variants": reading_variants,
        "expression_results": expression_results,
        "human_review_manifest": human_review,
    }
    validate_phase2_delta(summary)
    args.results_dir.mkdir(parents=True, exist_ok=True)
    (args.results_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _write_metrics(args.results_dir / "metrics.csv", output_records)
    (args.results_dir / "install_attempts.json").write_text(
        json.dumps(matrix, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "schema": "valid",
                "engine_count": len(engine_results),
                "case_result_count": len(output_records),
                "reading_variant_count": len(reading_variants),
                "expression_result_count": len(expression_results),
                "human_review_count": len(human_review),
            },
            ensure_ascii=False,
        )
    )
    return 0


def _cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:  # noqa: BLE001 - optional evaluator dependency
        return False


if __name__ == "__main__":
    raise SystemExit(main())
