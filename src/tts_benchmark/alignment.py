"""Sequence alignment helpers for locating a target pronunciation in ASR output."""

from __future__ import annotations


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
