import wave

import numpy as np

from tts_benchmark.audio import analyze_wave


def test_analyze_wave_reports_duration_and_silence(tmp_path):
    path = tmp_path / "fixture.wav"
    samples = np.concatenate([np.zeros(8000, dtype=np.int16), np.full(8000, 1000, dtype=np.int16)])
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(samples.tobytes())

    result = analyze_wave(path)

    assert result["sample_rate_hz"] == 16000
    assert result["channels"] == 1
    assert result["duration_sec"] == 1.0
    assert 0.45 < result["silence_ratio"] < 0.55
    assert result["anomaly_flags"] == []
