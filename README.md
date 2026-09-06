# Local Japanese TTS Benchmark

A reproducible, local-only benchmark harness for Japanese text-to-speech engines.
It records official-source research separately from measurements, keeps model and
full audio files out of Git, and evaluates pronunciation with kana/phoneme
 evidence rather than relying on kanji STT equality alone.

## Status

AivisSpeech Engine and VOICEVOX Engine were measured locally across all 30
common cases. Qwen3-TTS, IndexTTS-2.5, Style-Bert-VITS2, COEIROINK, and
CosyVoice remain explicit `対象外` entries because a reproducible local
runtime/checkpoint and the applicable model/voice terms were not established
in this run; they are not zero-scored. See [`docs/RESULTS.md`](docs/RESULTS.md).

## Reproduce

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev,evaluation]'
python -m pytest
python scripts/generate/run_benchmark.py --engine-config config/engines.yaml \
  --cases tests/cases.yaml --output-dir results --audio-dir tmp/audio
python scripts/evaluate/evaluate_results.py --results-dir results --audio-dir tmp/audio \
  --kana-repo /path/to/hiragana-asr \
  --kana-checkpoint /path/to/external/best-medium-ep5-inference.pt
```

The evaluation extras add local STT and optional phoneme/kana models; model
weights are downloaded to a cache outside the repository. The runner supports
`--engines aivis,voicevox` and configurable HTTP endpoints. It performs one
preprocessing retry only for failed pronunciation cases and retains both
attempts in the JSON result.

## Repository layout

- `config/`: engine metadata and run parameters
- `tests/cases.yaml`: fixed common cases from the supplied runbook
- `scripts/generate/`: repeatable TTS generation adapters
- `scripts/evaluate/`: local STT, pronunciation, and acoustic evaluation
- `results/`: schema-compliant summary and CSV measurements
- `docs/`: methodology, research, results, and license notes
- `environment/`: captured hardware and tool versions

No model weights, credentials, full audio corpus, or cache are committed.

## Scope and limitations

The benchmark is not a human MOS study. `mos_estimate` is explicitly an
automatic proxy when available. Ambiguous pronunciation is marked `要確認` if
recognizers disagree or no acoustic phoneme/kana evidence is available.
Candidate implementation and model licensing must be checked again before
production use; the report preserves what was verified at the run date.
