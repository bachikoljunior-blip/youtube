# AUTOMATION PAUSED — 2026-08-30

## Status

**動画の生成・アップロード・再スケジュールを停止する。分析とデータ保全だけは続けてよい。**

## Why

YouTube の現行チャンネル収益化ポリシーは、次を収益化不可として明示している。

- mass-produced / generic / repetitive / template-based content
- AI-generated personas presenting themselves as human experts on sensitive topics
- AI personas providing financial guidance or interpreting legal rules

Current channel configuration conflicts with that policy:

- niche: お金・税金・キャリア
- persona: 「元・事業会社の経理／人事」と名乗る
- narration: synthetic TTS
- production: automated template pipeline

このまま投稿を増やしても、目標である YouTube 収益化の到達可能性を上げず、審査時の不適合材料を増やすおそれがある。

Official policy reviewed 2026-08-30:
https://support.google.com/youtube/answer/1311392

## What is blocked

- `python -m src.pipeline`
- upload entry points
- batch/Shorts generation
- title/thumbnail/link/reschedule automation

`src/pause_guard.py` と `src/config.py` が二重に止める。

## What remains allowed

- analytics/status/reach/retention の読取
- 既存データの保存
- monetizable replacement format の調査
- dry analysis that does not generate, upload, schedule, retitle or otherwise modify channel content

## Resume gate

次の全条件が記録されるまで解除しない。

1. sensitive-topic AI persona を使わない  **← 2026-08-30 に閉じた（下の「進捗」）**
2. human expert を装わない                **← 2026-08-30 に閉じた（下の「進捗」）**
3. final videos are materially varied and demonstrate a clear original creative contribution
4. policy-compliant channel concept is reviewed against the current official policy
5. 既存動画の扱いと新旧テーマ混在リスクを決める
6. monetization path and acquisition economics are recalculated

**6件のうち2件が閉じました。解除はまだです**（3〜6が残っています）。
**この節を「もう解除してよい」と読まないこと。**

---

## 進捗

### 1・2 —— 2026-08-30 に閉じた（`config/channel.yaml` ＋ `src/verify.py`）

**入口**: `config/channel.yaml` の `persona` から、実在しない人間の実務経歴を落とした。

    旧  元・事業会社の経理／人事で、制度を実務で回してきた立場から解説する。
    新  肩書きも経歴も資格も名乗らない。一人称で職業や勤続年数を語らない。
        自分を専門家だと言わない（実在の経歴が1つも無いので、書けば嘘になる）。
        根拠にするのは経験ではなく、その回に自分で置いた前提と、そこから引いた計算式そのもの。
        …… 助言ではなく試算として書く

旧版は `src/script_writer.py:1086` から**毎本の台本の指示文**にそのまま入っていた。
つまりこの停止の中心的な前提は推測ではなく、**設定ファイルに書いてあった事実**である
（2026-08-30 00:5x の回が「コードに無い」と報告したのは誤り。`docs/JOURNAL.md` 01:5x）。

**出口**: `src/verify._check_no_human_expert_claim()` を足した。
`script_only_problems()` に入れてあるので、**22本のクリップを焼く前**に当たる。

**なぜ設定だけでは閉じないか**: `persona` は台本を書かせる指示文の一部でしかなく、
書き手（LLM）はそこに無い経歴を自分で足せる。「元・経理」を消しても
narration に「私が担当していたころは」と書かれれば、視聴者から見える形は同じ。
**入口だけを塞ぐと、次に人格を書き換えた回が黙って穴を開け直せる。**

**実測**（`tests/test_no_human_expert_claim.py`・20件が緑）:

    落とす   元・経理として／私は人事の担当でした／税理士としての経験から／
             実務で回してきた／自分の経験上／私は10年間、経理を担当してきました／
             専門家として断言します
    通す     税理士に確認してください（相手が専門家）／会社員として働く人は（主語が視聴者）／
             説明欄の定型文「専門家にご確認ください」／普通の計算の文
    偽陽性   **投稿済み735本の題を全部通して 0件**（`data/uploaded.jsonl`）

**落としたのは経歴であって、企画ではない。**
「制度を解説するのではなく、自分で計算した結果を発表する」（`CLAUDE.md` の根幹）は、
架空の実務経歴を1文字も必要としない —— 「元・経理」をやめても `src/calc/` の数字は減らない。

**覆る条件**: 実在する人間が実名で出演し、その経歴が事実になったら「装う」に当たらない。
そのときは検査ごと外してよい。**偽陽性が出ても、`persona` に経歴を戻すことでは直さないこと。**

### 5 —— 未着手。ただし**分類がもう1つある**

`data/uploaded.jsonl` の実測（2026-08-30）:

    控えにある本            735本
    **これから公開される予約  480本**（2026-08-30 12:00 〜 2026-10-09 23:00 JST・1日12〜20本）

**予約はすでに YouTube 側に入っている。機械が1回も起きなくても480本は公開される。**
停止が止めたのは「新しく作って足すこと」であって、**すでに並んでいる列ではない。**
5番は「既存動画」と書いており、**未公開だが予約済みの480本**はそのどちらでもない。
**5番を閉じる回は、この3つ（公開済み／予約済み・未公開／これから作る本）を別々に決めること。**

### 測れなかったこと（2026-08-30）

**公開済みの本の説明欄を読んで、実際に名乗りが入っているかを数えようとしたが、
YouTube Data API の日枠が尽きていて取れなかった**（`quotaExceeded`・同日に92本 投稿済み）。
題は735本とも 0件だったが、**題は短いので「入っていない」の証拠としては弱い。**
**次に枠がある回は、`videos().list(part=snippet)` で説明欄を全部通すこと**
（50件/回・15回・読み取りだけ。停止の「やってよいもの」の中）。
そこが 0件 に近ければ 5番の判断は軽くなり、多ければ重くなる。

## Override

緊急の手動検証だけ、明示的に次を設定したプロセスで許可する。

`ALLOW_POLICY_PAUSED_AUTOMATION=I_ACCEPT_YPP_POLICY_RISK`

通常の自動運転や恒久解除には使わない。
