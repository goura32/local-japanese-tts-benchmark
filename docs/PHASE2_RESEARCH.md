# Phase 2 official research and fixed inputs

調査基準日は 2026-09-06 (JST) です。外部情報は公式 repository、公式 Hugging Face model card、または公式 terms を取得して確認しました。Git の SHA は測定時に `git rev-parse HEAD` で固定し、重みと生成音声は公開 repository に含めません。

## Required candidates

| candidate | fixed source / model | Japanese and control surface | code / model / voice boundary | Phase 2 result |
|---|---|---|---|---|
| Qwen3-TTS | `QwenLM/Qwen3-TTS` `022e286b98fbec7e1e916cb940cdf532cd9f488e`; `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign` snapshot `5ecdb67327fd37bb2e042aab12ff7391903235d3` | Official documentation lists Japanese and VoiceDesign instruction control.[1][24] VoiceDesign was used without a reference recording. | Code is Apache-2.0.[3] The selected model card is separately audited; model/output rights are not inferred from source code alone. | **実測完了**: VoiceDesign, 43 raw cases plus 39 reading-variant outputs. |
| IndexTTS-2.5 | `index-tts/index-tts` `ee40fa7d6c6b8a2c7f06105f9f1e65775b74868c`; official model card `IndexTeam/IndexTTS-2.5` | The model card documents Japanese, reference-audio conditioning, `emo_alpha`, an eight-dimensional emotion vector, and duration control.[5][8] | Code and model are separate obligations; no checkpoint or reference audio was retained after the failed installation routes.[7] | **対象外**: three documented installation routes failed before a reproducible local checkpoint/runtime was available. It is not zero-scored. |
| Irodori-TTS | `Aratako/Irodori-TTS` `8224dafb46d0aba89209a8f905f1cb7e3299d9c1`; `Aratako/Irodori-TTS-500M-v2-VoiceDesign` snapshot `456e55708e7183f5c7faa1448209d54aa8991451` | The official runtime and selected model card provide Japanese VoiceDesign using natural-language captions.[9][29] The measured v2 path did not require a user reference recording. | Runtime code is MIT.[11] The v2 model card adds model-specific ethical/output conditions, so weights and audio remain excluded from the public tree. | **実測完了**: caption VoiceDesign, 43 raw cases plus 39 reading-variant outputs. |
| Style-Bert-VITS2 | `litagin02/Style-Bert-VITS2` `66de777e06392c0f313600be03c43ef96658b244`; `litagin/style_bert_vits2_jvnv` | Official docs provide Japanese inference and explicit style/emotion vectors.[13][25] The fixed `jvnv-F1-jp` speaker was reused across style cases. | The code and terms are AGPL-3.0-related; model/character/voice conditions are audited separately.[15] No model, BERT cache, or audio is committed. | **実測完了**: fixed speaker with style mapping, 43 raw cases plus 39 reading-variant outputs. |
| VOICEVOX Engine | `VOICEVOX/voicevox_engine` image `0.25.2`, digest `sha256:eb8c7f46a7d01217d1ff2b6f018261faedeceded3cc756b4fbbf371791ad6c90` | Official Engine API exposes Japanese text synthesis and engine-side frontend processing.[17][18] Phase 2 uses speaker `0`; expressive instructions are recorded as parameter approximations, not as native emotion semantics. | Engine code is LGPL v3 plus a source-code-non-disclosure dual-license.[19] Speaker/character credit and output conditions must be checked separately; the image, voice model, and output WAVs are not redistributed here.[18][19] | **実測完了**: baseline speaker with parameter mapping, 43 raw cases plus 39 reading-variant outputs. |

## Installation decision record

The exact sanitized commands and outcomes are machine-readable in [`config/phase2_installation_matrix.yaml`](../config/phase2_installation_matrix.yaml) and copied into [`results/phase2/install_attempts.json`](../results/phase2/install_attempts.json). The important boundary is:

- Qwen3-TTS, Irodori-TTS, Style-Bert-VITS2, and VOICEVOX reached a reproducible local generation probe. Their model/cache/audio files remain temporary.
- IndexTTS-2.5 was not silently treated as a zero. The official `uv` path hit the temporary disk quota; a source install with the available CUDA stack failed on the upstream cache API; the upstream project pin failed on the incompatible Hub API. The result is `対象外` with a reason and the three attempts.
- The temporary full CUDA dependency graphs were not copied into this repository. The successful paths reused one isolated CUDA PyTorch environment or the official Docker image, with per-engine compatibility dependencies recorded in the run log and reproduction document.

## Evaluation dependencies

`faster-whisper` is used only as an auxiliary Japanese STT round trip, not as the pronunciation ground truth.[20][21]

The primary pronunciation evidence is the Japanese hiragana CTC checkpoint and its kana/phoneme tooling.[22]

`pyopenjtalk` is used for the external target-reading substitution path.[23]

## Fixed revisions and non-redistribution hashes

| item | exact revision recorded | public tree policy |
|---|---|---|
| Qwen3-TTS source | `022e286b98fbec7e1e916cb940cdf532cd9f488e` | source URL and revision only |
| Qwen VoiceDesign model | Hub snapshot `5ecdb67327fd37bb2e042aab12ff7391903235d3` | model URL/revision only; no weights |
| Irodori source | `8224dafb46d0aba89209a8f905f1cb7e3299d9c1` | source URL and revision only |
| Irodori v2 model | Hub snapshot `456e55708e7183f5c7faa1448209d54aa8991451`; downloaded file SHA-256 `8b703c28e88f160dee0258b1136f8fe1ea68c063b45fc28375b5a134d6ce1131` | model URL/revision/hash only; no weights |
| Style-Bert-VITS2 source | `66de777e06392c0f313600be03c43ef96658b244` | source URL and revision only |
| VOICEVOX image | `sha256:eb8c7f46a7d01217d1ff2b6f018261faedeceded3cc756b4fbbf371791ad6c90` | image digest only; no image/voice binaries |
| kana checkpoint | Hub snapshot `d30d246cd24a225821d03d183de7bb2e769e18df`; 631542555 bytes; SHA-256 `1c8d97f2c01560da21df4095cea800f0b6f12dd1269c8e2233e6db659b502e14` | external cache only |

The Hub snapshot identifiers above are immutable retrieval revisions; they are not presented as a file SHA-256. A future run that needs byte-level publication must compute a SHA-256 after download and re-run the license audit.

The Qwen README and CustomVoice card were checked together with the selected VoiceDesign card.[2][4]

The Index README and model license were read separately from the model card.[6][26]

The Irodori README and base v2 card were checked as supporting materials.[10][12]

The Style-Bert-VITS2 README and terms document were checked separately from the model card.[14][16]

The v2 emoji-annotation page and the newer v4.1 model card were checked as adjacent official materials, but neither changes the selected v2 measurement input.[27][28]

## Sources

[1] https://github.com/QwenLM/Qwen3-TTS
[2] https://raw.githubusercontent.com/QwenLM/Qwen3-TTS/main/README.md
[3] https://raw.githubusercontent.com/QwenLM/Qwen3-TTS/main/LICENSE
[4] https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice/raw/main/README.md
[5] https://github.com/index-tts/index-tts
[6] https://raw.githubusercontent.com/index-tts/index-tts/main/README.md
[7] https://raw.githubusercontent.com/index-tts/index-tts/main/LICENSE
[8] https://huggingface.co/IndexTeam/IndexTTS-2.5/raw/main/README.md
[9] https://github.com/Aratako/Irodori-TTS
[10] https://raw.githubusercontent.com/Aratako/Irodori-TTS/main/README.md
[11] https://raw.githubusercontent.com/Aratako/Irodori-TTS/main/LICENSE
[12] https://huggingface.co/Aratako/Irodori-TTS-500M-v2/raw/main/README.md
[13] https://github.com/litagin02/Style-Bert-VITS2
[14] https://raw.githubusercontent.com/litagin02/Style-Bert-VITS2/master/README.md
[15] https://raw.githubusercontent.com/litagin02/Style-Bert-VITS2/master/LICENSE
[16] https://raw.githubusercontent.com/litagin02/Style-Bert-VITS2/master/docs/TERMS_OF_USE.md
[17] https://github.com/VOICEVOX/voicevox_engine
[18] https://raw.githubusercontent.com/VOICEVOX/voicevox_engine/master/README.md
[19] https://raw.githubusercontent.com/VOICEVOX/voicevox_engine/master/LICENSE
[20] https://github.com/SYSTRAN/faster-whisper
[21] https://raw.githubusercontent.com/SYSTRAN/faster-whisper/master/README.md
[22] https://huggingface.co/sakasegawa/japanese-wav2vec2-large-hiragana-ctc/raw/main/README.md
[23] https://github.com/r9y9/pyopenjtalk
[24] https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign/raw/main/README.md
[25] https://huggingface.co/litagin/style_bert_vits2_jvnv/raw/main/README.md
[26] https://huggingface.co/IndexTeam/IndexTTS-2.5/raw/main/LICENSE
[27] https://huggingface.co/Aratako/Irodori-TTS-500M-v2-VoiceDesign/raw/main/EMOJI_ANNOTATIONS.md
[28] https://huggingface.co/Aratako/Irodori-TTS-v4.1-Small/raw/main/README.md
[29] https://huggingface.co/Aratako/Irodori-TTS-500M-v2-VoiceDesign/raw/main/README.md
