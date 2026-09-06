# Local Japanese TTS Benchmark

A reproducible, local-only benchmark harness for Japanese text-to-speech engines.
It records official-source research separately from measurements, keeps model and
full audio files out of Git, and evaluates pronunciation with kana/phoneme
 evidence rather than relying on kanji STT equality alone.

## Status

Phase 1 remains reproducible in [`results/summary.json`](results/summary.json).
Phase 2 adds 43 raw cases (the original 30 plus the eight supplied expressive
cases, with `x06` expanded to six same-text styles), 39 reading-variant rows per
engine, and separate acoustic-expression evidence. Qwen3-TTS, Irodori-TTS,
Style-Bert-VITS2, and VOICEVOX were measured locally. IndexTTS-2.5 is an
explicit `対象外` result after three documented installation failures; it is
not zero-scored. See [`docs/PHASE2_RESULTS.md`](docs/PHASE2_RESULTS.md) and
[`results/phase2/summary.json`](results/phase2/summary.json).

Phase 2.1 is complete. A private 15-sample blind review was aggregated after
blind-map disclosure; only `naturalness` was entered. `instruction_match`,
`pronunciation_quality`, `would_use`, `reading_issue`, and `note` remain
`null` and are not treated as missing-input errors. The private map, review
audio, and score sheet are not in this repository. See
[`docs/PHASE2_1_HUMAN_REVIEW.md`](docs/PHASE2_1_HUMAN_REVIEW.md) and
[`results/phase2_1/`](results/phase2_1/).

## Reproduce

```bash
python3.11 -m venv <WORKDIR>/venv
. <WORKDIR>/venv/bin/activate
python -m pip install -e '.[dev,evaluation]'
python -m pytest
python scripts/generate/run_benchmark.py --engine-config config/engines.yaml \
  --cases tests/cases.yaml --output-dir results --audio-dir tmp/audio
python scripts/evaluate/evaluate_results.py --results-dir results --audio-dir tmp/audio \
  --kana-repo <WORKDIR>/hiragana-asr \
  --kana-checkpoint <WORKDIR>/best-medium-ep5-inference.pt
```

The evaluation extras add local STT and optional phoneme/kana models; model
weights are downloaded to a cache outside the repository. The runner supports
`--engines aivis,voicevox` and configurable HTTP endpoints. It performs one
preprocessing retry only for failed pronunciation cases and retains both
attempts in the JSON result.

For Phase 2, use [`docs/PHASE2_REPRODUCE.md`](docs/PHASE2_REPRODUCE.md):
`run_phase2.py` invokes the engine-specific adapters, keeps `raw`,
`engine_native`, and `external_preprocessed` reading paths separate, and
`evaluate_phase2.py` writes the additive `results/phase2/` delta without
overwriting the Phase 1 result.

For Phase 2.1 review aggregation, use
[`scripts/evaluate/aggregate_phase21.py`](scripts/evaluate/aggregate_phase21.py)
with the private score workbook and blind map. It writes only the anonymized
results under `results/phase2_1/`.

## Repository layout

- `config/`: engine metadata and run parameters
- `tests/cases.yaml`: fixed common cases from the supplied runbook
- `tests/phase2_cases.yaml`: fixed expressive/style cases for Phase 2
- `scripts/generate/`: repeatable TTS generation adapters
- `scripts/evaluate/`: local STT, pronunciation, and acoustic evaluation
- `results/`: schema-compliant summary and CSV measurements
- `docs/`: methodology, research, results, and license notes
- `environment/`: captured hardware and tool versions

No model weights, credentials, full audio corpus, or cache are committed.

## Scope and limitations

Phase 2.1 contains a bounded human naturalness review, not a complete human
MOS study. The public result reports the entered naturalness values separately
from Phase 2 machine metrics. The other review dimensions intentionally remain
`null`; no human pronunciation-quality, instruction-match, or would-use result
is claimed. Phase 2 still records `mos_estimate: null` when a validated MOS/style
evaluator is not available and never substitutes an invented human score.
Ambiguous pronunciation is marked `要確認` when recognizers disagree or no
acoustic phoneme/kana evidence is available.
Candidate implementation, model, speaker, reference-audio, and output terms
must be checked again before production use; the reports preserve what was
verified at the run date.
