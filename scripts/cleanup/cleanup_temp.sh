#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)

# Stop only the named benchmark container; never touch unrelated containers.
docker rm -f tts-bench-voicevox >/dev/null 2>&1 || true
if [[ "${KEEP_VOICEVOX_IMAGE:-0}" != "1" ]]; then
  docker image rm voicevox/voicevox_engine:latest >/dev/null 2>&1 || true
fi

# Stop only a process matching the benchmark's temporary Aivis invocation.
for pid in $(pgrep -f 'extracted/Linux-x64/run --host 127.0.0.1 --port 10101' || true); do
  if [[ -r "/proc/$pid/cmdline" ]] && tr '\0' ' ' < "/proc/$pid/cmdline" | grep -q '/tts-local-benchmark/aivis/'; then
    kill "$pid" >/dev/null 2>&1 || true
  fi
done

# AIVIS_PID may be supplied by the caller after verifying it belongs to the
# benchmark's temporary AivisSpeech Engine invocation.
if [[ -n "${AIVIS_PID:-}" ]] && [[ -r "/proc/${AIVIS_PID}/cmdline" ]]; then
  cmdline=$(tr '\0' ' ' < "/proc/${AIVIS_PID}/cmdline")
  if [[ "$cmdline" == *"tts-local-benchmark/aivis"* ]]; then
    kill "$AIVIS_PID" >/dev/null 2>&1 || true
  fi
fi

rm -rf "$ROOT/tmp" "$ROOT/.venv" "$ROOT/models" "$ROOT/cache"
SCRATCH_ROOT="${TTS_BENCHMARK_SCRATCH:-${TMPDIR:-/tmp}/tts-local-benchmark}"
rm -rf "$SCRATCH_ROOT"

printf 'temporary benchmark environments removed; repository artifacts retained at %s\n' "$ROOT"
