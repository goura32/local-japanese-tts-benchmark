#!/usr/bin/env python3
"""Generate the common fixture through reachable HTTP TTS engines."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import psutil
import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from tts_benchmark.audio import analyze_wave
from tts_benchmark.benchmark import (
    load_cases,
    load_yaml,
    validate_engine_result,
)


class EngineError(RuntimeError):
    """A reproducible engine request failure."""


def _gpu_used_gb() -> float | None:
    try:
        completed = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        values = [float(line.strip()) for line in completed.stdout.splitlines() if line.strip()]
        return max(values, default=0.0) / 1024
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def _service_ram_gb(engine: dict[str, Any]) -> float | None:
    """Read the external service/container RSS without assuming its process name."""
    try:
        if engine.get("adapter") == "voicevox_http":
            value = subprocess.run(
                ["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", "tts-bench-voicevox"],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout.strip().split("/", 1)[0].strip()
            match = re.fullmatch(r"([0-9.]+)([A-Za-z]+)", value)
            if not match:
                return None
            number, unit = match.groups()
            scale = {"B": 1, "KiB": 1024, "MiB": 1024**2, "GiB": 1024**3}[unit]
            return float(number) * scale / (1024**3)
        if engine.get("adapter") == "aivis_http":
            pids = subprocess.run(
                ["pgrep", "-f", "extracted/Linux-x64/run --host 127.0.0.1 --port 10101"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            ).stdout.split()
            rss_pages = []
            page_size = os.sysconf("SC_PAGE_SIZE")
            for pid in pids:
                try:
                    rss_pages.append(int(Path(f"/proc/{pid}/statm").read_text().split()[1]))
                except (FileNotFoundError, IndexError, ValueError):
                    continue
            return max(rss_pages, default=0) * page_size / (1024**3) or None
    except (OSError, subprocess.SubprocessError, ValueError, KeyError):
        return None
    return None


def _get_json(session: requests.Session, url: str, timeout: float = 10) -> Any:
    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        raise EngineError(f"GET {url} failed: {type(exc).__name__}: {exc}") from exc


def _post_json(session: requests.Session, url: str, payload: Any, timeout: float = 180) -> Any:
    try:
        response = session.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        raise EngineError(f"POST {url} failed: {type(exc).__name__}: {exc}") from exc


def _post_audio(session: requests.Session, url: str, payload: Any, timeout: float = 300) -> bytes:
    try:
        response = session.post(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            timeout=timeout,
        )
        response.raise_for_status()
        if not response.content.startswith((b"RIFF", b"RIFX")):
            raise EngineError(f"POST {url} returned non-WAV content")
        return response.content
    except requests.RequestException as exc:
        raise EngineError(f"POST {url} failed: {type(exc).__name__}: {exc}") from exc


def _style_mapping(engine: dict[str, Any], style: str) -> dict[str, Any]:
    mapping = engine.get("style_map", {}).get(style)
    if isinstance(mapping, dict):
        return mapping
    return {"speaker_id": engine.get("speaker_id"), "parameters": "default"}


def _apply_parameter_hint(query: dict[str, Any], hint: Any) -> dict[str, Any]:
    """Map the documented common intent to safe engine query parameters."""
    if not isinstance(hint, str) or hint == "default":
        return query
    parts = hint.split("_")
    if len(parts) == 3 and parts[0] in {"speed", "volume", "intonation"} and parts[1] == "scale":
        field = f"{parts[0]}Scale"
        try:
            query[field] = float(parts[2])
        except ValueError:
            pass
    return query


def _prepare_query(
    session: requests.Session,
    engine: dict[str, Any],
    text: str,
    mapping: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    endpoint = str(engine["endpoint"]).rstrip("/")
    speaker_id = mapping.get("speaker_id", engine.get("speaker_id"))
    if speaker_id is None:
        raise EngineError("no speaker_id configured")
    query_url = f"{endpoint}/audio_query?speaker={quote(str(speaker_id))}&text={quote(text, safe='')}"
    query = _post_json(session, query_url, {}, timeout=60)
    if not isinstance(query, dict):
        raise EngineError("audio_query did not return a JSON object")
    original_kana = query.get("kana")
    query = _apply_parameter_hint(query, mapping.get("parameters"))
    if engine.get("adapter") == "voicevox_http":
        # Older VOICEVOX versions accept the same schema; leave its defaults intact.
        pass
    return query, {"speaker_id": speaker_id, "parameters": mapping.get("parameters", "default"), "engine_reading_metadata": original_kana}


def _generate_one(
    session: requests.Session,
    engine: dict[str, Any],
    case: dict[str, Any],
    audio_root: Path,
) -> dict[str, Any]:
    raw_input = case["text"]
    mapping = _style_mapping(engine, case.get("style", "neutral"))
    start = time.perf_counter()
    query, mapping_record = _prepare_query(session, engine, raw_input, mapping)
    endpoint = str(engine["endpoint"]).rstrip("/")
    speaker_id = mapping_record["speaker_id"]
    synthesis_url = f"{endpoint}/synthesis?speaker={quote(str(speaker_id))}"
    audio = _post_audio(session, synthesis_url, query)
    generation_sec = time.perf_counter() - start
    output = audio_root / engine["engine_id"] / f"{case['id']}.wav"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(audio)
    features = analyze_wave(output)
    try:
        relative_audio = output.relative_to(ROOT).as_posix()
    except ValueError:
        relative_audio = str(output)
    return {
        "engine_id": engine["engine_id"],
        "case_id": case["id"],
        "raw_input": raw_input,
        "effective_input": raw_input,
        "requested_style": case.get("style", "neutral"),
        "mapped_style_or_parameters": mapping_record,
        "audio_path": relative_audio,
        "duration_sec": features["duration_sec"],
        "generation_sec": round(generation_sec, 6),
        "stt_transcript": None,
        "cer": None,
        "expected_reading": case.get("expected_reading"),
        "pronunciation_result": "要確認" if case.get("type") == "pronunciation" else "対象外",
        "pronunciation_evidence": {
            "status": "pending_acoustic_evaluator",
            "engine_reading_metadata": mapping_record.get("engine_reading_metadata"),
        },
        "mos_estimate": None,
        "acoustic_features": features,
        "retry_used": False,
        "error": None,
        "human_review_required": case.get("type") == "pronunciation",
    }


def _base_engine_result(engine: dict[str, Any]) -> dict[str, Any]:
    return {
        "engine_id": engine["engine_id"],
        "engine_name": engine["engine_name"],
        "version": engine.get("version", "未確認"),
        "source_url": engine["source_url"],
        "license": engine.get("license", {}),
        "local_inference": None,
        "japanese_support": engine.get("japanese_support", "未確認"),
        "install_status": "対象外",
        "install_notes": "",
        "model_size_gb": engine.get("model_size_gb"),
        "peak_vram_gb": None,
        "peak_ram_gb": None,
        "generation_rtf": None,
        "automation_score": None,
        "pronunciation_control_score": None,
        "expression_score": None,
        "naturalness_score": None,
        "content_accuracy_score": None,
        "overall_notes": engine.get("notes", "未計測"),
        "human_review_required_count": 0,
    }


def _probe_version(session: requests.Session, engine: dict[str, Any]) -> str:
    endpoint = str(engine["endpoint"]).rstrip("/")
    version = _get_json(session, f"{endpoint}/version", timeout=10)
    return str(version.get("version", version) if isinstance(version, dict) else version)


def run_engine(engine: dict[str, Any], cases: list[dict[str, Any]], audio_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    result = _base_engine_result(engine)
    case_results: list[dict[str, Any]] = []
    if engine.get("adapter") not in {"aivis_http", "voicevox_http"}:
        result["install_notes"] = engine.get("notes", "No adapter was configured for this snapshot.")
        result["overall_notes"] = (result["overall_notes"] + " No local adapter/checkpoint was run; scores remain null rather than zero.")[:2000]
        return result, case_results

    endpoint = engine.get("endpoint")
    if not endpoint:
        result["install_status"] = "失敗"
        result["install_notes"] = "HTTP adapter has no endpoint configured."
        return result, case_results

    session = requests.Session()
    try:
        observed_version = _probe_version(session, engine)
    except EngineError as exc:
        result["install_status"] = "失敗"
        result["local_inference"] = False
        result["install_notes"] = str(exc)
        result["overall_notes"] = (result["overall_notes"] + " Endpoint probe failed; no audio quality score was inferred.")[:2000]
        return result, case_results

    result["version"] = observed_version
    result["local_inference"] = True
    result["install_status"] = "成功"
    result["install_notes"] = f"Local HTTP endpoint probe succeeded: {endpoint}/version -> {observed_version}."
    before_gpu = _gpu_used_gb()
    max_gpu = before_gpu
    max_rss = max(
        psutil.Process().memory_info().rss / (1024**3),
        _service_ram_gb(engine) or 0.0,
    )
    failures = 0
    generation_total = 0.0
    audio_total = 0.0
    for case in cases:
        try:
            one = _generate_one(session, engine, case, audio_root)
            case_results.append(one)
            generation_total += one["generation_sec"]
            audio_total += one["duration_sec"]
            current_gpu = _gpu_used_gb()
            if current_gpu is not None:
                max_gpu = max(max_gpu or 0.0, current_gpu)
            max_rss = max(
                max_rss,
                psutil.Process().memory_info().rss / (1024**3),
                _service_ram_gb(engine) or 0.0,
            )
        except (EngineError, OSError, ValueError, wave_error()) as exc:  # type: ignore[misc]
            failures += 1
            case_results.append({
                "engine_id": engine["engine_id"],
                "case_id": case["id"],
                "raw_input": case["text"],
                "effective_input": case["text"],
                "requested_style": case.get("style", "neutral"),
                "mapped_style_or_parameters": _style_mapping(engine, case.get("style", "neutral")),
                "audio_path": None,
                "duration_sec": None,
                "generation_sec": None,
                "stt_transcript": None,
                "cer": None,
                "expected_reading": case.get("expected_reading"),
                "pronunciation_result": "要確認" if case.get("type") == "pronunciation" else "対象外",
                "pronunciation_evidence": {"status": "generation_failed"},
                "mos_estimate": None,
                "acoustic_features": None,
                "retry_used": False,
                "error": f"{type(exc).__name__}: {exc}",
                "human_review_required": case.get("type") == "pronunciation",
            })

    result["peak_vram_gb"] = round(max_gpu, 4) if max_gpu is not None else None
    result["peak_ram_gb"] = round(max_rss, 4)
    result["generation_rtf"] = round(generation_total / audio_total, 6) if audio_total else None
    if failures:
        result["install_status"] = "一部成功" if case_results else "失敗"
    result["automation_score"] = 4.0
    result["expression_score"] = 3.0
    result["overall_notes"] = (
        f"Measured {len(case_results) - failures}/{len(cases)} common cases through the local HTTP adapter. "
        "Expression score is a capability-mapping proxy, not a human MOS. "
        "Content, pronunciation, and automatic naturalness scores are filled by the separate local evaluator."
    )
    return result, case_results


def wave_error():
    # Keep wave import local so the runner's import surface stays small.
    import wave

    return wave.Error


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine-config", type=Path, default=ROOT / "config/engines.yaml")
    parser.add_argument("--cases", type=Path, default=ROOT / "tests/cases.yaml")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results")
    parser.add_argument("--audio-dir", type=Path, default=ROOT / "tmp/audio")
    parser.add_argument("--engines", help="comma-separated engine ids; defaults to all configured engines")
    args = parser.parse_args()

    engines = load_yaml(args.engine_config)["engines"]
    cases = load_cases(args.cases)
    selected = set(args.engines.split(",")) if args.engines else None
    engines = [engine for engine in engines if selected is None or engine["engine_id"] in selected]
    if not engines:
        raise SystemExit("no configured engines selected")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "engine_results").mkdir(parents=True, exist_ok=True)
    args.audio_dir.mkdir(parents=True, exist_ok=True)
    all_engine_results: list[dict[str, Any]] = []
    all_case_results: list[dict[str, Any]] = []
    run_started = datetime.now(UTC).isoformat()
    for engine in engines:
        result, case_results = run_engine(engine, cases, args.audio_dir)
        validate_engine_result(result)
        result["case_count"] = len(case_results)
        result["successful_case_count"] = sum(case["error"] is None for case in case_results)
        result["failed_case_count"] = sum(case["error"] is not None for case in case_results)
        all_engine_results.append(result)
        all_case_results.extend(case_results)
        (args.output_dir / "engine_results" / f"{engine['engine_id']}.json").write_text(
            json.dumps({"engine": result, "case_results": case_results}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    summary = {
        "schema_version": "1.0",
        "run_started_at": run_started,
        "run_finished_at": datetime.now(UTC).isoformat(),
        "cases_file": "tests/cases.yaml",
        "engines": all_engine_results,
        "case_results": all_case_results,
        "evaluation_status": "pending",
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "engines": [(item["engine_id"], item["install_status"], item["successful_case_count"]) for item in all_engine_results],
        "case_results": len(all_case_results),
        "summary": str(args.output_dir / "summary.json"),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
