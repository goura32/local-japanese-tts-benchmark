# ライセンスと公開境界

## このリポジトリ

- `LICENSE`：ベンチマークの新規コードと文書をMITで公開する。
- `THIRD_PARTY_NOTICES.md`：外部エンジン、評価器、モデル、音声の境界を記録する。
- 結果JSON・CSVは、この実行で作成した測定メタデータである。生成音声そのものの再配布許諾を意味しない。

## 候補ごとの分離

| 候補 | コード | モデル | 生成音声 |
|---|---|---|---|
| Qwen3-TTS | upstream LICENSEはApache-2.0。[21] | 選択checkpointのモデルカードを確認 | speaker/reference音声を含むため未配布 |
| IndexTTS-2.5 | repository LICENSEはbilibili Model Use License Agreement。[22] | 同規約とcheckpoint条件を確認 | 未配布 |
| AivisSpeech Engine | LGPL-3.0。[23] | AIVM/AIVMXのモデルごとの条件 | モデル提供者の条件を再確認。全WAVは未配布 |
| Style-Bert-VITS2 | AGPL-3.0。[25] | checkpointごとの条件 | 未配布 |
| VOICEVOX Engine | LGPL-3.0／別ライセンスのデュアルライセンス。[24] | 話者・音声ライブラリごとの条件 | 未配布 |
| COEIROINK | ソフトウェア規約を適用 | 学習済みモデルの再配布は禁止。[7] | 「COEIROINK:合成音声名」クレジットが必要。[7] 今回は生成・配布しない |
| CosyVoice | Apache-2.0。[26] | checkpointごとの条件 | 未配布 |

## 公開しないもの

次は意図的にリポジトリへ含めない。

- `models/`、Hugging Face／ModelScopeの重み、AIVM/AIVMX、safetensors、checkpoint
- `tmp/audio/`と全量・代表音声を含むWAV／FLAC／MP3
- ローカルAPIのログ、個人パスを含む設定、認証情報、`.env`
- COEIROINKのモデル・生成音声・キャラクター素材

取得元URL、固定version／commit、サイズ、SHA-256は再現性のためのメタデータとして記録できるが、URL自体は再配布許諾ではない。利用時は対象モデルと音声の最新規約を再確認する。

## Sources

[7] https://coeiroink.com/terms
[21] https://raw.githubusercontent.com/QwenLM/Qwen3-TTS/main/LICENSE
[22] https://raw.githubusercontent.com/index-tts/index-tts/main/LICENSE
[23] https://raw.githubusercontent.com/Aivis-Project/AivisSpeech-Engine/master/LICENSE
[24] https://raw.githubusercontent.com/VOICEVOX/voicevox_engine/master/LICENSE
[25] https://raw.githubusercontent.com/litagin02/Style-Bert-VITS2/master/LICENSE
[26] https://raw.githubusercontent.com/FunAudioLLM/CosyVoice/main/LICENSE
