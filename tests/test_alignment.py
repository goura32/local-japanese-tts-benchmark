from tts_benchmark.alignment import ctc_greedy_alignment, observed_for_reference_span


def test_ctc_greedy_alignment_exports_token_frame_spans():
    logits = [
        [4.0, 0.0, 0.0],
        [0.0, 4.0, 0.0],
        [0.0, 4.0, 0.0],
        [4.0, 0.0, 0.0],
        [0.0, 0.0, 4.0],
    ]

    aligned = ctc_greedy_alignment(logits, {0: "<blank>", 1: "あ", 2: "い"})

    assert aligned == [
        {"token_id": 1, "token": "あ", "start_frame": 1, "end_frame": 3},
        {"token_id": 2, "token": "い", "start_frame": 4, "end_frame": 5},
    ]


def test_observed_span_tracks_substitution_through_sequence_alignment():
    assert observed_for_reference_span("あいうえお", "あいずえお", 2, 3) == "ず"


def test_observed_span_returns_empty_for_deleted_reference_span():
    assert observed_for_reference_span("あいう", "あう", 1, 2) == ""
