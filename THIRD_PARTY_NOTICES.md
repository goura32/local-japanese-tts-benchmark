# Third-party notices

This repository contains benchmark code, configuration, reports, and metadata.
It does **not** redistribute TTS models, model caches, or the full generated
corpus. Third-party assets remain in their upstream distribution channels.

| Component | Role | License / usage condition | Repository treatment |
|---|---|---|---|
| AivisSpeech Engine | measured HTTP TTS engine | Verify the engine and each AIVM/AIVMX model license at download time | Not redistributed; source and version are recorded in `docs/LICENSE_NOTES.md` |
| VOICEVOX Engine | measured HTTP TTS engine when endpoint is available | Engine code and voice/model terms are separate; verify the selected speaker's terms | Not redistributed |
| faster-whisper | local STT evaluator | MIT; model terms follow the selected CTranslate2 model | Installed only in the temporary evaluation environment |
| hiragana-asr / Japanese wav2vec2 checkpoint | optional kana/phoneme pronunciation evaluator | Apache-2.0 for the checkpoint; training data terms are upstream-specific | Not redistributed; downloaded at runtime only |
| pyopenjtalk | optional reading and acoustic helper | MIT-style upstream terms; verify package notice when redistributing | Dependency only |

For COEIROINK, do not commit generated audio or model files without checking
the current voice/model-specific conditions. The upstream terms require the
applicable credit and prohibit treating model redistribution as automatic.
