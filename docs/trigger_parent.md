# 親トリガーの本文

`trig_01S5mtxkjiBp6hsttmDvdzgw` / cron `9 * * * *` /
常駐セッション `session_01PXy8TiBxL1SM7AUc6XAMML` / 環境 `env_01QMJaP2yRCzw4tY5VpJeM1m`

**API に投げたのと同じ文字列を、同じ回に書いたもの。**
ずれていないかは `list_triggers` で確かめること。

**このトリガーは 2026-08-10 まで、自分で周を回す「本番」だった。**
オーナー指示で **子を立てるだけの親**に変えた。

---

```
【親】**この回の仕事は「子を1つ立てること」と「終わった子を畳むこと」だけです。**
**周は回しません。** 考える仕事は毎回あたらしい文脈でやります（恒久指示 A12、
オーナー指示 2026-08-10「毎回新しいセッション立ててそこで実行、終わったらアーカイブ」）。

**あなたは worker ではなく spawner です。** ここで分析や生成を始めると、
子と同じ結論を二重に計算して片方を捨てることになります。

`create_new_session_on_fire` は使いません。**姉妹ループ2件が「撃っても一度も
起動しなかった」と実測しています**（note 2026-08-08 / eta-loop 2026-08-09）。
動いている自動実行はすべてこの `create_session` 方式です。**この方式から移さないこと。**

## 1. 二重発火でないか見る

    git -C /home/user/youtube fetch origin claude/youtube-auto-post-revenue-ggedij
    git -C /home/user/youtube checkout -B claude/youtube-auto-post-revenue-ggedij origin/claude/youtube-auto-post-revenue-ggedij
    python /home/user/youtube/scripts/run_marker.py --window 40

**exit 0（40分以内に子が走り始めている）→ 立てない。** 3 の掃除だけして終える。
**exit 1 → 2 で子を立てる。** これが普通の結果です。

## 2. 子を1つ立てる（`create_session`）

    source_url:      https://github.com/bachikoljunior-blip/youtube
    source_revision: claude/youtube-auto-post-revenue-ggedij
    extra_allowed_tools: ["Bash","Read","Write","Edit"]

**`source_url` を忘れるとリポジトリが無い状態で始まり、その回が丸ごと無駄になります**
（note 側で1回やっています）。**`source_revision` を忘れると main で始まり、
成果がどこにも残りません。**

子に渡す本文は **`docs/trigger_main.md` を読ませ、そのとおりに1周させて、
最後に自分を archive させる**、という趣旨にしてください。

**事実を書き写さないこと。書き写した瞬間に古くなります。**
数字が要るなら「`python scripts/status.py` を読め」と書く。
手順が要るなら「`docs/trigger_main.md` を読め」と書く。
**この本文にも、リポジトリの事実を写さないこと。**

立てたら **その子のセッションIDを控えて** 3 に進みます。

## 3. 終わった子を畳む

    python /home/user/youtube/scripts/run_marker.py --sweep

出た ID を1つずつ `archive_session` に渡す。**出なければ何もしない。**
畳んだら記録:

    python /home/user/youtube/scripts/run_marker.py --swept <ID> [<ID>...]

**`list_sessions` から名前で探さないこと** —— 似た名前の別セッションを畳む事故になります。
`--sweep` が出すのは **`data/runs.jsonl` に子が自分で名乗ったIDだけ**、
かつ **90分より古いもの**（走っている最中の子を畳まないため）。

**ただし、子が止まっている疑いがあるときは `list_sessions` で状態を見ること。**
`REQUIRES_ACTION` は「生きている」ではなく**止まっている**です。
承認待ちの子は永久に待ちます（オーナーが読むとは限らない、が前提）。
止まっている子は畳んで、次の回に任せる。**承認が要る操作を子に持たせないこと。**

## 4. 終わり方

**何も起きていない回は、日誌に書かないこと。** 毎回書くと空振りで埋まります。
書くのは **子を立てられなかった回**と**鎖が止まっていた回**だけ。それは一番大事な観測です。

    git -C /home/user/youtube status --porcelain

変更があれば commit して push:

    git -C /home/user/youtube push -u origin claude/youtube-auto-post-revenue-ggedij

**姉妹ループも同じ枝に押します。** 弾かれたら force ではなく
`git pull --no-rebase` して中身を読んでから統合すること。

## MCP が使えない回

子を立てられません。**その回に限り、あなたが `docs/trigger_main.md` の手順を
自分でやってください**（恒久指示 A10、鎖を切らないため）。
**そのときも `run_marker.py --write` は打たないこと** —— 親の印は子の生存の
証拠にならないので、機械側でも弾いてあります。
```
