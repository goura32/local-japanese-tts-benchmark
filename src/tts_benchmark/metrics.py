"""Text and pronunciation metrics used by the benchmark."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_ALLOWED_ACOUSTIC_EVIDENCE = {
    "forced_alignment",
    "hiragana_ctc",
    "kana_ctc",
    "phoneme_ctc",
}


def normalize_text(value: str) -> str:
    """Normalize Unicode and remove whitespace without changing Japanese text."""
    value = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", "", value)


def levenshtein(reference: str, hypothesis: str) -> int:
    """Return character-level Levenshtein distance."""
    if reference == hypothesis:
        return 0
    if not reference:
        return len(hypothesis)
    if not hypothesis:
        return len(reference)
    previous = list(range(len(hypothesis) + 1))
    for i, ref_char in enumerate(reference, start=1):
        current = [i]
        for j, hyp_char in enumerate(hypothesis, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[j] + 1,
                    previous[j - 1] + (ref_char != hyp_char),
                )
            )
        previous = current
    return previous[-1]


def cer(reference: str, hypothesis: str) -> float:
    """Compute normalized character error rate after whitespace normalization."""
    reference = normalize_text(reference)
    hypothesis = normalize_text(hypothesis)
    if not reference:
        return 0.0 if not hypothesis else 1.0
    return levenshtein(reference, hypothesis) / len(reference)


@dataclass(frozen=True)
class PronunciationAssessment:
    result: str
    evidence_type: str
    observed: str | None
    error_rate: float | None
    note: str


def assess_pronunciation(
    expected_reading: str,
    observed_reading: str | None,
    evidence_type: str,
) -> PronunciationAssessment:
    """Assess a target reading without treating kanji STT as acoustic evidence."""
    if evidence_type not in _ALLOWED_ACOUSTIC_EVIDENCE:
        return PronunciationAssessment(
            result="要確認",
            evidence_type=evidence_type,
            observed=observed_reading,
            error_rate=None,
            note="No acoustic kana/phoneme evidence was supplied; kanji STT equality is insufficient.",
        )
    if observed_reading is None or not normalize_text(observed_reading):
        return PronunciationAssessment(
            result="要確認",
            evidence_type=evidence_type,
            observed=observed_reading,
            error_rate=None,
            note="Acoustic recognizer returned no usable target reading.",
        )
    error_rate = cer(expected_reading, observed_reading)
    result = "合格" if error_rate == 0.0 else "不合格"
    return PronunciationAssessment(
        result=result,
        evidence_type=evidence_type,
        observed=observed_reading,
        error_rate=error_rate,
        note="Exact normalized kana/phoneme target match." if result == "合格" else "Acoustic target reading differs from expected reading.",
    )
