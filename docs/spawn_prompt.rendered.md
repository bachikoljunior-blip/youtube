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
  "prompt": "【定期の回】`docs/trigger_main.md` を読んで、そのとおりに1周してください。\n**最低1件は出してから終わること**（同 §4）。最後に自分を archive すること。\n\n**いま同じ枝で走っています: <<いま走っている子の識別子。いなければこの行ごと消す>>**\n**あなたの担当は、上のどれとも別のファイルのはずです。**\npush 前に必ず `git fetch`。競合したら rebase／merge で**相手の作業を残すこと。捨てないこと。**\n"
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
  "prompt": "【オーナーからの連絡】原文: 「<<オーナーの言葉を、ここに原文のまま。要約しない。数字は桁もそのまま>>」\n\n**いちばん先に `python scripts/inbox.py --open \"<この本文>\"` を打って push すること**（数秒）。\n**あなたが死んでも、次の子がそれを見つけます。** 親は repo を触れないので、\n押す前に落ちると依頼ごと消えます（8/15・8/16 に2回消えました）。\n\n`docs/FOR_OWNER.md` の該当項目を「済み」へ移し、受け取った数字があれば\n`docs/JOURNAL.md` に書いて push すること。\nそのうえで `docs/trigger_main.md` の1周をやること（**最低1件は出す**。同 §4）。\n最後に自分を archive すること。\n\n**いま同じ枝で走っています: <<いま走っている子の識別子。いなければこの行ごと消す>>**\n**あなたの担当は、上のどれとも別のファイルのはずです。**\npush 前に必ず `git fetch`。競合したら rebase／merge で**相手の作業を残すこと。捨てないこと。**\n"
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
  "prompt": "【オーナーからの連絡・記録のみ】原文: 「<<オーナーの言葉を、ここに原文のまま。要約しない。数字は桁もそのまま>>」\n\n**いちばん先に `python scripts/inbox.py --open \"<この本文>\"` を打って push すること**（数秒）。\n\n`docs/FOR_OWNER.md` の該当項目を「済み」へ移し、受け取った数字があれば\n`docs/JOURNAL.md` に書いて push すること。\n\n**`docs/trigger_main.md` の1周はやらないこと。別の子が回しています**\n（§4 の「1件は出してから終わる」も、この回には掛かりません。\n**記録して push したら、それがこの回の成果です**）。\n最後に自分を archive すること。\n\n**いま同じ枝で走っています: <<いま走っている子の識別子。いなければこの行ごと消す>>**\n**あなたの担当は、上のどれとも別のファイルのはずです。**\npush 前に必ず `git fetch`。競合したら rebase／merge で**相手の作業を残すこと。捨てないこと。**\n"
}
```
