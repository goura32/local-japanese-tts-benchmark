import wave
from pathlib import Path

import numpy as np
import pytest

from tts_benchmark.phase2 import (
    PHASE2_READING_VARIANTS,
    build_expression_result,
    build_phase2_requests,
    build_reading_variant,
    extract_expression_features,
    load_phase2_cases,
    map_instruction,
    select_human_review,
    validate_phase2_delta,
)

ROOT = Path(__file__).parents[1]


def test_phase2_fixture_expands_same_text_multi_style_cases():
    cases = load_phase2_cases(ROOT / "tests" / "phase2_cases.yaml")

    assert len(cases) == 13
    assert {case["id"] for case in cases} >= {
        "x01",
        "x02",
        "x03",
        "x04",
        "x05",
        "x06_neutral",
        "x06_cheerful",
        "x06_sad",
        "x06_angry",
        "x06_calm",
        "x06_tired",
        "x07",
        "x08",
    }
    x06 = [case for case in cases if case["group_id"] == "x06"]
    assert len(x06) == 6
    assert len({case["text"] for case in x06}) == 1


def test_instruction_mapping_prioritizes_native_capability_over_approximation():
    mapped = map_instruction(
        "formal_narration",
        {
            "natural_language": True,
            "official_style": True,
            "prosody_parameter": True,
            "same_speaker_multi_style": True,
        },
    )

    assert mapped["control_type"] == "自然言語"
    assert mapped["mapped_parameters"]["intent"] == "formal_narration"
    assert mapped["same_speaker_as_neutral"] is True


def test_reading_variant_keeps_raw_and_effective_input_separate():
    result = build_reading_variant(
        engine_id="example",
        case_id="p01",
        variant="external_preprocessed",
        raw_input="明日は東京へ行きます。",
        effective_input="あしたはとうきょうへいきます。",
        correction_method="pyopenjtalk",
        output_audio_path=None,
        stt_transcript="明日は東京へ行きます。",
        cer=0.0,
        kana_or_phoneme_result={"result": "合格", "confidence": 0.98},
        pronunciation_result="合格",
        evaluator_confidence=0.98,
        human_review_required=False,
    )

    assert tuple(result) == (
        "engine_id",
        "case_id",
        "variant",
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
        "expected_reading",
        "expected_kana",
        "expected_phonemes",
    )
    assert result["raw_input"] != result["effective_input"]
    assert result["variant"] in PHASE2_READING_VARIANTS


def test_reading_variant_keeps_expected_kana_and_phonemes():
    result = build_reading_variant(
        engine_id="engine",
        case_id="p01",
        variant="raw",
        raw_input="今日は一日中。",
        effective_input="今日は一日中。",
        correction_method="none",
        output_audio_path=None,
        stt_transcript=None,
        cer=None,
        kana_or_phoneme_result=None,
        pronunciation_result="対象外",
        evaluator_confidence=None,
        human_review_required=False,
        expected_reading="いちにちじゅう",
        expected_kana="いちにちじゅう",
        expected_phonemes="i ch i n i ch i j u u",
    )

    assert result["expected_kana"] == "いちにちじゅう"
    assert result["expected_phonemes"] == "i ch i n i ch i j u u"


def test_expression_result_does_not_turn_acoustic_proxy_into_mos():
    result = build_expression_result(
        engine_id="example",
        case_id="x06_cheerful",
        requested_instruction="明るく弾むように話す。",
        control_type="自然言語",
        mapped_parameters={"intent": "cheerful"},
        same_speaker_as_neutral=True,
        acoustic_features={"f0_range_hz": 72.0, "pause_ratio": 0.18},
        evaluator_score=None,
        human_review_required=True,
    )

    assert result["emotion_or_style_evaluator"]["status"] == "not_available"
    assert result["evaluator_score"] is None
    assert result["mos_estimate"] is None


def test_human_review_selection_is_bounded_per_engine_and_total():
    candidates = [
        {
            "engine_id": f"engine_{i % 6}",
            "case_id": f"x{i:02d}",
            "reason": "automatic evaluator disagreement",
            "priority": 100 - i,
            "regeneration_command": "python scripts/generate/run_phase2.py ...",
            "license_note": "private-only candidate; no public audio",
        }
        for i in range(24)
    ]

    selected = select_human_review(candidates, max_total=15, max_per_engine=5)

    assert len(selected) <= 15
    assert all(item["public_audio"] is False for item in selected)
    counts = {}
    for item in selected:
        counts[item["engine_id"]] = counts.get(item["engine_id"], 0) + 1
    assert max(counts.values()) <= 5


def test_human_review_selection_covers_expression_and_pronunciation_categories():
    candidates = [
        {"engine_id": "a", "case_id": "x06_neutral", "priority": 10, "review_category": "expression"},
        {"engine_id": "a", "case_id": "p01", "priority": 90, "review_category": "pronunciation"},
        {"engine_id": "a", "case_id": "p02", "priority": 89, "review_category": "pronunciation"},
        {"engine_id": "b", "case_id": "x06_neutral", "priority": 10, "review_category": "expression"},
        {"engine_id": "b", "case_id": "p01", "priority": 90, "review_category": "pronunciation"},
        {"engine_id": "b", "case_id": "p02", "priority": 89, "review_category": "pronunciation"},
    ]

    selected = select_human_review(candidates, max_total=4, max_per_engine=2)

    assert {(item["engine_id"], item["review_category"]) for item in selected} == {
        ("a", "expression"),
        ("a", "pronunciation"),
        ("b", "expression"),
        ("b", "pronunciation"),
    }


def test_phase2_schema_rejects_unbounded_review_queue():
    with pytest.raises(ValueError, match="human review"):
        validate_phase2_delta(
            {
                "schema_version": "2.0",
                "phase": "phase2",
                "baseline_schema_version": "1.0",
                "engines": [],
                "reading_variants": [],
                "expression_results": [],
                "human_review_manifest": [
                    {"engine_id": "x", "case_id": str(i)} for i in range(16)
                ],
            }
        )


def test_phase2_schema_rejects_a_score_for_target_out_engine():
    with pytest.raises(ValueError, match="target-out"):
        validate_phase2_delta(
            {
                "schema_version": "2.0",
                "phase": "phase2",
                "baseline_schema_version": "1.0",
                "engines": [
                    {
                        "engine_id": "unavailable",
                        "install_attempts": [{}],
                        "phase2_measurement_status": "対象外",
                        "phase2_exclusion_reason": "runtime unavailable",
                        "content_cer_mean": 0.0,
                    }
                ],
                "reading_variants": [],
                "expression_results": [],
                "human_review_manifest": [],
            }
        )


def test_expression_features_capture_f0_energy_pause_and_speaking_rate(tmp_path: Path):
    sample_rate = 16_000
    silence = np.zeros(sample_rate // 2, dtype=np.int16)
    time = np.arange(sample_rate, dtype=np.float64) / sample_rate
    tone = (0.25 * np.sin(2 * np.pi * 200 * time) * 32767).astype(np.int16)
    path = tmp_path / "tone.wav"
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(np.concatenate([silence, tone]).tobytes())

    features = extract_expression_features(path, "今日は元気です。")

    assert features["f0_mean_hz"] == pytest.approx(200, abs=5)
    assert features["f0_range_hz"] == pytest.approx(0, abs=10)
    assert features["energy_rms_dbfs"] < 0
    assert features["pause_ratio"] > 0.2
    assert features["speaking_rate_proxy"] is not None


def test_phase2_requests_keep_phase1_and_expand_reading_variants():
    phase1 = [
        {"id": "p01", "type": "pronunciation", "text": "今日は一日中。", "target_span": "一日中", "expected_reading": "いちにちじゅう"},
        {"id": "n01", "type": "naturalness", "text": "短い文です。"},
    ]
    phase2 = [{"id": "x01", "text": "明るく話す。", "instruction": "明るく。"}]

    requests = build_phase2_requests(phase1, phase2)

    assert len(requests) == 5
    p01 = [request for request in requests if request["case_id"] == "p01"]
    assert {request["reading_variant"] for request in p01} == set(PHASE2_READING_VARIANTS)
    external = next(request for request in p01 if request["reading_variant"] == "external_preprocessed")
    assert external["raw_input"] != external["effective_input"]
    assert sum(request["phase"] == "phase1" for request in requests) == 4
