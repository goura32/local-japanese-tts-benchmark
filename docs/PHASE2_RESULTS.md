# Phase 2 results

測定日は 2026-09-06 (JST) です。結果は [`results/phase2/summary.json`](../results/phase2/summary.json) に固定し、Phase 1の [`results/summary.json`](../results/summary.json) は保持しています。

## Acceptance counts

| item | result |
|---|---:|
| engines represented | 5 |
| raw cases per engine | 43 |
| generated raw rows | 276 / 345 |
| reading-variant rows | 195 (13 cases × 3 variants × 5 engines) |
| expression rows | 65 (13 × 5; unavailable rows retained) |
| human-review queue | 15 total; 5 maximum per measured engine |
| naturalness MOS | not measured (`null`) |
| automatic style evaluator | not available; acoustic proxies only |
| Phase 1 baseline | preserved and separately validated |

The 69 rows for IndexTTS-2.5 are explicit `unavailable`/`対象外` rows. They are not zero scores.

## Measured candidates

The CER and RTF columns below are means over the 13 Phase 2 expression rows with `reading_variant=raw`. They are content round-trip diagnostics, not a naturalness ranking.

| engine | raw cases | Phase 2 expression CER | expression generation RTF | reading result (`合格` / `要確認` / `不合格`) | same speaker across styles |
|---|---:|---:|---:|---|---|
| VOICEVOX Engine 0.25.2 | 43 / 43 | 0.120787 | 0.177549 | 6 / 3 / 30 | no; prosody approximation |
| Qwen3-TTS VoiceDesign | 43 / 43 | 0.140517 | 0.586816 | 4 / 10 / 25 | no guarantee; VoiceDesign |
| Irodori-TTS 500M v2 VoiceDesign | 43 / 43 | 0.129592 | 0.085583 | 8 / 9 / 22 | no guarantee; caption VoiceDesign |
| Style-Bert-VITS2 `jvnv-F1-jp` | 43 / 43 | 0.138604 | 0.051630 | 4 / 18 / 17 | yes; fixed speaker/style vector |

The full 43-case raw means are retained in each engine object (`content_cer_mean`, `generation_rtf_mean`), while the per-case CSV preserves the expression-only view used above.

## Interpretation

- VOICEVOX had the lowest Phase 2 expression CER among the measured engines, but its expressive mapping is a prosody-parameter approximation rather than a native emotion instruction. This does not establish a MOS advantage.
- Irodori-TTS and Qwen3-TTS provide natural-language VoiceDesign controls; their style identity is not asserted to be constant across instructions. Irodori had the lowest measured expression RTF in this run, while Qwen's RTF reflects its larger VoiceDesign path.
- Style-Bert-VITS2 provides the clearest same-speaker style-vector comparison in this run and the fastest measured expression RTF, but its reading recognizer produced many `要確認` rows and its AGPL/model/voice terms remain separate from this repository's MIT harness.
- IndexTTS-2.5 remains a documented target-out, not a missing zero. A future rerun must resolve its upstream dependency/checkpoint/reference-audio path before adding a number to the comparison.
- Pronunciation results require human confirmation for selected rows; recognizer disagreement is not treated as a model-quality proof. The human queue is stored separately and generated audio is not public.

## Reproduction evidence

The run was generated with 69 requests per candidate. Adapter logs and temporary WAVs were kept outside Git and removed after verification. The public result keeps request text, effective input, model/source revision, evidence fields, and sanitized relative metadata, but no model weights, reference audio, or full generated-audio corpus.

## Phase 2.1 human-review follow-up

The Phase 2.1 blind review is now complete for `naturalness` only. Its
engine/case aggregates and updated, metric-separated recommendations are in
[`PHASE2_1_HUMAN_REVIEW.md`](PHASE2_1_HUMAN_REVIEW.md) and
[`results/phase2_1/`](../results/phase2_1/). The Phase 2 machine tables above
remain unchanged; `pronunciation_quality`, `instruction_match`, `would_use`,
`reading_issue`, and `note` were intentionally not evaluated and remain
`null` in the Phase 2.1 result.
