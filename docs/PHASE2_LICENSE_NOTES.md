# Phase 2 license boundaries

This document is an audit boundary, not legal advice. Code, model weights, speaker/character terms, reference audio, and generated output are separate records. No Phase 2 model weights, reference recording, or generated WAV is committed.

| candidate | code | model | speaker / character | reference audio | generated output policy |
|---|---|---|---|---|---|
| Qwen3-TTS | upstream code Apache-2.0.[1][2][3] | selected VoiceDesign model card is separately recorded.[24] | no human/user speaker; VoiceDesign output | none used | do not infer unrestricted voice/output rights from code license; retain URL, revision, and local-only reproduction procedure |
| IndexTTS-2.5 | upstream code license is separate from model terms.[5][6][7] | model card identifies the bilibili model-use terms.[8][26] | fixed reference-audio conditioning would require a separately cleared speaker sample | no sample was retained because the runtime was not reproducibly installed | target-out; no checkpoint, reference, or output is published |
| Irodori-TTS | upstream runtime MIT.[9][10][11] | v2 VoiceDesign card adds model-specific ethical/output conditions.[12][27][29]; measured file SHA-256 is recorded in the research/config ledger | no user speaker; no-reference VoiceDesign path | none used | weights and generated audio remain local-only; audit the selected model card again before redistribution |
| Style-Bert-VITS2 | upstream repository AGPL-3.0.[13][14][15] | `litagin/style_bert_vits2_jvnv` has its own model-card conditions.[25] | fixed `jvnv-F1-jp` model speaker; character/voice credit is not assumed | none used | code license is not a blanket model/output/voice permission; no model or WAV is public |
| VOICEVOX Engine | upstream Engine code is LGPL v3 plus a source-code-non-disclosure dual-license.[17][18][19] | engine image/voice assets are not copied | speaker `0`; speaker/character credit and terms must be checked separately.[18] | none used | Docker digest and source URL only; no image, voice model, or generated WAV is public |

## Evaluation assets

The faster-whisper package is used as auxiliary STT only.[20][21] The hiragana CTC model is an external evaluation checkpoint, not a repository asset.[22] pyopenjtalk is an external reading-preprocessing dependency.[23] Their caches were outside the repository and removed during cleanup.

## Required publication rule

A future release may add an asset only when its exact source URL/revision, SHA-256, license, required credit, and redistribution decision are recorded together. Unknown or conflicting model/voice/output terms fail closed. A generated audio file is not made public merely because the code that produced it is open source.
