# ベンチマーク結果

**実行スナップショット:** 2026-09-06 JST（UTC `2026-09-06T04:06:48Z`〜`04:11:14Z`）
**結果:** `results/summary.json`、`results/metrics.csv`
**共通ケース:** 30件／実測エンジン（60 WAV）
**判定:** 生成エラーを0点へ変換せず、未実測は`対象外`、未検証スコアは`null`で保存した。

## 1. 実行環境

- Linux kernel `7.0.0-30-generic`、x86_64、Python `3.11.15`
- NVIDIA GeForce RTX 5070 Ti、16,303 MiB、driver `595.84`
- Docker `29.8.0`
- AivisSpeech Engine `1.2.0`（実行時API version）、VOICEVOX Engine `0.25.2`
- Aivis AIVMX取得物: `0.25161968 GiB`、SHA-256は`environment/hardware.json`に記録。モデルは公開していない。
- VOICEVOX Docker image: `4.0178215 GiB`、digestは`environment/hardware.json`に記録。
- 内容round-trip: local `faster-whisper` small、CUDA/FP16。読み: `sakasegawa/japanese-wav2vec2-large-hiragana-ctc`、CUDA、checkpointサイズ`631,542,555` bytes、SHA-256は同JSONに記録。[10][11]

## 2. 候補ごとの公式仕様

7候補の公式仕様、公式URL、コード／モデル／音声のライセンス境界は [`docs/RESEARCH.md`](RESEARCH.md) に分離している。Qwen3-TTSは日本語を含む多言語と指示・voice design系機能が候補理由である。[1] IndexTTS-2.5は感情・継続時間・読み置換を含む制御候補である。[2] AivisSpeechとVOICEVOXは今回使ったHTTP API互換のローカル実測対象である。[4][19] Style-Bert-VITS2、COEIROINK、CosyVoiceも仕様上の候補として残したが、今回のマシンで同一条件の再現可能なcheckpoint/runtimeまでは確立していない。[5][7][20]

## 3. 実測成功／対象外

| エンジン | version／commit | install_status | cases | RTF | CER平均 | 備考 |
|---|---|---:|---:|---:|---:|---|
| AivisSpeech Engine | `da5d4aa06bf47333d641b8b48f37ddd7a6be5ffa` / API 1.2.0 | 成功 | 30/30 | 0.502354 | 0.181025 | `--no-use_gpu`、AIVMX外部 |
| VOICEVOX Engine | `7aed82202a2fcff59d35def8899733db63c3fc7f` / API 0.25.2 | 成功 | 30/30 | 0.172220 | 0.132881 | pinned Docker image |
| Qwen3-TTS | `022e286b98fbec7e1e916cb940cdf532cd9f488e` | 対象外 | 0/30 | null | null | local checkpoint/runtime未確立 |
| IndexTTS-2.5 | `ee40fa7d6c6b8a2c7f06105f9f1e65775b74868c` | 対象外 | 0/30 | null | null | checkpoint／規約確認未完了 |
| Style-Bert-VITS2 | `66de777e06392c0f313600be03c43ef96658b244` | 対象外 | 0/30 | null | null | 再現可能なモデル未確立 |
| COEIROINK | `4e0cebd681bec13e6cdcc61d59e5efd9c588a686` | 対象外 | 0/30 | null | null | voice条件・クレジット確認前のため生成しない |
| CosyVoice | `074ca6dc9e80a2f424f1f74b48bdd7d3fea531cc` | 対象外 | 0/30 | null | null | Japanese local runtime未確立 |

実測した2エンジンでは生成失敗0件である。5候補の`対象外`は音質不合格ではなく、このスナップショットで導入・モデル条件を完了できなかったという意味である。

## 4. 自然さ

validated local MOS estimatorは利用可能な状態にならなかったため、`naturalness_score`と各caseの`mos_estimate`はnullである。これは0点ではない。代替としてWAVのsample rate、channels、bit depth、duration、RMS／peak、silence ratio、pitch proxy、anomaly flagsを全60生成物について検査した。単純な音響異常flagは60/60で空だった。長文`l01`はAivis 186.900045秒、VOICEVOX 209.344秒であり、長文としての長さを異常扱いしていない。人間MOSの代替結果として解釈してはならない。

## 5. 表現力

`expression_score=3.0`は聴感MOSではなく、共通意図（cheerful、sad、angry、energetic、whisper_or_soft、fast_excited）を話者ID・speed／volume／intonationパラメータへ再現可能に写像できたことを示す控えめな自動化proxyである。両エンジンとも6つのexpressionケースを生成し、style mappingをJSONへ保存した。声質の優劣、感情の自然さ、話者同一性はこの数値では結論できない。表現力だけを最適化する選定では代表音声の人手試聴が未解決である。

## 6. 読み精度

発音13ケースは、文字STTの漢字一致ではなく、かな／音素CTCの出力を期待読みの文脈へ編集距離アラインメントした。[11] エンジンが返す読みメタデータは補助情報として保存しただけで、音響証拠にはしていない。

| エンジン | 合格 | 不合格 | 要確認 | 対象外 | pronunciation_control_score | human review |
|---|---:|---:|---:|---:|---:|---:|
| AivisSpeech Engine | 2 | 4 | 7 | 17 | 1.667 | 7 |
| VOICEVOX Engine | 4 | 7 | 2 | 17 | 1.818 | 2 |

`対象外`17件は、発音評価対象ではない自然さ・表現・mixed・punctuation・long-formケースである。`pronunciation_control_score`は合格／不合格だけを分母にし、要確認を0点としていない。したがって、この実測ではVOICEVOXが相対的に良いが、合格率は4/11であり「読みが確実」とは言えない。運用時はかな原稿または辞書と同じphoneme gateを必須にする。

## 7. 読み前処理での改善

初回のかな／音素判定が明確に不合格だった場合だけ、対象漢字スパンを`expected_reading`へ置換して一度だけ再生成した。初回と再試行は`first_attempt`／`retry_attempt`として両方を保存し、原文入力の結果と混ぜていない。

- Aivis: 8件を再試行。`p06`、`p10`は再試行で合格。`p02`、`p13`は要確認へ変化し、他の不合格は解消しなかった。
- VOICEVOX: 11件を再試行。`p06`、`p08`、`p10`は再試行で合格、`p04`は要確認へ変化。残りは不合格。
- 合計19件。再試行音声もライセンス確認のため公開しない。

前処理で改善したケースがある一方、CERはraw inputとのround-trip値であり、読み置換による意味・内容差を品質改善として水増ししていない。

## 8. リソース

| エンジン | model／image size (GiB) | peak VRAM (GiB) | peak RAM (GiB) | generation RTF |
|---|---:|---:|---:|---:|
| AivisSpeech Engine | 0.251620 | 0.0146 | 2.2499 | 0.502354 |
| VOICEVOX Engine | 4.017822（image footprint） | 0.0146 | 16.91 | 0.172790 |

AivisのVRAM値は`--no-use_gpu`実行時の観測下限であり、GPU TTS比較ではない。VOICEVOXもGPUを割り当てないDockerである。RAMは外部サービス／container観測を優先し、測定定義は [`docs/METHODOLOGY.md`](METHODOLOGY.md) に記した。評価器のGPUメモリはTTS RTFへ混ぜていない。

## 9. 自動化容易性

実測2エンジンは、HTTP health/version probe、固定speaker／style map、query、synthesis、WAV検査、JSON／CSV記録までを非対話で完了し、30/30ケースを生成したため`automation_score=4.0`とした。ローカルサービスの起動、モデル取得、話者・音声の規約は別途必要である。5対象外候補は自動化スコアをnullとし、導入できなかったことを低品質と混同していない。

## 10. ライセンス

コード、モデル、生成音声を分けて [`docs/LICENSE_NOTES.md`](LICENSE_NOTES.md) に記録した。Qwen3-TTS、CosyVoice等のupstreamコードライセンスだけではcheckpointの条件を確定できない。[21][22][26] COEIROINKは適用規約上のクレジットとモデル再配布条件があるため、今回の公開成果物へモデル・生成音声を含めていない。[7] Public repositoryには重み、AIVM/AIVMX、full audio、credential、`.env`を含めない。

## 11. 総合推奨

**今回の測定範囲での暫定総合推奨はVOICEVOX Engine**である。理由は30/30生成成功、RTF 0.172790、CER平均0.132881で、Aivisよりround-trip内容一致と処理時間が良かったためである。ただし、自然さMOSは未計測、読み合格は4/11である。production採用前に対象話者の人手試聴、かな／音素gate、話者・キャラクター規約の確認を行う。

## 12. 表現力重視推奨

**確定推奨なし（Aivis／VOICEVOXを同列の試聴候補）**。両者とも共通style mapを通せたが、expression_scoreは同じproxy値3.0で、聴感評価器がない。表現力を主目的にするなら、Aivisのstyle／speaker候補とVOICEVOXのspeaker候補から同じ6ケースを試聴し、用途ごとに人手選定する。未実測5候補を「表現力が低い」とは判定しない。

## 13. 読み確実性・運用安定性重視推奨

**VOICEVOX Engineを第一候補、AivisSpeech Engineを第二候補**とする。VOICEVOXは今回のphoneme/kana判定で合格4、要確認2、human review 2で、Aivisの合格2、要確認7より運用上の確認負荷が小さかった。とはいえ7/11は不合格であり、エンジンだけに読みを任せず、`expected_reading`を入力辞書またはeffective inputとして明示する。

## 14. human_review対象一覧

今回の自動判定で`human_review_required=true`になった9件だけを列挙する。

- AivisSpeech Engine: `p02` 一日、`p03` 生物学、`p04` 生物、`p07` 大分県、`p11` 御器所、`p12` 新瑞橋、`p13` 栄生
- VOICEVOX Engine: `p04` 生物、`p13` 栄生

`first_attempt`と`retry_attempt`、かな／音素CTC出力、STT transcript、audio pathが各case resultにある。全件試聴ではなく、この集合と導入前の代表caseを確認する。

## 15. 再現手順

1. Python 3.11の一時venvで`python -m pip install -e '.[dev,eval]'`を実行する。モデル重みはrepository外のcacheへ置く。
2. AivisSpeech Engine 1.2.0を公式配布物から取得し、AIVMXモデルを利用条件に従って配置する。VOICEVOXは、公開済みdigestを確認して`voicevox/voicevox_engine:latest`を起動する。公式配布物とモデルの規約を先に確認する。
3. `python scripts/generate/run_benchmark.py --engines aivis,voicevox --output-dir results --audio-dir tmp/audio`を実行する。5候補の対象外レコードは、同スクリプトを別outputへ実行してsummaryへマージする。
4. `evaluate_results.py`へfaster-whisper cacheとかなCTC checkpointを渡し、`recompute_features.py`、`sync_engine_metadata.py`、`validate_results.py`の順で検証する。
5. audioは公開前に削除し、`results/summary.json`、`results/metrics.csv`、environment、license notesだけを監査する。

## 16. 未解決事項

- 5候補は日本語モデルの固定checkpoint、依存、GPU実行、モデル／音声規約まで同一runで確立していない。追加実測が必要である。
- validated local MOS／人間MOSがないため、自然さの順位は出していない。
- AivisとVOICEVOXは異なる話者モデルであり、style scoreの公平な聴感比較ではない。
- `sakasegawa/japanese-wav2vec2-large-hiragana-ctc`は強力な自動根拠だが、固有名詞・長文・TTS音声への誤認識は残る。human review対象をゼロにはしない。
- 公開後も各候補の最新規約、モデルカード、キャラクター／音声クレジットを再確認する。

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
[26] https://raw.githubusercontent.com/FunAudioLLM/CosyVoice/main/LICENSE
