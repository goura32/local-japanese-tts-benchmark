# Phase 2.1 results

These files are the Public-safe output of the completed blind human review.
They were generated from the private review sheet after applying the private
blind map.

- `review_summary.json`: engine and engine/case naturalness aggregates.
- `review_scores_anonymized.csv`: the same case-level aggregates without blind
  sample IDs or private identity mapping.
- `final_recommendation.json`: separate human-naturalness and Phase 2 machine
  comparisons plus usage-specific recommendations.
- `validation.json`: fail-closed schema/public-boundary validation result.

Only `naturalness` was evaluated by humans. `instruction_match`,
`pronunciation_quality`, `would_use`, `reading_issue`, and `note` remain null;
they are not missing-input errors. Raw scores, the blind map, reviewer audio,
model weights, and the completed workbook remain outside this repository.

Regenerate with `scripts/evaluate/aggregate_phase21.py` using the private
score workbook and owner-private blind map, then run
`scripts/evaluate/validate_phase21.py` on the generated JSON files.
