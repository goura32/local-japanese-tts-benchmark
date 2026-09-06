# Results artifacts

- `summary.json`: engine result and case result objects conforming to the supplied result schema.
- `metrics.csv`: one row per generated case with CER, RTF, pronunciation state, acoustic fields, retry, and error fields.
- `engine_results/<engine_id>.json`: per-engine split for downstream processing.
- `phase2_1/`: Public-safe naturalness-only human-review aggregates and final recommendations.

`install_status=対象外` and null scores mean unmeasured, not zero. `要確認` means the automatic path could not make a reliable decision. Full audio and model files live only in the temporary runtime and are deliberately excluded from Git.

Phase 2.1 keeps human naturalness separate from the Phase 2 machine metrics.
The private score sheet, blind map, sample IDs, and review audio are not stored
under this directory.
