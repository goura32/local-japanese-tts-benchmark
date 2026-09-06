# Phase 2 result delta

`summary.json` is schema `2.0` and is additive to the Phase 1 `results/summary.json` (`baseline_schema_version: 1.0`). It contains 5 engine entries, 345 case-result rows, 195 separate raw/native/external reading rows, and 65 expression rows. IndexTTS-2.5 rows are explicit `対象外`/`unavailable`; they are not zero-scored.

`metrics.csv` is a flat diagnostic view. `install_attempts.json` is the sanitized installation/target-out record. No full WAV, model weight, reference recording, credential, cache, or local absolute path is part of the public result.

`validation.json` is the fail-closed schema read-back for this snapshot. The private human-review manifest is kept in the Phase 2 Google Drive review area; it contains no audio in this run.

Validate with:

```bash
PYTHONPATH=src python scripts/evaluate/validate_phase2.py \
  --summary results/phase2/summary.json \
  --phase1-summary results/summary.json
```
