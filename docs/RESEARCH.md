# 調査結果（公式仕様の整理）

この表は、Runbookの7候補について、2026-09-06（JST）に公式リポジトリ／公式規約を読み直した結果である。公式仕様と今回の実測結果は分離している。モデル本体・音声モデル・生成音声の条件は同一ではないため、コードのライセンスだけで利用可否を決めない。

| 候補 | 日本語・表現制御 | ローカル自動化の入口 | 今回の状態 | ライセンス上の扱い |
|---|---|---|---|---|
| Qwen3-TTS | 公式READMEは日本語を含む10言語、VoiceDesign、CustomVoice、VoiceClone、指示制御を記載。[1] | Python API / Hugging Faceモデル | 実測対象外：互換チェックポイント未導入 | コードはApache-2.0。[21] モデルは選択するチェックポイントの規約を再確認 |
| IndexTTS-2.5 | 公式READMEに感情ベクトル、テキスト由来の感情、速度係数、読みの置換例がある。[2] | `indextts/infer_v2_5.py` とチェックポイント | 実測対象外：チェックポイント未導入 | LICENSEはbilibili Model Use License Agreementであり、利用規模・派生物・再配布条件を別途確認。[22] |
| AivisSpeech Engine | VOICEVOX ENGINE互換を基盤とする日本語TTS。AIVM/AIVMX、辞書、話者スタイルを扱う。[19] | `/audio_query` → `/synthesis` HTTP API | **実測成功：30ケース** | EngineはLGPL-3.0を継承。[23] 音声モデルと生成音声はモデルごとの条件を別確認 |
| Style-Bert-VITS2 | CPUのみの音声合成も可能で、Pythonライブラリ利用例がある。[5] | `pip install style-bert-vits2` またはWebUI/API | 実測対象外：再現可能なチェックポイント未導入 | リポジトリはAGPL-3.0。[25] `text/user_dict`はLGPL-3.0の由来を持つ |
| VOICEVOX Engine | `/audio_query` と `/synthesis` のHTTP API、ユーザー辞書の読み・アクセント修正がある。[4] | Dockerまたは配布バイナリ + HTTP API | **実測成功：30ケース** | LICENSEはLGPL-3.0と、ソース公開不要の別ライセンスのデュアルライセンス。[24] 話者ごとの条件を別確認 |
| COEIROINK | 公式規約上、生成音声は「COEIROINK」と合成音声名のクレジットが必須。[7] | 公式配布物のローカルAPI | 実測対象外：音声・モデル条件が未確定 | 学習済み音声モデルの再配布は禁止され、生成音声を共有する場合も規約遵守を要求。[7] 今回は生成物を作らず、公開物へ含めない |
| CosyVoice | 現行READMEは日本語を含む多言語、感情・速度・音量などの指示、0.5B級モデルを記載。[20] | Python / FastAPI / gRPC / Docker | 実測対象外：依存・チェックポイント未導入 | コードはApache-2.0。[26] モデル／音声条件は選択モデルごとに再確認 |

## 評価器

内容のround-tripには、CTranslate2ベースの`faster-whisper`をローカルGPUで使った。[10][27] これは文脈を使うため、誤発音を正しい漢字へ補正する可能性がある。したがって内容CERは読み精度の代替ではない。

読み評価には、ひらがなCTCと音素CTCのdual-headを持つ`japanese-wav2vec2-large-hiragana-ctc`を使用した。同モデルは315.6Mパラメータ、かな84 token、音素43 tokenを公表している。[11] ターゲット語の前後を`pyopenjtalk`で文脈化し、認識したひらがな列をシーケンスアラインメントして、`expected_reading`の対象区間だけを判定した。エンジンの`kana`／読みメタデータだけで「合格」とはしていない。

## 実測対象外の意味

実測対象外は0点ではない。今回の隔離環境にチェックポイントと対応アダプタを用意できなかったため、`install_status=対象外`、性能スコア=nullとした。公式仕様が魅力的でも、今回の結果から音質順位を推測していない。

## Sources

[1] https://raw.githubusercontent.com/QwenLM/Qwen3-TTS/main/README.md
[2] https://raw.githubusercontent.com/index-tts/index-tts/main/README.md
[4] https://raw.githubusercontent.com/VOICEVOX/voicevox_engine/master/README.md
[5] https://raw.githubusercontent.com/litagin02/Style-Bert-VITS2/master/README.md
[7] https://coeiroink.com/terms
[10] https://raw.githubusercontent.com/SYSTRAN/faster-whisper/master/README.md
[11] https://huggingface.co/sakasegawa/japanese-wav2vec2-large-hiragana-ctc/raw/main/README.md
[19] https://raw.githubusercontent.com/Aivis-Project/AivisSpeech-Engine/master/README.md
[20] https://raw.githubusercontent.com/QwenAudio/CosyVoice/main/README.md
[21] https://raw.githubusercontent.com/QwenLM/Qwen3-TTS/main/LICENSE
[22] https://raw.githubusercontent.com/index-tts/index-tts/main/LICENSE
[23] https://raw.githubusercontent.com/Aivis-Project/AivisSpeech-Engine/master/LICENSE
[24] https://raw.githubusercontent.com/VOICEVOX/voicevox_engine/master/LICENSE
[25] https://raw.githubusercontent.com/litagin02/Style-Bert-VITS2/master/LICENSE
[26] https://raw.githubusercontent.com/FunAudioLLM/CosyVoice/main/LICENSE
[27] https://raw.githubusercontent.com/SYSTRAN/faster-whisper/master/LICENSE
