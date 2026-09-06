# Phase 2.1 Blind Human Review

**状態:** 完了（naturalnessのみ入力済み）
**Phase 2.1 source:** Phase 2 commit `3874e2faace3995f69feeb0c0e4104746827cd7e` / tag `v0.2.0`
**Public result:** [`results/phase2_1/`](../results/phase2_1/)

## Review input and blinding

Private Driveのreview sheet 15行を、Private Driveのblind map開示後に集計した。
対象は表現12件（x01/x02/x03 × 4エンジン）と、evidenceベースで選定した発音3件である。
公開成果物にはblind map、sample ID、review音声、話者・モデルの対応表を含めていない。

入力値の扱いは次のとおりである。

- 入力済みとして扱うのは`naturalness`だけ（15/15件）。
- `instruction_match`、`pronunciation_quality`、`would_use`、`reading_issue`、`note`は未評価のため、集計値をすべて`null`とした。
- `completed=完了`はシート入力状態であり、未評価項目を評価済みとする意味ではない。
- 人手の未評価項目を機械CER、RTF、CTC、STT、音響特徴から推測していない。

## Human naturalness results

### Engine aggregate

| engine | naturalness mean | n |
|---|---:|---:|
| Irodori-TTS | 3.250 | 4 |
| Qwen3-TTS | 3.250 | 4 |
| VOICEVOX | 3.000 | 3 |
| Style-Bert-VITS2 | 2.500 | 4 |

Irodori-TTSとQwen3-TTSがnaturalnessで同率首位だった。サンプル数はエンジンごとに同一ではないため、統計的な優劣や普遍的なMOSとは解釈しない。

### Engine/case aggregate

| engine | case | category | naturalness mean | n |
|---|---|---|---:|---:|
| Irodori-TTS | p05 | pronunciation | 3.0 | 1 |
| Irodori-TTS | x01 | expression | 2.0 | 1 |
| Irodori-TTS | x02 | expression | 4.0 | 1 |
| Irodori-TTS | x03 | expression | 4.0 | 1 |
| Qwen3-TTS | p03 | pronunciation | 3.0 | 1 |
| Qwen3-TTS | x01 | expression | 3.0 | 1 |
| Qwen3-TTS | x02 | expression | 4.0 | 1 |
| Qwen3-TTS | x03 | expression | 3.0 | 1 |
| Style-Bert-VITS2 | p13 | pronunciation | 2.0 | 1 |
| Style-Bert-VITS2 | x01 | expression | 2.0 | 1 |
| Style-Bert-VITS2 | x02 | expression | 3.0 | 1 |
| Style-Bert-VITS2 | x03 | expression | 3.0 | 1 |
| VOICEVOX | x01 | expression | 3.0 | 1 |
| VOICEVOX | x02 | expression | 3.0 | 1 |
| VOICEVOX | x03 | expression | 3.0 | 1 |

## Phase 2 machine metrics（別表）

以下はPhase 2の43 raw casesの機械集計であり、human naturalnessとは別の指標である。
`対象外`を0点としていない。

| engine | measurement status | content CER mean | generation RTF mean | raw pronunciation result | same speaker across styles |
|---|---|---:|---:|---|---|
| VOICEVOX | 実測完了 | 0.126782 | 0.173855 | 合格1 / 要確認1 / 不合格11 | no |
| Qwen3-TTS | 実測完了 | 0.134206 | 0.589565 | 合格0 / 要確認3 / 不合格10 | no |
| Irodori-TTS | 実測完了 | 0.165371 | 0.104949 | 合格2 / 要確認3 / 不合格8 | no |
| Style-Bert-VITS2 | 実測完了 | 0.151042 | 0.038528 | 合格0 / 要確認6 / 不合格7 | yes |
| IndexTTS-2.5 | 対象外 | null | null | 対象外13 | not measured |

CERは低いほどround-trip内容一致が良い。RTFは低いほど生成が速い。どちらもnaturalness、人手発音品質、instruction match、would-useの代替ではない。

## Updated recommendations

### 1. 最良TTS単体

**単一の絶対1位は確定しない。既定候補はIrodori-TTS**とする。

- Irodori-TTSとQwen3-TTSはhuman naturalnessがともに3.250。
- 同率時の運用上のタイブレークとして、Irodori-TTS（RTF 0.104949）をQwen3-TTS（RTF 0.589565）より既定候補にした。
- これはnaturalnessを第一条件、RTFを同率時だけに使う明示的な方針であり、複数指標を合成した科学的総合点ではない。
- Qwen3-TTSはCER 0.134206でIrodori-TTSの0.165371より良いため、内容一致を優先する用途では別候補になる。

### 2. 表現力重視

表現3ケースだけのnaturalness平均は、Irodori-TTS 3.333、Qwen3-TTS 3.333、VOICEVOX 3.000、Style-Bert-VITS2 2.667である。
したがって**Irodori-TTSとQwen3-TTSを同率の試聴候補**とする。これはinstruction matchの評価ではない。instruction matchは入力されていないため`null`である。

### 3. 読み確実性重視

**人手のpronunciation_qualityは未評価であり、エンジンの人手発音順位は出していない。**
機械CERだけではVOICEVOXが候補だが、これは人手発音品質の推奨ではない。productionでは次のgateを必須とする。

`原文 → expected_reading/かな・音素による読み前処理 → TTS → CTC/STT・音響検証 → 要確認のみ人手試聴`

### 4. 同一話者style切替重視

Phase 2 capability metadata上の候補は**Style-Bert-VITS2**である。これは同一話者style-vector経路に関する機械／構成上の候補であり、人手instruction matchの評価結果ではない。

### 5. 自動化しやすさ重視

Phase 2の測定範囲では、最低RTFの**Style-Bert-VITS2**を候補とする。ただし、RTFは自動化全体の完全な指標ではなく、導入・モデル規約・読みgateを別途満たす必要がある。

### 6. 機械評価との不一致

human naturalnessの首位はIrodori-TTS/Qwen3-TTS、Phase 2のcontent CER最小候補はVOICEVOXだった。この差は観測された指標間の不一致であり、人手スコアと機械指標を混ぜた順位逆転とは扱わない。統合single scoreは作成していない。

## License and publication boundary

各エンジンのcode、model、speaker/character、reference audio、generated outputの条件は、生成前にPrivate Driveのowner-private監査記録で個別確認した。公開repositoryには監査の結論と再現に必要な識別子だけを残し、音声・重み・参照音声・blind mapは含めていない。条件が変わる場合は再監査が必要である。

既存の境界記録は [`docs/PHASE2_LICENSE_NOTES.md`](PHASE2_LICENSE_NOTES.md) と [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md) にある。

## Reproduction

次のCLIは、Private DriveのXLSXとblind mapを入力にし、Public-safeな結果だけを`results/phase2_1/`へ出力する。プレースホルダーを実際のPrivate Driveファイルへ置き換える。

```bash
PYTHONPATH=src python scripts/evaluate/aggregate_phase21.py \
  --scores-xlsx <PRIVATE_REVIEW_SCORES.xlsx> \
  --blind-map <PRIVATE_BLIND_MAP.json> \
  --phase2-summary results/phase2/summary.json \
  --output-dir results/phase2_1 \
  --source-phase2-commit 3874e2faace3995f69feeb0c0e4104746827cd7e \
  --source-phase2-tag v0.2.0
```

The command fails closed if the row count, blind-map join, naturalness range, completion status, or any unassessed field violates the naturalness-only contract.
