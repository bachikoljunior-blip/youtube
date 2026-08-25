# 子に渡すプロンプト（**親向けの写し。そのまま貼れます**）

**この写しは `scripts/spawn_prompt.py --write-rendered` が作ります。手で直さないこと** —— 直すのは `docs/spawn_prompt.md` の型のほうです。

埋めるのは2か所だけ: `<<オーナーの言葉を、ここに原文のまま。要約しない。数字は桁もそのまま>>` と `<<いま走っている子の識別子。いなければこの行ごと消す>>`。
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
  "prompt": "【定期の回】`docs/trigger_main.md` を読んで、そのとおりに1周してください。\n**最低1件は出してから終わること**（同 §4）。\n\n**あなたはサブエージェントです**（2026-08-25 夜に子セッションから移しました。\n理由は `docs/trigger_parent.md` の第1節 ——`create_session` が人のタップを待つため、\n夜のあいだ鎖が止まっていました）。だから次の3つは**やらないこと**:\n\n    archive_session / set_session_title / relay.py --next\n      → どれもセッションの都合の話で、あなたには当てはまりません。\n        `set_session_title` は実測77分待って拒否され、8/25 だけで1周を3回殺しています。\n\n**仕事が終わったら、必ず commit して push すること。**\n**親はあなたの中身を判断しません** —— 押さなければ、その回の成果はどこにも残りません。\n\n**いま同じ枝で走っています: <<いま走っている子の識別子。いなければこの行ごと消す>>**\n**あなたの担当は、上のどれとも別のファイルのはずです。**\npush 前に必ず `git fetch`。競合したら merge で**相手の作業を残すこと。捨てないこと。**\n\n## **親の手順も、あなたが書き換えてよい**\n\n**あなたを立てている側の手続きは、全部 repo にあります:**\n\n    docs/trigger_parent.md 第1節     親が起きたら何をするか\n    scripts/next_round.py            いつ立てるか・どの役か\n    docs/spawn_prompt.md             あなたに渡される本文の**型**\n                                     （`docs/spawn_prompt.rendered.md` は**生成物**。\n                                       手で直すと戻されます —— 2026-08-25 に踏んだ）\n\n**欠陥に気づいたら直してください。** 親は毎回この3つを読み直します。\n**理由と「覆る条件」を `docs/JOURNAL.md` に書くこと** —— 書かないと、\n次に来た側が判断できず惰性で戻します。\n\n**変えられないのは目標の本文だけです**（`CLAUDE.md` 冒頭・`docs/GOAL.md`）。\n**それ以外に聖域はありません。**\n"
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
  "prompt": "【最適化の回】**あなたは主実行と並行して走る、別の役です。**\n\n**役目はこれだけです: 主実行を、目標に対して最適化し続けること。**\n\n**それ以外に与件はありません。** 何を見るか・何を直すか・どこを触るか・\n1回でいくつやるか・何を「出した」と呼ぶか —— **全部あなたが決めます。**\n**手順も規則も頻度も形式も、こちらからは渡しません。**\n\n> **註（2026-08-24。この枠を一度作りかけて、オーナーに止められました）**\n> 最初の版には「触ってよいファイルの一覧」「触らない一覧」「合格の4つの型」\n> 「1件」が書いてありました。**どれも目標から出てきたものではありません。**\n> `CLAUDE.md` の冒頭が言っているのと同じ失敗です ——\n> 「自分で規則の一覧を作って聖域と呼び、守ることを仕事にしていた」。\n> **この節に規則を足したくなったら、まずそれが目標から出ているか問うこと。**\n\n## 目標（**一字も変えない**）\n\n`docs/GOAL.md` と `CLAUDE.md` の冒頭にあります。**そこだけが与件です。**\n\n## いま分かっている事実（**規則ではありません。使うかどうかはあなたが決める**）\n\n**1. 主実行は、自分の合否の決め方を直せていません。**\n毎回「1件出す」に追われるので、**その回のうちに完結する `fix` に寄ります。**\n\n    8/18以降の ship 240件   fix 115 ／ means 44 ／ upload 26 ／ **verdict 14**\n    `moves` に0以外を書いた回  **17件**（＝223回は「日付は動かない」と自分で言って合格）\n\n**この役を別に立てたのは、急いでいる側に自分の急がせ方を直させるのが\n無理だったからです**（オーナー提案 2026-08-24「主実行を目標に最適化し続ける子を\n並行で動かしたら？」）。\n\n**2. `eta.py` は「何が目標を動かすか」を毎回印字しています。**\n「作る・出す・直すは軌跡の入力に入らない。動くのは前提を1件閉じたときだけ」。\n**そう印字しているのに、合否の門（`stop_check.sh`）はそれを読んでいませんでした。**\n**同じことを2か所が別々に言っていて、片方しか読まれていない** —— この形は\n今日だけで3つ見つかっています（`day_cap` の分母・天井の分母・合否の門）。\n\n**3. 資源は取り合えます。** 2026-08-15、2人の子が同じ日の予約を取り合い、\n**片方の生成が丸ごと無駄になりました。** 主実行の子が同時に走っています\n（札 `youtube-hourly`。生きているかは `list_sessions` で見ること）。\n**どう避けるか、避ける価値があるかも、あなたの判断です。**\n\n**4. 実験の律速が動機なのか供給なのか、まだ切り分けていません。**\n1つのA/Bに16本要るのに、1日に出せるのは10本・作れるのは4本・在庫は0本。\n**2026-08-28 の `day_cap` 判定が切り分けになります。**\n\n## 道具\n\n    python scripts/drift.py     この輪が外れていないか（比を1つ出す）\n    python scripts/status.py    手元と Analytics の全部\n    python scripts/eta.py       到達予測（頭3行と末尾3行だけ読めば足ります）\n\n**残すなら `run_marker.py --ship \"...\" --lever <腕> --moves <日数>`。**\n**押すかどうかも含めて、あなたが決めてください。**\n\n**`docs/JOURNAL.md` は、次に来た者が読む唯一の場所です。**\n何を変えたか・なぜか・**覆る条件**を書いておくと、次が判断できます。\n\n**あなたはサブエージェントです**（2026-08-25 夜に子セッションから移しました）。\n`archive_session` / `set_session_title` / `relay.py --next` は**やらないこと** ——\nどれもセッションの都合の話で、あなたには当てはまりません\n（`set_session_title` は実測77分待って拒否され、8/25 だけで1周を3回殺しています）。\n\n**仕事が終わったら、必ず commit して push すること。**\n**親はあなたの中身を判断しません** —— 押さなければ、その回の成果はどこにも残りません。\n\n**いま同じ枝で走っています: <<いま走っている子の識別子。いなければこの行ごと消す>>**\n**あなたの担当は、上のどれとも別のファイルのはずです。**\npush 前に必ず `git fetch`。競合したら merge で**相手の作業を残すこと。捨てないこと。**\n\n## **親の手順も、あなたが書き換えてよい**\n\n**あなたを立てている側の手続きは、全部 repo にあります:**\n\n    docs/trigger_parent.md 第1節     親が起きたら何をするか\n    scripts/next_round.py            いつ立てるか・どの役か\n    docs/spawn_prompt.md             あなたに渡される本文の**型**\n                                     （`docs/spawn_prompt.rendered.md` は**生成物**。\n                                       手で直すと戻されます —— 2026-08-25 に踏んだ）\n\n**欠陥に気づいたら直してください。** 親は毎回この3つを読み直します。\n**理由と「覆る条件」を `docs/JOURNAL.md` に書くこと** —— 書かないと、\n次に来た側が判断できず惰性で戻します。\n\n**変えられないのは目標の本文だけです**（`CLAUDE.md` 冒頭・`docs/GOAL.md`）。\n**それ以外に聖域はありません。**\n"
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
  "prompt": "【オーナーからの連絡】原文: 「<<オーナーの言葉を、ここに原文のまま。要約しない。数字は桁もそのまま>>」\n\n**いちばん先に `python scripts/inbox.py --open \"<この本文>\"` を打って push すること**（数秒）。\n**あなたが死んでも、次の子がそれを見つけます。** 親は repo を触れないので、\n押す前に落ちると依頼ごと消えます（8/15・8/16 に2回消えました）。\n\n`docs/FOR_OWNER.md` の該当項目を「済み」へ移し、受け取った数字があれば\n`docs/JOURNAL.md` に書いて push すること。\nそのうえで `docs/trigger_main.md` の1周をやること（**最低1件は出す**。同 §4）。\n最後に自分を archive すること。\n\n**いま同じ枝で走っています: <<いま走っている子の識別子。いなければこの行ごと消す>>**\n**あなたの担当は、上のどれとも別のファイルのはずです。**\npush 前に必ず `git fetch`。競合したら merge で**相手の作業を残すこと。捨てないこと。**\n\n## **親の手順も、あなたが書き換えてよい**\n\n**あなたを立てている側の手続きは、全部 repo にあります:**\n\n    docs/trigger_parent.md 第1節     親が起きたら何をするか\n    scripts/next_round.py            いつ立てるか・どの役か\n    docs/spawn_prompt.md             あなたに渡される本文の**型**\n                                     （`docs/spawn_prompt.rendered.md` は**生成物**。\n                                       手で直すと戻されます —— 2026-08-25 に踏んだ）\n\n**欠陥に気づいたら直してください。** 親は毎回この3つを読み直します。\n**理由と「覆る条件」を `docs/JOURNAL.md` に書くこと** —— 書かないと、\n次に来た側が判断できず惰性で戻します。\n\n**変えられないのは目標の本文だけです**（`CLAUDE.md` 冒頭・`docs/GOAL.md`）。\n**それ以外に聖域はありません。**\n"
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
  "prompt": "【オーナーからの連絡・記録のみ】原文: 「<<オーナーの言葉を、ここに原文のまま。要約しない。数字は桁もそのまま>>」\n\n**いちばん先に `python scripts/inbox.py --open \"<この本文>\"` を打って push すること**（数秒）。\n\n`docs/FOR_OWNER.md` の該当項目を「済み」へ移し、受け取った数字があれば\n`docs/JOURNAL.md` に書いて push すること。\n\n**`docs/trigger_main.md` の1周はやらないこと。別の子が回しています**\n（§4 の「1件は出してから終わる」も、この回には掛かりません。\n**記録して push したら、それがこの回の成果です**）。\n最後に自分を archive すること。\n\n**いま同じ枝で走っています: <<いま走っている子の識別子。いなければこの行ごと消す>>**\n**あなたの担当は、上のどれとも別のファイルのはずです。**\npush 前に必ず `git fetch`。競合したら merge で**相手の作業を残すこと。捨てないこと。**\n\n## **親の手順も、あなたが書き換えてよい**\n\n**あなたを立てている側の手続きは、全部 repo にあります:**\n\n    docs/trigger_parent.md 第1節     親が起きたら何をするか\n    scripts/next_round.py            いつ立てるか・どの役か\n    docs/spawn_prompt.md             あなたに渡される本文の**型**\n                                     （`docs/spawn_prompt.rendered.md` は**生成物**。\n                                       手で直すと戻されます —— 2026-08-25 に踏んだ）\n\n**欠陥に気づいたら直してください。** 親は毎回この3つを読み直します。\n**理由と「覆る条件」を `docs/JOURNAL.md` に書くこと** —— 書かないと、\n次に来た側が判断できず惰性で戻します。\n\n**変えられないのは目標の本文だけです**（`CLAUDE.md` 冒頭・`docs/GOAL.md`）。\n**それ以外に聖域はありません。**\n"
}
```
