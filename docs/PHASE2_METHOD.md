# Phase 2 method

## Scope and counts

Phase 1 remains the baseline at [`results/summary.json`](../results/summary.json); it is not overwritten. Phase 2 adds the 8 supplied expressive cases, expanding `x06` into six same-text style rows:

- 30 Phase 1 common cases;
- 13 Phase 2 rows (`x01`–`x05`, six `x06_*` rows, `x07`, `x08`);
- 43 raw cases per candidate;
- `p01`–`p13` receive three explicitly separate reading variants, producing 69 generation requests per candidate and 39 reading-variant rows.

The expansion is fixed in [`tests/phase2_cases.yaml`](../tests/phase2_cases.yaml). The supplied Drive specifications are recorded in the result metadata and are the source of the acceptance criteria.

## Reading-control protocol

Every reading comparison retains all of these fields:

1. `raw_input`: the original Japanese text;
2. `expected_reading`, `expected_kana`, and `expected_phonemes` when supplied by the case;
3. `effective_input`: the exact string sent to the engine;
4. `reading_variant`: `raw`, `engine_native`, or `external_preprocessed`;
5. `correction_method`: no correction, engine-native frontend, or expected-reading substitution;
6. auxiliary STT transcript, kana/phoneme CTC evidence, CTC confidence, and alignment evidence;
7. strict pronunciation status, relaxed status, and `human_review_required`.

`raw` sends the source text. `engine_native` sends the source text through the engine's own frontend without manual reading replacement. `external_preprocessed` replaces only the specified target span with the expected reading; it is not allowed to overwrite the source text silently. For engines without a separate native-reading API, the two input strings are intentionally equal but remain separate result rows so that the limitation is visible.

The kana/phoneme path is primary for pronunciation. `faster-whisper` is an auxiliary round trip, not ground truth.[20][21] The hiragana CTC checkpoint supplies kana/phoneme evidence.[22] `pyopenjtalk` is used only for the external preprocessing path.[23] A mismatch between recognizers is retained as evidence and is not collapsed into a single optimistic score.

## Expressive-control mapping

The mapping is capability-first and is stored per engine and per expression result:

1. natural-language instruction;
2. official style/emotion control;
3. speaker/style embedding;
4. explicit prosody parameters;
5. simple approximation, only when the preceding controls do not exist.

The mapping stores `control_type`, `mapped_parameters`, and `same_speaker_as_neutral`. A natural-language VoiceDesign output is not described as the same speaker across styles unless the engine guarantees that property. A fixed Style-Bert-VITS2 speaker is marked as same-speaker for its style-vector comparison. VOICEVOX parameter changes are labelled `prosody parameter`, not native emotion semantics.

The `x06_*` rows use the same text and differ only in the requested style. That makes directionally useful acoustic comparisons possible even when no validated style classifier is available. The raw instruction and mapped control are both retained.

## Acoustic and human evaluation

For each generated WAV the evaluator records duration, generation RTF, F0 mean/range, RMS energy, silence/pause ratio, and a text-character speaking-rate proxy. These are diagnostic acoustic proxies; they are not MOS and are not converted into a fabricated naturalness score.

The Phase 2 run had no validated automatic style/emotion evaluator. `style_evaluator`, `evaluator_score`, and `mos_estimate` therefore remain `null`/`not_available`. Naturalness MOS remains `not_measured`.

Human review candidates are ranked from pronunciation disagreement, acoustic anomalies, and representative same-text style rows. The public result contains at most 15 queue entries and at most 5 per engine. The queue contains no public audio path. The private Drive manifest is at `human_review_private/phase2_human_review_manifest.json`; `audio_saved=false` because per-engine output/reference redistribution terms were not used as a blanket permission.

## Unavailable engines

An engine is `対象外` only after its installation attempts and failure reasons are recorded. It has no CER, RTF, or expression score. Missing measurements are never converted to zero. IndexTTS-2.5 is the Phase 2 example: it has 69 explicit unavailable request rows and no generated-audio rows.

## Schema compatibility

Phase 1 schema and files remain unchanged. Phase 2 is an additive `schema_version: 2.0` delta at [`results/phase2/summary.json`](../results/phase2/summary.json), with `baseline_schema_version: 1.0` and `phase1_baseline_preserved: true`. Consumers that only understand Phase 1 can continue reading `results/summary.json`; Phase 2-aware consumers read `results/phase2/summary.json` and its separate `reading_variants` and `expression_results` arrays.
