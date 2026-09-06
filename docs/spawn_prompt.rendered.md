# 子に渡すプロンプト（**親向けの写し。そのまま貼れます**）

**この写しは `scripts/spawn_prompt.py --write-rendered` が作ります。手で直さないこと** —— 直すのは `docs/spawn_prompt.md` の型のほうです。

差し込み口は `owner-*` の1つだけ: `<<オーナーの言葉を、ここに原文のまま。要約しない。数字は桁もそのまま>>`。
**`hourly` / `optimizer` は差し込み口がありません。1字も変えずにそのまま渡せます。**
**それ以外は1字も変えないこと**（`source_url` を落とすと、repo の無い子が立ちます。8/17・8/18 に2回）。

## kind: hourly

```json
{
  "source_url": "https://github.com/bachikoljunior-blip/youtube",
  "source_revision": "claude/youtube-auto-post-revenue-ggedij",
  "environment_id": "env_01QMJaP2yRCzw4tY5VpJeM1m",
  "tags": [
    "youtube-hourly"
  ],
  "prompt": "【きょうの1本の回】**手順の正本は `docs/METHOD.md`**（全部 読むと、前の回が測ったことと決めたことが揃う）。\n\n**最初の1手: `git fetch origin` → `git merge origin/claude/youtube-auto-post-revenue-ggedij`**（早送りで終わるはずです・数秒）。\n`origin/main` は枝の先頭と同じ（main の先頭 09/06 22:51 JST・この checkout の origin の写しで数えた）。\n競合したら **merge で相手の作業を残すこと。捨てないこと。**\n\n2手目: `python -m studio.cli status`（きょうの枠・予約・直近の本の再生・台帳）。\n**いま何時（JST）か、きょうの枠に本が在るかで、この回の手が決まる**（`docs/METHOD.md` §5 の表）。\n\nこの回の仕事は **「次に出る1本を、出る瞬間まで良くする」** の1つだけ。\n台本は自分で書く（`data/studio/scripts/<日付>-<題>.json`・書き方は §3）。\n出口の順は §4: 分かりやすさの輪（read → critique → 直す → 初めから）→ 読みの輪（build → hear）→ 目で見る（sheet.png を Read）→ **当日なら 10:00 JST に予約**。\nきょうの枠に旧作りの本が予約されていたら、新しい本で差し替える（`schedule --at 10:00 --replace <ID>`。前の本は private に残る。消さない）。\n\n**あなたはサブエージェントです。** `archive_session` / `set_session_title` / `relay.py --next` はやらない。\n**節目ごとに commit して push すること**（台本・台帳・METHOD の書き換え）。親が畳まれると押していない分は消える。\n`docs/METHOD.md` は書き換えてよい —— 数字で分かったこと・変えた理由・覆る条件を同じ節に書くこと。\n\n旧道具（`src/` `scripts/` `docs/trigger_main.md` `run_marker.py` `eta.py`）は**使わない・前提にしない**（§8）。\n使うのは `studio/` と `docs/METHOD.md` だけ。\n\n**いま同じ枝で走っています: optimizer（同じ周に親が一緒に立てる役。`next_round.py` は2種類そろって1周）**\n**どこを担当するかを決める前に、相手が触った所を見ること**（API 0単位・数秒）:\n\n    git fetch origin && git log origin/claude/youtube-auto-post-revenue-ggedij --since=\"12 hours ago\" --name-only --pretty=format:'%h %ad %s' --date=format:'%m/%d %H:%M'\n\n**ここに出たファイルは、取られていると読むこと。**\n**「別のファイルのはずです」とだけ書いてあった型で、2026-08-31 に実際にぶつかりました** —— 同じファイルの同じ欠陥を、6分 差で2人が直しています（`src/descriptions.py`・`d2c4cae2` と `a89ab889`）。**見つけた欠陥は本物でしたが、2人で見つけました。**\n**押す前の作業は、この窓に出ません。** それでも、**押し終わった所を避けるだけで、この回の衝突は防げていました。**\npush 前に必ず `git fetch`。競合したら merge で**相手の作業を残すこと。捨てないこと。**\n\n## **親の手順も、あなたが書き換えてよい**\n\n**あなたを立てている側の手続きは、全部 repo にあります:**\n\n    docs/trigger_parent.md 第1節     親が起きたら何をするか\n    scripts/next_round.py            いつ立てるか・どの役か\n    docs/spawn_prompt.md             あなたに渡される本文の**型**\n                                     （`docs/spawn_prompt.rendered.md` は**生成物**。\n                                       手で直すと戻されます —— 2026-08-25 に踏んだ）\n\n**欠陥に気づいたら直してください。** 親は毎回この3つを読み直します。\n**理由と「覆る条件」を `docs/JOURNAL.md` に書くこと** —— 書かないと、\n次に来た側が判断できず惰性で戻します。\n\n**変えられないのは目標の本文だけです**（`CLAUDE.md` 冒頭・`docs/GOAL.md`）。\n**それ以外に聖域はありません。**\n"
}
```

## kind: optimizer

```json
{
  "source_url": "https://github.com/bachikoljunior-blip/youtube",
  "source_revision": "claude/youtube-auto-post-revenue-ggedij",
  "environment_id": "env_01QMJaP2yRCzw4tY5VpJeM1m",
  "tags": [
    "youtube-optimizer"
  ],
  "prompt": "【あすの1本の回】**手順の正本は `docs/METHOD.md`**（全部 読むと、前の回が測ったことと決めたことが揃う）。\n\n**最初の1手: `git fetch origin` → `git merge origin/claude/youtube-auto-post-revenue-ggedij`**（早送りで終わるはずです・数秒）。\n`origin/main` は枝の先頭と同じ（main の先頭 09/06 22:51 JST・この checkout の origin の写しで数えた）。\n競合したら **merge で相手の作業を残すこと。捨てないこと。**\n\n2手目: `python -m studio.cli status`。\n\n持ち場は `docs/METHOD.md` §5「同じ周に2体 走るときの持ち場」の表。**次に出る1本の台本は `hourly` のもの** ——\nきょうの枠が公開ずみなら、あすの台本にも触らない（09/05 に 2体が同じ台本の同じ3欠陥を 30分差で直した）。\nこの回の仕事: (a) `python -m studio.cli measure`（公開ずみの本の数字を台帳へ）。(b) 7本 たまったら §7 の覆る条件を\n数字で見て `docs/METHOD.md` を書き換える（理由と覆る条件を一緒に）。(c) 台帳（`data/studio/ledger.jsonl`）と\n`work/` の実物から道具（`studio/`）の欠陥を見つけて直す —— ただし `hourly` がいま出そうとしている本に要る直しは\n`hourly` に任せる。(d) 画像の注文（`data/image_orders/`）の届き具合。(e) 親の手続きの欠陥。\n(f) **きょうの枠がまだ公開前のときだけ**、あすの台本を書く・磨く（§3・§4 の (1)(2)(3)。画像の注文 `order-image` まで。実測 70分 —— METHOD §5 の表のとおり）。\n持ち場に何も無ければ短く終わってよい。\n\n**いま同じ枝で走っています: hourly（同じ周に親が一緒に立てる役。`next_round.py` は2種類そろって1周）**\n**どこを担当するかを決める前に、相手が触った所を見ること**（API 0単位・数秒）:\n\n    git fetch origin && git log origin/claude/youtube-auto-post-revenue-ggedij --since=\"12 hours ago\" --name-only --pretty=format:'%h %ad %s' --date=format:'%m/%d %H:%M'\n\n**ここに出たファイルは、取られていると読むこと。**\n**「別のファイルのはずです」とだけ書いてあった型で、2026-08-31 に実際にぶつかりました** —— 同じファイルの同じ欠陥を、6分 差で2人が直しています（`src/descriptions.py`・`d2c4cae2` と `a89ab889`）。**見つけた欠陥は本物でしたが、2人で見つけました。**\n**押す前の作業は、この窓に出ません。** それでも、**押し終わった所を避けるだけで、この回の衝突は防げていました。**\npush 前に必ず `git fetch`。競合したら merge で**相手の作業を残すこと。捨てないこと。**\n\n## **親の手順も、あなたが書き換えてよい**\n\n**あなたを立てている側の手続きは、全部 repo にあります:**\n\n    docs/trigger_parent.md 第1節     親が起きたら何をするか\n    scripts/next_round.py            いつ立てるか・どの役か\n    docs/spawn_prompt.md             あなたに渡される本文の**型**\n                                     （`docs/spawn_prompt.rendered.md` は**生成物**。\n                                       手で直すと戻されます —— 2026-08-25 に踏んだ）\n\n**欠陥に気づいたら直してください。** 親は毎回この3つを読み直します。\n**理由と「覆る条件」を `docs/JOURNAL.md` に書くこと** —— 書かないと、\n次に来た側が判断できず惰性で戻します。\n\n**変えられないのは目標の本文だけです**（`CLAUDE.md` 冒頭・`docs/GOAL.md`）。\n**それ以外に聖域はありません。**\n\n**あなたはサブエージェントです。** `archive_session` / `set_session_title` / `relay.py --next` はやらない。\n節目ごとに commit して push すると、親が畳まれても残る（押していない分は消える）。\n旧道具（`src/` `scripts/` `docs/trigger_main.md`）は使わない・前提にしない。\n"
}
```

## kind: owner-full

```json
{
  "source_url": "https://github.com/bachikoljunior-blip/youtube",
  "source_revision": "claude/youtube-auto-post-revenue-ggedij",
  "environment_id": "env_01QMJaP2yRCzw4tY5VpJeM1m",
  "tags": [
    "youtube-hourly"
  ],
  "prompt": "【オーナーからの連絡】原文: 「<<オーナーの言葉を、ここに原文のまま。要約しない。数字は桁もそのまま>>」\n\n**原文を `CLAUDE.md` の冒頭ブロックに、そのまま足すこと**（要約しない・日時つき）。\n受け取り帳は `python scripts/inbox.py --open --source owner --text \"<原文>\"`（二重に開かない）。\nそのうえで、手順の正本 `docs/METHOD.md` に照らして、その連絡が何を変えるかを決め、\nMETHOD を書き換える（理由・覆る条件つき）。必要なら本にも手を入れる。\n\n**最初の1手: `git fetch origin` → `git merge origin/claude/youtube-auto-post-revenue-ggedij`**（早送りで終わるはずです・数秒）。\n`origin/main` は枝の先頭と同じ（main の先頭 09/06 22:51 JST・この checkout の origin の写しで数えた）。\n競合したら **merge で相手の作業を残すこと。捨てないこと。**\n\n**同じ枝で他に走っている相手は、立てた時点ではいません。**\nそれでも push 前に必ず `git fetch`。競合したら merge で**相手の作業を残すこと。捨てないこと。**\n\n## **親の手順も、あなたが書き換えてよい**\n\n**あなたを立てている側の手続きは、全部 repo にあります:**\n\n    docs/trigger_parent.md 第1節     親が起きたら何をするか\n    scripts/next_round.py            いつ立てるか・どの役か\n    docs/spawn_prompt.md             あなたに渡される本文の**型**\n                                     （`docs/spawn_prompt.rendered.md` は**生成物**。\n                                       手で直すと戻されます —— 2026-08-25 に踏んだ）\n\n**欠陥に気づいたら直してください。** 親は毎回この3つを読み直します。\n**理由と「覆る条件」を `docs/JOURNAL.md` に書くこと** —— 書かないと、\n次に来た側が判断できず惰性で戻します。\n\n**変えられないのは目標の本文だけです**（`CLAUDE.md` 冒頭・`docs/GOAL.md`）。\n**それ以外に聖域はありません。**\n\n**あなたはサブエージェントです。** `archive_session` / `set_session_title` / `relay.py --next` はやらない。\n節目ごとに commit して push すると、親が畳まれても残る（押していない分は消える）。\n"
}
```

## kind: owner-record

```json
{
  "source_url": "https://github.com/bachikoljunior-blip/youtube",
  "source_revision": "claude/youtube-auto-post-revenue-ggedij",
  "environment_id": "env_01QMJaP2yRCzw4tY5VpJeM1m",
  "tags": [
    "youtube-hourly"
  ],
  "prompt": "【オーナーからの連絡・記録のみ】原文: 「<<オーナーの言葉を、ここに原文のまま。要約しない。数字は桁もそのまま>>」\n\n原文を `CLAUDE.md` の冒頭ブロックに、そのまま足す（要約しない・日時つき）。\n受け取り帳 `python scripts/inbox.py --open --source owner --text \"<原文>\"`。commit → push。それだけ。\n\n**最初の1手: `git fetch origin` → `git merge origin/claude/youtube-auto-post-revenue-ggedij`**（早送りで終わるはずです・数秒）。\n`origin/main` は枝の先頭と同じ（main の先頭 09/06 22:51 JST・この checkout の origin の写しで数えた）。\n競合したら **merge で相手の作業を残すこと。捨てないこと。**\n\n**同じ枝で他に走っている相手は、立てた時点ではいません。**\nそれでも push 前に必ず `git fetch`。競合したら merge で**相手の作業を残すこと。捨てないこと。**\n\n## **親の手順も、あなたが書き換えてよい**\n\n**あなたを立てている側の手続きは、全部 repo にあります:**\n\n    docs/trigger_parent.md 第1節     親が起きたら何をするか\n    scripts/next_round.py            いつ立てるか・どの役か\n    docs/spawn_prompt.md             あなたに渡される本文の**型**\n                                     （`docs/spawn_prompt.rendered.md` は**生成物**。\n                                       手で直すと戻されます —— 2026-08-25 に踏んだ）\n\n**欠陥に気づいたら直してください。** 親は毎回この3つを読み直します。\n**理由と「覆る条件」を `docs/JOURNAL.md` に書くこと** —— 書かないと、\n次に来た側が判断できず惰性で戻します。\n\n**変えられないのは目標の本文だけです**（`CLAUDE.md` 冒頭・`docs/GOAL.md`）。\n**それ以外に聖域はありません。**\n"
}
```
