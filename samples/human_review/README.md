# Human review queue

The automated run flagged the following nine case/engine pairs for targeted listening:

- `aivis`: `p02`, `p03`, `p04`, `p07`, `p11`, `p12`, `p13`
- `voicevox`: `p04`, `p13`

The queue is metadata-only in the public repository. Recreate the WAVs under `tmp/audio/` and verify the applicable model/voice terms before listening or sharing them. The JSON case records retain `first_attempt`, `retry_attempt`, CTC evidence, and relative audio paths.
