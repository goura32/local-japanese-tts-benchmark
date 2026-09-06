from tts_benchmark.alignment import observed_for_reference_span


def test_observed_span_tracks_substitution_through_sequence_alignment():
    assert observed_for_reference_span("あいうえお", "あいずえお", 2, 3) == "ず"


def test_observed_span_returns_empty_for_deleted_reference_span():
    assert observed_for_reference_span("あいう", "あう", 1, 2) == ""
