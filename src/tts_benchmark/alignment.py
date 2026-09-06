"""Sequence alignment helpers for locating a target pronunciation in ASR output."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def ctc_greedy_alignment(
    logits: Sequence[Sequence[float]],
    token_map: Mapping[int, str],
    blank_id: int = 0,
) -> list[dict[str, int | str]]:
    """Return collapsed CTC tokens with half-open frame spans.

    This is an evidence export, not a forced alignment claim: it records the
    frames selected by greedy CTC decoding and leaves acoustic-to-text timing
    calibration to the caller.
    """
    aligned: list[dict[str, int | str]] = []
    active: dict[str, int | str] | None = None
    for frame, row in enumerate(logits):
        if not row:
            continue
        token_id = max(range(len(row)), key=row.__getitem__)
        if token_id == blank_id:
            if active is not None:
                aligned.append(active)
                active = None
            continue
        if active is not None and active["token_id"] == token_id:
            active["end_frame"] = frame + 1
            continue
        if active is not None:
            aligned.append(active)
        active = {
            "token_id": token_id,
            "token": token_map.get(token_id, "<unk>"),
            "start_frame": frame,
            "end_frame": frame + 1,
        }
    if active is not None:
        aligned.append(active)
    return aligned


def observed_for_reference_span(reference: str, hypothesis: str, start: int, end: int) -> str:
    """Return hypothesis characters aligned to ``reference[start:end]``.

    Insertions are not assigned to a reference character. Substitutions keep
    the hypothesis character, while deletions contribute nothing. This makes a
    target-span decision explicit instead of comparing an unrelated whole-string
    STT result.
    """
    if not 0 <= start <= end <= len(reference):
        raise ValueError("reference span is out of bounds")
    rows = len(reference) + 1
    cols = len(hypothesis) + 1
    distances = [[0] * cols for _ in range(rows)]
    for i in range(1, rows):
        distances[i][0] = i
    for j in range(1, cols):
        distances[0][j] = j
    for i in range(1, rows):
        for j in range(1, cols):
            distances[i][j] = min(
                distances[i - 1][j - 1] + (reference[i - 1] != hypothesis[j - 1]),
                distances[i - 1][j] + 1,
                distances[i][j - 1] + 1,
            )

    mapped: list[str | None] = [None] * len(reference)
    i, j = len(reference), len(hypothesis)
    while i or j:
        if i and j:
            diagonal = distances[i - 1][j - 1] + (reference[i - 1] != hypothesis[j - 1])
            if distances[i][j] == diagonal:
                mapped[i - 1] = hypothesis[j - 1]
                i -= 1
                j -= 1
                continue
        if i and distances[i][j] == distances[i - 1][j] + 1:
            i -= 1
            continue
        if j and distances[i][j] == distances[i][j - 1] + 1:
            j -= 1
            continue
        raise RuntimeError("failed to backtrack sequence alignment")
    return "".join(char for char in mapped[start:end] if char is not None)
