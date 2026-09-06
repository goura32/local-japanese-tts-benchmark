# Reproduce Phase 2

Run on Linux with an NVIDIA CUDA device for the measured configuration. Keep `<WORKDIR>` outside the repository. Never commit the model caches, reference audio, or generated WAVs.

## 1. Install the harness

```bash
python3.11 -m venv <WORKDIR>/harness-venv
. <WORKDIR>/harness-venv/bin/activate
python -m pip install -e '.[dev,evaluation]'
python -m pytest
```

The Phase 2 request set is deterministic:

```bash
python scripts/generate/run_phase2.py \
  --engine-config config/phase2_engines.yaml \
  --cases tests/cases.yaml \
  --phase2-cases tests/phase2_cases.yaml \
  --output-dir <WORKDIR>/runs/<engine> \
  --audio-dir <WORKDIR>/audio \
  --engines <engine>
```

The command writes a temporary `phase2_manifest.json` and invokes the selected adapter. Use one isolated Python environment per adapter where its official dependencies require incompatible versions.

## 2. Engine-specific inputs

The public config contains model IDs and logical adapter paths, not local model paths. Set the following caller-owned values before running the matching adapter:

- Qwen3-TTS: `TTS_PHASE2_QWEN_MODEL` points to the pinned `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign` snapshot. VoiceDesign uses natural-language Japanese instructions and no reference recording.
- Irodori-TTS: `TTS_PHASE2_IRODORI_CHECKPOINT` points to the pinned `Aratako/Irodori-TTS-500M-v2-VoiceDesign` `model.safetensors` file; set `HF_HOME` to the external cache used by the official runtime.
- Style-Bert-VITS2: `TTS_PHASE2_STYLE_MODEL_ROOT` points to the downloaded `jvnv-F1-jp` model directory; set `TTS_PHASE2_STYLE_BERT_MODEL` to the Japanese BERT model ID or external local cache.
- VOICEVOX: start the official `voicevox/voicevox_engine:0.25.2` image and expose port `50021`; the adapter uses speaker `0`.
- IndexTTS-2.5: set `TTS_PHASE2_INDEX_MODEL_DIR` and `TTS_PHASE2_INDEX_REFERENCE_AUDIO` only after the upstream dependency and reference-audio license audit succeeds. The current pinned run is target-out.

The adapter source files record the exact API calls and keep `raw`, `engine_native`, and `external_preprocessed` request records separate.

## 3. Evaluate

Use all per-engine manifests from step 1:

```bash
python scripts/evaluate/evaluate_phase2.py \
  --manifest <WORKDIR>/runs/voicevox/phase2_manifest.json \
  --manifest <WORKDIR>/runs/qwen3_tts/phase2_manifest.json \
  --manifest <WORKDIR>/runs/irodori_tts/phase2_manifest.json \
  --manifest <WORKDIR>/runs/style_bert_vits2/phase2_manifest.json \
  --manifest <WORKDIR>/runs/indextts_25/phase2_manifest.json \
  --results-dir results/phase2 \
  --phase1-summary results/summary.json \
  --engine-config config/phase2_engines.yaml \
  --installation-matrix config/phase2_installation_matrix.yaml \
  --stt-model small \
  --stt-cache <WORKDIR>/cache/stt \
  --kana-repo <WORKDIR>/hiragana-asr \
  --kana-checkpoint <WORKDIR>/cache/hiragana-ctc/best-medium-ep5-inference.pt
python scripts/evaluate/validate_phase2.py \
  --summary results/phase2/summary.json \
  --phase1-summary results/summary.json
```

`faster-whisper` is auxiliary; kana/phoneme CTC and alignment evidence are retained for pronunciation. If an evaluation model cannot be loaded, the result records `not_loaded` and does not invent a score. If a naturalness MOS study is not performed, `mos_estimate` remains `null`.

## 4. Review and cleanup

Human-review audio is never put in the public repository. If the applicable engine, speaker, reference, and output terms permit private review, save only to the private Drive review area and update its manifest. Otherwise keep `audio_saved=false` and regenerate locally from the recorded request.

After verification, stop only the benchmark's named process/container and delete only `<WORKDIR>` and the external model/audio cache used by this run. Re-run the prepublish audit after cleanup.
