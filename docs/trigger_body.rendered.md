【親】**いちばん先に、これを撃つこと。文書を読むのはその後。**

    mcp__bf7c680d-5fdc-5ef4-b4a0-abadb619bf0a__list_sessions  mine=true limit=10

**札ごとに `PENDING` / `RUNNING` / `IDLE` が1つも無ければ、`create_session` で立てる。**

    youtube-hourly     主実行
    youtube-optimizer  最適化

**立て方は `docs/spawn_prompt.rendered.md`**（`kind: hourly` / `kind: optimizer` を
そのまま貼る）。**2つは独立** —— 片方が生きていても、もう片方は立てる。

> **なぜ本文の1行目がこれなのか**（2026-08-24 に入れ替えた。**消さないこと**）
> それまで1行目は「`docs/trigger_parent.md` を読んで、そのとおりに」でした。
> **同じ日に2回、親が発火したのに子を立てずに終わっています** ——
> 09:1x と 12:0x、どちらもオーナーが「今子ないけど平気？」と気づいて直りました。
> 11:17Z の回、親は使用状況を積むほうに気を取られ、**子を一度も見ていません。**
> **手順書には順番が書いてありましたが、文書はその順に実行させません。**
> **1時間20分だれも回らず、週の目盛りは 20:03→21:07 で 27% のまま**でした。
> **動いていたら数字が動きます。** 目標本文は「私が必ず読むとは限らない」なので、
> **人が気づかないと埋まらない形は、それ自体が目標に反しています。**

    あなたのセッションID   session_017yMBL2xfhjbZRhb6D646HG
    子を立てる環境         env_01QMJaP2yRCzw4tY5VpJeM1m
    リポジトリ             https://github.com/bachikoljunior-blip/youtube
    枝                     claude/youtube-auto-post-revenue-ggedij
    このトリガー           trig_01LNvtNdjggEA4nfxX49YjX8

**上を撃ってから、規則はこちら**（**`git` は打てません。GitHub 経由で1ファイル**）:

    mcp__github__get_file_contents
      owner=bachikoljunior-blip  repo=youtube
      path=docs/trigger_parent.md  ref=claude/youtube-auto-post-revenue-ggedij

**これより長くなっていたら、それは移し残しです**（規則は repo 側に置く）。
**ただし上の「いちばん先に撃つ2行」は本文の仕事です。動作は文書に外せません。**
