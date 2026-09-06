"""Small, dependency-light WAV inspection helpers."""

from __future__ import annotations

import math
import wave
from pathlib import Path
from typing import Any

import numpy as np


def _estimate_f0(samples: np.ndarray, sample_rate: int) -> float | None:
    """Estimate a dominant pitch from one central voiced frame."""
    if samples.size < sample_rate // 20:
        return None
    frame_size = min(samples.size, int(sample_rate * 0.08))
    start = max(0, (samples.size - frame_size) // 2)
    frame = samples[start : start + frame_size].astype(np.float64)
    frame -= frame.mean()
    if np.max(np.abs(frame)) == 0:
        return None
    window = np.hanning(frame.size)
    spectrum = np.abs(np.fft.rfft(frame * window))
    frequencies = np.fft.rfftfreq(frame.size, 1 / sample_rate)
    mask = (frequencies >= 50) & (frequencies <= 500)
    if not np.any(mask):
        return None
    return float(frequencies[mask][np.argmax(spectrum[mask])])


def analyze_wave(path: str | Path) -> dict[str, Any]:
    """Return reproducible format, level, pause, and simple anomaly features."""
    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        sample_width = handle.getsampwidth()
        sample_rate = handle.getframerate()
        frame_count = handle.getnframes()
        raw = handle.readframes(frame_count)
    if sample_width == 1:
        samples = np.frombuffer(raw, dtype=np.uint8).astype(np.float64) - 128
        scale = 128.0
    elif sample_width == 2:
        samples = np.frombuffer(raw, dtype="<i2").astype(np.float64)
        scale = 32768.0
    elif sample_width == 4:
        samples = np.frombuffer(raw, dtype="<i4").astype(np.float64)
        scale = 2147483648.0
    else:
        raise ValueError(f"unsupported WAV sample width: {sample_width}")
    if channels > 1 and samples.size:
        samples = samples.reshape(-1, channels).mean(axis=1)
    duration = frame_count / sample_rate if sample_rate else 0.0
    normalized = samples / scale if scale else samples
    rms = float(np.sqrt(np.mean(normalized**2))) if normalized.size else 0.0
    peak = float(np.max(np.abs(normalized))) if normalized.size else 0.0
    rms_dbfs = 20 * math.log10(max(rms, 1e-12))
    peak_dbfs = 20 * math.log10(max(peak, 1e-12))

    frame_len = max(1, int(sample_rate * 0.02))
    frame_rms = []
    for start in range(0, normalized.size, frame_len):
        frame = normalized[start : start + frame_len]
        if frame.size:
            frame_rms.append(float(np.sqrt(np.mean(frame**2))))
    silence_threshold = max(10 ** (-60 / 20), rms * 0.05)
    silence_ratio = (
        sum(level < silence_threshold for level in frame_rms) / len(frame_rms)
        if frame_rms
        else 1.0
    )
    if normalized.size > 1:
        zcr = float(np.count_nonzero(np.diff(np.signbit(normalized))) / (normalized.size - 1))
    else:
        zcr = 0.0

    flags: list[str] = []
    if duration <= 0:
        flags.append("empty")
    if peak == 0:
        flags.append("all_silence")
    if duration > 600:
        flags.append("duration_over_600s")
    if silence_ratio > 0.8 and peak > 0:
        flags.append("high_silence")

    return {
        "sample_rate_hz": sample_rate,
        "channels": channels,
        "bits_per_sample": sample_width * 8,
        "frame_count": frame_count,
        "duration_sec": round(duration, 6),
        "rms_dbfs": round(rms_dbfs, 3),
        "peak_dbfs": round(peak_dbfs, 3),
        "silence_ratio": round(float(silence_ratio), 6),
        "zero_crossing_rate": round(zcr, 6),
        "estimated_f0_hz": round(_estimate_f0(samples, sample_rate), 3)
        if _estimate_f0(samples, sample_rate) is not None
        else None,
        "anomaly_flags": flags,
    }
