# Phase 2 installation matrix

The authoritative machine-readable matrix is [`config/phase2_installation_matrix.yaml`](../config/phase2_installation_matrix.yaml). Each attempt is a real command run in an isolated temporary area. The matrix preserves failures instead of turning them into a generic `対象外` without evidence.

## Outcomes

| engine | successful path | target-out rule |
|---|---|---|
| Qwen3-TTS | upstream source with the existing CUDA PyTorch environment; pinned core runtime import and VoiceDesign probe passed | not target-out |
| IndexTTS-2.5 | none | target-out after official `uv`, source/CUDA compatibility, and upstream-pinned dependency routes failed; no checkpoint downloaded |
| Irodori-TTS | upstream source with existing CUDA PyTorch plus documented runtime dependencies; v2 VoiceDesign probe passed | not target-out |
| Style-Bert-VITS2 | upstream source with existing CUDA PyTorch and inference dependencies; fixed JP-Extra speaker probe passed | not target-out |
| VOICEVOX Engine | official `0.25.2` Docker image; `/version` returned `0.25.2` | not target-out |

## Isolation and cleanup

No dependency directory, model cache, Docker image, reference audio, or generated WAV is stored in Git. Reproduction commands use a caller-selected temporary work directory and cache; they must not point a virtual environment into the repository. The cleanup script accepts only the declared benchmark scratch directory and does not remove unrelated Docker containers or host files.

The public result contains installation route, source revision, model URL/revision, status, and reason. It does not contain a local absolute path or credential.
