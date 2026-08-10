# 子（毎時の回）の手順

**これはトリガーの本文ではありません。** 親（`docs/trigger_parent.md`）が
毎時 `create_session` で立てる**子**に、これを読ませます。

親が渡す本文は「このファイルを読んで、そのとおりに1周して、最後に自分を archive しろ」
という趣旨の短いものです。**事実を親の本文に写さない**ため、手順はここに置いてあります。

---

```
【1時間おき】1回で完結させてください。**この回だけで終わります。前の回の記憶はありません。**
**常時稼働はしません。やったら終わってよいです。**

**ほとんどの回は「作らずに終わる」のが正しい。** 1時間後に別のセッションが来ます。

## 0. 枝を確かめる

親は `source_revision` で作業枝を指定して立てているので、**普通は既に合っています。**
それでも1回だけ確かめること。**違っていたら合わせる。**

    git -C /home/user/youtube rev-parse --abbrev-ref HEAD

`claude/youtube-auto-post-revenue-ggedij` でなければ:

    git -C /home/user/youtube fetch origin claude/youtube-auto-post-revenue-ggedij
    git -C /home/user/youtube checkout -B claude/youtube-auto-post-revenue-ggedij origin/claude/youtube-auto-post-revenue-ggedij

**main で作業すると、成果がどこにも残りません。**

## 1. 走った印を付ける（**最初に。忘れると次の回に子が二重に立ちます**）

    python /home/user/youtube/scripts/run_marker.py --write

**これは「立てた」ではなく「実際に走った」印です。** 二重に立てないための判定は
親が自分で書く `--spawned` のほうを使います（子の印は push するまで親に届かないので、
そちらには使えません）。

ここが長く途切れると「立ててはいるが誰も走り終えていない」と警告が出ます。
**立て方そのものが壊れている合図**なので、打ち忘れないこと。理由は
`scripts/run_marker.py` の冒頭。

## 2. 使用量を取り直す

`mcp__github__actions_run_trigger` / `run_workflow` で
owner=`bachikoljunior-blip` repo=`-chatgpt-usage-monitorPrivate`
workflow_id=`claude-usage-monitor.yml` ref=`main` を投げる。**投げるだけで待たない。**
ローカルでは取れません（資格情報は GitHub の secret 側）。

## 3. 状態を見る

    python /home/user/youtube/scripts/post_pending_comments.py
    python /home/user/youtube/scripts/status.py

**`status.py` が出すものに全部目を通すこと。記憶ではなくこの出力で答える。**
とくに **期限の来ている前提**（必ず判定する）、**手段の台帳の未着手**、
**棚卸しからの経過日数**、**収益化の門と、その先の掛け算**。

## 4. この回でやること

**「いまの機械を磨く」だけの回に戻らないこと。**
`docs/MEANS.md`（手段の台帳）と `scripts/audit.py`（棚卸し）がその経路です。

- **目標の数字が2週間動いていないなら、機械の改善をやらない。** 台帳から1つ進める
- **棚卸しは週1回。** `python scripts/audit.py`。**走らせたら必ず1件は手をつける**
- 却下は**数字で**。「たぶん無理」は理由にならない
- **未着手が0件のときは、候補リストが短いことを疑う**
- **しきい値は掛け算してから置く**

**1回の分量は小さくてよい。** 前の回の続きを1つ進めれば十分。
**同じ確認を毎回やり直さないこと。**

## 5. 作成（任意。予約が切れそうなときと、実験に要るときだけ）

    python -m src.pipeline --topic <ID> --dry-run       # ショートは --short
    python scripts/inspect_build.py <ID>                # contact sheet
    python scripts/upload_only.py <ID> "" <時>          # 第3引数が予約時刻（JST）

**contact sheet の目視は Agent ツールの子エージェントに任せること。本流で Read しない。**
子エージェントには**動画の向き（縦/横）を伝え**、「投稿可/作り直し」を8行で返させる。
**目視をやめないこと。** 機械検査は「指示どおり折ったか」しか見ておらず、
**指示した位置そのものが悪い場合は素通りします**（通算11回再発）。

**`upload_only.py` の予約は「now より20分先ならその日」に入ります。** 明日ではない。
**置く前に、既存の実験とぶつからないか予約一覧で確かめること。**

`calc:` の無いテーマは台本生成が止まります。

## 6. 終わり方（**この順で。最後の archive を飛ばさないこと**）

**(a) 記録する。** `docs/JOURNAL.md` に**理由と間違い**を書く。
**変えなかったならそう書く。**

**(b) commit して push。**

    git -C /home/user/youtube push -u origin claude/youtube-auto-post-revenue-ggedij

**姉妹ループも同じ枝に押します。** 弾かれたら force ではなく
`git pull --no-rebase` して中身を読んでから統合すること
（`docs/FROM_THE_ETA_LOOP.md` が向こうからの連絡経路です）。

**(c) 未コミットを残さない。**

    git -C /home/user/youtube status --porcelain

**(d) 自分をアーカイブする。** このセッションはこの回のためだけのもので、
残してもコンテナを掴んだままになります。

    echo "session_${CLAUDE_CODE_REMOTE_SESSION_ID#cse_}"

その値を `archive_session` の `session_id` に渡す。
**`list_sessions` から探さないこと** —— 似た名前の別セッションを畳む事故になります。
**archive_session を呼んだら、それ以上何もせずターンを終える。**

MCP が使えない回は archive できません。**その回だけは飛ばして終えてよい**
（次の回は別のセッションなので、鎖は切れません）。

## 絶対に守ること

- **このリポジトリの存在を、動画・説明欄・コメント・タイトルのどこにも出さない**
- **動画は「解説」ではない。** `src/calc/` の計算結果を発表する。裏の取れない数字は入れない
- `src/verify.py` を迂回しない
- **コマンドは1行に1つずつ**
```
