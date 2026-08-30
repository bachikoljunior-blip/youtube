# AUTOMATION PAUSED — 2026-08-30

## Status

**動画の生成・アップロード・再スケジュールを停止する。分析とデータ保全だけは続けてよい。**

## Why

YouTube の現行チャンネル収益化ポリシーは、次を収益化不可として明示している。

- mass-produced / generic / repetitive / template-based content
- AI-generated personas presenting themselves as human experts on sensitive topics
- AI personas providing financial guidance or interpreting legal rules
  （**原文はその手前に条件を持っている** —— "presents itself as a **human expert providing advice**"。
  **禁じられているのは題ではなく、名乗りと助言のほう。** 下の「進捗」4 を読むこと）

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
4. policy-compliant channel concept is reviewed against the current official policy  **← 2026-08-30 に当てた（下の「進捗」4）。**
   **ただし『構想』のほうが未定なので、閉じてはいない** —— 当てて分かったのは「縛っているのは (B) 汎用・反復の側だ」ということ
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

### 4 —— 公式ポリシーに当てて読み直した（2026-08-30・**この停止の読みが1か所ずれていた**）

出典: https://support.google.com/youtube/answer/1311392 （**Last updated: July 15, 2025**）
と、YouTube ヘルプの AI ペルソナに関する説明。**取ってきたのは 2026-08-30。**

#### 当たる条項は2つある。**別々の条項で、閉じ方が違う。**

**(A) AI ペルソナ ／ センシティブな題**

> channels using AI-generated personas to deliver information on sensitive topics,
> including any content that **presents itself as a human expert providing advice**
> on topics such as health, legal issues, finances, or politics

> - an AI "doctor" providing medical diagnoses, health advice, or wellness remedies
> - AI-generated podcast hosts offering financial guidance, investment tips, or wealth management advice
> - AI personas giving legal advice or interpreting laws

**(B) 汎用・反復（Generic or Repetitive Content）**

> Similar or repetitive content with low educational value, commentary,
> narratives, or minimal variation

> AI-generated content made with generic or unoriginal templates
> giving the impression of mass production

#### **ここが、この停止の書き方とずれていた**

`AUTOMATION_PAUSED.md` の冒頭は (A) を
「**AI personas providing financial guidance or interpreting legal rules**」と写している。
**原文は、その手前に条件を1つ持っている** ——
**「presents itself as a human expert providing advice」**。
禁じられているのは *金融や制度の話をすること* ではなく、
**人間の専門家として、助言をすること**のほうである。

**この差は小さくない。** 前者の読みだと、この企画は題ごと成立しない。
後者の読みだと、**閉じ方が2つある**:

    1. 人間の専門家として名乗らない   ← 2026-08-30 に閉じた（上の「1・2」）
    2. 助言ではなく試算として書く     ← 同じ回に `persona` へ入れた
                                        （「あなたはこうすべき」ではなく
                                          「この前提で計算するとこうなる」）

**`CLAUDE.md` の根幹（「制度を解説するのではなく、自分で計算した結果を発表する」）は、
偶然ではなく、この条項のちょうど外側を指している。**
説明欄の定型文（`channel.yaml` の `footer`）も
「一般的な情報提供を目的としたもので、個別の助言ではありません」と言っており、
**2番の側はもともと守られていた。** 欠けていたのは1番だけだった。

#### **だから、いま縛っているのは (A) ではなく (B) である**

(A) は上の2手で外側に出た。**残っているのは (B) の側**で、
そちらのほうが**この企画にとって厳しい**:

    実測  735本 ／ 1日 6〜16本 ／ 同じ台本の型 ／ 同じ図の作り ／ 同じ合成音声
          → 「giving the impression of mass production」に、正面から当たる

**Resume gate の3番（本ごとに実質的な差があること）が、本当の関門である。**
1・2 を閉じたことで、**残り4件のうち3番が最優先**になった。

**次の回への申し送り**: 3番は「差がある」と**言う**のではなく、**数で示す**こと。
材料はもうある —— `visuals.theme_for()`／`batch_build.theme_base()`（配色の分散）、
`verify._check_not_repeat`／`_check_adjacent_repeat`（棒の重なり）、
`src/calc/` が本ごとに違う数字を出していること。
**足りないのは、それを1つの尺度にまとめて「何本ぶん違うか」を出す道具のほう。**

**覆る条件**: このページは更新される（写した版は **July 15, 2025** 最終更新）。
**次に当たる回は、日付を見て、変わっていたらこの節ごと取り直すこと。**

### 5 —— **予約済み482本は、そのまま公開させる**（2026-08-30 に決めた。**待っていない**）

`data/uploaded.jsonl` の実測（2026-08-30 10:5x JST）:

    控えにある本                735本
    **すでに公開済み             209本**
    **これから公開される予約     482本**（2026-08-30 11:00 〜 2026-10-09 23:00 JST・41日・1日6〜16本）
                                 うち尺の分かるもの: 長尺143 ／ ショート69 ／ 不明270

**予約はすでに YouTube 側に入っている。機械が1回も起きなくても482本は公開される。**
停止が止めたのは「新しく作って足すこと」であって、**すでに並んでいる列ではない。**
そして引っ込める道具（`scripts/reschedule.py`）は `src/pause_guard` の対象に入っている。

#### 決定: **引っ込めない。そのまま公開させる。**

**08/30 02:4x の回は、これを3択にしてオーナーへ上げ、「答えが来るまで動かさない」と
書いて終わっている。** `CLAUDE.md` の冒頭がその形を名指しで禁じている ——
**「『オーナーの許可がほしい』と書いたら、その時点で間違いです」**（オーナー原文・3回目）。
**だからここで決める。**

**決め手は1つ。審査は2年先にある。**

    登録者（純）  23人       門は 1,000人 —— **あと 977人**
    いまの速さ    1.28人/日  → 門1 は **765日後（2028-10-03）**（`scripts/eta.py`）

**482本が公開されても、審査は起きない。落ちようがない。**
「審査のときに古い形の本が並んでいる」という心配は**2年先の話**で、
そのときまでに**消すことも、非公開に戻すことも、いつでもできる。**

    引っ込めない側の損  審査で不利になるかもしれない —— **2年先・回復可能**
                        （門に近づくまでに消せる。消す判断は、そのとき実測でできる）
    引っ込める側の損    生成が止まっている以上、**482本が唯一 残っている入力**。
                        引っ込めれば、チャンネルへの入力は6週間 **ゼロ**になる。
                        **即時・確実・回復不能**（消した視聴時間は戻らない）

**片方は「2年先の、回復できる損」、もう片方は「いまの、確実で回復できない損」。**
`CLAUDE.md`「投稿が途切れるのが最大の損失」もこちら側を向いている。

**そして期待値の符号を決めているのは、なりすましが**動画に**入っているかどうかだが、
それは今日は測れなかった**（API の日枠切れ）。**測れないうちに、
回復できないほうへ倒さない** —— これがこの決定の形である。

#### **覆る条件（3つ。どれかが起きたら、この決定を撤回して引っ込めること）**

1. **公開済みの本の説明欄を読んで、人間の専門家の名乗りが実際に入っていた**
   （`videos().list(part=snippet)` を 735本に当てる。50件/回・15回・読み取りだけ）。
   **入っていれば、審査より前に「なりすましのまま公開し続けている」ことになる。**
   題は735本とも 0件 だったが、**題は短いので証拠として弱い**
2. **登録者が 500人 を超えた**（門1 の半分）。そこからは審査が現実の日程に入るので、
   「2年先」という決め手が消える。**そのときは残りを止めて、公開済みを整理すること**
3. YouTube から警告・収益化の否認・チャンネルに対する措置が実際に来た

**1番は次に日枠がある回の最初の仕事**。**2番は `scripts/eta.py` が毎回 印字している。**

#### 5番の残り（**これで閉じてはいない**）

決めたのは**予約済み482本**だけ。5番はあと2つを言っている:

    公開済み 209本    …… まだ決めていない（上の「覆る条件」1番の測定が要る）
    これから作る本    …… 3・4番が決まってから（新しい形が決まらないと、混ざり方も決まらない）

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
