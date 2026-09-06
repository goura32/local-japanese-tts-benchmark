# Setup notes

The benchmark runner does not silently install heavyweight model weights. Install the project in an isolated Python 3.11 environment, then start one or more local engines.

## VOICEVOX Engine

```bash
docker pull voicevox/voicevox_engine@sha256:eb8c7f46a7d01217d1ff2b6f018261faedeceded3cc756b4fbbf371791ad6c90
docker run --rm -d --name tts-bench-voicevox \
  -p 127.0.0.1:50021:50021 voicevox/voicevox_engine@sha256:eb8c7f46a7d01217d1ff2b6f018261faedeceded3cc756b4fbbf371791ad6c90
```

## AivisSpeech Engine

Install the Linux distribution and a model separately, start the engine on
`127.0.0.1:10101`, and set the `endpoint` and `speaker_id` in
`config/engines.yaml`. Do not commit the distribution or model.

## Local evaluators

The optional `evaluation` extra contains `faster-whisper`, PyTorch,
torchaudio, pyopenjtalk, and transformers. Clone `nyosegawa/hiragana-asr`
outside this repository, download its checkpoint outside this repository, and
pass both paths to `evaluate_results.py`.
