from pathlib import Path

import pytest

from tts_benchmark.benchmark import load_cases, validate_engine_result
from tts_benchmark.metrics import assess_pronunciation, cer, levenshtein

ROOT = Path(__file__).parents[1]


def test_levenshtein_counts_insertions_deletions_and_substitutions():
    assert levenshtein("kitten", "sitting") == 3
    assert levenshtein("", "abc") == 3
    assert levenshtein("abc", "") == 3


def test_cer_normalizes_whitespace_but_preserves_japanese_content():
    assert cer("今日は  晴れです。", "今日は晴れです。") == pytest.approx(0.0)
    assert cer("今日は晴れです。", "今日は雨です。") == pytest.approx(2 / 8)


def test_pronunciation_requires_a_kana_or_phoneme_observation():
    assert assess_pronunciation("いちにちじゅう", "いちにちじゅう", "hiragana_ctc").result == "合格"
    assert assess_pronunciation("いちにちじゅう", "いちにちちゅう", "hiragana_ctc").result == "不合格"
    assert assess_pronunciation("いちにちじゅう", None, "hiragana_ctc").result == "要確認"
    # A kanji STT transcript alone is not pronunciation evidence.
    assert assess_pronunciation("いちにちじゅう", None, "stt_kanji_only").result == "要確認"


def test_cases_fixture_contains_all_required_case_families():
    cases = load_cases(ROOT / "tests" / "cases.yaml")
    assert {case["id"][0] for case in cases} == {"n", "e", "p", "m", "q", "l"}
    assert len(cases) == 30
    long_form = next(case for case in cases if case["id"] == "l01")
    assert 1000 <= len(long_form["text"]) <= 1500


def test_engine_result_rejects_missing_required_fields():
    with pytest.raises(ValueError, match="engine_id"):
        validate_engine_result({})


def test_engine_result_allows_null_unmeasured_scores():
    result = {
        "engine_id": "not_run",
        "engine_name": "Not run",
        "version": "unknown",
        "source_url": "https://example.invalid",
        "license": {},
        "local_inference": None,
        "japanese_support": "限定的",
        "install_status": "対象外",
        "install_notes": "Not run",
        "model_size_gb": None,
        "peak_vram_gb": None,
        "peak_ram_gb": None,
        "generation_rtf": None,
        "automation_score": None,
        "pronunciation_control_score": None,
        "expression_score": None,
        "naturalness_score": None,
        "content_accuracy_score": None,
        "overall_notes": "Not measured.",
        "human_review_required_count": 0,
    }
    validate_engine_result(result)
