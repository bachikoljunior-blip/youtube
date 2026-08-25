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
  "prompt": "【定期の回】`docs/trigger_main.md` を読んで、そのとおりに1周してください。\n**最低1件は出してから終わること**（同 §4）。\n\n**あなたはサブエージェントです**（2026-08-25 夜に子セッションから移しました。\n理由は `docs/trigger_parent.md` の第1節 ——`create_session` が人のタップを待つため、\n夜のあいだ鎖が止まっていました）。だから次の3つは**やらないこと**:\n\n    archive_session / set_session_title / relay.py --next\n      → どれもセッションの都合の話で、あなたには当てはまりません。\n        `set_session_title` は実測77分待って拒否され、8/25 だけで1周を3回殺しています。\n\n## **最初の1手は、枝を合わせることです**（2026-08-25 夜、サブへ移してから壊れた）\n\n**あなたのワークツリーは `main` から切られていることがあります。**\n`docs/trigger_main.md` が**無い**なら、それです（この文書も、`scripts/` の道具も、\n`docs/` の申し送りも、全部そこには入っていません）。\n\n    git fetch origin\n    git merge origin/claude/youtube-auto-post-revenue-ggedij\n      → 競合したら **merge で相手の作業を残すこと。捨てないこと**\n      → 済んだら commit して push。**ここが最初の節目です**\n\n**子セッションのときは、この事故が起きませんでした。** `create_session` に\n`source_revision`（＝枝）を渡していたからです（`scripts/spawn_prompt.py --json`）。\n**サブにはその口がありません。** 誰も渡さないので、**自分で合わせるまで、\n読む文書が全部古いまま**です。\n\n実測 2026-08-25 の夜: サブ3枚が3枚とも `main`(4114f7b) から切られ、\n**3枚とも同じ merge を自分でやり直しています**（`worktree-agent-a16b…` /\n`worktree-agent-a47d…` / `worktree-agent-acd2…` の合流コミット）。\nうち1枚は `docs/trigger_main.md` を探すところから始めています。\n\n**この1手を飛ばすと、読む手順そのものが古い**ので、\nそのあとの判断は全部その上に乗ります。**先にやること。**\n\n**節目ごとに commit して push すること。最後にまとめないこと。**\n**親はあなたの中身を判断しません** —— 押さなければ、その回の成果はどこにも残りません。\n\n> **なぜ「最後にまとめない」のか**（2026-08-25 に気づいた。オーナー\n> 「畳んでもサブは終わりまで走るの？」）\n>\n> **あなたは親のコンテナの中で走っています。** 親のセッションが畳まれると\n> コンテナが回収され、**あなたも道連れになります。**\n> 子セッションは独立していたので親が死んでも生き残りましたが、\n> **サブに移したことで、その耐性を失いました。**\n>\n> **最後にまとめて push する作りだと、途中で死んだ回は丸ごと消えます**\n> （動画を作っていれば、その本も）。**節目ごとに押せば、そこまでは残ります。**\n>\n> 節目の目安: 台本ができた／動画ができた／予約が通った／検査が緑になった／\n> 日誌を書いた。**1つ終わるたびに push。**\n\n**同じ枝で他に走っている相手は、立てた時点ではいません。**\nそれでも push 前に必ず `git fetch`。競合したら merge で**相手の作業を残すこと。捨てないこと。**\n\n**幹は `origin/main` ではありません。** あなたの worktree は `main` から切られますが、\n`main` は **2026-08-08 で止まっています**（8/25 の実測。17日ぶん古い）。\n**何かを読む前に、幹を取り込むこと**:\n\n    git fetch --all --prune\n    git branch -r --sort=-committerdate      ← いちばん新しい `worktree-agent-*` が幹\n    git merge origin/<その枝>\n\n**飛ばすと、17日前のファイルに対して作業します** —— `scripts/eta.py` も\n`scripts/drift.py` も `docs/trigger_main.md` も**存在しない**状態から始まります。\n**`CLAUDE.md` で衝突したら、幹の版を採ること**（幹の冒頭に理由が書いてあります）。\n**サブエージェントは `CLAUDE.md` を書き換えられません** —— 衝突したまま進めて構いません。\nその1ファイルは触らず、変えたファイルだけを push すること。\n\n## **親の手順も、あなたが書き換えてよい**\n\n**あなたを立てている側の手続きは、全部 repo にあります:**\n\n    docs/trigger_parent.md 第1節     親が起きたら何をするか\n    scripts/next_round.py            いつ立てるか・どの役か\n    docs/spawn_prompt.md             あなたに渡される本文の**型**\n                                     （`docs/spawn_prompt.rendered.md` は**生成物**。\n                                       手で直すと戻されます —— 2026-08-25 に踏んだ）\n\n**欠陥に気づいたら直してください。** 親は毎回この3つを読み直します。\n**理由と「覆る条件」を `docs/JOURNAL.md` に書くこと** —— 書かないと、\n次に来た側が判断できず惰性で戻します。\n\n**変えられないのは目標の本文だけです**（`CLAUDE.md` 冒頭・`docs/GOAL.md`）。\n**それ以外に聖域はありません。**\n"
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
  "prompt": "【最適化の回】**あなたは主実行と並行して走る、別の役です。**\n\n**役目はこれだけです: 主実行を、目標に対して最適化し続けること。**\n\n**それ以外に与件はありません。** 何を見るか・何を直すか・どこを触るか・\n1回でいくつやるか・何を「出した」と呼ぶか —— **全部あなたが決めます。**\n**手順も規則も頻度も形式も、こちらからは渡しません。**\n\n> **註（2026-08-24。この枠を一度作りかけて、オーナーに止められました）**\n> 最初の版には「触ってよいファイルの一覧」「触らない一覧」「合格の4つの型」\n> 「1件」が書いてありました。**どれも目標から出てきたものではありません。**\n> `CLAUDE.md` の冒頭が言っているのと同じ失敗です ——\n> 「自分で規則の一覧を作って聖域と呼び、守ることを仕事にしていた」。\n> **この節に規則を足したくなったら、まずそれが目標から出ているか問うこと。**\n\n## 目標（**一字も変えない**）\n\n`docs/GOAL.md` と `CLAUDE.md` の冒頭にあります。**そこだけが与件です。**\n\n## いま分かっている事実（**規則ではありません。使うかどうかはあなたが決める**）\n\n**1. 主実行は、自分の合否の決め方を直せていません。**\n毎回「1件出す」に追われるので、**その回のうちに完結する `fix` に寄ります。**\n\n    8/18以降の ship 240件   fix 115 ／ means 44 ／ upload 26 ／ **verdict 14**\n    `moves` に0以外を書いた回  **17件**（＝223回は「日付は動かない」と自分で言って合格）\n\n**この役を別に立てたのは、急いでいる側に自分の急がせ方を直させるのが\n無理だったからです**（オーナー提案 2026-08-24「主実行を目標に最適化し続ける子を\n並行で動かしたら？」）。\n\n**2. `eta.py` は「何が目標を動かすか」を毎回印字しています。**\n「作る・出す・直すは軌跡の入力に入らない。動くのは前提を1件閉じたときだけ」。\n**そう印字しているのに、合否の門（`stop_check.sh`）はそれを読んでいませんでした。**\n**同じことを2か所が別々に言っていて、片方しか読まれていない** —— この形は\n今日だけで3つ見つかっています（`day_cap` の分母・天井の分母・合否の門）。\n\n**3. 資源は取り合えます。** 2026-08-15、2人の子が同じ日の予約を取り合い、\n**片方の生成が丸ごと無駄になりました。** 主実行の子が同時に走っています\n（札 `youtube-hourly`。生きているかは `list_sessions` で見ること）。\n**どう避けるか、避ける価値があるかも、あなたの判断です。**\n\n**4. 実験の律速が動機なのか供給なのか、まだ切り分けていません。**\n1つのA/Bに16本要るのに、1日に出せるのは10本・作れるのは4本・在庫は0本。\n**2026-08-28 の `day_cap` 判定が切り分けになります。**\n\n## 道具\n\n    python scripts/drift.py     この輪が外れていないか（比を1つ出す）\n    python scripts/status.py    手元と Analytics の全部\n    python scripts/eta.py       到達予測（頭3行と末尾3行だけ読めば足ります）\n\n**残すなら `run_marker.py --ship \"...\" --lever <腕> --moves <日数>`。**\n**押すかどうかも含めて、あなたが決めてください。**\n\n**`docs/JOURNAL.md` は、次に来た者が読む唯一の場所です。**\n何を変えたか・なぜか・**覆る条件**を書いておくと、次が判断できます。\n\n**あなたはサブエージェントです**（2026-08-25 夜に子セッションから移しました）。\n`archive_session` / `set_session_title` / `relay.py --next` は**やらないこと** ——\nどれもセッションの都合の話で、あなたには当てはまりません\n（`set_session_title` は実測77分待って拒否され、8/25 だけで1周を3回殺しています）。\n\n## **最初の1手は、枝を合わせることです**（2026-08-25 夜、サブへ移してから壊れた）\n\n**あなたのワークツリーは `main` から切られていることがあります。**\n`docs/trigger_main.md` が**無い**なら、それです（この文書も、`scripts/` の道具も、\n`docs/` の申し送りも、全部そこには入っていません）。\n\n    git fetch origin\n    git merge origin/claude/youtube-auto-post-revenue-ggedij\n      → 競合したら **merge で相手の作業を残すこと。捨てないこと**\n      → 済んだら commit して push。**ここが最初の節目です**\n\n**子セッションのときは、この事故が起きませんでした。** `create_session` に\n`source_revision`（＝枝）を渡していたからです（`scripts/spawn_prompt.py --json`）。\n**サブにはその口がありません。** 誰も渡さないので、**自分で合わせるまで、\n読む文書が全部古いまま**です。\n\n実測 2026-08-25 の夜: サブ3枚が3枚とも `main`(4114f7b) から切られ、\n**3枚とも同じ merge を自分でやり直しています**（`worktree-agent-a16b…` /\n`worktree-agent-a47d…` / `worktree-agent-acd2…` の合流コミット）。\nうち1枚は `docs/trigger_main.md` を探すところから始めています。\n\n**この1手を飛ばすと、読む手順そのものが古い**ので、\nそのあとの判断は全部その上に乗ります。**先にやること。**\n\n**節目ごとに commit して push すること。最後にまとめないこと。**\n**親はあなたの中身を判断しません** —— 押さなければ、その回の成果はどこにも残りません。\n\n> **なぜ「最後にまとめない」のか**（2026-08-25 に気づいた。オーナー\n> 「畳んでもサブは終わりまで走るの？」）\n>\n> **あなたは親のコンテナの中で走っています。** 親のセッションが畳まれると\n> コンテナが回収され、**あなたも道連れになります。**\n> 子セッションは独立していたので親が死んでも生き残りましたが、\n> **サブに移したことで、その耐性を失いました。**\n>\n> **最後にまとめて push する作りだと、途中で死んだ回は丸ごと消えます**\n> （動画を作っていれば、その本も）。**節目ごとに押せば、そこまでは残ります。**\n>\n> 節目の目安: 台本ができた／動画ができた／予約が通った／検査が緑になった／\n> 日誌を書いた。**1つ終わるたびに push。**\n\n**同じ枝で他に走っている相手は、立てた時点ではいません。**\nそれでも push 前に必ず `git fetch`。競合したら merge で**相手の作業を残すこと。捨てないこと。**\n\n**幹は `origin/main` ではありません。** あなたの worktree は `main` から切られますが、\n`main` は **2026-08-08 で止まっています**（8/25 の実測。17日ぶん古い）。\n**何かを読む前に、幹を取り込むこと**:\n\n    git fetch --all --prune\n    git branch -r --sort=-committerdate      ← いちばん新しい `worktree-agent-*` が幹\n    git merge origin/<その枝>\n\n**飛ばすと、17日前のファイルに対して作業します** —— `scripts/eta.py` も\n`scripts/drift.py` も `docs/trigger_main.md` も**存在しない**状態から始まります。\n**`CLAUDE.md` で衝突したら、幹の版を採ること**（幹の冒頭に理由が書いてあります）。\n**サブエージェントは `CLAUDE.md` を書き換えられません** —— 衝突したまま進めて構いません。\nその1ファイルは触らず、変えたファイルだけを push すること。\n\n## **親の手順も、あなたが書き換えてよい**\n\n**あなたを立てている側の手続きは、全部 repo にあります:**\n\n    docs/trigger_parent.md 第1節     親が起きたら何をするか\n    scripts/next_round.py            いつ立てるか・どの役か\n    docs/spawn_prompt.md             あなたに渡される本文の**型**\n                                     （`docs/spawn_prompt.rendered.md` は**生成物**。\n                                       手で直すと戻されます —— 2026-08-25 に踏んだ）\n\n**欠陥に気づいたら直してください。** 親は毎回この3つを読み直します。\n**理由と「覆る条件」を `docs/JOURNAL.md` に書くこと** —— 書かないと、\n次に来た側が判断できず惰性で戻します。\n\n**変えられないのは目標の本文だけです**（`CLAUDE.md` 冒頭・`docs/GOAL.md`）。\n**それ以外に聖域はありません。**\n"
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
  "prompt": "【オーナーからの連絡】原文: 「<<オーナーの言葉を、ここに原文のまま。要約しない。数字は桁もそのまま>>」\n\n**いちばん先に `python scripts/inbox.py --open \"<この本文>\"` を打って push すること**（数秒）。\n**あなたが死んでも、次の子がそれを見つけます。** 親は repo を触れないので、\n押す前に落ちると依頼ごと消えます（8/15・8/16 に2回消えました）。\n\n`docs/FOR_OWNER.md` の該当項目を「済み」へ移し、受け取った数字があれば\n`docs/JOURNAL.md` に書いて push すること。\nそのうえで `docs/trigger_main.md` の1周をやること（**最低1件は出す**。同 §4）。\n最後に自分を archive すること。\n\n**同じ枝で他に走っている相手は、立てた時点ではいません。**\nそれでも push 前に必ず `git fetch`。競合したら merge で**相手の作業を残すこと。捨てないこと。**\n\n**幹は `origin/main` ではありません。** あなたの worktree は `main` から切られますが、\n`main` は **2026-08-08 で止まっています**（8/25 の実測。17日ぶん古い）。\n**何かを読む前に、幹を取り込むこと**:\n\n    git fetch --all --prune\n    git branch -r --sort=-committerdate      ← いちばん新しい `worktree-agent-*` が幹\n    git merge origin/<その枝>\n\n**飛ばすと、17日前のファイルに対して作業します** —— `scripts/eta.py` も\n`scripts/drift.py` も `docs/trigger_main.md` も**存在しない**状態から始まります。\n**`CLAUDE.md` で衝突したら、幹の版を採ること**（幹の冒頭に理由が書いてあります）。\n**サブエージェントは `CLAUDE.md` を書き換えられません** —— 衝突したまま進めて構いません。\nその1ファイルは触らず、変えたファイルだけを push すること。\n\n## **親の手順も、あなたが書き換えてよい**\n\n**あなたを立てている側の手続きは、全部 repo にあります:**\n\n    docs/trigger_parent.md 第1節     親が起きたら何をするか\n    scripts/next_round.py            いつ立てるか・どの役か\n    docs/spawn_prompt.md             あなたに渡される本文の**型**\n                                     （`docs/spawn_prompt.rendered.md` は**生成物**。\n                                       手で直すと戻されます —— 2026-08-25 に踏んだ）\n\n**欠陥に気づいたら直してください。** 親は毎回この3つを読み直します。\n**理由と「覆る条件」を `docs/JOURNAL.md` に書くこと** —— 書かないと、\n次に来た側が判断できず惰性で戻します。\n\n**変えられないのは目標の本文だけです**（`CLAUDE.md` 冒頭・`docs/GOAL.md`）。\n**それ以外に聖域はありません。**\n"
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
  "prompt": "【オーナーからの連絡・記録のみ】原文: 「<<オーナーの言葉を、ここに原文のまま。要約しない。数字は桁もそのまま>>」\n\n**いちばん先に `python scripts/inbox.py --open \"<この本文>\"` を打って push すること**（数秒）。\n\n`docs/FOR_OWNER.md` の該当項目を「済み」へ移し、受け取った数字があれば\n`docs/JOURNAL.md` に書いて push すること。\n\n**`docs/trigger_main.md` の1周はやらないこと。別の子が回しています**\n（§4 の「1件は出してから終わる」も、この回には掛かりません。\n**記録して push したら、それがこの回の成果です**）。\n最後に自分を archive すること。\n\n**同じ枝で他に走っている相手は、立てた時点ではいません。**\nそれでも push 前に必ず `git fetch`。競合したら merge で**相手の作業を残すこと。捨てないこと。**\n\n**幹は `origin/main` ではありません。** あなたの worktree は `main` から切られますが、\n`main` は **2026-08-08 で止まっています**（8/25 の実測。17日ぶん古い）。\n**何かを読む前に、幹を取り込むこと**:\n\n    git fetch --all --prune\n    git branch -r --sort=-committerdate      ← いちばん新しい `worktree-agent-*` が幹\n    git merge origin/<その枝>\n\n**飛ばすと、17日前のファイルに対して作業します** —— `scripts/eta.py` も\n`scripts/drift.py` も `docs/trigger_main.md` も**存在しない**状態から始まります。\n**`CLAUDE.md` で衝突したら、幹の版を採ること**（幹の冒頭に理由が書いてあります）。\n**サブエージェントは `CLAUDE.md` を書き換えられません** —— 衝突したまま進めて構いません。\nその1ファイルは触らず、変えたファイルだけを push すること。\n\n## **親の手順も、あなたが書き換えてよい**\n\n**あなたを立てている側の手続きは、全部 repo にあります:**\n\n    docs/trigger_parent.md 第1節     親が起きたら何をするか\n    scripts/next_round.py            いつ立てるか・どの役か\n    docs/spawn_prompt.md             あなたに渡される本文の**型**\n                                     （`docs/spawn_prompt.rendered.md` は**生成物**。\n                                       手で直すと戻されます —— 2026-08-25 に踏んだ）\n\n**欠陥に気づいたら直してください。** 親は毎回この3つを読み直します。\n**理由と「覆る条件」を `docs/JOURNAL.md` に書くこと** —— 書かないと、\n次に来た側が判断できず惰性で戻します。\n\n**変えられないのは目標の本文だけです**（`CLAUDE.md` 冒頭・`docs/GOAL.md`）。\n**それ以外に聖域はありません。**\n"
}
```
