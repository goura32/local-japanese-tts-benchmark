# Results artifacts

- `summary.json`: engine result and case result objects conforming to the supplied result schema.
- `metrics.csv`: one row per generated case with CER, RTF, pronunciation state, acoustic fields, retry, and error fields.
- `engine_results/<engine_id>.json`: per-engine split for downstream processing.

`install_status=対象外` and null scores mean unmeasured, not zero. `要確認` means the automatic path could not make a reliable decision. Full audio and model files live only in the temporary runtime and are deliberately excluded from Git.
