# 子（サブ）に渡すプロンプトの型（2026-09-05 にゼロから書き直した）

`python scripts/spawn_prompt.py --kind <役>` がこの型を組み立てる。**文言はここにだけ持つ。**
`<<first_move>>`（枝を合わせる1手）と `<<siblings_block>>`（同じ周に走る相手）は道具が埋める。

手順の正本は **`docs/METHOD.md`**。ここには「それを読め」と、役の違いだけを書く。

**「〜すること」「必ず」の形は書かない**（オーナー 09/06 14:0x「お前が判断すんじゃなくて、サブが判断すんだよ。あとは絶対やれっていうな。」）。
親が渡すのは、原文・数字・事実（押していない分は親が畳まれると消える、など）。何をどの順でやるかはサブが決める。
09/06 15:xx（optimizer）に「まず全部 読むこと」「push すること」を事実の形に直した。**覆る条件**: サブが押さずに終わって成果が消えた周が 2周 続いたら、その事実を数字つきで本文に足す（それでも「必ず」とは書かない）。

## なぜ型が短いか（2026-09-05）

前の型は 400行 あり、`docs/trigger_main.md`（5,533行）を読ませ、6種類の ship の帳簿を
つけさせていた。実測（直近5日）: ship 244件・`--moves 0` 238件・fix 48% ——
**帳簿は動いたが本は良くならず、再生/日は 6,299 → 787**。オーナー 09/05「今の手法全てまっさらにしてから作り直して」。
型は「何を読んで、きょう何をするか」だけにする。

## kind: hourly

```text
<<lead>>

<<siblings_block>>
```

## block: lead-round

```text
【きょうの1本の回】**手順の正本は `docs/METHOD.md`**（全部 読むと、前の回が測ったことと決めたことが揃う）。

<<first_move>>

2手目: `python -m studio.cli status`（きょうの枠・予約・直近の本の再生・台帳）。
**いま何時（JST）か、きょうの枠に本が在るかで、この回の手が決まる**（`docs/METHOD.md` §5 の表）。

この回の仕事は **「次に出る1本を、出る瞬間まで良くする」** の1つだけ。
台本は自分で書く（`data/studio/scripts/<日付>-<題>.json`・書き方は §3）。
出口の順は §4: 分かりやすさの輪（read → critique → 直す → 初めから）→ 読みの輪（build → hear）→ 目で見る（sheet.png を Read）→ **当日なら 10:00 JST に予約**。
きょうの枠に旧作りの本が予約されていたら、新しい本で差し替える（`schedule --at 10:00 --replace <ID>`。前の本は private に残る。消さない）。

**あなたはサブエージェントです。** `archive_session` / `set_session_title` / `relay.py --next` はやらない。
**節目ごとに commit して push すること**（台本・台帳・METHOD の書き換え）。親が畳まれると押していない分は消える。
`docs/METHOD.md` は書き換えてよい —— 数字で分かったこと・変えた理由・覆る条件を同じ節に書くこと。

旧道具（`src/` `scripts/` `docs/trigger_main.md` `run_marker.py` `eta.py`）は**使わない・前提にしない**（§8）。
使うのは `studio/` と `docs/METHOD.md` だけ。
```

## block: lead-only

```text
【指名の回】**この回はこれだけです: <<only>>**

手順の正本は `docs/METHOD.md`。それ以外には手を出さない。

<<first_move>>

**あなたはサブエージェントです。** `archive_session` / `set_session_title` / `relay.py --next` はやらない。
節目ごとに commit して push すると、親が畳まれても残る（押していない分は消える）。
```

## kind: optimizer

```text
【あすの1本の回】**手順の正本は `docs/METHOD.md`**（全部 読むと、前の回が測ったことと決めたことが揃う）。

<<first_move>>

2手目: `python -m studio.cli status`。

持ち場は `docs/METHOD.md` §5「同じ周に2体 走るときの持ち場」の表。**次に出る1本の台本は `hourly` のもの** ——
きょうの枠が公開ずみなら、あすの台本にも触らない（09/05 に 2体が同じ台本の同じ3欠陥を 30分差で直した）。
この回の仕事: (a) `python -m studio.cli measure`（公開ずみの本の数字を台帳へ）。(b) 7本 たまったら §7 の覆る条件を
数字で見て `docs/METHOD.md` を書き換える（理由と覆る条件を一緒に）。(c) 台帳（`data/studio/ledger.jsonl`）と
`work/` の実物から道具（`studio/`）の欠陥を見つけて直す —— ただし `hourly` がいま出そうとしている本に要る直しは
`hourly` に任せる。(d) 画像の注文（`data/image_orders/`）の届き具合。(e) 親の手続きの欠陥。
(f) **きょうの枠がまだ公開前のときだけ**、あすの台本を書く・磨く（§3・§4 の (1)(2)(3)。画像の注文 `order-image` まで。実測 70分 —— METHOD §5 の表のとおり）。
持ち場に何も無ければ短く終わってよい。

<<siblings_block>>

**あなたはサブエージェントです。** `archive_session` / `set_session_title` / `relay.py --next` はやらない。
節目ごとに commit して push すると、親が畳まれても残る（押していない分は消える）。
旧道具（`src/` `scripts/` `docs/trigger_main.md`）は使わない・前提にしない。
```

## kind: owner-full

```text
【オーナーからの連絡】原文: 「<<note>>」

**原文を `CLAUDE.md` の冒頭ブロックに、そのまま足すこと**（要約しない・日時つき）。
受け取り帳は `python scripts/inbox.py --open --source owner --text "<原文>"`（二重に開かない）。
そのうえで、手順の正本 `docs/METHOD.md` に照らして、その連絡が何を変えるかを決め、
METHOD を書き換える（理由・覆る条件つき）。必要なら本にも手を入れる。

<<first_move>>

<<siblings_block>>

**あなたはサブエージェントです。** `archive_session` / `set_session_title` / `relay.py --next` はやらない。
節目ごとに commit して push すると、親が畳まれても残る（押していない分は消える）。
```

## kind: owner-record

```text
【オーナーからの連絡・記録のみ】原文: 「<<note>>」

原文を `CLAUDE.md` の冒頭ブロックに、そのまま足す（要約しない・日時つき）。
受け取り帳 `python scripts/inbox.py --open --source owner --text "<原文>"`。commit → push。それだけ。

<<first_move>>

<<siblings_block>>
```
