# 方法

## 1. 仕様への対応

Runbookと共通テストケースを`tests/cases.yaml`へ固定した。30ケースは、自然さ3、表現6、曖昧読み13、数字・英字4、句読点3、長文1で構成される。`l01`は1,153文字の固定技術解説文で、全エンジンに同じ本文を入力する。原文は変更せず、再試行時だけ`effective_input`を別に保存する。

## 2. 生成

`scripts/generate/run_benchmark.py`は、VOICEVOX API互換の`/audio_query`と`/synthesis`を使うHTTPアダプタである。[4][19] 各ケースの`raw_input`、`effective_input`、要求スタイル、話者ID／パラメータ、query+synthesis所要時間、WAV特性を保存する。実測できない候補は、推測で実行済みにせず、エンジン結果だけを`対象外`として残す。

今回のスタイル対応は、声質や感情の同一性を意味しない。以下は共通意図からの再現可能な近似である。

| 共通意図 | AivisSpeech | VOICEVOX |
|---|---|---|
| neutral | speaker 606865152 | speaker 0 |
| calm / slow_explanatory | speaker 888753763 / speed 0.85 | speaker 0 / speed 0.85〜0.9 |
| cheerful / energetic / fast_excited | speaker 888753762 / speed 1.0〜1.2 | speaker 1 / speed 1.0〜1.2 |
| sad / angry | speaker 888753765 / 888753764 | speaker 0 / 1 + intonation調整 |
| whisper_or_soft | volume 0.75 | volume 0.75 |

`natural-language instruction`を受け付けないエンジンでは、このマッピング差を結果へ記録し、指示追従性能と同一視しない。

## 3. 内容一致

生成WAVをローカル`faster-whisper` smallへ渡し、言語`ja`、beam size 5、`condition_on_previous_text=false`で文字起こしした。[10][27] CERはUnicode正規化と空白除去後の文字編集距離で計算した。音声が生成できなかったケースや評価器が使えなかったケースはnullである。

## 4. 読み

発音ケースは、単純な「STT出力漢字 == 原文」では判定しない。`sakasegawa/japanese-wav2vec2-large-hiragana-ctc`のかなCTCと音素CTCを同じ音声へ適用し、期待読みを含む文脈とのアラインメントから対象区間を切り出した。[11] 完全一致を`合格`、相違を`不合格`、認識出力が空／評価器が不在を`要確認`とする。エンジンが返した読みメタデータは補助的な再現情報であり、音響証拠ではない。

初回の音響判定が明確に`不合格`の場合だけ、対象漢字スパンを`expected_reading`へ置換した発話原稿を一度生成し、初回と再試行を`retry_attempt`へ残す。再試行で原文の意味が変わる可能性があるため、改善結果を原文入力の性能と混ぜない。

## 5. 自然さと異常検出

この実行では検証済みローカルMOS推定器を利用できなかったため、`mos_estimate`と自然さスコアはnullとした。代わりに全WAVについて、サンプルレート、チャンネル、ビット深度、長さ、RMS、ピーク、無音比、ゼロ交差率、簡易F0、異常フラグを保存した。長文については途中切断・無音・反復・音量崩れ・速度急変を機械的に置き換えて判定せず、音響特徴を人間確認候補の根拠として残す。

## 6. 資源

生成時間はqueryからWAV保存までを計測し、総生成時間／総音声時間をRTFとした。Aivisは一時Engineを`--no-use_gpu`で起動したため、Aivis TTSのGPU使用量は測定下限である。[19] VOICEVOXはGPUを割り当てないDockerコンテナで測定した。RAMは外部サービス（AivisプロセスまたはVOICEVOXコンテナ）の観測値を優先し、取得できない場合はrunner RSSのみとした。評価器のGPU使用量はTTSのRTFへ混ぜていない。

## 7. 人手

全件試聴は行っていない。機械判定不能な曖昧読みだけを`human_review_required=true`とし、最終リポジトリには音声をコピーせず、ケースIDと根拠JSONを残した。

## 8. 再現

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev,evaluation]'
python scripts/setup/capture_environment.py
python scripts/generate/run_benchmark.py
python scripts/evaluate/evaluate_results.py --kana-checkpoint /path/to/best-medium-ep5-inference.pt
```

モデル本体、キャッシュ、全量WAVはGit管理しない。公開後の一時環境削除には`scripts/cleanup/cleanup_temp.sh`を使用する。

## Sources

[4] https://raw.githubusercontent.com/VOICEVOX/voicevox_engine/master/README.md
[10] https://raw.githubusercontent.com/SYSTRAN/faster-whisper/master/README.md
[11] https://huggingface.co/sakasegawa/japanese-wav2vec2-large-hiragana-ctc/raw/main/README.md
[19] https://raw.githubusercontent.com/Aivis-Project/AivisSpeech-Engine/master/README.md
[27] https://raw.githubusercontent.com/SYSTRAN/faster-whisper/master/LICENSE
