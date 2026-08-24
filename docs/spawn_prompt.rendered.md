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

## kind: optimizer

```json
{
  "source_url": "https://github.com/bachikoljunior-blip/youtube",
  "source_revision": "claude/youtube-auto-post-revenue-ggedij",
  "environment_id": "env_01QMJaP2yRCzw4tY5VpJeM1m",
  "tags": [
    "youtube-optimizer"
  ],
  "prompt": "【最適化の回】**あなたは主実行と並行して走る、別の役です。**\n\n**やること: 「主実行の合否の決め方」と「目標が実際に動く条件」のズレを1つ潰す。**\n\n    python scripts/drift.py     ← ここから始める（この輪が外れていないか）\n\n## 何を触るか（**ここだけ**）\n\n    scripts/stop_check.sh   合否の門       docs/trigger_main.md  1周の手順\n    scripts/drift.py        外れの計器     docs/GOAL.md          判断の並び\n    scripts/eta.py          軌跡の模型     config/hypotheses.yaml 前提の立て方\n    scripts/run_marker.py   印の付け方     scripts/spawn_prompt.py 渡し方\n\n## 何を触らないか（**主実行の子とぶつかるので**）\n\n**動画を作らない。予約しない。`src/calc/` に節を書かない。`config/topics.yaml`\nを触らない。`reschedule.py` を撃たない。** それは主実行の子の担当です。\n2026-08-15 に2人が同じ日の予約を取り合い、片方の生成が丸ごと無駄になりました。\n**役を分けている意味は、資源を取り合わないことです。**\n\n## この回の合格（**`fix` を1件出すことではありません**）\n\n**「決め方」が変わったこと**を1件。次のどれかの形になるはずです。\n\n    門     合否の条件を、目標が動く条件に近づけた（近づいた根拠を数字で）\n    計器   外れを、いままで見えなかった角度から1つ測れるようにした\n    模型   eta の入力・天井・軌跡の引き方を、実測に合わせて直した\n    手順   主実行が毎回落とすものを、落ちない形にした\n\n**「道具が壊れていたので直した」は、この役の成果ではありません。**\nそれは主実行の子の `fix` です。**あなたが直すのは、道具ではなく決め方。**\n\n## 必ず書くこと\n\n`docs/JOURNAL.md` に、次の3つを数字で:\n\n    1. どのズレを見つけたか（**2か所が別々に言っていて、片方しか読まれていない**箇所）\n    2. 直したあと、その比がどう変わる見込みか\n    3. **覆る条件** —— この直しが効かないと分かるのは、何がどうなったときか\n\n**印は `run_marker.py --ship \"opt: ...\" --lever <腕> --moves <日数>`。**\n`--lever` は、この直しが**主実行に引かせたい腕**を書くこと。\n\n最後に自分を archive すること。\n\n**いま同じ枝で走っています: <<いま走っている子の識別子。いなければこの行ごと消す>>**\n**あなたの担当は、上のどれとも別のファイルのはずです。**\npush 前に必ず `git fetch`。競合したら rebase／merge で**相手の作業を残すこと。捨てないこと。**\n"
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
