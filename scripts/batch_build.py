#!/usr/bin/env python3
"""1回のセッションで、複数本をまとめて作って予約する。

    python scripts/batch_build.py --count 2                 # 既定は 09:00 の空き枠へ
    python scripts/batch_build.py --count 3 --hour 11
    python scripts/batch_build.py --topics s-fukugyo-3,s-iryohi-3
    python scripts/batch_build.py --count 2 --skip-upload   # 作るだけ（予約しない）
    python scripts/batch_build.py --count 8 --date 2026-08-30 --jobs 3   # 同時に3本ずつ

## 律速は「作る速さ」でした（2026-08-15 に測って直した）

8/15 に7本を通したとき **80分＝1本11分**でした。この11分がどこに行っているかを
`ps` で見たら、**生成中の python は CPU を 2〜4% しか使っていません。**
内訳はほぼ全部が `claude -p`（`src/claude_cli.py`）の**待ち時間**です。
台本を書かせるのが一番高い工程で、そこは**こちらの CPU では何も起きていない。**

**待ち時間は重ねられます。** 直列で待っていたのは、そう書いてあったからで、
理由はありませんでした。`--jobs`（既定 3）で同時に走らせます。

    直列   8本 × 11分 = 88分   ← 1周に収まらない
    同時3  8本 ÷ 3 × 11分 ≒ 30分

**【2026-08-15 22:3x】この「11分」は、もう本当ではありません。**
実測は **1本 1.7分**（同時1）／**2.7分**（同時6）です。11.4分だったのは
8/15 18:xx の7本で、**そのあと台本の作り方が変わりました。**
この数字は文書に3回引用され、**誰も測り直していませんでした。**
**上の掛け算は当時の記録として残しますが、根拠に使わないこと。**
いまの値は `python scripts/batch_build.py --report` が出します。

**予約だけは直列のまま**です（`upload_only.py` は `next_publish_at` と
待ち行列という共有の状態を触るので、同時に走らせると予約時刻がぶつかる）。
段を分けてあるのはそのためで、**作る段と予約の段を混ぜないこと。**

## なぜ要るか（2026-08-15）

門は **「90日で1000万ショート再生」の一本**に縮みました（`docs/MEANS.md`
「M4 の土台が崩れた」）。1本あたりは 1777 が天井と確定済みなので、
**残っている変数は1日あたりの本数だけ**です。1000万/90日 ＝ 1日11.1万再生、
1本1200再生なら **1日92本**。

ところが、この輪は **1セッション＝1本**でした（`docs/trigger_main.md` §4 の
「最低1件」を、そのまま上限として運用していた）。1周は実測15〜45分なので、
**丸1日回しても十数本が上限**です。M14 が測ろうとしている 4 → 8 の段を、
**手段のほうが先に支えられません。**

だから、律速は「テーマ在庫」でも「配信」でもなく、**1回の起動で作れる本数**でした。
ここを機械化しないと、M14 は 8 の段で必ず止まります。

## この道具が守っていること

- **1本落ちても、残りは作る。** 例外は握って次のテーマへ進む（`--stop-on-error` で従来動作）
- **calc は全部ばらす。** 同じ計算を並べると量産判定に当たる（`CLAUDE.md`「この作りの根幹」）
- **`--dry-run` で作ってから `upload_only.py` で予約する。** 既存の2段構えのまま。
  検査（`src/verify.py`）も独立評価の材料保存も、そちらに入ったままです
- **予約時刻は `next_publish_at` に任せる。** 同じ時刻が埋まっていれば翌日へ送るので、
  連続で呼ぶと1日ずつ後ろに積まれます。**実験の窓を踏まないよう、時刻で選ぶこと**
- **結果は `data/batch_runs.jsonl` に残す。** `build/` は gitignore なので、
  セッションが畳まれた後に「何が出て何が落ちたか」を読めるのはここだけです
- **かかった時間も残す**（2026-08-15 22:3x に足した。下の節が理由）

## 「`--jobs` の上限を測る」が4回持ち越された理由（2026-08-15 22:3x）

`retro.py` の持ち越しで **`--jobs` が4回**（19:0x / 19:2x / 20:5x / 22:0x）出ています。
**4回とも「次の回で測る」と書かれ、4回とも測られませんでした。**
「忙しかったから」ではありません。**測れなかったからです。**

    data/batch_runs.jsonl に入っていたもの   at / hour / date / slots / results[topic,calc,video_id,error]
    入っていなかったもの                     **`jobs` も、かかった秒数も**

**この台帳を後から読んでも、何本ずつ走らせたのかすら分かりません。**
19:0x の「6本を4.7分」は**その回の画面にしか無く**、次の回には残っていない。
だから毎回「まず測り直すところから」になり、10分かかるので後回しになる ——
**それが4回くり返されました。**

そして、持ち越しの文言が**測り方そのものを高くしていました。**
「`--jobs` の上限」を **jobs=3 の回と jobs=6 の回を別々に走らせて比べる**と読むと、
1回10分の生成が2回要り、**しかも題材が違うので条件が揃いません**（台本の長さも
落ちる本数も毎回ちがう）。**1周に収まらない測定は、永久に後回しになります。**

**1本ずつの所要時間を記録すれば、1回の走りで答えが出ます。**

    直列に要る時間 ＝ 1本ずつの秒数の合計
    実際にかかった時間 ＝ 壁時計
    **速くなった倍率 ＝ 合計 ÷ 壁時計**（jobs に近ければ、待ち時間は素直に重なっている）

    **1本あたりの秒数が jobs を上げるほど伸びていたら、そこが上限です**
    （待ち時間ではなく、こちらの CPU かメモリを取り合い始めている）

**上限は「速くならなくなる点」ではなく「1本あたりが太り始める点」で出ます。**
前者は本数と題材に左右されますが、後者は**同じ走りの中で比べられます。**

    python scripts/batch_build.py --report    # 台帳を jobs 別に並べる（生成しない・数秒）

## この道具が答えないこと

**目視も独立評価もやりません**（`docs/trigger_main.md` §5・`docs/CRITIQUE.md`）。
機械検査は「指示どおり折ったか」しか見ておらず、**指示した位置そのものが悪い場合は
素通りします**。まとめて作ったぶんは、**投稿後に `scripts/critique_queue.py` の
待ち行列に積まれます。** そこを消化するのは呼んだ側の仕事です。
"""
from __future__ import annotations

import hashlib
import functools
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from datetime import time as dtime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import auth, config, dupes, history, lanes, measure_window, upload_cap, uploader  # noqa: E402
from src import renderer, verify

JST = timezone(timedelta(hours=9))
LOG = ROOT / "data" / "batch_runs.jsonl"
FLAGS = ROOT / "data" / "build_flags.jsonl"

# **M14 の比較の窓**（`docs/MEANS.md` M14）。8/16 が4本・8/17〜8/23 が各1本で、
# 「1日あたりの本数」を測っています。**ここへ足すと測定そのものが壊れます。**
#
# 文書には「実験の窓を踏まないこと」と3か所に書いてありましたが、
# **守るのは毎回こちらの記憶でした。** 8/15 の日誌が4回続けて言っている
# 「人が見れば一目で分かる欠陥を、機械検査が素通りさせた」と同じ形なので、
# **窓を機械に持たせます。**
#
# **正本は `src/measure_window.py` に移しました**（2026-08-18）。ここに
# 置いてあったあいだ、門は**この道具の `--date` を渡した時にしか**効かず、
# `--hour` も `upload_only.py` も `reschedule.py` も素通りでした。
# ここは別名です。**窓を終わらせるときは `src/measure_window.py` を直すこと。**
#
# **`None` は「一覧をそのまま見ろ」の意味です**（2026-08-21 22:4x）。
# 前はここに `measure_window.WINDOW`（＝区間1本）を写していましたが、
# 窓が離れた2日（08/22 と 09/10）になったので、区間で写すと
# **間の18日まで止まります。** 検査が `M14_WINDOW = (日, 日)` と
# 差し替える手は、そのまま効きます（区間を渡せば区間で見ます）。
M14_WINDOW: tuple[str, str] | None = None

# 台本生成〜レンダリングの実測は5〜10分。倍を上限に取る（無限には待たない）。
BUILD_TIMEOUT = 1800
UPLOAD_TIMEOUT = 600

# **同時に走らせる本数の既定**（2026-08-15 に足した。理由は下）。
#
# 1本11分の内訳は、ほぼ全部が `claude -p`（`src/claude_cli.py`）の**待ち時間**です。
# 生成中の python は **CPU 2〜4%** しか使っていません（実測、`ps` で確認）。
# **CPU が空いているのに直列で待っていた**ので、ここは待ち時間を重ねるだけで縮みます。
#
# 4 にしていないのは、レンダリング（ffmpeg・open-jtalk）だけは CPU を使うからで、
# 4コアに対して 3 なら、山が重なっても 1コア残ります。**`--jobs` で変えられます。**
#
# ## **2026-08-29 23:xx に 3 → 5 へ上げた（実測。上の「1コア残す」は測って外れた）**
#
# 上の理由は**測っていない見立て**でした。`--report` を尺ごとに割って測ると
# （`_jobs_report`。混ぜた表は尺の差を jobs の差として出します）:
#
#     ショート  jobs 1/2/3/4/5/6/8 の 1時間あたり  17.5 / 30.3 / 36.9 / 53.4 / **86.5** / 53.0 / 59.4本
#               1本あたりは 3.4/3.0/3.4/3.4/2.9/3.1/3.8分 ＝ **jobs では動かない**
#     長尺      jobs 1/2/3/5/8 の 1時間あたり       6.4 /  7.9 /  9.0 / **16.3** / 17.4本
#               1本あたりは 8.7/10.5/9.8/11.7/11.8分 ＝ **1.35倍までしか太らない**
#
# **両方の尺で jobs 5 が jobs 3 の 1.8〜2.3倍**です（長尺 9.0 → 16.3・ショート 36.9 → 86.5）。
# 長尺の jobs 5 は 2026-08-29 の同じ回が2回 撃って測りました ——
# **6本 19.7分（12.2分/本）と 9本 37.6分（12.0分/本）**で、1本あたりが一致しています。
# 「4コアに 3 なら1コア残る」が効くなら**1本あたりが jobs で伸びるはず**で、伸びていません
# （生成の中身は `claude -p` の待ちで、CPU は 2〜4%）。
#
# **`--report` の「同時 5 が峰」に従っただけではありません** —— その行は
# 同じ日の朝まで**ショートだけの走り 2回**から出ており、
# **長尺に掛かる根拠は無い**と、同じ回が一度 書いています（`docs/JOURNAL.md`）。
# 上げたのは、**そのあと長尺の側でも2回 測ってから**です。
#
# **覆る条件**（どれか1つで戻す/動かす）:
#   - 長尺の1本あたりが **1.5倍** を超えて太ったら（いま 1.35倍）。
#     そこからは待ちではなく資源の取り合いなので、`--report` の
#     「1時間あたり」が伸びていても、きょうだいの回を巻き込みます
#   - きょうだいと同じコンテナで走る回が増えて、**同じ jobs で1本あたりが伸びたら**
#     （`ps` で他の `src.pipeline` を数えること。**機械は1台**です）
#   - `--report` の長尺の表で jobs 8 の走りが5回 たまり、そこが峰なら **8 へ**
DEFAULT_JOBS = 5

# 1つの `calc` から、1回の batch で取ってよい本数。
#
# **天井の話です**（2026-08-15 19:5x）。それまでは「calc が全部ちがう」＝実質 1 で、
# `calc` は11本しかないので **1回 11本が上限**でした。M14 の段はその先を狙う手なのに、
# 上限がどこにも書いてありません。**節（`calc_sections`）で見れば 54 件あります。**
# 2 にしているのは、同じ制度の本が並ぶと題も似て「繰り返しのように感じられる」側に
# 寄るからで、**根拠のあるぶんだけ（11 → 22）上げています。**
DEFAULT_PER_CALC = 2

#: **長尺の既定の予約時刻（JST）。**（2026-08-26 に足した）
#:
#: 既定は長らく **ショートと同じ 9時**でした。ところが 9時はショートで埋まっており、
#: `next_publish_at()` は**その時刻が空いている最初の日**まで後ろへ流します。
#: 実測（2026-08-26 07:0x・控え462本で解いた）:
#:
#:     09:00 JST → **2026-09-28**（32日先）  ← それまでの既定
#:     14:00 JST → 2026-08-28（2日後）
#:     18:00 JST → **2026-08-26（当日）**
#:     20:00 JST → **2026-08-26（当日）**
#:     22:00 JST → **2026-08-26（当日）**
#:
#: **同じ本が、時刻を変えるだけで 33日 早く出ます。作る手間は1秒も増えません。**
#: この回は既定の 9時 で4本 作ってしまい、4本とも 09/28〜10/01 に入りました
#: （`docs/JOURNAL.md` 2026-08-26 06:0x の第4節）。
#:
#: **長尺にだけ掛けます。** 長尺は `SHORTS_FEED` の枠を1つも使わないので、
#: `src/day_cap.py` の「1日10本／13:30まで」はショートの面の話であって、
#: 夜に置いても長尺の生死には掛かりません（`eta.py` の `density_surfaces`）。
#: **ショートを夜へ動かすのは別の話** —— あちらは上限の内側で争っているので、
#: ここを共通の既定にしないこと。
#:
#: **覆る条件**: 長尺の面でも時刻べつの生死が測れたら、その実測で置き直すこと。
#: いまは「**空いている**」以上の根拠はありません（生死は未測定）。
LONG_HOUR_JST = 20

#: **長尺を、同じ日に何本まで置くか**（2026-08-26・最適化の回に足した）。
#:
#: 上の `LONG_HOUR_JST` は「1本目がいつ出るか」を 33日 早めましたが、
#: **2本目から先は直していません。** `slots()` は `--date` が無いと
#: `[str(hour)] * count` を返し、`next_publish_at()` は
#: 「**その時刻で最初に空いている日**」を返します。つまり同じ時刻を N回 渡すと
#: **N日 に1本ずつ**ばらけます（`slots` の docstring 自身がそう書いています）。
#:
#: 実測（2026-08-26 16:0x・控え545本で数えた）:
#:
#:     長尺は 08/25 に **25本**、08/26 に 3本 作られている（`uploaded_at`）
#:     その 28本 の**予約日**は 08/26〜10/05 の **21日** に散っている ＝ **1.3本/日**
#:     いちばん後ろは **10/05**
#:
#: **作る側は既に1日25本 出せています。散らしているのは置き方だけです。**
#:
#: ## なぜ「散らさない」ほうが目標に近いか
#:
#: **4,000時間の門に入るのは長尺だけ**です（`src/levers.py` / `src/day_cap.py` /
#: `src/verify.py` が同じことを書いています）。ショートは `SHORTS_FEED` に
#: 99.9% を出していますが、**その門には1分も積みません**
#: （実測 2026-08-26・直近28日: `SHORTS_FEED` 64,283再生 / `WATCH` **67再生**）。
#: つまり**長尺の公開が後ろへ流れたぶん、開いている唯一の門は止まっています。**
#:
#: ## 上限を 5 にした根拠（**推測で上げないこと**）
#:
#: `src/day_cap.long_form()` の実測: `most=5` `alive=5` `collapsed=False`
#: —— **1日5本 出した日（08/21）は、5本とも再生が付きました。**
#: 天井はそこより上にあるはずですが、**5本を超えた日はまだ一度もありません**
#: （`measured=False` はそういう意味です。`src/levers.py` の
#: `_long_surface_measured` の註）。
#:
#: **だから 5 で止めます。** ここを 6以上 にすると、それは
#: 「**まだ測っていない天井を、黙って測りにいく**」ことになります。
#: 測るなら前提として登録して測ること（`config/hypotheses.yaml`）。
#:
#: **覆る条件**: `day_cap.long_form()` の `collapsed` が True になったら
#: （＝いちばん多く出した日に「出したのに付かない」本が出たら）、
#: **その日の本数より1つ下**へ落とすこと。逆に 5本/日 が続いても崩れないなら、
#: 前提を1件立てて 6本/日 を試すこと —— **黙って上げないこと。**
LONG_PER_DAY = 5

#: 長尺を同じ日に置くための時刻の輪。**`LONG_HOUR_JST` から後ろへ広げます。**
#: 時刻そのものに意味はありません（上の註「夜に置いても長尺の生死には掛かりません」）。
#: 要るのは「**その日に空いている別々の時刻が `LONG_PER_DAY` 個ある**」ことだけです。
#: 21時・22時を先に使うのは、ショートが 9〜19時 に固まっているためです。
LONG_HOURS_JST = (20, 21, 22, 19, 18)


def _section_key(topic: dict) -> tuple:
    """その本が**実際に見せる計算**を指す鍵。

    テーマは `calc`（モジュール）と `calc_sections`（その中のどの節を出すか）を
    持ちます。**画面に出る数字も棒の形も決めているのは節のほう**なので、
    「同じものが続くか」を見るときに見るべきなのはここです。

    節の指定が無い古いテーマは**モジュール全体**を指しているとみなします
    （どの節とも重なるので、その calc を1本で使い切る扱い）。
    """
    sections = tuple(sorted(topic.get("calc_sections") or ()))
    return (topic["calc"], sections)


def _posted_including_ledger() -> set[str]:
    """投稿済みのテーマIDを、**チャンネルと手元の控えの和**で返す（2026-08-16 07:5x）。

    ## 何が起きていたか（この回が2回踏み、2本ぶんの生成を捨てた）

    `pick` はチャンネルの説明欄からだけ「投稿済み」を復元していました。
    ところが復元の口は**両方とも欠けます** —— uploads プレイリストは予約中を落とし、
    `search` は**この日1日枠を使い切っています**（HTTP 429。`src/history.py` の実測）。
    欠けたぶんは**未投稿として選び直され**、11分かけて動画を作った後、
    投稿の直前の門（`src/dupes.blocking`）が止めます。

        s-furusato-5   作った → 却下（既にある b3ZewNvalXc と同じテーマID）
        s-shitsugyo-6  作った → 却下（既にある 8PMLfjjCe4w と同じテーマID）

    **この回に作った8本のうち2本、25%が捨てになりました。**
    **門は正しく働いています。**間違っていたのは、**門の位置ではなく選ぶ側**です。

    ## なぜ控えを混ぜてよいか（前は、意図してやっていませんでした）

    `src/dupes.ledger_rows` はこう書いています ——「どのテーマを次に作るか（`pick`）は
    **今もチャンネルから決めます**。動画を消したときにファイルが嘘になるからです」。

    **その心配は、いまのこちらには当たりません。** 動画を消す道が1本もないからです
    （`docs/FOR_OWNER.md` の済み3。`videos().delete` も、private に落とす
    `videos().update` も、環境の判定に弾かれます）。**控えは増えるだけで、
    嘘になる経路が存在しません。** 一方、混ぜない費用は**実測で生成の25%**です。

    **覆る条件**: 動画を消せるようになったら、ここは生存確認（`videos.list`）を
    通すか、チャンネルだけに戻すこと。**消した動画のテーマが永久に選べなくなります。**
    """
    posted = set(history.posted_topic_ids())
    from src import dupes

    extra = {r["topic"] for r in dupes.ledger_rows() if r.get("topic")} - posted
    if extra:
        # **黙って足さないこと。** 差は「口が欠けた量」そのもので、読める唯一の場所です。
        print(f"[pick] 控えにしか無い投稿済みテーマ {len(extra)}件を足しました"
              f"（口が欠けたぶん）: {', '.join(sorted(extra)[:6])}"
              f"{' …' if len(extra) > 6 else ''}")
    return posted | extra


def _drop_doomed(usable: list[dict], pool: list[dict],
                 posted: set[str] | None = None) -> list[dict]:
    """**投稿の門が必ず止めるテーマを、作る前に外す**（2026-08-17 に足した）。

    `s-menjo-hangaku-10200` は3回続けて申し送りに出ています ——
    `pick` が上位で返し、11分かけて作り、`upload_only.py` の
    `dupes.blocking()` が **毎回** 止める。**作った1本はそのたび捨てになります。**
    そのあいだ手順は `--topics` で手で避けていましたが、
    **手で避けている限り、避け忘れた回が必ず出ます。**

    ここで見るのは**控え（`data/` のローカル）だけ**で、API は1単位も使いません
    （`dupes.blocking(title, id, [], topics)` は videos が空でも控えを読みます）。
    見ているのは `title_seed` なので、門と同じではありません:

    - **同じテーマID**（`same-topic`）は、これで確実に当たります
    - **金額の入れ子**（`same-yen`）は、種に主役の数字が出ていれば当たります。
      台本が別の数字を主役にしたら当たりません。**そのぶんは門が受けます**

    逆に「門は通すのに、ここで落とす」ことはあり得ます（種にだけ数字がある場合）。
    **だから落としたものは必ず名前を出し**、`--topics` で明示すれば
    この関門は通りません（`explicit` は上で先に返っています）。
    """
    from src import dupes

    # **投稿済みのぶんも含めて、テーマ全部の calc を渡すこと。**
    # 控えの1行は「どの calc の本か」をテーマID経由でしか知りません。
    # 未投稿ぶんだけ渡すと、**既にある本の calc が空になり、`same-yen` が
    # 1組も当たりません**（最初にそう書いて、s-menjo-hangaku-10200 が素通りしました）。
    topics_calc = {t["id"]: t.get("calc", "") for t in pool}
    kept, dropped = [], []
    for t in usable:
        seed = t.get("title_seed") or ""
        hits = dupes.blocking(seed, t["id"], [], topics_calc) if seed else []
        if hits:
            dropped.append((t["id"], hits[0]["why"]))
        else:
            kept.append(t)
    # **`calc_sections` が1つも当たらないテーマも、必ず落ちます**（2026-08-30 に足した）。
    #     `script_writer` は当たる節が無いと `RuntimeError` を投げるので、
    #     **台本を書く前に、確実に、毎回**落ちます ——`dupes` の門と同じ
    #     「作る前に分かる死」です。ここで外さないと、その1本ぶんの
    #     生成（長尺で 13〜19分）がまるごと捨てになります。
    #
    #     **実測 2026-08-30**: `tokurou-danjo-48kagetsu-4800000` は、
    #     同じ日の別の回が `calc: saishushoku → tokurou` を直したとき
    #     **`calc_sections` を写し忘れて**おり、再就職手当の見出しを
    #     指したままでした。`--count 11 --long` がそれを 11本目に選んでいます。
    #     見つかったのは**全体スイートを別件で回したから**で、
    #     `pick()` からは見えていませんでした。
    #
    #     **`_section_numbers` が既に同じ表を読んでいます**（`_calc_sections_cached`）。
    #     追加の費用は、**`calc_sections` を持つテーマの calc だけ**・
    #     キャッシュ済みなら 0 です。
    #     **覆る条件**: `script_writer` が当たらないときに全節を渡す形に変わったら、
    #     これは死ではなくなるので、ここで落とさないこと。
    missing = []
    for t in list(kept):
        words = t.get("calc_sections") or []
        calc = t.get("calc") or ""
        if not words or not calc:
            continue
        try:
            heads = [h for h, _ in _calc_sections_cached(calc)]
        except SystemExit:
            continue                    # 表そのものが落ちるのは別の話（門が受ける）
        if not any(w in h for w in words for h in heads):
            kept.remove(t)
            missing.append((t["id"], calc, words, heads))
    for tid, calc, words, heads in missing:
        print(f"[pick] **`calc_sections` が `src.calc.{calc}` の見出しに"
              f"1つも当たりません。作る前に外します**: {tid} — {words}")
        print(f"       見出しは {heads}。"
              " **`calc:` を差し替えた回が `calc_sections` を写し忘れた形**が"
              "いちばん多い（`tests/test_calc_sections_still_hit.py`）。"
              " 直すのは `config/topics.yaml` の `calc_sections` のほうです"
              "（**短くて動かない語に**）。")
    # **公開済みの本と、図の棒がまるごと重なるテーマも落ちます**（2026-08-30 に足した）。
    #
    #     `_bars_clash` は長らく**この回に選んだ2本どうし**にしか当たっておらず
    #     （`pick()` の下の `chosen` の輪）、**公開済みとの突き合わせがありませんでした。**
    #     `script_writer` は `used_bars()` で公開済みの棒を読み、重なると
    #     **台本の時点で `RuntimeError`** を投げます ——`dupes` の門と同じ
    #     「作る前に分かる死」なのに、選ぶ側からは見えていませんでした。
    #
    #     **実測（2026-08-30 04:5x）**: `nenkin-minimax-69sai7kagetsu` は
    #     公開済みの `nenkin-saidai-torikoboshi-69-7` と、節に出る4桁以上の数が
    #     **17個ぜんぶ同じ**（Jaccard **1.00**）。**同じ節を指しています。**
    #     このテーマは 08/29 23:2x・08/30 03:33 の2回・04:2x と
    #     **4回 続けて同じ理由で落ち**、そのつど長尺の生成 13〜19分 を捨てています。
    #     `_drop_doomed` の `dupes.blocking` は種（`title_seed`）しか見ないので
    #     当たりません（この節の上の docstring）。
    #
    #     **`posted` を渡さない回では何もしません**（既定 `None`）——
    #     突き合わせる相手が無いだけで、門が緩むわけではありません。
    #
    #     ## **`_bars_clash` だけでは落としすぎます**（同じ回に測って narrowed）
    #
    #     最初は「同じ calc で `_bars_clash`」だけで書きました。**実測で
    #     未投稿 22件 のうち 11件（半分）が落ちます** ——
    #     そのうち **9件の相手は `s-` で始まるショート**で、
    #     **同じ節のショートが公開済みなだけ**でした。
    #     ショートは節から2〜4本しか棒を取らず、長尺は節ぜんぶを何枚もの図にするので、
    #     **形がちがえば同じ節でも図は割れます** ——実測: 直前の回は
    #     `s-` の相手が居る長尺を 11本 予約できています。
    #     **「同じ節」は死の条件ではありません。**
    #
    #     死ぬのは「**同じ形で・同じ節を・同じ言葉で指している**」＝
    #     **同じ本を二度 書いている**ときだけです。実測でこの3条件を全部 満たすのは
    #     22件中 **1件**（`nenkin-minimax-69sai7kagetsu` ↔
    #     `nenkin-saidai-torikoboshi-69-7`。どちらも長尺・`calc_sections` は
    #     片方がもう片方を丸ごと含む・題も「いちばん損の小さい開始は69歳7か月」で同じ）。
    #
    #     **覆る条件**: `s-` の相手しか居ない長尺が、この理由で実際に
    #     `RuntimeError` になったら、形の条件を外すこと（`data/batch_runs.jsonl`
    #     に理由ごと残ります）。逆に、この3条件を満たしていない組が落ち続けたら、
    #     見ているのは節ではなく**題の主張**なので、`title_seed` の側で測ること。
    #     `used_bars()` が公開済みを読むのをやめたら（`build/` だけに戻ったら）、
    #     これは死ではなくなるので丸ごと外すこと。
    #     検査は `tests/test_drop_doomed_published_bars.py`。
    if posted:
        by_calc: dict[str, list[dict]] = {}
        for t in pool:
            if t["id"] in posted and t.get("calc"):
                by_calc.setdefault(t["calc"], []).append(t)
        keep2 = []
        for t in kept:
            hit = next((p for p in by_calc.get(t.get("calc") or "", [])
                        if p["id"] != t["id"]
                        and _same_form(t, p) and _same_section_words(t, p)
                        and _bars_clash(t, p)), None)
            if hit is None:
                keep2.append(t)
            else:
                dropped.append((t["id"],
                                f"公開済みの {hit['id']} と同じ形・同じ節・同じ言葉"
                                f"（`script_writer.used_bars` が台本の時点で止めます）"))
        kept = keep2
    for tid, why in dropped:
        print(f"[pick] **門が必ず止めるので外します**: {tid} — {why}")
    return kept


#: 着地点のまわり何日ぶんの calc を避けるか（**長尺だけ**）。
#: 新しい本は「いちばん早い空き日」に入るので、そこから数日ぶんを見ます。
QUEUE_TAIL_DAYS = 7


#: 節の本文から数を拾う型。**4桁以上の整数だけ**を見ます。
#: 3桁以下（年数・パーセント・段の番号）は、どの表にも出てくるので当たり前に被ります。
_BIG_NUMBER = re.compile(r"\d[\d,]{3,}")


@functools.lru_cache(maxsize=None)
def _calc_sections_cached(calc: str) -> tuple[tuple[str, str], ...]:
    """`src.calc.<calc>` を1回だけ走らせて `(見出し, 本文)` を返す。

    **`topic_forge.sections()` と同じものです**（あちらが正本）。
    ここで呼び直すのは、`pick()` が `topic_forge` を import すると
    `config.load_topics()` まで連れてくるためです。
    """
    import topic_forge                                   # noqa: PLC0415
    return tuple(topic_forge.sections(calc).items())


def _section_numbers(topic: dict) -> set[str]:
    """そのテーマの節に出てくる**4桁以上の数**の集合。

    **`calc_sections` は部分一致**です（`topic_forge.sections_for` の docstring）。
    読めない calc は空集合を返します —— **この門で投稿を止めないため。**
    """
    calc = topic.get("calc")
    if not calc:
        return set()
    try:
        secs = dict(_calc_sections_cached(calc))
    except (Exception, SystemExit):
        # **`SystemExit` も受けること。** `topic_forge.sections()` は
        # 表が落ちたときに `raise SystemExit` します（あちらは道具の入口なので正しい）。
        # **`except Exception` では受からず、pick ごと落ちます**（2026-08-29 に踏んだ）。
        return set()                     # 表が落ちても pick は止めない
    words = topic.get("calc_sections") or []
    body = "\n".join(b for h, b in secs.items()
                     if not words or any(w in h for w in words))
    return {m.group(0).replace(",", "") for m in _BIG_NUMBER.finditer(body)}


#: 節の数がここまで重なったら「同じ表を別の見出しで出している」と見る。
#: **実測で決めた値です**（下の `_bars_clash` の表）。通った 23組 の最大は **0.31**、
#: 落ちた1組は **0.67**。あいだを取って 0.45 に置いてあります。
BARS_CLASH_JACCARD = 0.45


def _same_form(a: dict, b: dict) -> bool:
    """**同じ形か**（どちらもショート、またはどちらも長尺）。

    形は `s-` で始まるかどうかで決まります（`topic_forge` の `LONG_ID_RE` / `ID_RE`）。
    **同じ節でも、形がちがえば図は割れます** —— ショートは節から2〜4本しか棒を取らず、
    長尺は節ぜんぶを何枚もの図にするからです（`_drop_doomed` の実測）。
    """
    return a["id"].startswith("s-") == b["id"].startswith("s-")


def _same_section_words(a: dict, b: dict) -> bool:
    """**同じ節を、同じ言葉で指しているか**（片方がもう片方を丸ごと含む）。

    `calc_sections` は部分一致なので、**別の言葉で同じ節に当たる**ことがあります。
    そこまで同じなら「同じ本を二度 書いている」と見ます。
    どちらかが空なら **False**（判定材料が無いので落としません）。
    """
    aw = " / ".join(a.get("calc_sections") or [])
    bw = " / ".join(b.get("calc_sections") or [])
    if not aw or not bw:
        return False
    return aw in bw or bw in aw


def _bars_clash(a: dict, b: dict) -> bool:
    """**この2本は、同じ図を出すか。**（`src/verify.py` の門を、選ぶ前に当てる）

    ## なぜ要るのか（2026-08-29 に踏んだ。**2本 作って 0本**）

    `--per-calc 2` は「同じ制度が並びすぎないように」の上限で、
    **選んだ2本が同じ数を出すかどうかを1文字も見ていません。**
    `used_sections` は節が違うことしか見ず、**節が違っても数は被ります。**

    実測: `shogaku-murishi-sa-1458282` と `shogaku-years-total-repay` は
    別の節ですが、どちらも **4,474,969円 と 8,949,938円**（3年と6年の返還総額）を
    出します。並べて作った結果:

        shogaku-years-total-repay    RuntimeError: 台本の時点で過去の図と重なっています
        shogaku-murishi-sa-1458282   VerificationError: 投稿前の検査に落ちました

    **2本とも落ちました。** しかも `--jobs 2` で**同時に**作っているので、
    `script_writer.used_bars()` が読む `build/*/script.json` は
    **相手の台本がまだ存在しません** —— 書き手には避けようがありませんでした。
    そして `--no-retry` を付けていない回は、**もう一度 同じ2本を作り直します。**
    落ち方は決まっているので、**作り直しも必ず落ちます**（この回で実測 約13分 × 2 を捨てた）。

    ## 何を見ているか —— **共通の本数ではなく、重なりの割合**

    節の本文に出る**4桁以上の数**の集合を2本ぶん取り、
    **Jaccard**（共通 ÷ 合併）が `BARS_CLASH_JACCARD` 以上なら「当たる」と言います。

    **最初は「共通が `verify.REPEAT_BARS`（2）以上」で書いて、外しました。**
    同じ calc の節は、入力の定数（上限額・年収の刻み）を当たり前に共有するので、
    **実際に通って予約に入っている 23組 のうち 15組**がその線に当たります。
    予約の実物で測り直したのが、この表です（同じ日・同じ calc・別のテーマ）:

        実際に通った 23組    Jaccard の最大 **0.31**（`inshi` の2本・共通11/合併36）
                             共通の本数だけ見ると最大 **11本**（＝2本の線は使えない）
                             `mishikyu` の1組は**片側を全部 含んで**いるのに通っている
                             （共通2 / 片方が2個しか持たない ＝ 包含率 1.00・Jaccard 0.18）
        この回に落ちた1組    Jaccard **0.67**（共通12 / 18と12 ＝ **片方は丸ごと部分集合**）

    **0.31 と 0.67 のあいだ**に線を引いています。
    包含率（共通 ÷ 小さいほう）で引かなかったのは、`mishikyu` の組が
    **1.00 なのに通っている**からです —— 数を2つしか持たない節は、
    包含率では必ず 1.00 になります。

    **これは近似です**（`verify` が見るのは台本が書いた棒の `display` で、
    こちらは表の生の数）。**表に無い数を棒にすることはできない**ので
    （`_checks.numbers_backed`）、見落とす向きにしか外れません。

    **覆る条件**: この線で落ちた組が実際には通ったと分かったら、上げること。
    逆に `verify` の「図の棒が … と N本 共通」が**同じ回の相手**を名指しして
    落ちたら、その組の Jaccard を測って下げること。
    **どちらも `data/batch_runs.jsonl` に理由ごと残ります。**
    検査は `tests/test_batch_bars_clash.py`。
    """
    if a.get("calc") != b.get("calc"):
        return False                     # 別の calc は `_queue_tail_calcs` の担当
    na, nb = _section_numbers(a), _section_numbers(b)
    if not na or not nb:
        return False                     # 読めなかった回は止めない
    return len(na & nb) / len(na | nb) >= BARS_CLASH_JACCARD


def _queue_tail_calcs(pool: list[dict], days: int = QUEUE_TAIL_DAYS,
                      land: date | None = None) -> set[str]:
    """**これから公開される長尺の calc** を返す（**API を1単位も使いません**）。

    ## なぜ要るのか（2026-08-25 に踏んだ）

    `--per-calc` は **1回の batch の中でしか効きません。** 2回続けて走らせると、
    同じ calc が何本でも**連続して**予約に入ります。実際にそうなりました:

        08/28 tokurou / 08/29 tokurou / 08/30 yukyu / 08/30 furusato
        08/31 tokurou ← 2回目の batch / 09/01 tokurou ← 同

    **次の長尺6本のうち4本が同じ計算で、題名の頭まで同一**でした。これは
    `CLAUDE.md` が引いているポリシー本文そのもの ——「**同じチャンネルの動画を
    続けて数本視聴した後、繰り返しのように感じられる可能性のあるコンテンツ**」は
    **収益化の対象外**。収益化されなければ収入はゼロなので、
    **在庫を厚くした効果を自分で打ち消します。**

    **見るのは「末尾」ではありません**（一度そう書いて外しました）。
    `upload_only.py` は**いちばん早い空き日**を取るので、新しい本は列の先頭側に
    入ります。実測: 08/30 まで埋まっている状態で撃ったら 08/31・09/01 に着きました。
    **末尾（09/26）を避けても、着地点の隣は避けられません。**
    だから**いまから `days` 日ぶん**を見ます。

    **長尺だけを見ます。** ショートは1日10本入るので、その calc まで避けると
    候補が枯れます（実測: 全490件のうち、ショート込みで避けると大半が落ちる）。
    そして踏んだ事故も長尺でした ——**題名の頭が同一の長尺が4本続く**形です。

    ## **窓は「今日から」ではなく「着地する日のまわり」です**（2026-08-29 に踏んだ）

    ここは長らく `now` 〜 `now + days` の**固定窓**でした。上の docstring が
    「**着地点の隣は避けられない**」と正しく言っているのに、
    **その着地点が今日から7日以内だという前提が、どこにも確かめられていません。**

    実測 2026-08-29 —— **両方の道で外れます**:

        `--date` を渡した回   釘づけした日（この回は 09/14〜09/16）に着く。
                            窓は 08/29〜09/05 を見ていた ＝ **完全に外**
        既定（`live_ring`）   `queue_lag.py` の実測で着地は **8〜11日後**。
                            窓は 7日 なので、**これも外**

    その結果この回は、**09/12〜09/16 の長尺 6本 が bunkatsu 3・mishikyu 3** に
    なりました。`CLAUDE.md` が引いているポリシー本文そのもの ——
    「**同じチャンネルの動画を続けて数本視聴した後、繰り返しのように
    感じられる可能性のあるコンテンツ**」は**収益化の対象外**です。
    **この関数は、まさにそれを止めるために書かれています。**

    だから `land`（着地する日）を受け取り、**その前後 `days` 日**を見ます。
    渡されなければ今日を使います（＝ 前と同じ）。

    **覆る条件**: 未投稿テーマの calc が偏っていて、避けると毎回 `pick` が
    空になるようなら、`QUEUE_TAIL_DAYS` を下げること
    （下の呼び出し側が、空になった回は避けずに通します）。
    **検査は `tests/test_queue_tail_land.py`。**
    """
    calc_of = {t["id"]: (t.get("calc") or "") for t in pool}
    now = datetime.now(timezone.utc)
    centre = now if land is None else datetime.combine(
        land, dtime(0, 0), tzinfo=timezone.utc)
    # **前へも見ます。** 釘づけした日の**手前**に同じ calc が並んでいても、
    #     見る側には「続けて数本」に見えます（順番は公開日で決まる）。
    since = max(now, centre - timedelta(days=days)) if land is not None else now
    until = (centre + timedelta(days=days)).isoformat()
    now_s = since.isoformat()
    calcs = set()
    for row in dupes.ledger_rows():
        at = row.get("at") or ""
        if not (now_s < at <= until) or not row.get("topic"):
            continue
        if "#Shorts" in (row.get("title") or ""):
            continue
        calcs.add(calc_of.get(row["topic"], ""))
    return calcs - {""}


def _drop_queue_tail_calcs(usable: list[dict], pool: list[dict],
                           land: date | None = None) -> list[dict]:
    """末尾の calc を落とす。**全部落ちる回は落とさない**（出すほうが先）。

    `land` は**その回の本が着地する日**（`--date` か `live_plan()` の先頭）。
    渡さないと今日を中心に見ます —— **それでは着地点の隣を避けられません**
    （`_queue_tail_calcs` の「窓は着地する日のまわり」）。
    """
    try:
        tail = _queue_tail_calcs(pool, land=land)
    except Exception as exc:                                  # noqa: BLE001
        print(f"[pick] これからの予約を読めませんでした（避けずに続けます）: {exc}")
        return usable
    if not tail:
        return usable
    kept = [t for t in usable if t.get("calc") not in tail]
    if not kept:
        print(f"[pick] これから7日ぶんの長尺の calc {sorted(tail)} を避けると候補が0件になります"
              " —— **避けずに続けます**（出さないより、隣接するほうがまだ良い）。"
              " 偏りが続くなら QUEUE_TAIL_DAYS を下げること。")
        return usable
    if len(kept) < len(usable):
        # **「これから7日ぶん」と書かないこと**（2026-08-29 に直した）。
        #     窓は着地点のまわりで、`land` を渡さない回だけ今日が中心です。
        #     字面が固定だと、**避けた先が読み手に見えません** ——
        #     この回は「15件 避けました」と読んで、避けるべき2件が
        #     窓の外にあることに気づけませんでした。
        where = (f"着地（{land.isoformat()}）の前後 {QUEUE_TAIL_DAYS}日"
                 if land is not None else f"今日から {QUEUE_TAIL_DAYS}日")
        print(f"[pick] {where} の長尺に出ている calc を避けました: {sorted(tail)}"
              f"（候補 {len(usable)} → {len(kept)}件）")
    return kept


def _hoist_floor_topics(usable: list[dict]) -> list[dict]:
    """**開いた前提の床が待っている題を、並びの先頭へ**（順番だけを変えます）。

    どの題が待たれているかは `src/floor_topics.starved()` が返します
    （API 0単位・`config/hypotheses.yaml` と `data/uploaded.jsonl` と
    `config/topics.yaml` だけを読む）。**なぜ要るかの実測は、あちらの
    docstring** —— 要点だけ言うと、実績の順は「どれがよく回るか」であって
    「どれを作らないと前提が閉じないか」ではありません。

    **落とすものはありません。** 持ち上げるだけなので、床の題が尽きても
    残りはそのままの順で残り、**投稿が止まることはありません**。

    **`per_calc` は迂回しません。** 1回に同じ族から取れる本数は変わらず、
    先頭に来ても `_sweep()` が同じように切ります（同じ制度の本が1日に
    何本も並ぶのは、収益化の側の事実。`CLAUDE.md`）。だから
    **床 6本 は「1回で6本」ではなく「3回で6本」**として埋まります。

    持ち上げる本数は `short`（床までの残り）で切ります。**切らないと、
    床が埋まったあとも同じ族が先頭に居座り**、実績の順が死にます。

    覆る条件: 床のある接頭辞が同時に3つ以上 開いたら、先頭は取り合いに
    なります（`floor_topics` の docstring の3つ目）。
    `tests/test_floor_topics.py` の 3番目が、その形を見ています。
    """
    try:
        from src import floor_topics
        rows = floor_topics.starved()
    except Exception as exc:                                   # noqa: BLE001
        print(f"[pick] 台帳の床が読めませんでした（実績の順だけで並べます）: {exc}")
        return usable
    if not rows:
        return usable

    front: list[dict] = []
    taken: set[str] = set()
    for r in rows:
        hit = [t for t in usable
               if str(t["id"]).startswith(r["prefix"]) and t["id"] not in taken]
        if not hit:
            continue
        for t in hit[:r["short"]]:
            front.append(t)
            taken.add(t["id"])
        print(f"[pick] {floor_topics.lines([r])[0]}"
              f"　→ **この回の並びで {min(len(hit), r['short'])}件 を先頭へ**",
              flush=True)
    if not front:
        return usable
    return front + [t for t in usable if t["id"] not in taken]


def pick(count: int, explicit: list[str], per_calc: int = DEFAULT_PER_CALC,
         long_form: bool = False, land: date | None = None) -> list[dict]:
    """未投稿・`calc` あり・**計算の節が全部ちがう** テーマを score の高い順に取る。

    ## ここが 2026-08-15 19:5x に変わりました（天井の測り違い）

    それまでの規則は「**calc が全部ちがう**」でした。`calc` は11本しかないので、
    **1回の batch は最大11本**です。M14（本数の段）は 8 → その先を狙う手なのに、
    **11 で頭打ちになることが、どこにも書いてありませんでした。**

    実測（この回）: 未投稿テーマ7件のうち calc は5種類で、`pick(8)` は
    **5件しか返しませんでした。** 前の回が次の宿題に置いた「`--jobs` の上限を測る」は、
    **`pick` が5件しか返さない状態では意味がありません**（同時に作る相手がいない）。
    **律速は並列度ではなく、取れるテーマの数のほうでした。**

    節で見ると 54 件あります。**節がちがえば、前提も数字も棒の形もちがう** ——
    `calc_sections` は「モジュールのどの節を出すか」を指していて、
    画面に出るものを決めているのはこちらです。つまり
    **「同じ計算を2回出さない」を守ったまま、天井は 11 から上げられます。**

    ただし**節だけにはしません。** 同じ制度の本が1日に何本も並ぶと、
    題も似るので「繰り返しのように感じられる」側に寄ります（収益化の条件）。
    だから **1つの calc から取るのは既定で2本まで**（`per_calc`）。
    天井は 11 → 22 で、**根拠のあるぶんだけ上げています。**

    **覆る条件**: 同じ calc の2本を並べた日の engaged 比率の中央値が、
    全部ちがう calc の日を下回ったら、`per_calc` を 1 に戻すこと。

    ## `long_form` は 2026-08-26 に足しました（**`--long` が選ぶ側に効いていなかった**）

    `--long` は長らく **`build_one(topic, long_form)` にしか渡っていません**でした。
    つまり**作り方だけが長尺になり、題は在庫の上から取っていた**ということです。
    `scripts/topic_forge.py` は `--long` を付けた回だけ `s-` で始まらない id を書き、
    **ショート向けの題は `s-` で始まります**（`LONG_ID_RE` / `ID_RE`）。
    在庫はショートが圧倒的多数（実測 08/26: 未投稿34件のうち長尺向けは7件）なので、
    **`--long` を付けても、ほぼ確実にショート向けの題で長尺を作ります。**

    実測（2026-08-26 01:5x）: `--count 1 --long` が
    `s-zangyo-nenkan-kyujitsu-tanka` を取り、5.4分の長尺として投稿しました。
    **落ちも警告も出ません** —— ショート向けに書かれた細い表が、
    長尺の尺に引き伸ばされるだけなので、**外からは成功に見えます。**

    **在庫が尽きているときは止めません**（投稿が途切れるのが最大の損失）。
    その回は理由を印字して、ショート向けの題で作ります。
    """
    pool = config.load_topics()["topics"]
    by_id = {t["id"]: t for t in pool}

    if explicit:
        missing = [i for i in explicit if i not in by_id]
        if missing:
            raise SystemExit(f"config/topics.yaml に無いテーマ: {', '.join(missing)}")
        chosen = [by_id[i] for i in explicit]
        no_calc = [t["id"] for t in chosen if not t.get("calc")]
        if no_calc:
            raise SystemExit(
                f"calc の無いテーマは台本生成が止まります: {', '.join(no_calc)}"
            )
        return chosen

    posted = _posted_including_ledger()
    # **作ってあるが未投稿の本も「使った」に数える**（2026-08-23 に踏んで足した）。
    # `--skip-upload` の本は投稿の記録に入らないので、次の `pick()` が**同じテーマを
    # 選び直し、`build/` を上書き**します。実測: 対照群8本を作った直後に
    # 動きあり8本を作ったら **8/8 が同じテーマ**で、ディスクは動きあり・
    # 記録の1件目は動きなし、という食い違いになりました（A/B の群が静かに嘘になる）。
    built = {d.name for d in (ROOT / "build").iterdir() if d.is_dir()} \
        if (ROOT / "build").is_dir() else set()
    usable = [t for t in pool if t["id"] not in posted and t["id"] not in built
              and t.get("calc")]
    usable = _drop_doomed(usable, pool, posted)
    usable = _drop_queue_tail_calcs(usable, pool, land=land)

    # **長尺は、長尺向けに書かれた題からしか取らない**（上の docstring）。
    if long_form:
        long_usable = [t for t in usable if not t["id"].startswith("s-")]
        if long_usable:
            usable = long_usable
        else:
            print("[pick] 長尺向けのテーマ（`s-` で始まらない id）が在庫にありません。"
                  "**ショート向けの題で長尺を作ります**（投稿を止めないため）。"
                  "`python scripts/topic_forge.py --count N --long` で足すこと")
            # **ただし、開いた前提が「ショートとして」数えている題は外します**
            # （2026-08-29 に踏んで足した）。
            #
            # `scripts/family_gap.py` の群分けは **id の `s-` だけ**を見ます
            # （`is_short = topic.startswith("s-")`）—— **尺は見ていません。**
            # だから `s-ribo-…` を長尺として出すと、**5分の本が
            # 「ショート」の群に入って**、その前提の判定がそこで壊れます。
            # 実測 2026-08-29 11:0x: 長尺の在庫が尽きたこの回で、
            # `_hoist_floor_topics` が `族を外へ-ribo8本`（床 8本・期限 09-19・
            # 腕 rpm）の `s-ribo-` を先頭へ上げ、**その2本を長尺として作りはじめました。**
            # `needs` の数え方（`startswith('s-ribo-')`）も尺を見ないので、
            # **床は「埋まった」と出て、群だけが汚れます。**
            #
            # **投稿は止めません** —— 外したあとに何も残らない回は、
            # 今までどおり在庫の上から取ります（在庫切れで止めるほうが高い）。
            try:
                from src import floor_topics
                claimed = tuple(r["prefix"] for r in floor_topics.starved())
            except Exception as exc:                          # noqa: BLE001
                print(f"[pick] 台帳の床が読めませんでした（そのまま続けます）: {exc}")
                claimed = ()
            if claimed:
                keep = [t for t in usable
                        if not str(t["id"]).startswith(claimed)]
                dropped = len(usable) - len(keep)
                if dropped and keep:
                    print(f"[pick] うち {dropped}件 は**開いた前提がショートとして"
                          f"数えている題**なので外しました（{', '.join(claimed)}）"
                          "　—— 長尺として出すと `family_gap.py` の群が汚れます")
                    usable = keep
                elif dropped:
                    print(f"[pick] 残る {dropped}件 は全部**開いた前提が"
                          "ショートとして数えている題**です（"
                          f"{', '.join(claimed)}）。**投稿を止めないため通します** ——"
                          "その前提の群は、この回のぶんだけ汚れます")

    # **順番は実績で決める**（2026-08-16 に測って変えた。それまでは手書きの
    # `score` だけで、実績を1つも見ていませんでした ＝ 91件中64件が `1.0`）。
    # 族ごとの engaged 比率は実物で **4倍ちがい**、登録も上位の族からしか
    # 入っていません（`src/family_perf.py` に測り方と割り引き方）。
    # 手書きの見立ては捨てず、**掛ける**（実績は事前分布、`score` は狙い）。
    # 測っていない族は全体平均になるので、**真ん中の順位から試されます。**
    from src import family_perf

    try:
        family_score = family_perf.scorer()
    except Exception as exc:              # 実績が読めなくても止めない
        print(f"[pick] 実績が読めませんでした（手書きの score だけで並べます）: {exc}")
        family_score = lambda calc: 1.0   # noqa: E731
    usable.sort(key=lambda t: -float(t.get("score", 1.0)) * family_score(t["calc"]))

    # **台帳の床が待っている題を、先頭へ持ち上げる**（2026-08-29・最適化の回）。
    #     実績の順（`score × family_perf`）は「どれがよく回るか」の順で、
    #     **「どれを作らないと前提が閉じないか」を1文字も見ていません。**
    #     実測: `s-ribo-` の床 8本 に対し、題は 8件 在るのに **2件しか
    #     作られておらず**、`ribo` は実績の無い族なので順位は真ん中でした。
    #     そのあいだ `deadline_check.py` は「この回は何もしないのが正解です」。
    #     **なぜそれが高くつくかは `src/floor_topics.py` の docstring。**
    usable = _hoist_floor_topics(usable)

    if per_calc < 1:
        raise SystemExit(f"--per-calc は1以上です: {per_calc}")

    # **節を指定したテーマが1つでもある calc では、節の指定が無いテーマを取りません**
    # （2026-08-18 に測って足した）。`calc_sections` の無いテーマは
    # **表を書くと決めた回の「題材」**で、`calc:` を繋いだ時点から
    # 「モジュール全体を1本にする」テーマとして `usable` に残ります。
    # 下の `whole_module` は「全体の1本」と「節の1本」が並ばないようにする規則ですが、
    # **どちらが勝つかは並び順まかせ**で、実測では**題材のほうが勝っていました。**
    #
    # 実測（2026-08-18・`per_calc=2`）: 直近8回で書いた5本の表
    # （`shokibo` `invoice` `rousai` `tsukin` `seimeihoken`）が、**どれも1本ずつ**しか
    # 出していません。節は6件ずつあるのに、**題材の1件が全部を飲み込んでいた**からです。
    # **`pick` の返り 14本 → 19本**（5族 × 1本）。表を1本書いても
    # 「桁が変わらない」ように見えていた原因の一つが、ここでした。
    #
    # **題材のほうを捨てるのが正しい向き**です —— 節を指定しないテーマは
    # 表ぜんぶを1本に詰める形になり、「テンプレートで大量生産された」と
    # 判定される側に寄ります（収益化の条件。`CLAUDE.md`）。
    has_sections = {t["calc"] for t in usable if t.get("calc_sections")}

    chosen: list[dict] = []
    used_sections: set[tuple] = set()
    per_calc_taken: dict[str, int] = {}
    whole_module: set[str] = set()   # 節の指定が無いテーマを取った calc

    # **族を空にする深い題は、後回しにする**（2026-08-26 12:0x に測って足した）。
    # 詳しくは `_deep_left()` の docstring。ショートの回だけに効きます。
    deep_left = _deep_left(pool, posted, built) if not long_form else {}

    def _sweep(protect: bool) -> None:
        """`usable` を1周して `chosen` を埋める。

        `protect=True` の周は、**その族の深い題を使い切る一手を取りません。**
        埋まらなければ `protect=False` でもう1周するので、
        **在庫が尽きているときに投稿が止まることはありません**（上の docstring）。
        """
        for topic in usable:
            if len(chosen) >= count:
                return
            calc = topic["calc"]
            key = _section_key(topic)
            sections = key[1]

            if not sections and calc in has_sections:
                continue                  # 題材のテーマは、節があるあいだ取らない
            if key in used_sections:
                continue                  # **同じ計算は2回出さない**
            if per_calc_taken.get(calc, 0) >= per_calc:
                continue                  # 同じ制度が並びすぎないように
            if calc in whole_module:
                continue                  # モジュール全体のテーマと必ず重なる
            if not sections and per_calc_taken.get(calc, 0):
                continue                  # 逆向きも同じ

            deep = not topic["id"].startswith("s-")
            if protect and deep and deep_left.get(calc, 0) <= 1:
                continue                  # **この一手で族が消える。後回し**

            # **同じ calc の2本目は、節の数が被っていないことを先に見る**
            # （2026-08-29 に踏んだ。**0/2 になった**）。理由は `_bars_clash`。
            clash = next((t for t in chosen if _bars_clash(t, topic)), None)
            if clash is not None:
                print(f"[pick] **同じ表を別の見出しで出すので外します**: {topic['id']} —— "
                      f"この回に取った `{clash['id']}` と節の数が"
                      f" {BARS_CLASH_JACCARD:.0%} 以上 重なります"
                      f"（`src/verify.py` の『図の棒が … と N本 共通』に当たる側）",
                      flush=True)
                continue

            chosen.append(topic)
            used_sections.add(key)
            per_calc_taken[calc] = per_calc_taken.get(calc, 0) + 1
            if deep and calc in deep_left:
                deep_left[calc] -= 1
            if not sections:
                whole_module.add(calc)

    if not long_form:
        _sweep(protect=True)
    if len(chosen) < count:
        _sweep(protect=False)

    if len(chosen) < count:
        print(
            f"[batch] **計算の節がちがう未投稿テーマが {len(chosen)} 件しかありません**"
            f"（要求 {count} 件 / 1つの calc から最大 {per_calc} 本）。"
            f"在庫のほうが先に尽きています。",
            flush=True,
        )
    if not long_form:
        _warn_long_stock_eaten(chosen, pool, posted, built)
    return chosen


def _deep_used(posted: set[str], built: set[str]) -> set[str]:
    """もう使った題（投稿済み・控えに在る・`build/` に在る）を1つにまとめる。

    `_warn_long_stock_eaten` が同じ数え方をしています。**片方だけ直すと、
    値札と実際の選び方がずれます**ので、両方ここから引くこと。
    """
    used = set(posted) | set(built)
    try:
        from src import dupes as _dupes
        used |= {r["topic"] for r in _dupes.ledger_rows() if r.get("topic")}
    except Exception:                                          # noqa: BLE001
        pass
    return used


def _deep_left(pool: list[dict], posted: set[str], built: set[str]) -> dict[str, int]:
    """族べつに、**まだ使っていない深い題（`s-` で始まらない）が何件 残っているか**。

    ## なぜ要るか（2026-08-26 12:0x に測って足した）

    `_warn_long_stock_eaten` は 09:5x に **値札を出すところまで**やりました ——
    「この回のショート N件 は長尺の在庫です。族の最後の1件があるので、
    7日ぶんの長尺の上限が M本 落ちます」。**止めない**と書いてあり、
    「どちらが得かはその回の判断」で終わっていました。

    **その判断は、たいてい要りませんでした。** 実測（この関数を書いた回）:

        使っていない深い題      **31件 / 族 12**
        族の残りが1件だけ       **2族**（`jutaku` `nenkin`）
        族を空にせず使える題    **19件**

    つまり **19件は、長尺の上限を1本も落とさずにショートへ回せます。**
    ところが同じ回の `pick(60)` は深い題を9件 取り、そのうち
    **5族ぶんを空にして上限を 10本 落としていました。**
    落ちた族は `kouki` `shougai` `izoku` `kakyu`（**残り2件の族**）と
    `jutaku` `nenkin`（残り1件）—— `per_calc=2` が
    **残り2件の族をちょうど飲み干す**ためです。

    **並び順が実績だけで決まっていて、「この一手で族が消えるか」を
    誰も見ていなかった**、というだけの話です。値札は出ていましたが、
    値札は**選んだ後**に出ます。

    だから `pick()` は、ショートの回に**2周**します ——
    1周目は族を空にする手を取らず、埋まらなければ2周目で取る。
    **在庫が尽きているときに投稿を止めないため**（`pick` の docstring）。

    ## これは「深い題をショートに出さない」ではありません

    `deep_shorts` の前提（腕 `rpm`・期限 09/03）は、まさに
    **深い題のショートが 16本 溜まるのを待っています**（08/26 時点で 9本、
    08/20 から7日 止まっている）。止めたらその前提は永久に判定できません。
    ここでやっているのは **同じ 7本 を、族を殺さない側から取る**ことだけです。

    **覆る条件**: 族を空にしない深い題が尽きたとき（実測 19件）。
    そのときは2周目が働くので、動きは 08/26 以前と同じに戻ります。
    `python scripts/status.py` の「長尺向けのテーマ … / 族 N」が
    **ショートの回のあとで減っていたら、この守りが効いていません。**
    """
    used = _deep_used(posted, built)
    left: dict[str, int] = {}
    for topic in pool:
        calc = topic.get("calc")
        if not calc or topic["id"].startswith("s-") or topic["id"] in used:
            continue
        left[calc] = left.get(calc, 0) + 1
    return left


def _warn_long_stock_eaten(chosen: list[dict], pool: list[dict],
                           posted: set[str], built: set[str] | None = None) -> None:
    """**ショートの回が、長尺の在庫を黙って食っていないか**（2026-08-26 09:5x に踏んだ）。

    `--long` を付けない `pick` は `s-` で始まらない題も候補に残します
    （**そうでないと「深い題をショートで出す」前提が永久に溜まりません**）。
    ですが `s-` で始まらない題は、そのまま**長尺の在庫**でもあります ——
    `topic_forge.print_long_stock()` が数えているのはちょうどそれです。

    **ショートで1本 使うと、その族の長尺の在庫が1件 減ります。**
    族の最後の1件を使うと、**7日ぶんの長尺の上限が丸ごと2本 落ちます**
    （`--per-calc` が族あたり2本なので、族が1つ消えるのと同じ）。

    実測（この関数を書いた回）: `topic_forge --count 2 --long` で
    `jutaku` の族を作って上限を 22本 → 24本 にした直後、
    **同じ回の `batch_build --count 2`（`--long` なし）が
    `jutaku-hanbun-jougen` を取りました** —— 残り1件だったので、
    そのまま **24本 → 22本** に戻ります。**どこにも印字されません。**

    **止めません。** どちらの使い道にも理由があり
    （長尺は門2a、深い題ショートは `deep_shorts` の前提 期限 09/03）、
    **どちらが得かはその回の判断**です。**見えないことだけが問題**なので、
    ここでは**値札を出すだけ**にします。

    **覆る条件**: `deep_shorts` の前提が閉じたら、
    「非 `s-` の題をショートに回す」理由が1つ減ります。そのときは
    **止める側に倒してよい**（`usable` を `s-` だけに絞る）。
    """
    deep = [t for t in chosen if not t["id"].startswith("s-")]
    if not deep:
        return
    # **1族から何本かは、数えている側から引くこと**（写すと片方が古びます）
    try:
        import topic_forge
        per_calc_long = topic_forge.PER_CALC_DEFAULT
    except Exception:                                          # noqa: BLE001
        return                                                 # 値札が出せないなら黙る
    # **選ぶ側と同じ数え方から引く**（`_deep_used`）。片方だけ直すと、
    # 値札と実際の選び方がずれます（2026-08-26 12:0x）。
    used = _deep_used(posted, built or set())
    lost = 0
    for topic in deep:
        calc = topic["calc"]
        left = [t for t in pool
                if t.get("calc") == calc and t["id"] not in used
                and not t["id"].startswith("s-")
                and t["id"] not in {d["id"] for d in deep}]
        if not left:
            lost += per_calc_long
    if not lost:
        print(f"[pick] 長尺の在庫から {len(deep)}件 をショートに回します"
              "（族はまだ残るので、7日ぶんの長尺の上限は動きません）", flush=True)
        return
    print(f"[pick] [!] **この回のショート {len(deep)}件 は長尺の在庫です。**"
          f"うち族の最後の1件があるので、**7日ぶんの長尺の上限が {lost}本 落ちます**"
          f"（`topic_forge --list` の『族』が減るため）。"
          "**止めません** —— 深い題ショートは `deep_shorts` の前提（期限 09/03）に積みます。"
          "**戻すなら `python scripts/topic_forge.py --count N --long`**", flush=True)


def _row_times(row: dict) -> list[datetime]:
    """その1本について、控えに**一度でも書かれた**予約時刻を全部返す。

    `ledger_rows()` は 1本を1行にたたみますが、**たたむのは「数える側」のため**です
    （`src.dupes._collapse`）。置き場所を避ける側はたたんではいけません ——
    `at` の食い違う組はどちらが本物か行から言えないので、
    **両方を「埋まっている」と読む**のが安全な向きです。
    空きを1つ余計に飛ばすだけで済み、逆向きは**ぶつけて1本捨てます。**
    """
    out = []
    for raw in [row.get("at"), *(row.get("at_others") or [])]:
        if not raw:
            continue
        try:
            out.append(datetime.fromisoformat(str(raw).replace("Z", "+00:00")))
        except ValueError:
            continue
    return out


def ledger_hours(date_jst: str) -> set[int]:
    """その日に**もう置いてある**時刻（JST の時）を、手元の控えから読む。

    読むのは `data/uploaded.jsonl`（`src.dupes.ledger_rows`）で、**API は叩きません。**
    予約の一覧を口から取ると channels + playlistItems + videos で数単位かかるうえ、
    **Data API の日枠が切れている回では、そもそも読めません**
    （日枠が戻るのは JST 16:00。それ以前の回はここが唯一の手がかりです）。

    **控えは上限側の見積りです**（`scripts/status.py` の「予約の先」と同じ性質）。
    取り消した本の行も残るので、**空いているのに「埋まっている」と読むことがあります。**
    外す向きは安全です —— 空き枠を1つ余計に飛ばすだけで、**ぶつけて1本捨てるより安い。**
    逆向き（埋まっているのに空きと読む）は起きません。控えは投稿した本人が書くので、
    **置いた本が控えから落ちることはない**からです。

    読めなかったら空集合を返します。**この道具のために回を止めないこと。**
    """
    try:
        rows = [r for r in dupes.ledger_rows() if r.get("at")]
    except Exception as exc:                                  # noqa: BLE001
        print(f"[batch] 控えが読めませんでした（続行）: {str(exc)[:80]}", flush=True)
        return set()
    taken: set[int] = set()
    for row in rows:
        for at in _row_times(row):
            when = at.astimezone(JST)
            if when.strftime("%Y-%m-%d") == date_jst:
                taken.add(when.hour)
    return taken


def ledger_minutes(date_jst: str) -> set[int]:
    """その日に埋まっている時刻を**0時からの分**で返す（API 0単位）。

    `ledger_hours()` は同じ控えを**時だけ**に落として読んでいました。
    落とすと 10:00 の1本が 10:30 まで塞ぎます —— **1時間に1本しか置けない**
    のは制度でも枠でもなく、**この読み方**でした（2026-08-18 に測った:
    予約262本の分は**全部 :00**、公開は 1日6.4本、置ける枠は 9〜19時の11個）。

    投稿の本数枠は1日92本あります。**律速は置く場所のほうです。**
    """
    try:
        rows = [r for r in dupes.ledger_rows() if r.get("at")]
    except Exception as exc:                                  # noqa: BLE001
        print(f"[batch] 控えが読めませんでした（続行）: {str(exc)[:80]}", flush=True)
        return set()
    taken: set[int] = set()
    for row in rows:
        for at in _row_times(row):
            when = at.astimezone(JST)
            if when.strftime("%Y-%m-%d") == date_jst:
                taken.add(when.hour * 60 + when.minute)
    return taken


def _show_slot(spec: str) -> str:
    """`slots()` が返した指定を、人が読む `H:MM` にする。

    `2026-08-24@10` → `10:00` ／ `2026-08-24@10:30` → `10:30`
    """
    text = spec.partition("@")[2] or spec
    return text if ":" in text else f"{text}:00"


def _slot_minutes(spec: str) -> int:
    """枠の指定 → **その日の何分めか**（`_show_slot()` と同じ読み方）。

    `_ab_slot_order()` が「時刻の早い順」を作るために使います。
    読めなければ `0`（＝いちばん手前）に落とします —— **ここで例外を上げると
    投稿が止まります**（`CLAUDE.md`「投稿を途切れさせないこと」）。
    並べ替えは実験で、投稿は本体。
    """
    try:
        h, _, m = _show_slot(spec).partition(":")
        return int(h) * 60 + int(m or 0)
    except (ValueError, TypeError):                            # noqa: BLE001
        return 0


def _ab_slot_order(topics: list[dict], when: list[str]) -> list[str]:
    """**枠と題材の対応を、IDのハッシュで配り直す**（`src/ab_split.slot_half`）。

    ## なぜ要るか（2026-08-29 に測って足した。**2つ同時に直ります**）

    ここまで、枠は **`pick()` が返した順**に配られていました
    （`results[n] = row` の註「**枠の対応は並び順で決まる**」）。
    `pick()` は **score の高い順**、`live_plan()` は **手前の日・手前の時刻から**。
    つまり:

        score 1位 のテーマ → いちばん手前の枠
        score 最下位       → いちばん後ろの枠

    **(1) 配信の側が測れません。** 「帯の中の位置」と「題材の見込み」が
    いつも同じ向きに並ぶので、控えをどれだけ積んでも分けられません。
    **(2) 中身の側の A/B が痩せます。** 実測（`scripts/ab_slots.py`）:

        title_form  問い **8本/16**（50%）  ／ 断定 14本/16（88%）
        hook_form   問い 14本/16（88%）     ／ 条件 **7本/16**（44%）

    **別々の群が痩せています** —— 痩せた群に残るのは「たまたま生きた枠に
    入った本」なので、差が出ても「作りの差」か「枠の差」か分けられません。

    ハッシュで配ると、この相関が両方 切れます。

    ## 何を変えて、何を変えないか

    **変えるのは対応だけ**です。`when` の中身は1つも作り替えません ——
    `slots()` が既に選んだ枠を**並べ替えて返すだけ**なので、
    1日の本数も、埋まる時刻も、帯の外へこぼれる本も、1つも増えません。
    **順位は「時刻」で作ります。`when` の添字ではありません**（2026-08-30 に測った）。
    `live_ring()` が返すのは**埋め順**で、実物はこう来ます:

        13:30, 13:30, 9:30, 10:30, 11:30, 12:30, 13:30

    手前の日は 13:30 しか空いていない、という形です。**添字で配ると、
    早枠に渡るのは「早い日の遅い時刻」**になり、`config/hypotheses.yaml` の
    claim（「**帯の中の位置**」＝時刻）と測っているものがずれます ——
    **claim と処置がずれた実験は、どちらに転んでも読めません。**
    時刻で並べれば、同じ日の中で 早枠 が手前・遅枠 が後ろになるので、
    **日の効き（チャンネルのその日の配分）は両群に等しく乗ります。**

    ## 呼ぶのは `live` の回だけ

    `--date` / `--hours` / `--hour` / `--long`（`_long_ring()`）は
    どれも「置き先を指示された」回なので触りません
    （`slots()` の `live` の判定と同じ）。長尺は帯を1枠も使わないので、
    この実験はショートにしか掛かりません（`ab_split` 側は `eligible=_shorts_only`）。

    ## 覆る条件

    - **`slot_half` が閉じたら**、この配り直しを続けるかを選び直すこと。
      早枠が勝っていたなら「score 順に手前へ」は正しかったので**戻す**
      （そのとき失うのは、中身の側の A/B の釣り合いのほう ——
      代わりに `scripts/ab_slots.py` の入れ替えで釣ること）。
      差が無ければ、`day_cap` の (A) 模型どおり **帯の 10枠 は同じ**なので、
      このまま置いておいてよい（釣り合いだけが残る）
    - `SLOT_EARLY_SHARE` を 0 にすると `slot_half()` が全部 `遅枠` を返し、
      並べ替えは**ハッシュ順**になります。**元の score 順には戻りません** ——
      戻すならこの呼び出しごと外すこと
    """
    if len(when) != len(topics) or len(topics) < 2:
        return when
    try:
        from src import ab_split
    except Exception:                                          # noqa: BLE001
        return when

    def _key(i: int):
        tid = str(topics[i].get("id") or "")
        h = hashlib.sha1((ab_split.SLOT_HALF_SALT + tid).encode("utf-8")).digest()
        # **群が第1鍵、同じ群の中はハッシュ順**（第2鍵）。
        # 第2鍵まで入れないと、群の中では score 順が残ります。
        return (0 if ab_split.slot_half(tid) == "早枠" else 1,
                int.from_bytes(h[4:8], "big"))

    # **枠は「時刻の早い順」に並べます。添字の順ではありません**（2026-08-30 に測った）。
    #     `live_ring()` が返すのは**埋め順**で、実物は
    #     `13:30, 13:30, 9:30, 10:30, 11:30, 12:30, 13:30` のように来ます
    #     （手前の日は 13:30 しか空いていない、という形）。
    #     添字で配ると、早枠に渡るのは「**早い日**の遅い時刻」になり、
    #     `config/hypotheses.yaml` の claim（「**帯の中の位置**」＝時刻）と
    #     測っているものがずれます —— **claim と処置がずれた実験は、
    #     どちらに転んでも読めません**（この repo が通算11回 踏んだ
    #     「言っている所と、している所が別」）。
    #     時刻で並べれば、同じ日の中で 早枠 が 9:30〜11:30・遅枠 が 12:30〜13:30 に
    #     なるので、**日の効き（チャンネルのその日の配分）は両群に等しく乗ります。**
    #     同じ時刻どうしは元の順を保つので、日の割り当ては今までどおり。
    slot_rank = sorted(range(len(when)),
                       key=lambda n: (_slot_minutes(when[n]), n))
    order = sorted(range(len(topics)), key=_key)
    out: list[str] = [""] * len(topics)
    for rank, i in enumerate(order):
        out[i] = when[slot_rank[rank]]
    early = sum(1 for t in topics if ab_split.slot_half(str(t.get("id") or "")) == "早枠")
    print(f"[batch] 枠は**IDのハッシュ**で配ります（`ab_split.slot_half`・"
          f"早枠 {early}本 ／ 遅枠 {len(topics) - early}本）。"
          " **枠そのものは1つも変わりません** —— 変わるのはどの題材がどの枠へ行くか。"
          " これが配信の側の最初の無作為化された A/B で、"
          "同時に中身の側の A/B の釣り合いも直します", flush=True)
    return out


# **1日に置く本数の目安**（`scripts/reschedule.py` の `DEFAULT_PER_DAY` と同じ数）。
# 08/20 の実測で11本目から先が 0〜3 再生でした。**止める門ではなく、言うだけ**です
# （判定は 08/23 に済み・`config/hypotheses.yaml` の「予約の間隔」）。
#
# **2026-08-24: ここも計器から取ります**（`src/day_cap.py`。定数だと測り直しに
# 付いていきません）。読めない回は 10 に落ちます。
@functools.cache
def _per_day_soft(fallback: int = 10) -> int:
    """**呼ばれたときに測ります**（import では読みません。理由は reschedule.py と同じ）。"""
    try:
        from src import day_cap
        m = day_cap.measure()
        return int(m["cap"]) if m.get("measured") else fallback
    except Exception:
        return fallback


_PER_DAY_SOFT = 10            # **読めない回の既定**。実際に使う数は `_per_day_soft()`


# --- **1日の公開本数の、機械の上限**（2026-08-30。解除条件4）-----------------
#
# **文書だけの上限は、上限ではありません。** `docs/MEANS.md` M14 は 2026-08-25 から
# 「崩れる点は 10本/日」と書いてあり、`config/hypotheses.yaml` の `next_done` も
# 08-28 に「頭打ちと確定させた」と書いています。**それでも機械は 08/27 に 19本、
# 08/28 に 22本 置きました。** 書いてある数と、出している数が別だった、という形です。
#
# ## なぜ `_per_day_soft()` があるのに足りなかったか
#
# あれが効くのは `_band_walk()` の**帯の中だけ**です。数えているのは
# `busy & set(grid)` ＝ **帯（09:00〜13:30）の枠に入っている本だけ**なので、
#
#     長尺の `ring`（20:00〜）           日を名指ししないので `_band_walk` を通らない
#     `--hours` の明示                  `slots()` が「明示は通す」で素通しする
#     `--step-min 30` の `_slots_fine`  別の道
#     **同じ日に2回 走った回**          2回目は、1回目が帯の外に置いた本を数えない
#
# の4つが素通りします。19〜22本/日 は、この4つの足し算です。
#
# **だからここは `slots()` が返した後**に当てます。置き先を決める道が何本あっても、
# 出口はこの1本だからです（`main()` の「0.7」）。**そして生成の前に当てます** ——
# 作ってから捨てると、その本は `build/` ごとコンテナと一緒に消えます。
#
# ## 上限の出どころ（**定数を書かないこと**）
#
# `src.density_verdict.HOUR_HI` ＝ **測れている帯の上端 13本/日**。
# 同じ数を `scripts/eta.py` の `PLAN_PUBLISH_PER_DAY` が使っています ——
# **計画が立てている本数と、機械が出せる本数を、同じ1か所から取る**ためです
# （検査 `tests/test_density_cap.py`。ずれたら赤くなります）。
#
# 2026-08-30 の判定（`python -m src.density_verdict`・API 0単位）:
#
#     詰めた日（1日16本以上）    1本あたり再生の中央値   2回（5日・119本）
#     1時間きざみの日（8〜13本）                      716回（4日・42本）
#     倍率 **0.003**（`falsified_if` は 0.5 未満）→ **falsified**
#
# **覆る条件**: `density_verdict` を撃ち直して倍率が 0.5 以上に戻ったら、
# この門ごと外してよい。上端が動けば上限も動きます（`HOUR_HI` を読むだけなので、
# ここを書き換える必要はありません）。

#: **上限が読めなかった回の既定。** `density_verdict.HOUR_HI` と同じ数を書きます
#: （検査が一致を見ています）。**読めない回に無制限へ落ちないこと** ——
#: 落ちると、計器が壊れた回だけ 22本/日 に戻ります。
_DENSITY_CAP_FALLBACK = 13


@functools.cache
def density_cap() -> int:
    """**1日に置いてよい本数**（`src.density_verdict.HOUR_HI`）。API 0単位。"""
    try:
        from src import density_verdict                          # noqa: PLC0415
        return max(1, int(density_verdict.HOUR_HI))
    except Exception:                                            # noqa: BLE001
        return _DENSITY_CAP_FALLBACK


def cap_by_density(when: list[str], cap: int | None = None,
                   ledger: dict[str, set[int]] | None = None
                   ) -> tuple[list[int], list[str]]:
    """`slots()` の返りから、**1日の上限を超えるぶんを落とす**（API 0単位）。

    返り: `(残す添字, 印字する行)`。呼ぶ側は `topics` と `when` を
    **同じ添字で**絞ること（対応が崩れると別の本が別の枠へ行きます）。

    ## 2種類の指定を、別々に数えます

    `"YYYY-MM-DD@H"` / `"…@H:MM"`
        **日が名指しされている。** その日の控えの本数に足して数え、
        上限を超えたぶんを落とす。控えは取り消し済みの本も埋まりに数える
        **上限側の見積り**です（`slots()` の docstring と同じ扱い）。

    `"9"`（時だけ）
        **日が名指しされていない。** `uploader.next_publish_at()` が
        「その時刻で最初に空いている**日**」を返すので、
        **1日に着きうる本数は、この回が使う相異なる時刻の数**が上限になります
        （同じ時刻を n 回 返す回は 1日1本ずつ n日 に散る ＝ 落とすものはありません）。
        だから数えるのは本数ではなく**時刻の種類**です。

    **控えが読めなかった回は、この回の本だけで数えます**（0本 とみなす）。
    黙って素通しするより、少なくともこの回の中の詰め込みは止まります。
    """
    cap = density_cap() if cap is None else int(cap)
    notes: list[str] = []
    if cap <= 0 or not when:
        return list(range(len(when))), notes
    if ledger is None:
        try:
            ledger = _ledger_by_day()
        except Exception as exc:                                 # noqa: BLE001
            notes.append("[batch] 控えが読めないので、1日の上限は"
                         f"**この回の本だけ**で数えます（続行）: {str(exc)[:60]}")
            ledger = {}
    used = {d: len(v) for d, v in (ledger or {}).items()}
    before = dict(used)
    keep: list[int] = []
    dropped: dict[str, int] = {}
    hours_seen: set[str] = set()
    for i, w in enumerate(when):
        if "@" in w:
            day = w.split("@", 1)[0]
            if used.get(day, 0) >= cap:
                dropped[day] = dropped.get(day, 0) + 1
                continue
            used[day] = used.get(day, 0) + 1
        else:
            if w not in hours_seen and len(hours_seen) >= cap:
                dropped["(時刻だけの指定)"] = dropped.get("(時刻だけの指定)", 0) + 1
                continue
            hours_seen.add(w)
        keep.append(i)
    if dropped:
        detail = "／".join(
            (f"{d} は控え {before.get(d, 0)}本 ＋ この回 "
             f"{used.get(d, 0) - before.get(d, 0)}本 で上限 → **{n}本 落とす**"
             if d in used else f"{d} で **{n}本 落とす**")
            for d, n in sorted(dropped.items()))
        notes.append(
            f"[batch] **1日の上限 {cap}本/日 に当てて、{sum(dropped.values())}本 を"
            f"この回から外します**（{detail}）。"
            " 上限は `src.density_verdict.HOUR_HI`（測れている帯の上端）で、"
            "**16本以上の日は1本あたり再生の中央値が 2回**（1時間きざみの日は 716回・"
            "倍率 0.003 ＝ `falsified_if` を桁で下回る）。"
            " **落とした本は作っていません** —— 題材は在庫に残るので、"
            "次の回が別の日へ置けます。")
    return keep, notes


#: **1回に逃がす死に枠の上限**（`_rescue_dead_slots()`）。1手 50単位。
#: 日枠 10,000 のうち `videos.insert` が 1本 1,600単位 ＝ 1日 6本 が限度なので、
#: ここを大きくすると**その日の投稿が減ります**。20手 ＝ 1,000単位 ＝ 投稿 0.6本ぶん。
#: **残りは次の回が続けます**（`--plan` は毎回 実物の控えから組み直す）。
_RESCUE_MAX = 20

#: **いまから何分より後の枠なら置いてよいか。** `uploader.next_publish_at()` の門は
#: 20分 なので、それより広く取ります（作ってから予約するまでに時間が経つため）。
_BAND_LEAD_MIN = 45


def _band_bounds() -> tuple[int, int]:
    """**生きる帯の両端**（0時からの分）。**写さずに引く。**

    下端は `PROVEN_FROM_MIN`（この節の註）、上端は `src/collisions.LIVE_TO_MIN`。
    どちらかが測り直しで動いたら、帯を使う所は全部いっしょに動きます。
    """
    try:
        from src import collisions                              # noqa: PLC0415
        return PROVEN_FROM_MIN, int(collisions.LIVE_TO_MIN)
    except Exception:                                           # noqa: BLE001
        return PROVEN_FROM_MIN, 13 * 60 + 30


def _ledger_by_day() -> dict[str, set[int]]:
    """控えを **1回だけ**読んで、日 → 埋まっている分（0時から）にする（API 0単位）。

    `ledger_minutes()` は1日ぶんを返すために**控えを丸ごと読み直します**。
    帯が埋まった日から次の日へ歩くと日数ぶん呼ぶことになるので、ここで1回に畳みます。
    """
    out: dict[str, set[int]] = {}
    try:
        rows = [r for r in dupes.ledger_rows() if r.get("at")]
    except Exception as exc:                                    # noqa: BLE001
        print(f"[batch] 控えが読めませんでした（続行）: {str(exc)[:80]}", flush=True)
        return out
    for row in rows:
        for at in _row_times(row):
            when = at.astimezone(JST)
            out.setdefault(when.strftime("%Y-%m-%d"),
                           set()).add(when.hour * 60 + when.minute)
    return out


def _band_walk(count: int, date_jst: str, from_min: int = 0,
               first_day_taken: set[int] | None = None,
               taken_by_day: dict[str, set[int]] | None = None,
               lanes_n: int | None = None,
               horizon: int = 120,
               now: datetime | None = None) -> list[str]:
    """**ショートの置き先を、生きる帯の空きから日をまたいで拾う**（API 0単位）。

    ## なぜ要るか（2026-08-29・最適化の回。**この回に実測して足した**）

    `_slots_fine()` の枠は長らく `range(hour * 60, 24 * 60, step_min)` で、
    **1日の終わりまで**でした。だから `--date` を渡した回は、帯（09:00〜13:30）が
    埋まると **14:00 以降の枠へ静かにこぼれます。** こぼれた本は死にます。

    **この回の実測**（`data/uploaded.jsonl` × `data/views.jsonl`・
    08-19 以降・齢 20〜120時間 の最初の読み・**題の `#Shorts` で形を分けた**）:

        ショート 帯の中 09:00〜13:30    99本  合計 53,185再生   1本あたり **537.2**
        ショート 帯の外               60本  合計     43再生   1本あたり **0.7**

    **同じ形・同じ作り方で 768倍**です。切り分けも1組あります ——
    08/27 の 05:00〜08:30 に置いた **8本**（全部ショート）は**8本とも 0再生**、
    同じ日の 09:00〜13:30 の 10本 は 56〜918再生。**違うのは時刻だけ**です。

    そして 2026-08-29 の予約には、**帯の外のショートが 99本** 残っていました
    （14:00 に12本・15:00 に17本・16:00 に11本・21:00 に10本・05:00 台に11本…）。
    そのうち **66本 は、同じ日の帯に空き枠があるのに外へ置かれています。**
    本数の取り合いですらなく、**枠の選び方だけ**で捨てていました。

    ## 何をするか

    `date_jst` の帯から拾い、足りなければ**次の日の帯へ**進みます
    （`24:00` へではなく）。1日に取る本数は `day_cap.cap()` まで ——
    帯に枠が残っていても、上限を超えたぶんは 0再生 だからです。

    **`--long` には掛けません。** 長尺は `SHORTS_FEED` の枠を1つも使わず、
    上限も別（`day_cap.long_form()`）で、置き先は `_long_ring()` の 18〜22時 です。

    **覆る条件**: `src/day_cap.window()` が **(B)「T までに出した本は全部生きる」**
    と決着したら、上端 `collisions.LIVE_TO_MIN` を測り直すこと ——
    そのときは帯が広がり、1日に置ける本数も増えます。
    左端 `PROVEN_FROM_MIN` を下げるのは (B) が出てからです
    （**08:30 より前は測って 0再生**。`src/day_cap.py` の窓の節）。
    帯の中の1本あたりが、帯の外の1本あたりを**下回ったら**この関数を外すこと。
    検査は `tests/test_band_walk_shorts.py`。

    ## 渡された埋まりを、必ず先に使うこと

    `first_day_taken` は**呼ぶ側が明示した `date_jst` の埋まり**（`taken_min`/`taken`）で、
    渡されたらそちらが正です。**控えを読みに行かないこと** ——
    ここは 2026-08-29 に一度 踏みました（渡された `taken_min=set()` を無視して
    `data/uploaded.jsonl` を読み、**検査の答えが実物の予約で変わりました**）。
    控えは、**`date_jst` より後ろの日を初めて見るときにだけ**、遅れて1回 読みます。
    """
    lo, hi = _band_bounds()
    # **きざみは `day_cap.MIN_GAP_MIN` そのもの**（呼ぶ側の `--step-min` ではない）。
    # これより詰めた本は死に（08/21 の :15/:45 が7本とも0）、
    # これより空けると帯の枠を捨てます（1時間きざみだと 10枠 が 5枠 になる）。
    # **帯の枠数 10 と `day_cap.cap()` の 10本/日 は、同じ実測から来ています。**
    try:
        from src import day_cap                                 # noqa: PLC0415
        step = max(1, int(day_cap.MIN_GAP_MIN))
        per_day = max(1, int(day_cap.cap()))
    except Exception:                                           # noqa: BLE001
        step, per_day = 30, _PER_DAY_SOFT
    lo = max(lo, int(from_min))          # `--hour` は**下端**として効かせる
    grid = [m for m in range(lo, hi + 1, step)]
    if not grid or count <= 0:
        return []
    now = now or datetime.now(JST)
    known: dict[str, set[int]] = dict(taken_by_day or {})
    if first_day_taken is not None:
        known[date_jst] = set(first_day_taken)
    ledger: dict[str, set[int]] | None = taken_by_day if taken_by_day else None
    n_lanes = lanes.LANES if lanes_n is None else lanes_n

    day = datetime.strptime(date_jst, "%Y-%m-%d").date()
    out: list[str] = []
    for _ in range(horizon):
        if len(out) >= count:
            break
        key = day.strftime("%Y-%m-%d")
        if key not in known:
            if ledger is None:
                ledger = _ledger_by_day()      # **後ろの日を見るときだけ読む**
            known[key] = set(ledger.get(key, set()))
        busy = known[key]
        free = [m for m in grid if m not in busy]
        # **過ぎた枠を返さないこと**（2026-08-29 に、この関数を書いた直後に踏んだ）。
        #
        # 帯は朝だけ（09:00〜13:30）なので、**夕方以降に走った回**が今日を指すと、
        # ここは黙って `今日@9:00` を返します。`uploader.next_publish_at()` は
        # 「**過去か直近すぎます**」で落とし、**作った1本がそのまま捨てられます**
        # （`build/` はコンテナと一緒に消えます —— `slots()` の docstring が
        #  「3回持ち越された穴」として同じ代金を書いています）。
        #
        # 直す前の `range(hour, 24)` は 21:00 を返せたので**落ちはしませんでした**
        # （そのかわり 0.7再生 で公開されます）。**どちらでもなく、翌日の帯へ送ること。**
        # 余裕は `next_publish_at()` の門（20分）より広く取ります。
        if day <= now.date():
            edge = (now.hour * 60 + now.minute + _BAND_LEAD_MIN
                    if day == now.date() else 24 * 60)
            free = [m for m in free if m > edge]
        room = min(len(free), max(0, per_day - len(busy & set(grid))))
        if room:
            want = min(room, count - len(out))
            # **車線から取る**（同じ回に走るきょうだいと同じ分を選ばないため。
            # 理由は `src/lanes.py`）。控えは互いに見えないので、避けるだけでは足りません。
            picked = sorted(lanes.order(free, step_min=step, lanes=n_lanes)[:want])
            out += [f"{key}@{m // 60}:{m % 60:02d}" for m in picked]
            known[key].update(picked)
        day += timedelta(days=1)
    return out


def _slots_fine(count: int, hour: int, date_jst: str, hours: list[int],
                step_min: int, taken: set[int] | None,
                taken_min: set[int] | None,
                lanes_n: int | None = None,
                long_form: bool = False,
                now: datetime | None = None) -> list[str]:
    """`step_min` が 60 未満のときの割り当て（0時からの分で数える）。

    **`slots()` から呼ばれる前提**です。単体で呼ばないこと（`date_jst` を必須にしてある）。
    """
    if not 1 <= step_min < 60 or 60 % step_min:
        raise SystemExit(
            f"--step-min は 60 の約数で 1〜59 のどれか: {step_min}\n"
            "        （1時間を割り切らないと、日をまたぐ所で目盛りがずれます）"
        )
    if hours:
        raise SystemExit(
            "--hours と --step-min は同時に使えません。\n"
            "        `--hours` は**時だけ**の指定なので、分の目盛りを打ち消します。"
        )
    if taken_min is None:
        if taken is not None:
            raise SystemExit(
                "step_min が 60 未満のときは taken（時）ではなく taken_min"
                "（0時からの分）を渡すこと。\n"
                "        時に落として読むと 10:00 の1本が 10:30 まで塞ぎます —— "
                "**それがこの目盛りの相手そのもの**です。"
            )
        taken_min = ledger_minutes(date_jst)
    # **ショートは、生きる帯の外へこぼさない**（2026-08-29・最適化の回）。
    # 実測は `_band_walk()` の docstring —— 帯の中 537.2再生/本 対 帯の外 0.7再生/本。
    # 帯が埋まったら 14:00 以降ではなく**次の日の帯**へ進みます。
    if not long_form:
        walked = _band_walk(count, date_jst, hour * 60,
                            first_day_taken=taken_min, lanes_n=lanes_n, now=now)
        if len(walked) == count:
            days = sorted({w.split("@")[0] for w in walked})
            if days != [date_jst]:
                print(f"[batch] **{date_jst} の帯（09:00〜13:30）が埋まっているので、"
                      f"次の日の帯へ回します**: {', '.join(days)}"
                      "　—— 帯の外は実測 0.7再生/本（帯の中 537.2）。"
                      "**同じ日の 14:00 以降へは置きません**", flush=True)
            return walked
        print(f"[batch] [!] 帯の空きが {len(walked)}枠 しか読めませんでした"
              f"（{count}本 要ります）。**今までどおり時刻で埋めます** —— "
              "帯の外に落ちたぶんは 0再生 になります（`_band_walk` の実測）",
              flush=True)
    grid = [m for m in range(hour * 60, 24 * 60, step_min) if m not in taken_min]
    if len(grid) < count:
        busy = sorted(f"{m // 60}:{m % 60:02d}" for m in taken_min)
        raise SystemExit(
            f"{date_jst} は {hour}時以降の空きが {len(grid)} 個しかありません"
            f"（{count} 本ぶん要ります／{step_min}分きざみ／控えでの埋まり {busy}）。\n"
            "        **別の日にするか、--hour を早めるか、--step-min を細かくすること。**"
        )
    # **自分の車線から先に取る**（2026-08-25。理由は `src/lanes.py` の docstring）。
    #
    # 控えは**このコンテナの中にしか無い**ので、同じ回に走っているきょうだいが
    # いま置いた本は見えません（`git` で配られるのは push のあと）。だから
    # `taken_min` を避けただけでは足りず、**同じ日の先頭から取る2つの回は
    # 必ず同じ分を選びます。** 実測: 08/27 に5組・09/06 に3組が同じ分でした。
    #
    # 車線は**セッションIDと「0時からの分」だけ**から決まります（控えを見ない）。
    # 相手の控えがこちらと食い違っていても、車線が違えば選ぶ分は重なりません。
    n_lanes = lanes.LANES if lanes_n is None else lanes_n
    picked = sorted(lanes.order(grid, step_min=step_min, lanes=n_lanes)[:count])
    # **1日に置きすぎていないか言う**（2026-08-21 の実測。止めはしません）
    #
    # 08/20 に Shorts を25本置いた実測: 公開の早い10本は 185〜1,394 再生、
    # **11本目から先は 0〜3**（同じ経過11時間の時点。10本目と11本目は30分差）。
    # 1日の合計は 4本の日 5,301 と 25本の日 5,948 で**ほぼ同じ**でした。
    # つまり **11本目から先は在庫を捨てている**のと同じです。
    #
    # **ここで止めないのはわざとです。** `config/hypotheses.yaml` の
    # 「1時間より詰めても1本あたりは落ちない」は 08/23 に判定します
    # （1日16本以上の日が3日ぶん要る）。**判定の前に条件を変えないこと。**
    # 判定が出たら、ここを `raise SystemExit` に変えるか、
    # `scripts/reschedule.py --spread` で後から均すこと。
    soft = _per_day_soft(_PER_DAY_SOFT)
    if len(taken_min) + count > soft:
        print(f"[batch] [!] **{date_jst} は控えと合わせて {len(taken_min) + count}本**"
              f"（1日の目安 {soft}本・実測）。08/20 の実測では**11本目から先が 0〜3 再生**です。"
              "\n        置いたあと `python scripts/reschedule.py --spread` で均せます"
              "（1本50単位）。**作る前に日を割るほうが安いです。**", flush=True)
    if picked != list(range(hour * 60, hour * 60 + step_min * count, step_min)):
        shown = ", ".join(f"{m // 60}:{m % 60:02d}" for m in picked)
        print(f"[batch] {date_jst} の埋まりと車線（{lanes.lane(lanes=n_lanes)}/{n_lanes}）"
              f"を避けて {shown} に置きます（控えから。API 0単位）", flush=True)
    return [f"{date_jst}@{m // 60}:{m % 60:02d}" for m in picked]


def _long_ring() -> tuple[int, ...]:
    """**長尺を1日に何本 置くか**を、実測から決めて時刻の輪にして返す。

    `LONG_PER_DAY` は「まだ崩れていないと分かっている一番上」です。
    ところが**それは測り直しで下がることがある**ので、定数のまま使いません
    （`scripts/reschedule.py::_measured_per_day` が同じ理由で計器から取っています）。

    見るのは `src/day_cap.long_form()` の2つだけ:

        collapsed=True  いちばん多く出した日に「出したのに再生が付かない」本が出た
                        → **その日の本数より1つ下**へ落とす（`most - 1`）
        collapsed=False そこまでは崩れていない → `most` と `LONG_PER_DAY` の**小さいほう**

    **上へは伸ばしません。** `most` が 5 なら、6本目がどうなるかは
    **一度も観測されていません**（`measured=False`）。ここで 6 を返すのは
    「測っていない天井を、黙って測りにいく」ことです。**測るなら前提を立てること。**

    読めない回は **1本**（＝今までどおり1日1本）に落ちます ——
    **分からないときは、今までの動きへ倒すこと。**
    """
    try:
        from src import day_cap
        lf = day_cap.long_form()
        most = int(lf.get("most") or 0)
        if most <= 0:
            return (LONG_HOUR_JST,)
        n = (most - 1) if lf.get("collapsed") else min(most, LONG_PER_DAY)
        n = max(1, min(n, len(LONG_HOURS_JST)))
        return tuple(LONG_HOURS_JST[:n])
    except Exception:                                        # noqa: BLE001
        return (LONG_HOUR_JST,)


#: **実測で生きていると分かっている帯の下端**（JST の分）。
#:
#: `src/collisions.py` の `LIVE_FROM_MIN` は **05:00** ですが、その根拠の行は
#: 「**08:59〜13:30** の :00/:30 が10本とも生き、あいだの :15/:45 は7本とも 0〜2再生」
#: です。**05:00〜08:59 は測っていません** —— そこは
#: `src/day_cap.py` が「09:00 より前に置いたぶんは丸ごと上積みになるか」を
#: **2026-08-27 に測っている、まさにその帯**です（05/06/07/08時 の4本）。
#:
#: **作った本を、測定中の帯へ置かないこと。** `live_slots.py` が
#: そこへ「逃がす」のは別の話です（あちらは既に死に枠にいる本の救出で、
#: 置かなければ 0再生 が確定している）。こちらは**まだ死んでいない本**なので、
#: 測れている側から埋めます。
#:
#: **覆る条件は「09:00 より前も生きるか」ではありません**（2026-08-27 に直した）。
#: **その問いは、どちらのモデルでも「生きる」と答えます** ——
#: (A)「1日 C本 まで」なら、朝より前に置いた本は**その日の先頭**なので生きます。
#: 死ぬのはそのぶん後ろへ押し出された 09:00〜13:30 の本のほうで、
#: **1日に生きる本数は 10本 のまま**です。
#:
#: 読むのは `config/hypotheses.yaml` の `falsified_if` が言っているほう ——
#: **その日の「生きた本数」が 11本以上か**（＝ (B)「T までに出す」）。
#:
#:     (B) と出た   ここを `collisions.LIVE_FROM_MIN` に差し替える。
#:                  枠が 10 → 18 に増え、1日に置ける本数もそのぶん増える
#:     (A) と出た   **差し替えないこと。** 広げると、いま朝より前に置いてある本が
#:                  上限を食うので、**置ける日はかえって後ろへ下がります**
#:
#: **値打ちは `python scripts/queue_lag.py` が毎回その場で出します**
#: （(A) と (B) を並べて印字する。**この註に数を写さないこと**）。
#: 実測 2026-08-27 の一度きりの姿: 128本 を置くのに いまの帯 +34日 /
#: (A) で広げると +67日 / (B) で広げると +12日。**符号が逆になります。**
PROVEN_FROM_MIN = 9 * 60        # 09:00 JST


def _band_grid() -> list[tuple[int, int]]:
    """**実測で生きている帯**（09:00〜13:30）の 30分きざみの枠。**写さずに引く。**

    上端は `src/collisions.LIVE_TO_MIN`、きざみは `src/day_cap.MIN_GAP_MIN`
    （「これより詰めた本は死ぬ」の実測）。どちらかが測り直しで動いたら、
    ここも一緒に動きます。下端だけは `PROVEN_FROM_MIN`（理由はその註）。

    枠は 10個 で、`day_cap.cap()` の 10本/日 とちょうど同じです。**偶然ではありません**
    —— どちらも 08/21 の同じ実測から来ています。
    """
    try:
        from src import collisions, day_cap                     # noqa: PLC0415
        hi = int(collisions.LIVE_TO_MIN)
        step = max(1, int(day_cap.MIN_GAP_MIN))
    except Exception:                                           # noqa: BLE001
        hi, step = 13 * 60 + 30, 30
    return [(m // 60, m % 60) for m in range(PROVEN_FROM_MIN, hi + 1, step)]


def live_ring(count: int, now: datetime | None = None) -> list[str] | None:
    """**`--date` も `--hours` も無い回の予約時刻**を、控えの空きから選ぶ（API 0単位）。

    ## なぜ要るか（2026-08-26・最適化の回。実測でこの回に見つけた）

    ここは長らく `[str(hour)] * count`（＝ショートなら 09:00 を count 回）でした。
    `uploader.next_publish_at()` は**時刻を一度も動かさず、1日ずつ後ろへ**試すので
    （`target += timedelta(days=1)` だけ）、**09:00 が埋まっている日数ぶん、
    そのまま後ろへ落ちます。**

    実測（2026-08-26 の控え 362本。`scripts/queue_lag.py` の `by_slot`）:

        09:00 が空くまで  **49日**   ← `batch_build` の既定（ショート）
        20:00 が空くまで  **2日**    ← 既定（長尺）。ただし帯の外
        12:00 が空くまで  **3日**    ┐ どれも**生きる帯の中**で、
        13:00 が空くまで  **3日**    │ 同じ日の帯には空き枠が
        10:00 / 11:00     **4日**    ┘ 5〜8個 残っています

    **開いている前提の期日は、いちばん遠いもので 17日 先**です（`config/hypotheses.yaml`）。
    **49日 先に置いた本は、いま開いている前提を1件も閉じません** ——
    `eta.py` が「軌跡の腕が動くのは前提を1件閉じたときだけ」と印字しているとおり、
    **その本は到達日を1日も動かせない**ということです。

    ## `day_cap` の (A)/(B) が未判定でも、この選び方は損をしません

    `day_cap.window()` は `confounded`（(A) 1日C本まで ／ (B) T までに出す）です。
    **どちらでも、帯の空き枠のほうが弱くても同じ**になります:

        (B) 帯の外は死んでいる      → 帯へ置くのは**まるごと上積み**
        (A) 早く出た C本 が生きる   → 帯は朝なので**その C本 の側**。
                                     押し出されるのは、同じ既定が夜へ落とした本

    **どちらに賭けてもいません。** 賭けが要るのは「何本 作るか」のほうで、
    ここは「**同じ本をどこへ置くか**」だけを決めています。

    ## 覆る条件

    - `day_cap` の切り分け（08/27 の測定）が **(A) かつ 帯の外も生きる** と出たら、
      帯にこだわる理由が消えます。**そのときは `_band_grid()` を広げること。**
    - 帯が埋まって `first_free` が 09:00 と変わらなくなったら、
      **効いているのは選び方ではなく在庫の少なさ**です。`--step-min` を細かくするか、
      帯そのものを測り直すこと。

    返り: `["12:00", "13:00", …]`（`upload_only.split_when()` が読む形）。
    読めなければ `None` —— **呼ぶ側は今までどおりに倒すこと**（黙って粗くしない）。

    **中身は `live_plan()` です**（2026-08-27 に切り出した）。あちらは
    **選んだ日も一緒に返します** —— `queue_lag.band_lines()` が
    「あと N本 を置き切るのは何日か」を、**この関数と同じ手順で**数えるためです。
    切り出す前、あちらは「帯の空き枠の**平均**」で割っていて、**11日 楽観**でした
    （実測 2026-08-27: 平均だと 128本 に 23日、実際に置くと 34日 ——
    置く側は**手前の日から埋める**ので、空いている先の日が平均を持ち上げます）。
    """
    plan = live_plan(count, now)
    return [t for t, _ in plan] or None


def long_plan(count: int, ring: tuple[int, ...] | list[int] | None = None,
              now: datetime | None = None,
              taken: dict[str, set[int]] | None = None) -> list[tuple[int, date]]:
    """`--long` の回が **実際にどの日へ着くか**を返す（時, 日）。API 0単位。

    ## なぜ要るか（2026-08-29 に踏んで足した。**門が効いていませんでした**）

    `_drop_queue_tail_calcs` は「着地点の前後 7日 に出ている calc を避ける」
    ための門で、その着地点を `main()` が渡します。ところがそこは
    **`--date` が無ければ `live_plan()`**（＝ **ショートの生きる帯** 09:00〜13:30）
    を読んでいました。**長尺はその帯へは1本も置きません** ——
    置き先は `_long_ring()` の 18〜22時 で、`next_publish_at()` が
    「その時刻が空いている最初の日」を返します。

    実測 2026-08-29 10:4x（`--count 4 --long`）:

        印字された着地点   2026-09-06   ← `live_plan()`（ショートの帯）
        実際に着く日       2026-09-19   ← 長尺の 19〜22時 が最初に空く日
        門が選んだ4本      teiji×2 ＋ shokyu×2
        09/16 に既に在る   teiji×2 ＋ shokyu×1   ← **どちらも着地点の 3日前**

    **13日 ずれた窓で門を掛けたので、避けるべき calc が1つも見えていません。**
    そのまま置けば「同じ制度の長尺が3日おきに4本」になり、これは
    `CLAUDE.md` が名指ししている「続けて数本 視聴すると繰り返しに感じられる」
    そのものです。**門は在るのに、別の日を見ていた**だけでした。

    ## 何を写しているか

    `uploader.next_publish_at()` の自動の枝（`date_jst` なし）そのものです ——
    その時刻の今日ぶんが 20分 以内なら翌日から始め、
    **控えで埋まっている日と `measure_window` の窓を飛ばして**最初の空きへ置く。
    `ring` が複数の時刻を持つ回は、`slots()` が時刻を順に配るので、
    ここも同じ順で配ってから日を解きます。

    `taken`（日 → 埋まっている時（JST））を渡さなければ控えから読みます
    （`ledger_hours` と同じ `data/uploaded.jsonl`。**API 0単位**）。
    **控えは上限側**なので、空いている枠を「埋まっている」と読むことがあります ——
    外す向きは安全（門の窓が1日ずれるだけ）で、逆は起きません。

    読めない回は `[]` を返します。**呼ぶ側は今までどおりに倒すこと**
    （＝ `land=None` ＝ 今日を中心に見る）。**黙って粗くしない。**
    """
    ring = tuple(ring or (LONG_HOUR_JST,))
    if count <= 0 or not ring:
        return []
    now = now or datetime.now(JST)
    if taken is None:
        taken = {}
        try:
            for row in dupes.ledger_rows():
                if not row.get("at"):
                    continue
                for at in _row_times(row):
                    when = at.astimezone(JST)
                    taken.setdefault(when.strftime("%Y-%m-%d"), set()).add(when.hour)
        except Exception as exc:                              # noqa: BLE001
            print(f"[batch] 控えが読めませんでした（着地点は今日を中心に見ます）: "
                  f"{str(exc)[:80]}", flush=True)
            return []
    else:
        taken = {k: set(v) for k, v in taken.items()}

    out: list[tuple[int, date]] = []
    for i in range(count):
        hour = int(ring[i % len(ring)])
        target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if target <= now + timedelta(minutes=20):
            target += timedelta(days=1)
        for _ in range(60):
            day_jst = target.strftime("%Y-%m-%d")
            if measure_window.inside(day_jst) or hour in taken.get(day_jst, set()):
                target += timedelta(days=1)
                continue
            taken.setdefault(day_jst, set()).add(hour)
            out.append((hour, target.date()))
            break
        else:
            break
    return out


def live_plan(count: int, now: datetime | None = None,
              grid: list[tuple[int, int]] | None = None,
              horizon: int = 90,
              cap: int | str | None = "auto",
              taken: dict | None = None) -> list[tuple[str, date]]:
    """`live_ring()` の中身。**時刻と、置くことになる日**を返す（API 0単位）。

    `live_ring()` は時刻しか返さないので、**日は `uploader.next_publish_at()` が
    もう一度 探し直します。** ここはその探し方をそのまま写したもので、
    **数える側（`queue_lag`）と置く側（`batch_build`）が同じ答えを出す**ための1本です。

    `grid` を渡すと帯を差し替えて数えられます（`PROVEN_FROM_MIN` を下げたら
    何日 早まるか、の反実仮想）。**既定はいま置いている帯そのもの**です。

    `cap` は **`day_cap.window()` の (A)/(B) がそのまま入る所**です:

        `"auto"`  `day_cap.cap()` を読む ＝ **(A)「1日 C本 まで」**。
                  その日の帯に既に C本 在れば、その日は後ろへ回す
        `None`    上限なし ＝ **(B)「T までに出す」**。帯に在るだけ置ける

    **既定は `"auto"`（＝ `live_ring()` がいま置いている形）です。**
    (A)/(B) はまだ切り分いていないので（`day_cap.window()` が `confounded`）、
    **帯を広げる値打ちを数えるときは両方を出すこと** —— (A) では
    帯を広げても**1日に生きる本数は増えません**（上限のほうが先に当たる）。

    `taken`（日 → 埋まっている時刻の集合）を渡すと、**予約の側を差し替えて**
    数えられます。**反実仮想の唯一の継ぎ目です** —— 既定は今までどおり
    `queue_lag.scheduled()` を読みます。渡した辞書は書き換えません（写します）。

        なぜ要るか（2026-08-29・最適化の回）: `queue_lag.band_lines()` は
        「この群だけを最優先しても間に合いません」と印字しますが、それは
        **いまの予約を動かせないものとした場合**の話です。動かす道具は
        同じファイルに在る（`--apply` の `--move`）ので、**「何本 どければ
        間に合うか」**を数えるには、予約の側を差し替えて歩けることが要ります。
        `queue_lag.scheduled` を差し替える手もありますが、あれは
        **呼ぶたびに新しい dict を作る**ので、外から本を落とすと
        `id()` では取りこぼします（この回に実際に踏んで、
        **「145本 どけても1日も動きません」という偽の答え**が出ました）。

    読めなければ `[]` —— 呼ぶ側は今までどおりに倒すこと（黙って粗くしない）。
    """
    if count <= 0:
        return []
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import queue_lag                                        # noqa: PLC0415
        if taken is None:
            rows = queue_lag.scheduled()
            if not rows:
                return []
            taken = queue_lag._taken(rows)
        taken = {d: set(s) for d, s in taken.items()}
        today = (now or datetime.now(JST)).date()
        if cap == "auto":
            try:
                from src import day_cap                         # noqa: PLC0415
                cap = int(day_cap.cap())
            except Exception:                                   # noqa: BLE001
                cap = 10
        grid = list(grid) if grid else _band_grid()
        band = set(grid)
        # **ここの上限は「その日の帯に何本 置いたか」で、その日のショートの数では
        # ありません。** 帯の外に在るショート（09:00 より前・14:00 以降）は
        # 数えていない ＝ (A)「1日 C本 まで」なら、**もう上限に達している日へ
        # 置くことがあります**（実測 2026-08-27: 今後60日の帯の空き 402枠 のうち
        # **105枠（26%）**、**16日ぶん**。`scripts/queue_lag.py` が毎回 印字します）。
        #
        # **直そうとして、いったん入れて外しました**（同日）。その日のショートの数で
        # 上限を見ると、`full` が並べ替えの鍵にしか効かないので
        # **手前の詰まった日を飛ばして遠い空き日へ跳び**、128本 の最後が
        # **+34日 → +163日** になりました（**5倍 悪化**）。
        #
        # **正しく直すには、この関数が時刻だけでなく日も返し、呼ぶ側が
        # `"YYYY-MM-DD@HH:MM"` で渡す必要があります**（`upload_only.split_when()` は
        # その形を読めます）。**ただしその形は「埋まっていたら失敗」**で、
        # 落ちた本はそのまま捨てになります（`build/` はコンテナと消える）。
        # きょうだいが同じ枠を取り合った実測が 2026-08-15 に在るので、
        # **釘づけに倒す前に、取り合いをどう避けるかを先に決めること。**
        seen: dict[object, bool] = {}
        _mine = lanes.lane()

        def _win(d) -> bool:
            if d not in seen:
                seen[d] = queue_lag._in_window(d)
            return seen[d]

        def _first(hm) -> object:
            """`next_publish_at()` と同じ探し方（時刻は動かさず、1日ずつ後ろ）。"""
            for i in range(1, horizon + 1):
                d = today + timedelta(days=i)
                if _win(d):
                    continue                    # 窓の日は飛ばす
                if hm not in taken.get(d, set()):
                    return d
            return None

        out: list[tuple[str, date]] = []
        for _ in range(count):
            best = None
            for hm in grid:
                d = _first(hm)
                if d is None:
                    continue
                # **その日の帯が上限に達しているか。** 達していれば (A) では死ぬので
                # **その日ごと後ろへ回します**（(B) なら生きるので、外しはしない）。
                full = 0 if cap is None else (
                    1 if sum(1 for t in taken.get(d, set())
                             if t in band) >= cap else 0)
                # 同着は車線で割る（`src/lanes.py`）。**控えを見ない**ので、
                # 同じ回に走っているきょうだいと相談せずに分かれます。
                key = (full, d,
                       (lanes.lane_of(hm[0] * 60 + hm[1], 30) - _mine)
                       % lanes.LANES, hm)
                if best is None or key < best[0]:
                    best = (key, hm, d)
            if best is None:
                break
            _, hm, d = best
            taken.setdefault(d, set()).add(hm)
            out.append((f"{hm[0]}:{hm[1]:02d}", d))
        return out
    except Exception as exc:                                    # noqa: BLE001
        print(f"[batch] 帯の空きが読めませんでした（既定の時刻へ倒します）: "
              f"{str(exc)[:80]}", flush=True)
        return []


def slots(count: int, hour: int, date_jst: str | None, hours: list[int],
          taken: set[int] | None = None, step_min: int = 60,
          taken_min: set[int] | None = None,
          lanes_n: int | None = None,
          ring: tuple[int, ...] | list[int] | None = None,
          live: bool = False, long_form: bool = False,
          now: datetime | None = None) -> list[str]:
    """各本の予約時刻の指定を返す（`upload_only.py` の第3引数の形）。

    `date_jst` が無ければ従来どおり全部同じ時刻 —— `next_publish_at` が
    埋まった日を飛ばすので、**結果として1日ずつ後ろに積まれます**（1日1本）。

    `date_jst` があると**その日に釘づけ**して、時刻のほうをずらします。
    これが「1日にN本」です。M14 の 8 の段はこの道が無くて止まっていました。

    ## 空き時刻を自分で読みます（2026-08-17。**3回持ち越された穴**）

    ここは長らく `hour + i` で、**その日に何が置いてあるかを一度も見ていませんでした。**
    埋まっている時刻に当たると `upload_only.py` が
    「すでに埋まっています。**翌日へは送りません**」で落ちるので、
    **作った1本がそのまま捨てられます**（`build/` はコンテナと一緒に消えるため）。

    避ける道は「**人が予約一覧を見て `--hours` に手で写す**」しかありませんでした。
    申し送りは3回とも同じことを言っています ——
    「手で `--hours` を写している限り、埋まっている時刻とぶつけて1本捨てる回が出る」。
    **人の記憶と手写しに依存する門は、この輪では毎回落ちる側**です。

    `taken` を渡さなければ `ledger_hours()` が控えから読みます（**API 0単位**）。
    実測（2026-08-17 の控え）: 09-01 は 9,10,12〜16 が埋まりで **空きは 11 だけ** ——
    前の回が API を叩いて手で出した答えと一致しました。
    既定の `hour + i` なら 9,10 とぶつけて**先頭2本を捨てていた**ところです。

    `--hours` を明示したときは**そちらを通します**（控えは上限側なので、
    取り消し済みの枠へ置き直す道を塞がない）。ただし**重なっていれば必ず言います。**

    ## `step_min` を足した理由（2026-08-18。**律速は投稿でも作りでもなかった**）

    ここは長らく**時の目盛りしか持っていませんでした**（`range(hour, 24)`）。
    だから1日に置けるのは最大24枠、実際に使う 9〜19時では **11枠**です。
    ところが投稿の本数枠は **1日92本**あり、作る側も1日118本まで出ています。
    **4倍以上足りないのは、置く場所の目盛りのほうでした**（予約262本の分は全部 `:00`）。

    実測（2026-08-18 の控え）: 予約257本が **09/27 まで40日ぶん**に伸びていて、
    公開は **1日6.4本**。同じ在庫を 30分きざみ（1日22枠）で置けば
    **13日ぶん**に縮みます。**追加の生成も、追加の投稿枠も要りません。**

    `next_publish_at` は最初から分を受け取ります（`minute_jst`）。
    **受け取る側はできていて、渡す側が時しか持っていなかった**だけです。

    **控えを時に落として読まないこと**（`ledger_minutes`）。落とすと
    10:00 の1本が 10:30 まで塞ぎ、目盛りを細かくした意味が消えます。
    だから `step_min < 60` では `taken`（時）を受け取りません ——
    **黙って粗く読むより、止まるほうがよい**（この輪では「片方だけ」が7回起きています）。

    **効きは前提として登録済みです**（`config/hypotheses.yaml`・9/05 判定）。
    1本あたりの再生が半分未満に落ちるなら、この道は間違いです。
    """
    if not date_jst:
        # **同じ時刻を count 回 返すと、1日1本になります**（この docstring の冒頭）。
        # `next_publish_at()` が「その時刻で最初に空いている**日**」を返すからです。
        # `ring` を渡すと、**別々の時刻を順に配る**ので、同じ日に `len(ring)` 本 入り、
        # そこから先が翌日へ回ります。**日を釘づけしないので `--date` とは別物です**
        # （窓の門も、埋まっていたら例外、も踏みません。空いている所を探すだけ）。
        #
        # 2026-08-26 に足しました。長尺 28本 が 21日 に散っていた（1.3本/日）のは、
        # ここが1つの時刻しか配っていなかったからです。**作る側は1日25本 出せています。**
        if ring:
            return [str(ring[i % len(ring)]) for i in range(count)]
        # **`--hour` を書かなかった回は、帯の空きから選びます**（2026-08-27 に足した）。
        # 理由と実測は `live_ring()` の docstring —— 既定の 09:00 は
        # **48日 先**まで埋まっていて、開いている前提の期日はいちばん遠くて 17日 先です。
        # **明示した回は触りません**（`--hour` / `--hours` は常に通す）。
        if live:
            picked = live_ring(count)
            if picked:
                print("[batch] 予約は**生きる帯の空き**へ置きます（控えから。API 0単位）: "
                      + ", ".join(picked[:8])
                      + (" …" if len(picked) > 8 else "")
                      + f"  ← 既定の {hour}:00 は埋まりで後ろへ流れます", flush=True)
                return picked
        return [str(hour)] * count
    if step_min != 60:
        return _slots_fine(count, hour, date_jst, hours, step_min, taken, taken_min,
                           lanes_n=lanes_n, long_form=long_form, now=now)
    if taken is None:
        taken = ledger_hours(date_jst)
    if hours:
        picked = hours
        clash = sorted(set(hours[:count]) & taken)
        if clash:
            print(f"[batch] **{date_jst} の {clash} は控えでは埋まっています。**"
                  " --hours が明示されているので続けますが、"
                  "取り消し済みの枠でなければ `upload_only.py` が落とします。",
                  flush=True)
        # **明示は通す。ただし帯の外なら必ず言う**（2026-08-29・最適化の回）。
        # `--hours` は「取り消し済みの枠へ置き直す道を塞がない」ために通していますが、
        # **黙って通すと、この節が塞いだ穴が `--hours` 越しに開いたままになります。**
        if not long_form:
            lo, hi = _band_bounds()
            outside = sorted(h for h in hours[:count]
                             if not lo <= h * 60 <= hi)
            if outside:
                print(f"[batch] [!] **{outside} は生きる帯（"
                      f"{lo // 60}:{lo % 60:02d}〜{hi // 60}:{hi % 60:02d}）の外です。**"
                      " --hours が明示されているので通しますが、"
                      "この回の実測で **帯の外は 0.7再生/本**（帯の中 537.2・"
                      "ショート 159本）—— **その本は 0再生 で公開されます。**"
                      " 帯へ入れたいなら `--hours` を外すこと（`_band_walk()` が"
                      "空きを拾い、埋まっていれば次の日の帯へ回します）",
                      flush=True)
    else:
        # **ショートは帯（09:00〜13:30）の外へこぼさない**（2026-08-29・最適化の回）。
        # `range(hour, 24)` は、帯が埋まると 14:00 以降へ静かにこぼれます。
        # 実測は `_band_walk()` の docstring —— 帯の中 537.2再生/本 対 帯の外 0.7再生/本。
        if not long_form:
            # `taken` は**時**なので、分に開いて渡します（09:00 の1本が
            # 09:30 まで塞がないように。`ledger_minutes()` の註と同じ理由）。
            walked = _band_walk(count, date_jst, hour * 60,
                                first_day_taken={h * 60 for h in taken},
                                lanes_n=lanes_n, now=now)
            if len(walked) == count:
                days = sorted({w.split("@")[0] for w in walked})
                if days != [date_jst]:
                    print(f"[batch] **{date_jst} の帯が埋まっているので、次の日の帯へ"
                          f"回します**: {', '.join(days)}　—— 帯の外は実測 0.7再生/本",
                          flush=True)
                return walked
            print(f"[batch] [!] 帯の空きが {len(walked)}枠 しか読めませんでした"
                  f"（{count}本 要ります）。**今までどおり時刻で埋めます**", flush=True)
        picked = [h for h in range(hour, 24) if h not in taken]
        if len(picked) < count:
            raise SystemExit(
                f"{date_jst} は {hour}時以降の空きが {len(picked)} 個しかありません"
                f"（{count} 本ぶん要ります／控えでの埋まり {sorted(taken)}）。\n"
                "        **別の日にするか、--hour を早めるか、本数を減らすこと。**\n"
                "        控えは上限側の見積りなので、取り消した本の枠も埋まりに数えます。\n"
                "        そこへ置き直すなら --hours で明示すること。"
            )
        if picked[:count] != list(range(hour, hour + count)):
            print(f"[batch] {date_jst} の埋まり {sorted(taken)} を避けて"
                  f" {picked[:count]} 時に置きます（控えから。API 0単位）", flush=True)
    if len(picked) < count:
        raise SystemExit(
            f"--hours が {len(picked)} 個しかありません（{count} 本ぶん要ります）"
        )
    bad = [h for h in picked[:count] if not 0 <= h <= 23]
    if bad:
        raise SystemExit(f"時刻が 0〜23 の外です: {bad}")
    if len(set(picked[:count])) != count:
        raise SystemExit(f"同じ時刻が2本以上あります: {picked[:count]}")
    return [f"{date_jst}@{h}" for h in picked[:count]]


def check_window(date_jst: str, force: bool) -> None:
    """M14 の比較の窓に置こうとしていないかを見る。**記憶に任せない。**

    中身は `src/measure_window.check` です。**窓を読むのは呼ばれた時**なので、
    検査が `M14_WINDOW` を差し替える手はそのまま効きます。
    """
    measure_window.check(date_jst, force=force, tool="batch_build.py --date",
                         window=M14_WINDOW)


def run(cmd: list[str], timeout: int, label: str = "",
        env: dict[str, str] | None = None) -> tuple[int, str]:
    """出力をそのまま流しながら、末尾も返す（VIDEO_ID を拾うため）。

    **並列で呼ばれます。** 途中経過を流すと複数本の行が混ざって読めなくなるので、
    1本ぶんを**1回の `print` にまとめて**出す（行の途中で割り込まれない）。

    `env` は**この1本だけ**に効きます。`os.environ` を書き換えないこと ——
    生成はスレッドで並列に走るので、**環境変数は全部のスレッドで共有**です。
    A/B の腕を `os.environ["YT_OPENING_MOTION"]` で切り替えると、
    **同時に走っている別の本の腕まで変わります**（そして台帳のラベルだけが
    正しいまま残るので、`src/motion_groups.py` が言う「ラベルが静かに嘘になる」
    形そのものになります）。
    """
    tag = f"[{label}] " if label else ""
    print(f"[batch] {tag}$ {' '.join(cmd)}", flush=True)
    try:
        proc = subprocess.run(
            cmd, cwd=ROOT, timeout=timeout,
            capture_output=True, text=True,
            env=({**os.environ, **env} if env else None),
        )
    except subprocess.TimeoutExpired:
        print(f"[batch] {tag}**{timeout}秒を超えたので打ち切りました**", flush=True)
        return 124, f"{timeout}秒を超えたので打ち切りました"
    out = (proc.stdout or "") + (proc.stderr or "")
    body = "\n".join(f"{tag}{line}" for line in out[-4000:].splitlines())
    print(body, flush=True)
    return proc.returncode, out


NEEDED_BINS = ("ffmpeg", "ffprobe", "open_jtalk")


def ensure_toolchain(root: Path = ROOT) -> bool:
    """生成に要る外部コマンドを確かめ、欠けていれば `setup.sh` を撃つ。

    **2026-08-22 に足した。この回、コンテナに ffmpeg も open_jtalk も
    入っていませんでした。** `scripts/setup.sh` は「何度でも安全」なのに、
    **生成の道の上で誰も呼んでいません** —— `scripts/preflight.py` は
    まったく同じ検査（`shutil.which`）を持っているのに、`batch_build` からも
    `src.pipeline` からも呼ばれていませんでした。

    実測の損: **3本 × 2回 ＝ 約8分**を使ってから `ffprobe が見つかりません`
    で全部落ちました。1周が実測 44分なので、**その回の2割**です。

    **落ちること自体は正しい。落ちる場所が8分先だったのが欠陥です**
    （下の「0. 投稿本数の枠」がまったく同じ形で、そこは 2026-08-17 に直っている）。
    しかも**1回目は図の重なりで落ちた**ので、本当の理由は作り直しの側に
    しか出ず、読む側からは道具の不足に見えません。**症状が理由を隠します。**

    **訊かずに撃ちます**（CLAUDE.md 2「人間の作業に依存する計画を立てない」）。
    入っていれば `which` 3回ぶんで戻るので、普通の回の費用はゼロです。

    **覆る条件**: `setup.sh` が壊れて毎回2分かかるようになったら、
    ここを「欠けていたら止めるだけ」に落とすこと。
    """
    missing = [b for b in NEEDED_BINS if not shutil.which(b)]
    if not missing:
        return True
    print(f"[batch] **道具が欠けています: {', '.join(missing)}** —— "
          "`scripts/setup.sh` を撃ちます（何度でも安全）", flush=True)
    try:
        proc = subprocess.run(["bash", str(root / "scripts" / "setup.sh")],
                              capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        print("[batch] **setup.sh が 15分で終わりませんでした。**", flush=True)
        return False
    still = [b for b in NEEDED_BINS if not shutil.which(b)]
    if still:
        tail = "\n".join((proc.stdout or "").splitlines()[-5:])
        print(f"[batch] **まだ欠けています: {', '.join(still)}**"
              f"（setup.sh exit={proc.returncode}）\n{tail}", flush=True)
        return False
    print(f"[batch] 入りました: {', '.join(missing)}", flush=True)
    return True


# 落ちた出力から「理由の1行」を取り出す形。**綴りを並べません。**
#
# 前に同じ所を、落ちる文言の一覧で書こうとした跡が `src/queue_mix.py` にあります
# （2026-08-23「手で持った名前が腐る」）。文言は増えるので、**例外の名前のほうを拾います** ——
# `RuntimeError: …` は言語が出す形で、こちらが書き換えても綴りが変わりません。
_EXC_LINE = re.compile(
    r"^(?:\S*\.)?([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception|Exit|Interrupt))\s*:\s*(.+)$"
)


def _failure_reason(out: str) -> str:
    """落ちた本の理由を、**1行**にする（台帳に積んで、次の回が数えられる形）。

    返すのは「例外の名前: 中身の頭」。取れなければ最後の非空行をそのまま返す。
    **分からないときに「不明」と書かないこと** —— 中身を捨てるのが元の欠陥です。
    """
    lines = [ln.rstrip() for ln in (out or "").splitlines() if ln.strip()]
    if not lines:
        return "出力が空のまま落ちました（殺された可能性。exit の値を見ること）"
    for ln in reversed(lines):
        m = _EXC_LINE.match(ln.strip())
        if m:
            return f"{m.group(1)}: {m.group(2)}"[:300]
    return lines[-1][:300]


#: `YT_OPENING_MOTION` を呼ぶ側が明示したか（したなら、こちらは何も決めない）。
_MOTION_ENV = "YT_OPENING_MOTION"


def motion_shortfall() -> tuple[int, str]:
    """**`opening_motion` の対照群は、判定の床まであと何本要るか。**

    ## なぜ生成側がこれを読むのか（2026-08-26・最適化の回）

    `config/hypotheses.yaml` の「冒頭0.9秒の動き」は、対照群を
    **`YT_OPENING_MOTION=0` で作らないかぎり永久に増えません**
    （`src/renderer.opening_motion_on` / `scripts/deadline_check.py` の
    `zero_means_never`）。そして機械は、足りない側を既に印字しています:

        src/motion_groups.py:447   「足りない側を `YT_OPENING_MOTION` を明示して作り足すこと」
        scripts/queue_lag.py       「opening_motion 判定できる日が出ません ← **本が足りない**」

    **その2つを読む口が、作る側にありませんでした。** `batch_build` は
    既定（動きあり）で作り続けるので、**作った本は全部、既に飽和している側**へ入ります。

    実測 2026-08-26（`src/judgeable.members`。再生が付く枠だけ）:

        処置(動きあり)  **20本** ／ 床 8   ← 250%。ここへ足しても判定は1日も早まらない
        対照(動きなし)  ** 3本** ／ 床 8   ← **あと5本。ここだけが期限を動かす**

    **これは「作る本数」の話ではありません。** `scripts/queue_lag.py` は
    予約の順番待ちが律速だと言っていて、**作る本数を増やすと待ちが伸びて悪化**します。
    ここでやるのは**同じ本数の行き先を変える**ことだけです ——
    **1本も増やさずに、`eta.py` が言う唯一の動かし方（前提を1件閉じる）へ寄せます。**

    ## 数え方

    - **床に入るのは「再生が付く枠」の本だけ**（`src/judgeable.members` が
      `day_cap.live_ids` で絞ります）。**生の8本ではなく3本**です ——
      前に作った対照8本のうち**5本が0再生の枠**に落ちました（`scripts/ab_slots.py`）。
    - **まだ投稿していない対照も数えます**（作った時点で腕は確定しているので）。
      数えないと、判定に入るまでの数日で毎周ぶん作り足して**大幅に超過**します。

    **覆る条件**: 投稿してみたら死んだ枠だった、という本はここでは分かりません
    （枠は予約のときに決まる）。`scripts/ab_slots.py` が入れ替えで直す側です。
    この関数は「まだ1本も作っていない」ぶんだけを埋めます。
    """
    try:
        from src import judgeable, motion_groups
    except Exception as exc:                                   # noqa: BLE001
        return 0, f"（群を読めませんでした: {exc}）"
    try:
        floor = int(judgeable.MEMBER_SOURCES["opening_motion"][1])
        live = len(judgeable.members("opening_motion").get("対照(動きなし)", []))
        # **作ったが、まだ投稿していない対照。** これを数えないと毎周ぶん作り足します。
        by_topic = motion_groups.motion_by_topic()
        posted = set(motion_groups.topic_by_video().values())
        pending = sum(1 for tid, on in by_topic.items() if not on and tid not in posted)
        # **床は「本数」ではなく「期限に間に合う本数」で数えること**（2026-08-26 に踏んだ）。
        #     ここは長らく `floor - live` でした。**本数は合っていました** ——
        #     08/26 の回はその印字（「あと 1本」）を読んで1本 作り、対照は 7→8本。
        #     **それでも `test_judgeable` / `test_deadline_check` /
        #     `test_hypothesis_deadline_reachable` の3件は赤のまま**でした。
        #     8本の公開日が 08/28・09/02・09/06・09/06・09/12・10/02・10/04・10/10 で、
        #     **期限 09/13 に間に合うのは 4本**だったからです（`last_useful_day` 09/07）。
        #     **縛っていたのは本数ではなく日付**で、この口はそれを見ていませんでした。
        #     判定の側（`judgeable.Floor.shortfall_in_time`）から引きます ——
        #     **同じ床を2つの口が別々に数えない**ため（この形は `queue_lag` で3件目）。
        in_time = None
        for f in judgeable.floors():
            if f.key == "opening_motion":
                in_time = f
                break
        if in_time is not None:
            live = in_time.in_time().get("対照(動きなし)", live)
            floor = in_time.min_per_group
    except Exception as exc:                                   # noqa: BLE001
        return 0, f"（群を読めませんでした: {exc}）"
    want = max(0, floor - live - pending)
    cut = (f"（期限 {in_time.deadline:%m/%d} に間に合うのは"
           f" {in_time.last_useful_day:%m/%d} までの公開）" if in_time is not None else "")
    if not want:
        return 0, (f"対照(動きなし) 判定に入る **{live}本** ＋ 作り置き {pending}本"
                   f" ／ 床 {floor}本 → **足りています**{cut}")

    # **置く所があるかを、作る前に数える**（2026-08-26。**踏みかけました**）。
    #
    # `docs/trigger_main.md` に、**この手を撃って外した回**が記録されています ——
    # 申し送りは3回続けて「対照を2本 作り足すこと」と書いていましたが、
    # `scripts/live_slots.py --plan` の実物は
    # **「期限までに空いた生きた枠は 0本。作った本はその日の 11本目 ＝ 死に枠」**。
    # そのまま撃っていたら、**2本ぶんの生成を 0再生の枠に捨てて**いました。
    #
    # **自動で寄せる仕掛けは、その失敗も自動にします。** だから同じ数え方
    # （`live_slots._free_live_before`）をここから読みます —— `judgeable.members`
    # が標本を絞るのと**同じ `day_cap.live_ids` の定義**なので、
    # 「作れば判定に入る」と「入らない」がここで一致します。
    room = _live_room()
    if room is None:
        return want, (f"対照(動きなし) **期限に間に合う {live}本** ＋ 作り置き {pending}本"
                      f" ／ 床 {floor}本 → **あと {want}本**{cut}"
                      "（置き先を数えられなかったので、絞っていません）")
    need = min(want, room)
    why = (f"対照(動きなし) **期限に間に合う {live}本** ＋ 作り置き {pending}本 ／ 床 {floor}本"
           f" → **あと {want}本**{cut} ／ 期限までに空いた生きた枠 **{room}本**"
           f" → **この回で作るのは {need}本**")
    if need < want:
        why += ("  [!] **足りないのは本ではなく、置き先です。**"
                " 作っても その日の上限の外（0再生）に入るので、判定には入りません。"
                "**効くのは「A/B でない本を1本 生きた枠から押し出して、そこへ入れる」"
                "まで通した1手だけ**（`python scripts/live_slots.py --plan`）。")
    return need, why


def _live_room() -> int | None:
    """**新しい本が入れる、生きた枠の数。**（API 0単位）

    数え方は `scripts/live_slots.py` の1か所に置いてあります。**写さないこと** ——
    この輪は「同じことを2か所が別々に言っていて、片方しか読まれていない」で
    何度も外しています。読めなければ `None`（＝絞らない）を返します。

    ## **空いた生きた枠を、二度 数えないこと**（2026-08-26 に踏みかけた）

    `_free_live_before()` を素の盤面に当てると **5本** 返ります。
    ところがその 5本は、**`live_slots.plan()` が既に取りに行っている枠**です ——
    あの手は「**もう予約に在る**対照の本を、死に枠から生きた枠へ動かす」もので、
    **生成を1本も要りません。** 同じ枠を新しい本にも数えると、
    **どちらか片方は必ず死に枠に落ちます**（実測: 手を置くと 5 → **0**）。

    **安いほうが先です。** 入れ替えは 50単位、生成は1本 数分＋1,600単位。
    だからここは**入れ替えを済ませた後の盤面**で数えます。
    つまり `need` は「**入れ替えでは埋まらず、本当に作るしかないぶん**」だけになります。
    """
    try:
        import live_slots
        from src import judgeable

        board = live_slots.Board(live_slots._rows())
        limit = next((f.deadline for f in judgeable.floors()
                      if f.key == "opening_motion"), None)
        if limit is None:
            return None
        live_slots.plan(board)          # **盤面を進める**（出力は要らない）
        return live_slots._free_live_before(board, limit)
    except Exception:                                          # noqa: BLE001
        return None


def motion_plan(n: int, shortfall: tuple[int, str] | None = None) -> list[bool | None]:
    """この回の `n` 本を、どちらの腕で作るか。`True`＝動きあり／`False`＝動きなし。

    `None` は「決めない」＝ `src/renderer.opening_motion_on()` の既定に任せる、
    という意味で、**呼ぶ側が `YT_OPENING_MOTION` を明示している回**がこれです。
    **人（や別の回）が明示した指示を、こちらが上書きしないこと。**

    ## 半分までしか対照にしません

    `src/motion_groups.paired()` は**同じ JST 日に両群が居る日**しか標本に
    数えません（「片方しか居ない日の本は、動きの差とその日の配信の差を分けられない」）。
    1回ぶんを全部 対照にすると、**その日が片群だけの日になりかねません。**
    半々で作れば、同じ回の本は近い日へ入るので**共有日になります。**
    """
    if os.environ.get(_MOTION_ENV) is not None:
        return [None] * n
    if n <= 0:
        return []
    # **数え直さないこと。** `motion_shortfall()` は盤面ぜんぶを引き直します
    # （`live_slots.plan()` を通す）。呼ぶ側が既に数えていたら、それを使います ——
    # 2回 数えると遅いだけでなく、**2つの答えが食い違う隙**ができます。
    need, _why = shortfall if shortfall is not None else motion_shortfall()
    if need <= 0:
        return [True] * n
    off = min(need, max(1, n // 2))
    # **先頭に固めないこと。** 落ちた本は先頭から撃ち直されるので、
    # 固めると撃ち直しの回が片群だけになります。交互に置きます。
    plan: list[bool | None] = [True] * n
    if off:
        step = max(1, n // off)
        for i in range(off):
            plan[min(n - 1, i * step)] = False
    return plan


_THEME_ENV = "YT_THEME_INDEX"


def theme_base() -> int:
    """**この回の配色の起点**（チャンネルの投稿済み本数）。読むのは1回だけ。

    ## なぜ「1回だけ」が要るのか（2026-08-28 の最適化の回・実測）

    `build_one()` は1本につき子プロセスを立て、その全部が
    `src/pipeline.py` で `history.posted_topic_ids()` を呼んでいました
    （1回 ≒ **25単位**）。窓 08/27 16:00 JST の `data/day_quota.jsonl` で
    **108回**（`by` が `history.py:_scan`・間隔の中央値 **2.0秒**）——
    枠が生きていれば **約2,700単位 ＝ 日枠の 27%** です。

    ## そして、読み直しても**答えは動きません**。だから色が揃っていました

    `build_one` は `--dry-run` で、**作っているあいだ1本も投稿されません。**
    つまり `len(posted_topic_ids())` は**この回のあいだ定数**で、
    `visuals.theme_for(topic_id, index)` は `index` が来ると
    **テーマIDを見ません**（`THEMES[index % 5]`）。
    → **1回で作った本は、全部おなじ配色**になります。

    実測（`data/critique_queue/` の実物の1コマ目・背景色で判定）:

        08/27 21:56-21:57  **8本すべて** THEMES[2]
        08/28 08:40        4本すべて THEMES[1]
        08/28 00:59        4本すべて THEMES[0]
        08/27 10:34        4本すべて THEMES[0]
        08/27 08:07        4本すべて THEMES[1]
        08/27 20:58        3本すべて THEMES[4]

    `visuals.theme_for` の docstring は「index を渡すと**連続する回が
    必ず違う色になる**ので、こちらを使うこと」と書いてあり、
    **渡し方のほうが、その保証を外していました。**
    `CLAUDE.md` は「**同じ絵を続けないこと**」を収益化の条件として挙げ、
    ポリシーの引用は「同じチャンネルの動画を続けて数本視聴した後、
    繰り返しのように感じられる可能性のあるコンテンツ」です。

    **読み直しをやめるのと、色を散らすのは、同じ1つの直しです** ——
    起点を1回だけ読んで、**本ごとに +1 して渡します。**

    ## 覆る条件

    - `visuals.theme_for` が `index` でもテーマIDを混ぜるようになったら、
      ここで散らす必要は無くなります（**起点を1回だけ読むほうは残すこと**）
    - 読めなかった回は **0** を返します。色は回の中では散りますが、
      回をまたぐと重なりえます —— **読めないことを、作らない理由にはしません。**

    ## **API を1単位も使いません**（手元の控えを数えるだけ）

    最初この関数は `history.posted_topic_ids()` を呼んでいました。**1回で足りる**
    ので 108回 が 1回 にはなりますが、**その1回が並列の手前に立ちます** ——
    `tests/test_batch_parallel.py::test_builds_actually_overlap` が
    **1.1秒 の増**で落ちて、そう教えました（枠切れの窓では 403 まで待つ）。

    起点に要るのは「**回をまたいで違う数**」だけで、正確な投稿本数ではありません。
    `data/uploaded.jsonl` の行数は投稿のたびに増えるので、**それで足ります。**
    控えは git で配られるので、枠が尽きた窓でも読めます。
    """
    try:
        path = ROOT / "data" / "uploaded.jsonl"
        if not path.exists():
            return 0
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines()
                   if line.strip())
    except Exception as exc:                                   # noqa: BLE001
        print(f"[batch] 配色の起点を読めませんでした（0 から回します）: {exc}",
              flush=True)
        return 0


def build_one(topic: dict, long_form: bool, motion: bool | None = None,
              theme_index: int | None = None) -> dict:
    """**作るところまで**を1本ぶん。予約はしない（呼ぶ側が直列でやる）。

    ここが並列に走る部分です。**予約を混ぜないこと** —— `upload_only.py` は
    `next_publish_at` と待ち行列（`critique_queue`）という**共有の状態**を触るので、
    同時に走らせると予約時刻がぶつかります（8/15 03:48 の二重起動と同じ壊れ方）。

    `motion` は `opening_motion` の腕（`None`＝既定に任せる）。**子プロセスの環境で
    渡します。** `os.environ` を書き換えると、並列で走っている別の本にも効きます。
    """
    tid = topic["id"]
    row: dict = {"topic": tid, "calc": topic["calc"], "video_id": "", "error": ""}

    # **1本ぶんの秒数を残す。** これが無かったので「`--jobs` の上限」が
    # 4回持ち越されました（上の節）。**落ちた本も測ります** ——
    # 落ちるまでに使った時間も、他の本を待たせているからです。
    started = datetime.now(JST)
    cmd = [sys.executable, "-m", "src.pipeline", "--topic", tid, "--dry-run"]
    if not long_form:
        cmd.append("--short")
    env = {} if motion is None else {_MOTION_ENV: "1" if motion else "0"}
    # **配色の番号を渡す**（`theme_base()` の docstring に実測と理由）。
    # 渡した回は、子プロセスがチャンネルを読み直しません（1本 ≒ 25単位）。
    if theme_index is not None:
        env[_THEME_ENV] = str(theme_index)
    code, out = run(cmd, BUILD_TIMEOUT, tid, env=env or None)
    row["build_sec"] = round((datetime.now(JST) - started).total_seconds(), 1)
    if code != 0:
        row["error"] = f"生成が失敗（exit {code}）"
        # **落ちた理由を台帳に残す**（2026-08-24 に足した。**症状が理由を隠していました**）。
        #
        # ここは `code, _ = run(...)` で、**出力を捨てていました。** 出力は
        # `run()` が端末へ流しますが、**その端末はその回のコンテナと一緒に消えます。**
        # 残るのは `data/batch_runs.jsonl` の `生成が失敗（exit 1）` の1行だけで、
        # **次の回は「何が落ちたか」を1文字も持っていません。**
        #
        # 実測の損: 2026-08-24 18:58 の回が **8本すべて exit 1** で落ちました。
        # 台帳に理由が無いので、この回は**同じ本をもう一度撃って**（約4分）
        # 理由を取り直すところから始めています。**長尺は直近 15/31 本（48%）しか
        # 通っておらず**、`config/hypotheses.yaml` の 08-31 の判定
        # （「長尺は1日4本 作れる」）は、この歩留りにそのまま乗っています。
        #
        # **`build_one` は `--dry-run` なので、ここを残すのに副作用はありません。**
        row["error_reason"] = _failure_reason(out)
        row["error_tail"] = "\n".join(out.strip().splitlines()[-25:])[-2000:]
        row["built"] = False
        return row

    # **contact sheet は投稿の前に作る。**
    #
    # 最初に書いたときここを飛ばしていて、**1本目の投稿でそのまま踏みました**
    # （2026-08-15、`H28qfOxuJF0`）。`critique_queue.stash()` は
    # `inspect.jpg` が無いと材料を残さないので、**その動画は独立評価を
    # 永久に回せなくなります**（`build/` はコンテナと一緒に消える）。
    # `docs/CRITIQUE.md` が「投稿の時点から残る」と書いているのはこの1枚のことです。
    code, _ = run([sys.executable, "scripts/inspect_build.py", tid], UPLOAD_TIMEOUT, tid)
    if code != 0:
        # **止めません。**contact sheet は評価の材料で、動画そのものではない。
        # 投稿が途切れるほうが損なので、印だけ残して先へ進みます。
        row["error"] = "contact sheet を作れず、独立評価の材料が残りません"
    row["built"] = True
    row["make_sec"] = round((datetime.now(JST) - started).total_seconds(), 1)
    # **その本の腕を、結果の行にも残す。** 回のおしまいの1個の旗は、
    # 腕が混ざった回には書けません（下の `mixed` を見ること）。
    row["opening_motion"] = (renderer.opening_motion_on() if motion is None
                             else bool(motion))
    # **群のラベルは、作った時に書く**（2026-08-23 に踏んで足した）。
    # それまで `opening_motion` は**回のおしまいに1回だけ**書いていたので、
    # **途中で落ちると、実際に作った本のラベルが丸ごと消えました** ——
    # 実測: 8本頼んで6本できた回が落ち、`data/batch_runs.jsonl` に1行も残らず、
    # **6本が「どちらの群か分からない本」になった**（`src/motion_groups` が落とす）。
    # A/B は「あとから推定する」と必ず壊れる。**作るたびに1行残す。**
    _flag_line(tid, row["opening_motion"])
    return row


def _flag_line(tid: str, motion: bool | None = None) -> None:
    """1本ぶんの群のラベルを、その場で `data/build_flags.jsonl` に足す。

    **`motion` は、その本を実際に作った値**です。ここで
    `renderer.opening_motion_on()` を読み直さないこと ——
    腕は子プロセスの環境で渡すので、**この親プロセスの値とは別**になり得ます。
    """
    try:
        rec = {"at": datetime.now(JST).isoformat(timespec="seconds"),
               "topic": tid,
               "opening_motion": (renderer.opening_motion_on() if motion is None
                                  else bool(motion))}
        FLAGS.parent.mkdir(parents=True, exist_ok=True)
        with FLAGS.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as exc:                                   # noqa: BLE001
        # **記録に失敗しても作るのは止めない。**ただし黙らない。
        print(f"[batch] 群のラベルを残せませんでした（{tid}）: {exc}", flush=True)


def video_id_of(out: str) -> str:
    for line in reversed(out.splitlines()):
        if line.startswith("VIDEO_ID "):
            return line.split(None, 1)[1].strip()
    return ""


def _median(xs: list[float]) -> float:
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return 0.0
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def _print_ab_groups(topics: list[dict]) -> None:
    """選んだ本が、走っている A/B のどちらの群に落ちるかを出す（**API 0単位**）。

    ## なぜ要るか（2026-08-29 13:4x に測って足した）

    **振り分けは全部テーマIDだけの純関数**です（`ab_split.EXPERIMENTS[*].split`）。
    つまり**作る前に、どちらの群になるか分かります。** ところがそれを見る口が
    どこにも無く、13:4x の回は `slide_pace` の床（速い あと2本 ／ 遅い あと2本）を
    埋めるのに、**`python -c` で `pick()` を呼んで手で割りました。**

    `live_slots.py --plan` は「どの群があと何本 足りないか」を出しますが、
    **その群に落ちる題がどれかは言いません。** 逆にこの道具は題を選びますが、
    **選んだ題がどの群かを言いませんでした。** 床を埋める回は、
    その2つを毎回 人が突き合わせています。

    ## 覆る条件

    `pick()` が「足りない群」を見て並べるようになったら、この印字は要りません
    （そのときは `_hoist_floor_topics()` の隣に置くのが近い）。
    """
    try:
        from src import ab_split
    except Exception as exc:                                  # noqa: BLE001
        print(f"[pick] 群が読めませんでした: {str(exc)[:120]}")
        return
    ids = [str(t["id"]) for t in topics]
    print("\n[pick] **この本が落ちる A/B の群**"
          "（振り分けはテーマIDだけの純関数なので、作る前に決まっています）")
    for name, exp in sorted(ab_split.EXPERIMENTS.items()):
        try:
            labels = [ab_split.group_of(exp, i) for i in ids]
        except Exception as exc:                              # noqa: BLE001
            print(f"        {name:<14} 読めません: {str(exc)[:80]}")
            continue
        tally: dict[str, int] = {}
        for lab in labels:
            tally[lab] = tally.get(lab, 0) + 1
        shown = " / ".join(f"{k} {v}本" for k, v in sorted(tally.items()))
        print(f"        {name:<14} {shown}")
        for i, lab in zip(ids, labels):
            print(f"          {lab:<8} {i}")
    print("        **あと何本 要るかは `python scripts/live_slots.py --plan`**"
          "（『あと N本 足りません』の行）。**入れ替えで埋まらない群は、"
          "本を足すしかありません**（`docs/trigger_main.md` §4 の 4）。")


def _print_live_days(days: int = 45, want: int = 8) -> None:
    """**本当に生きる枠が残っている日**を、早い順に出す（API 0単位）。

    ## なぜ `live_plan()` の答えと別に要るか（2026-08-29 13:4x に測って足した）

    `live_plan()` の上限は「**その日の帯に何本 置いたか**」で数えており、
    **その日のショートが既に上限に達しているかは見ていません**（同関数の中の註。
    直そうとして入れ、`+34日 → +163日` の悪化で外した経緯もそこに在ります）。
    だから既定の置き先は、**もう上限に達している日**を選ぶことがあります ——
    実測 2026-08-27: 今後60日の帯の空き 402枠 のうち **105枠（26%）**がそれ。

    `scripts/live_slots.py` の `Board` は `day_cap.live_ids()` を通してから
    数えるので、**そちらは取り違えません。** ここはその読みを借りて
    **印字だけ**します（置き先は変えません）。**呼ぶ側が `--date` / `--hours` で
    釘づけするための材料**で、`live_plan()` の挙動は1文字も動かしていません。

    実測 2026-08-29 13:4x: **09/23 までは全日が上限（10本）で満杯**、
    いちばん早い生きた枠は **09/24（1枠）**、次が 09/28（4枠）・09/30（3枠）。
    同じ回の既定（`live_plan`）は **09/08 の 9:30/10:30/13:30** を返しており、
    **そこへ置いた本は 0再生の側（595本 中 143本）に入るところ**でした。

    ## 覆る条件

    `live_plan()` が `Board` と同じ数え方になったら、この印字は要りません
    （そのときは「既定のままで置ける」と1行 書いて、この関数を消すこと）。
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import live_slots                                       # noqa: PLC0415
        board = live_slots.Board(live_slots._rows())
        live = board.live()
    except Exception as exc:                                    # noqa: BLE001
        print(f"[pick] 生きた枠が読めませんでした: {str(exc)[:120]}")
        return
    today = board.now.date()
    found: list[str] = []
    for i in range(days + 1):
        d = today + timedelta(days=i)
        free = board._slots(d, same_day=False, live=live)
        if not free:
            continue
        shown = ", ".join(f"{m // 60}:{m % 60:02d}" for m in free[:6])
        found.append(f"        {d.isoformat()}  空き {len(free)}枠  {shown}")
        if len(found) >= want:
            break
    print("\n[pick] **本当に生きる枠が残っている日**"
          f"（`live_slots.Board`。上限 {board.cap}本/日・帯 09:00〜13:30 JST）")
    if not found:
        print(f"        {days}日 先まで、生きた枠は1つも空いていません。"
              " **足した本はその日の誰かを押し出すだけ**です"
              "（`python scripts/live_slots.py --plan --all`）。")
    else:
        for line in found:
            print(line)
        print("        **既定（`--date` も `--hours` も無い回）はこの表を見ません** ——"
              "`live_plan()` は帯の枠しか数えないので、"
              "**もう上限に達している日を選ぶことがあります**。"
              " 判定の床を埋める回は、上の日を `--date` / `--hours` で釘づけすること"
              "（`--hours` は**時だけ**なので、:30 の空きは掴めません）。")


def report() -> int:
    """台帳を `jobs` 別に並べる。**生成しません**（数秒で終わります）。

    見るのは2つだけ。

        速くなった倍率   直列の合計 ÷ 壁時計。**jobs に近いほど、待ち時間が素直に重なっている**
        1本あたりの中央値 **jobs を上げるほど伸びていたら、そこが上限**

    倍率だけでは上限が出ません（本数と題材で動くので）。
    **太り始めたかどうかが、同じ走りの中で比べられる唯一の量**です。
    """
    if not LOG.exists():
        print("まだ1回も走っていません（data/batch_runs.jsonl が空）。")
        return 1
    rows = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    timed = [r for r in rows if r.get("jobs") and r.get("wall_sec")]
    print(f"=== batch の走り {len(rows)} 回（うち時間が入っているのは {len(timed)} 回）===")
    if not timed:
        print("\n  **時間の入った走りがまだありません。**")
        print("  2026-08-15 22:3x より前の走りには `jobs` も秒数も入っていません")
        print("  （入れていなかったので、`--jobs` の上限が4回持ち越されました）。")
        print("  次に `batch_build.py` を走らせた回から、ここに並びます。")
        return 1

    # **尺の欄を落とさないこと**（2026-08-29 23:xx に足した）。この一覧は
    # 走りを時刻順に並べるだけですが、**1本あたりは尺で桁がちがいます**
    # （ショート 3分台／長尺 8〜13分）。尺が見えないと、隣り合う2行の差を
    # `jobs` の差として読みます —— 下の表がまさにそれで壊れていました
    # （`_jobs_report` の註）。
    print("\n  日時              尺  同時 本数  壁時計   直列なら  倍率  1本あたりの中央値")
    for r in timed:
        per = [float(x["build_sec"]) for x in r.get("results", [])
               if x.get("build_sec")]
        med = _median(per)
        print(f"  {r['at'][5:16]:<16} {'長尺' if r.get('long') else 'ショ':<3}"
              f" {r['jobs']:>3} {r.get('count', len(per)):>4}"
              f" {r['wall_sec']/60:>7.1f}分 {(r.get('serial_sec') or 0)/60:>8.1f}分"
              f" {str(r.get('speedup') or '—'):>5}  {med/60:>6.1f}分")

    # **1回の走りの中で出した「倍率」は、自分に甘い。**
    #
    # `speedup` は「1本ずつの秒数の合計 ÷ 壁時計」ですが、その1本ずつの秒数は
    # **既に混雑で太った後の値**です。太るほど分子も大きくなるので、
    # **混雑しているときほど倍率が良く見えます**（8/15 22:3x の実測で 4.2倍と出た。
    # 本当は 2.6倍）。**割る相手は、いちばん空いている走りの1本あたり**です。
    #
    # ## **2026-08-29 21:xx に、この節が逆の答えを出していました**
    #
    # ここは長らく **`max(per_run_thru[j])`** ——「その jobs で**いちばん良かった
    # 走り**」——で1時間あたりを出し、**失敗した本も1本として数えて**いました。
    # その2つが重なると、こうなります（実測・`data/batch_runs.jsonl` 49行目）:
    #
    #     {"at": "2026-08-17T03:20", "jobs": 1, "wall_sec": 2.2,
    #      "results": [{"video_id": "", "error": "生成が失敗（exit 1）",
    #                   "build_sec": 2.2}]}
    #
    # **2.2秒 で失敗した1本**が「1本 ÷ 2.2秒」＝ **1時間あたり 1636本** に化け、
    # `max` なので**その1件だけ**が jobs=1 の代表になります。結果、この道具は
    # **「出る本数がいちばん多いのは同時 1。そこが上限です」**と印字していました。
    #
    # **それは、この道具が答えるべき問いの逆**です。同じ台帳を
    # **失敗を外して・走りの中央値**で読むと、こうなります:
    #
    #     同時   いま(max・失敗こみ)     直したあと(中央値・失敗ぬき)
    #       1        1636.4本/時                7.0本/時
    #       2         371.1本/時               13.2本/時
    #       3          62.6本/時               34.4本/時   ← いまの既定
    #       4          66.9本/時               53.4本/時
    #       5          92.2本/時              **86.5本/時**  ← 峰
    #       6          90.9本/時               53.0本/時
    #       8         103.4本/時               47.7本/時
    #
    # **既定の 3 は、峰の 4割**です。**`--jobs 5` を1回 試すこと。**
    # ただし **5 と 6 は走りが 2回 と 3回 しかありません**（下の「走り」の欄）。
    # **走りの少ない峰を、そのまま既定にしないこと。**
    #
    # **覆る条件**: 走りが増えて峰が動いたら、この表の数ごと書き換えること
    # （数を写しているのは、`max` に戻す回への証拠として残すためです）。
    def _made(res: list[dict]) -> list[dict]:
        """**実際に本になったものだけ。** 失敗は本ではありません。

        **見るのは `error` だけ**です。`video_id` の有無で判じないこと ——
        古い行と検査の仕掛けは `video_id` を持たないので、
        そちらを門にすると**全部 落ちて「走り 0回」**になります
        （2026-08-29 に踏んだ。`tests/test_batch_timing.py` が2件 赤くなった）。
        """
        return [x for x in res if x.get("build_sec") and not x.get("error")]

    _jobs_report(timed)
    return 0


def _jobs_report(timed: list[dict]) -> None:
    """**jobs べつの表を、尺ごとに分けて出す。**（2026-08-29 23:xx に測って直した）

    ## なぜ分けるか —— **分けないと、尺の差が jobs の差に化けます**

    ここは長らく、ショートと長尺を**1つの表にまとめて**いました。
    ところが1本あたりの時間は尺で桁がちがいます（実測・中央値）:

        ショート  **3.2〜3.7分**（jobs 1〜8 で ほぼ平ら）
        長尺      **8.7〜13.1分**

    そして **jobs べつの走りが、尺で偏っています**:

        jobs 4 / 5 / 6 / 8   ほぼ全部が**ショート**（08-16〜08-21）
        jobs 1 / 2 / 3       長尺 61本 のほとんどがここ（08-22〜08-29）

    だから混ぜた表は「jobs を上げると 1本あたりが速くなる」と出ます。
    **速いのは jobs ではなく、その jobs で走ったのがショートだったから**です。
    実際、この形で出た結論は

        **出る本数がいちばん多いのは同時 5**（1時間あたり 86.5本・走り 2回）
        …… **そこが上限です。** `--jobs 5` を1回 試すこと

    でしたが、**その「同時 5」の走り 2回 は 08-16 のショート 5本 ずつ**です。
    尺で割ると峰は消えます（下の表）。

    **同じ形が、この repo で3件目です**（`build_perf._time_split` の
    「尺 × 再生 = -0.33」＝ 08/15 の切替の言い換え／
    2026-08-29 の `--report` の `max` ＝ 2.2秒 で落ちた1本）。
    **共通するのは「一斉に切り替えた作りは、全部この形になる」。**

    ## 覆る条件

    - **同じ尺の中で jobs が 4以上 の走りが 5回 たまったら**、そちらだけで
      峰が言えます。いまは長尺の jobs 4以上 が **1回**（08-20 の 8）しかないので、
      **長尺の側の上限は「まだ測っていない」**が正しい答えです
    - 1本あたりが尺で桁ちがいでなくなったら（形式を変えたときなど）、
      この分けは要らなくなります
    - **検査は `tests/test_batch_timing.py`**
    """
    def _made(res: list[dict]) -> list[dict]:
        """**実際に本になったものだけ。** 失敗は本ではありません。

        **見るのは `error` だけ**です。`video_id` の有無で判じないこと ——
        古い行と検査の仕掛けは `video_id` を持たないので、
        そちらを門にすると**全部 落ちて「走り 0回」**になります
        （2026-08-29 に踏んだ。`tests/test_batch_timing.py` が2件 赤くなった）。
        """
        return [x for x in res if x.get("build_sec") and not x.get("error")]

    groups: list[tuple[str, list[dict]]] = [
        ("ショート", [r for r in timed if not r.get("long")]),
        ("長尺", [r for r in timed if r.get("long")]),
    ]
    groups = [(name, rs) for name, rs in groups if rs]
    if len(groups) > 1:
        print("\n  **尺ごとに分けて出します**（混ぜると、尺の差が jobs の差に化けます ——"
              " 1本あたりはショート 3分台・長尺 8〜13分 で桁がちがい、"
              "**jobs 4以上 の走りはほぼ全部ショート**です。`_jobs_report` の註）")

    for name, rs in groups:
        by_jobs: dict[int, list[float]] = {}
        per_run_thru: dict[int, list[float]] = {}
        for r in rs:
            per = [float(x["build_sec"]) for x in r.get("results", [])
                   if x.get("build_sec")]
            if per:
                by_jobs.setdefault(int(r["jobs"]), []).extend(per)
            ok = _made(r.get("results") or [])
            if ok and r.get("wall_sec"):
                per_run_thru.setdefault(int(r["jobs"]), []).append(
                    len(ok) / float(r["wall_sec"]))
        if not by_jobs:
            continue

        def _thru(j: int, _t=per_run_thru) -> float:
            """その jobs の1時間あたり。**max ではなく中央値**（上の註）。"""
            return _median(_t.get(j, [0.0])) * 3600.0

        js = sorted(by_jobs)
        base = _median(by_jobs[js[0]])
        base_thru = _thru(js[0])

        print(f"\n  **jobs 別・{name}**（1本あたりが太り始めた点と、実際に出た本数）")
        print("    **1時間あたりは走りの中央値で、失敗した本は数えません**"
              "（max ＋ 失敗こみだと、2.2秒 で落ちた1本が 1636本/時 に化けます）")
        print("    同時  本数 走り  1本あたり  太り方   1時間あたり  空いているときの何倍")
        for j in js:
            med = _median(by_jobs[j])
            swell = med / base if base else 0.0
            thru = _thru(j)
            gain = (thru / base_thru) if base_thru else 0.0
            print(f"    {j:>3} {len(by_jobs[j]):>5}本 {len(per_run_thru.get(j, [])):>3}回"
                  f" {med/60:>8.1f}分 {swell:>7.2f}倍"
                  f" {thru:>10.1f}本 {gain:>13.2f}倍")

        if len(js) < 2:
            print(f"    **{name}は、まだ1種類の `jobs` しか走っていません。** 上限は言えません。")
            continue

        top = max(js, key=_thru)
        worst = max(js, key=lambda j: _median(by_jobs[j]))
        swell = _median(by_jobs[worst]) / base if base else 0.0

        if swell >= 1.3:
            print(f"    **同時 {worst} で1本あたりが {swell:.2f}倍に太っています。**"
                  " 待ち時間だけでなく、こちらの資源も取り合い始めています。")
        else:
            print(f"    1本あたりは最大でも {swell:.2f}倍で、**まだ太っていません。**")

        # **太り始めた ≠ 上限。** 1本あたりが遅くなっても、同時に走る本数が
        # それ以上に増えていれば、**1時間あたりに出る本数は増え続けます。**
        # 止めるのは「太ったから」ではなく「**出る本数が増えなくなったから**」。
        runs_at_top = len(per_run_thru.get(top, []))
        if top == max(js):
            print(f"    それでも**いちばん出たのは同時 {top}**です"
                  f"（1時間あたり {_thru(top):.1f}本・走り {runs_at_top}回）。"
                  " **太り始めた点は上限ではありません。**")
            print(f"    まだ上げられます。次は同時 {max(js)*2} を1回。"
                  " **出る本数が増えなくなったところが上限**です。")
        else:
            print(f"    **出る本数がいちばん多いのは同時 {top}**"
                  f"（1時間あたり {_thru(top):.1f}本・走り {runs_at_top}回）で、"
                  "それより上げると減っています。**そこが上限です。**")
            if DEFAULT_JOBS != top and _thru(top) > 0 and _thru(DEFAULT_JOBS) > 0:
                print(f"    **既定は同時 {DEFAULT_JOBS}"
                      f"（1時間あたり {_thru(DEFAULT_JOBS):.1f}本）**"
                      f" ＝ 峰の {_thru(DEFAULT_JOBS)/_thru(top):.0%}。"
                      f" **`--jobs {top}` を1回 試すこと。**")
        if runs_at_top < 5:
            print(f"    [!] **その峰の走りは {runs_at_top}回 しかありません。**"
                  " 走りの少ない峰を、そのまま既定にしないこと"
                  "（1回 走らせるたびに、この行は自分で消えます）。")


def _pull_verdicts_first() -> None:
    """**予約の入れ替えを、この回の投稿が単位を使い切る前に撃つ。**

    ## なぜ要るか（2026-08-26・最適化の回。**サムネイルと同じ穴の、2件目**）

    下の `_push_thumbnails_first()` の註がこう書いています ——
    「`thumbnails.set` は 50単位しか要らないのに、**いつも投稿の後ろに
    並んでいた**ので一度も順番が回ってきませんでした。**一覧が悪いのでは
    ありません。押せる時刻に、押す手順が無かっただけです**」。

    **`scripts/queue_lag.py --apply` が、いま同じ所に立っています。**
    こちらも 1回 50単位（`videos.update`）ですが、**手で撃つ道具のままなので、
    順番そのものが無い。** 実測（2026-08-26 03:1x）:

        入れ替え **26手 ＝ 2,600単位** で、判定が **合計8日 早まる**
          title_form  09/08 → 09/06（2日）  hook_form  09/11 → 09/05（6日）
        同じ窓で上げた本 **11本 ＝ 概算 17,600単位**
        **日枠の 403 は、その窓で 22回 観測**

    **17,600単位 は見つかっていて、2,600単位 が見つかっていません。**

    8/26 05:0x の申し送りは「**16:00 JST を過ぎたら、まず `--plan` を撃つこと**」
    でした。**申し送りでは直りません** —— 次に起きた回が16時をまたぐとは限らず、
    またいでも投稿のほうが先に窓を空にします。だから**手順にします。**

    ## なぜサムネイルより前か

    `scripts/eta.py` が毎回印字しているとおり、**軌跡の腕が動くのは
    前提を1件閉じたときだけ**です。入れ替えは**その日を手前に倒す唯一の手**。
    サムネイルは「あれば良いもの」。**同じ50単位なら、こちらが先です。**

    **ただし「θ は待ち時間の逆数」ではありません**（2026-08-26・最適化の回に訂正）。
    ここは「`rate = p·log(g)·θ` の θ をそのまま上げます（θ は待ち時間の逆数）」と
    書いていました。**系としては合っていますが、実装はそうなっていません** ——
    `src/arm_speed.throughput()` が返す θ は
    `閉じた前提の件数 ÷ 最初に閉じた日からの経過日数`（**過去だけ**）で、
    待ちは1つも入りません。**撃った直後の `eta.py --reflect` は +0日 と出ます。
    それが正しい**（効きは、実際に前提が早く閉じてから遅れて入る）。

    **`queue_lag.py` の印字する「合計 N日」も、到達日の日数ではありません** ——
    4つの前提の判定日を手前に倒した日数の足し算です。実測 2026-08-26 は
    **合計 40日 に対し、予定表から数えた θ は 今後14日 +29% ／30日 +10% ／
    60日 ±0**（`src/arm_speed.forward()`。60日 で消えるのは、入れ替えが
    前提を1件も増やさないから）。**到達日への効きは 3〜4日 相当。**

    **それでも順番は変えません** —— 2,500単位・投稿を1本も減らさない・
    自動で撃てる手に対して、3〜4日 は十分に見合います。
    **訂正したのは見込みの立て方だけ**で、この関数の位置は正しいままです。

    ## なぜ投稿より前でよいか —— **投稿は1本も減りません**（03:5x に数え直した）

    最初はここに「1〜2本を32日先へ置くのと、8日ぶんの θ を交換している」と
    書きました。**それは間違いです。取り違えると、次の回が「投稿を削ってまで
    やることか」と読んで戻します。**

    **`videos.insert` と `videos.update` は、別々に閉じます**（`src/auth.py`）:

    > 8/17 05:2x の実測 —— `insert`(1600) が通るのに `update`(50) が 403。
    > **安いほうが先に閉じます。** 403 は**読みと `thumbnails.set` /
    > `videos.update` だけ**を止めるので、**投稿は続けること**

    **2026-08-26 の実物が、同じことをもう一度言っています** ——
    同じ窓で **403 を 22回 観測しながら、投稿は 11本 通っています**
    （1本 1,600単位 なら 17,600単位。**同じ 10,000 の袋なら不可能**）。

    **つまり、この 2,900単位 は投稿から取っていません。** 取っているのは
    `thumbnails.set` と同じ、**先に閉じる安いほうの袋**からです。
    **交換は起きておらず、順番だけの問題でした。**

    ### **その1窓の推論を、8窓の実測に置き換えました**（2026-08-26・最適化の回）

    上の根拠は **1つの窓**の「同じ 10,000 の袋なら不可能」という推論でした。
    **ここが崩れると、この関数を投稿より前に置く理由ごと崩れます**（「投稿を
    削ってまでやることか」に反転する）。だから帳面の全部で数え直しました ——
    **各窓の最初の 403 より後に成功した `videos.insert` があるか**:

        窓      初403(UTC)  uploads  そのうち初403の後   判定
        08/17     13:35        97          44          別の袋
        08/18     19:10        95          95          別の袋
        08/19     07:08        28          28          別の袋
        08/20     14:37        35          19          別の袋
        08/21     15:03         1           1          別の袋
        08/23     21:26        35          14          別の袋
        08/24     14:22         5           2          別の袋
        08/25     17:36        15           4          別の袋

    **8窓とも、日枠が尽きた後に投稿が通っています。** 推論ではなく実測です。
    出どころは `data/day_quota.jsonl`（403）と `data/uploaded.jsonl`
    （`uploaded_at`）の2つだけなので、**疑ったら同じ2つで数え直せます。**

    ### **ついでに測れたこと: 安いほうの袋は、1日の 3分の2 死んでいます**

    同じ8窓で、**窓が開いてから最初の 403 までが 0.1〜14.4時間**
    （＝ **死んでいる時間が 9.6〜23.9時間／中央値およそ 16時間**）。
    **その死んでいる間に落ちるのは、読み・`thumbnails.set`・`videos.update`**
    —— つまり **判定と入れ替え、到達日を動かせる手の側だけ**です。
    投稿（`videos.insert`）はその間もずっと通ります。

    **だから順番がここまで効きます。** 到達日を動かす手は1日の3分の1しか
    撃てる窓が無く、動かさない手は24時間 撃てる。**後ろに並べたら、
    順番は回ってきません。**

    それでも投稿より前に置くのは、**安い袋のほうが先に尽きるから**です ——
    後ろに並べると、`thumbnails.set` がそうだったように**順番が回ってきません。**

    ## 2段ある（**順番が意味を持ちます**）

        (1) `_rescue_dead_slots()`   死に枠の A/B を生きた枠へ（標本をそろえる）
        (2) `_pull_ready_dates()`    その「判定できる日」を手前へ倒す

    **(1) が先です。** 標本が足りない群は、そもそも**判定できる日が出ません**
    （`judgeable.Floor.ready is None`）。日付の無いものは手前へ倒せません。

    ## 撃たない条件（**下2つは既に呼ぶ先の中にあります**）

    - **日枠の 403 をこの窓で観測している** → 撃たない（**実測だけの門**）
    - **判定に要る本を割る** → 撃たない（`--force-quota` でも抜けられない）
    - **取り戻せる日数が 0 ／ 手が 0** → 撃たない（単位を捨てないため）

    **落ちても投稿は続けます**（サムネイルと同じ。**順番を逆にしないこと**）。

    ## 覆る条件

    **待ち行列が短くなったら、この交換は成り立ちません。**
    `queue_lag` の「いちばん後ろ」が数日まで縮み、**後ろへ回った投稿が
    その窓のうちに公開される**ようになったら、投稿を先に戻すこと。
    """
    if not upload_cap.day_quota().open:
        # **閉じていても、証拠で閉じたのでなければ一度は撃ちます**（2026-08-26）。
        # `note_quota_ok` の反証は「通った呼び出し」を材料にしますが、
        # **撃つ側はここを含めて全部この門の下にいます** ——
        # 閉じている＝撃たない＝成功が記録されない＝閉じたまま、で自分を閉じ込めます。
        # `worth_a_try()` に実測（窓が開いた直後の403は日枠ではない）。
        if not upload_cap.worth_a_try():
            return                      # 観測済みで閉じている。撃つだけ無駄
        print("[batch] 日枠は閉じていますが、**403 は窓が開いた直後のものだけ**です。"
              "**一度だけ撃ってみます**（403 は単位を使いません）", flush=True)
    _rescue_dead_slots()                # (1) 標本を生き返らせる
    _pull_ready_dates()                 # (2) その日を手前へ倒す
    _pack_long_form()                   # (3) 長尺を実測の密度まで詰める


def _pack_long_form() -> None:
    """**予約済みの長尺を、実測の密度（1日5本）まで前へ詰める**。

    ## なぜここか —— **サムネイルより前、投稿より前**

    `_push_thumbnails_first()` の註が「同じ50単位なら、到達日を動かす手が先」と
    書いています。**同じ理屈がこちらにも当たります。**

    **4,000時間の門に入るのは長尺だけ**です。ショートは再生の 99.9% を
    取りますが（実測 08/26・直近28日: `SHORTS_FEED` 64,283 / `WATCH` 67）、
    **その門には1分も積みません。** しかも `thumbnails.set` は
    **ショートでは絵が出ません**（フィードで自動再生される）——
    `src/upload_cap.py` の「同じ50単位を、2つの用途が取り合っています」の節が
    同じ実測を載せています。**こちらを後ろに置く理由がありません。**

    ## 何が起きていたか（2026-08-26 に数えた）

        長尺は 08/25 に 25本・08/26 に 3本 作られている（作る側は1日25本 出せる）
        その 28本 の**予約日**は 08/26〜10/10 の 21日 に散っている ＝ **1.3本/日**
        詰め直すと 最後の1本が **10/10 → 09/01（39日 早い）**・前倒しの合計 **369日**

    散らしていたのは置き方だけです —— `slots()` が `--date` の無い回に
    **同じ時刻を count 回**返し、`next_publish_at()` が
    「その時刻で最初に空いている**日**」を返すため（**N本 = N日**）。
    **作る側は `_long_ring()` で直しました。ここはもう予約に入っている本の後始末**で、
    そちらの直しは効きません。

    ## 撃たない条件（`long_pack_plan` の中と、ここと、両方）

    - 動かす本が0本 → 撃たない（単位を捨てないため）
    - 後ろへ下がる本は**そもそも計画に入りません**（純関数側の不変条件）
    - 測定の窓の日は置き先から外れます（同上）
    - 1日 `per_day` 本を超えません。**既定 5 は実測**
      （`day_cap.long_form()`: `most=5` `alive=5` `collapsed=False`）

    **落ちても投稿は続けます**（他の段と同じ。**順番を逆にしないこと**）。

    ## 覆る条件

    **長尺の面が崩れたら**（`day_cap.long_form()['collapsed']` が True）、
    `per_day` は自動で `most - 1` に落ちます（`_long_ring()` と同じ計器を読む）。
    **予約の長尺が常に0〜1本なら、この段は空振りし続けます** —— そのときは
    詰める話ではなく、**長尺を作る本数**のほうが律速です。
    """
    try:
        import json as _json

        from src import dupes, uploader
        from scripts import reschedule

        dur: dict[str, float] = {}
        with open(ROOT / "data" / "uploaded.jsonl", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = _json.loads(line)
                dur[row.get("video_id")] = float(row.get("duration_s") or 0)

        rows = [r for r in dupes.ledger_rows() if r.get("at")]
        per_day = len(_long_ring())          # 実測の上限（崩れたら自動で下がる）
        plan = reschedule.long_pack_plan(rows, dur, now=datetime.now(timezone.utc),
                                         per_day=per_day)
        if not plan:
            return
        gain = sum((p["old"] - p["new"]).days for p in plan)
        last_o = max(p["old"] for p in plan)
        last_n = max(p["new"] for p in plan)
        print(f"[batch] **予約済みの長尺 {len(plan)}本 を 1日 {per_day}本 まで詰めます**"
              f"（{len(plan) * 50}単位）。最後の1本 {last_o:%m/%d} → **{last_n:%m/%d}**"
              f"・前倒しの合計 {gain}日。**4,000時間の門に入るのは長尺だけ**です",
              flush=True)
        svc = uploader._service()
        done = 0
        for p in plan:
            stamp = p["new"].astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            try:
                reschedule._update(svc, p["id"], stamp,
                                   fallback_status=uploader.base_status())
            except (Exception, SystemExit) as exc:             # noqa: BLE001
                # **`SystemExit` を必ず捕まえること**（2026-08-26 に検査が捕まえた）。
                #     `reschedule._update` は日枠の 403 で `SystemExit` を上げます。
                #     あれは `BaseException` なので **`except Exception` を素通り**し、
                #     この段から `batch_build` の外まで抜けます ＝
                #     **その回は1本も作らずに終わります。**
                #     `docs/GOAL.md`「投稿が途切れるのが最大の損失」に真っ向から反します。
                #     **詰め直しは「あれば良いもの」。投稿を止める権利はありません。**
                print(f"[batch] 長尺の詰め直しは {done}本 で止めます: "
                      f"{str(exc)[:100]}", flush=True)
                break
            dupes.retime(p["id"], stamp)
            # **ここで `note_quota_ok` を呼ばないこと**（2026-08-28 に実測して外した）。
            # `reschedule._update` が**通ったときだけ**自分で1行 書きます。
            # ここでも書くと、**同じ呼び出しが同じ秒に2行**になり、しかも
            # `_update` が「もうその値です」と**撃たずに帰った回**まで
            # 「通った」として載ります。実測（窓 08/27 07:00Z〜）:
            #
            #     `videos.update` の ok 行     **273行**
            #     うち (時刻, 本) が同じ行     **100行 ＝ 5,000単位ぶんの幻**
            #     → 実際に通ったのは          **173回 ＝ 8,650単位**
            #
            # この幻が `upload_cap.measured_budget()` の枠の実測を
            # **14,150単位** に見せていました。08/27 の回はそれを読んで
            # 「**枠は既定の 10,000 ではない**」と結論し、コードの註に残しています
            # （`measured_budget` の docstring）。**逆です** —— 二重に数えた側の
            # 誤りで、8,650＋500 ＝ 9,150単位（＋帳面に載らない
            # `playlistItems.insert` と読み）は **10,000 とよく合います。**
            done += 1
            time.sleep(1.2)     # **短い間に撃ちすぎると 403**（08/26 に 120本 で踏んだ）
        if done:
            print(f"[batch] 長尺を {done}本 詰めました", flush=True)
    except (Exception, SystemExit) as exc:                     # noqa: BLE001
        print(f"[batch] 長尺の詰め直しは飛ばします: {str(exc)[:120]}", flush=True)


def _rescue_dead_slots() -> None:
    """**死に枠に落ちた A/B の本を、生きた枠へ逃がす**（`scripts/live_slots.py`）。

    **`_pull_ready_dates()` より先です。** 入れ替えは「判定できる日」を手前へ
    倒しますが、**そもそも標本が足りない群は、日付が出ません**
    （`judgeable.Floor.ready is None`）。先に本数をそろえること。

    実測（2026-08-26 03:3x）: **6手 ＝ 300単位**で
    `stat_split 処置(後)` が **13本 → 16本（要 16）＝ 足ります**。
    生きている本の総数も **363 → 368**。
    これは 8/26 05:0x の申し送りが「**日枠が戻る 16:00 JST 以降に立った回が
    撃つこと**」と書いていた手で、**待っているあいだ `tests/test_judgeable.py`
    の `stat_split` は赤のまま**でした。

    ## **`--all` も撃ちます**（2026-08-29・最適化の回。**理由が測れたので変えた**）

    ここには長らく「**`--all` は撃ちません。** あれは A/B に限らず全部を逃がす
    広い手で、ここが自動でやってよい範囲を超えます（人が見て撃つこと）」と
    書いてありました。**その「範囲」は、当時 数字で決めていません。**

    **この回に測った数字**（`data/uploaded.jsonl` × `data/views.jsonl`・
    08-19 以降・齢 20〜120時間 の最初の読み・題の `#Shorts` で形を分けた）:

        ショート 帯の中   99本  1本あたり **537.2再生**
        ショート 帯の外   60本  1本あたり **  0.7再生**

    そして `live_slots.py --plan --all` はこの回、
    **生きている本 444 → 506（+62本）／62手（3,100単位）** と出しました。

        1手 50単位 で **+537再生** ＝ **10.7再生/単位**
        `videos.insert` は 1,600単位 で 1本（帯に入れば 537再生）＝ **0.34再生/単位**

    **同じ単位で 31倍**です。「人が見て撃つ」ために待たせる理由は、
    この比の側にはありません。**待っているあいだ、その本は 0.7再生 で公開されます。**

    ## ただし、投稿を止めないこと（**上限を置く理由**）

    日枠は 10,000単位、`videos.insert` は 1本 1,600単位 ＝ **1日 6本**が限度です。
    62手（3,100単位）を1回で撃つと、**その日の投稿が2本 減ります。**
    だから1回に撃つのは `_RESCUE_MAX` 手まで。**残りは次の回が続けます**
    （`--plan` は毎回 実物の控えから組み直すので、手は消えません）。

    **覆る条件**: `day_cap.cap()` が上がって帯に余りが出たら、この手は要らなくなります
    （`live_slots.plan_all()` の覆る条件と同じ）。
    帯の中の1本あたりが帯の外を**下回ったら**、逃がすのをやめること。
    """
    try:
        from scripts import live_slots

        board = live_slots.Board(live_slots._rows())
        live_slots.plan(board)          # API 0単位。`board.moves` を埋める
        if board.moves:
            print(f"[batch] **死に枠の A/B を {len(board.moves)}本 逃がします**"
                  f"（{len(board.moves) * 50}単位。**投稿より先に撃ちます**）",
                  flush=True)
            live_slots.main(["--apply"])

        # **`live_slots.main(["--apply"])` が持っている枠の門を、こちらにも掛ける**
        # （手を `_RESCUE_MAX` で切るために `apply_moves` を直に呼んでいるので、
        #  門をすり抜けます。**片方だけ直す**が、この repo が繰り返している形）。
        #
        # **門は (2) と (3) の手前に1回だけ置きます**（2026-08-30 に直した）。
        # 最初に書いたときは (2) の中に埋めていて、**(2) に手が無い回
        # （`gain <= 0 or not board.moves`）は `return` で (3) ごと飛んでいました。**
        # (2) の手が尽きるのは**平常の姿**（逃がし終えた状態）なので、
        # そのままだと (3) は「(2) がまだ残っている回」にしか走りません。
        from scripts import queue_lag                           # noqa: PLC0415
        _lines, ok = queue_lag.quota_lines(queue_lag.Plan())
        if not ok:
            print("[batch] 0再生の枠の逃がしは、**枠が戻ってから**"
                  "（`--plan` は毎回 組み直すので、手は消えません）", flush=True)
            return

        # **A/B に限らない側**（付け替えではなく、生きる本が実際に増えるぶん）
        board = live_slots.Board(live_slots._rows())
        was = len(board.live())
        live_slots.plan_all(board)      # API 0単位
        gain = len(board.live()) - was
        if gain > 0 and board.moves:
            board.moves = board.moves[:_RESCUE_MAX]
            print(f"[batch] **0再生の枠のショートを {len(board.moves)}本 逃がします**"
                  f"（{len(board.moves) * 50}単位。この回の実測で 帯の中 537.2再生/本 対 "
                  f"帯の外 0.7 ＝ **1単位あたり 投稿の31倍**）", flush=True)
            live_slots.apply_moves(board)

        # --- (3) **帯の外に居る本を、同じ日の帯へ**（2026-08-29・最適化の回）---
        #
        # 上の (2) が拾うのは **`board.live()` が「死んでいる」と言う本だけ**です。
        # あれは `day_cap.live_ids()` ＝ **(A)「その日の先頭 `cap()` 本」**で、
        # **帯（09:00〜13:30）を1文字も見ていません。** だから
        # **1日ちょうど10本 の日は、何時に置いても全部「生きている」**と数えます。
        #
        # ところが `day_cap.window()` は **(A)/(B) を切り分けていません**
        # （`confounded`・答えは 2026-09-03）。**(B)「13:30 までが生きる」なら、
        # その帯の外はぜんぶ 0再生**です。実測（この回に数えた・控えの予約ぶん）:
        #
        #     (A) で生きている本            446本
        #     **そのうち帯の外に居る本      78本**   ← (B) なら全部 0再生
        #     同じ日の帯に空き分があった本   78本   ← **全部 入る**
        #     入れ直したあとの (A) の生存数  446本  ← **±0。押し出していません**
        #
        # **どちらの説明でも損をしません**（(A) は同じ日の中で時刻を早めるだけ ＝ ±0、
        # (B) は帯の外 → 帯の中 ＝ その1本が生き返る）。`live_ring()` の註と同じ理屈で、
        # **賭けになりません。** (B) なら 78本 × 655回/本 ＝ **約5万再生**で、
        # いまのチャンネルの **14日ぶんの産出**にあたります。
        #
        # **測定の窓の日は `board.movable()` が外します。** 実測でこの回の手は
        # **全部 09/06 以降**で、(A)/(B) の切り分けの日（09/02・読むのは 09/03）に
        # 1手も掛かりません。**日ごとの本数はどの日も変わりません**（時刻だけ動かす）
        # ので、`eta.py` の「答えが返るまで、他の日の本数を増やさないこと」にも触れません。
        #
        # **覆る条件**: `day_cap.window()` が **(A)** と決めたら、この段は要りません
        # （消してよい）。**(B)** と決まったら、直す先は `live_slots.plan_all()` の
        # `same_day_first=False` のほうです。**検査は `tests/test_live_slots_band.py`。**
        board = live_slots.Board(live_slots._rows())
        live_slots.plan_band(board, limit=_RESCUE_MAX)     # API 0単位
        if not board.moves:
            return
        print(f"[batch] **帯の外のショートを {len(board.moves)}本 帯の中へ入れ直します**"
              f"（{len(board.moves) * 50}単位。**(A) なら ±0・(B) なら生き返る** ——"
              "どちらでも損をしません。切り分けは 2026-09-03）", flush=True)
        live_slots.apply_moves(board)
    except Exception as exc:                                   # noqa: BLE001
        print(f"[batch] 死に枠の逃がしは飛ばします: {str(exc)[:120]}", flush=True)


def _pull_ready_dates() -> None:
    """**判定できる日を手前へ倒す**（`scripts/queue_lag.py --apply`）。

    **0日 なら撃ちません。**（単位を捨てないため。`Plan.gain_days()` が門）
    """
    try:
        from scripts import queue_lag

        plan = queue_lag.Plan()
        plan.improve()
        if not plan.swaps:
            return
        days = plan.gain_days()
        if days <= 0:
            print(f"[batch] 入れ替え {len(plan.swaps)}手 は **0日** なので撃ちません",
                  flush=True)
            return
        print(f"[batch] **判定を {days}日 手前に倒します**"
              f"（入れ替え {len(plan.swaps)}手 ＝ {len(plan.swaps) * 100}単位。"
              "**投稿より先に撃ちます**）", flush=True)
        # **撃った結果を読むこと。** ここは長らく返り値を捨てていたので、
        # 枠が閉じている窓では「**倒します**」と印字してから **1日も倒さず**、
        # 帳面には倒したように見えていました（2026-08-26 の実測 ——
        # 日枠の 403 を 516回 観測した窓で、この行だけが出ていた）。
        rc = queue_lag.main(["--apply"])
        if rc:
            print(f"[batch] **倒せませんでした**（上の理由）。"
                  f"{days}日 はまだ残っています —— "
                  "**手は消えません**（`--plan` は毎回 実物の控えから組み直す）",
                  flush=True)
    except Exception as exc:                                   # noqa: BLE001
        print(f"[batch] 予約の入れ替えは飛ばします: {str(exc)[:120]}", flush=True)


def _push_thumbnails_first() -> None:
    """溜まったサムネイルを、**この回の投稿が単位を使い切る前に**押す。

    **落ちても投稿は続けます。** ここで止めると、サムネイル（あれば良いもの）の
    ために投稿（途切れるのが最大の損失）を止めることになります。**順番が逆です。**

    ## **長尺だけを押します**（2026-08-28 に直した）

    ここは長らく `push_missing()` を素で呼んでいました。ショートを止めていたのは
    `upload_cap.thumbnail_yield_to_schedule()` の**穴の門**だけで、
    **あれは「単位の行き先が他に在る」という代理の理由**です。

    実測 2026-08-28: 予約の穴は **10/11 の1日だけ**で、埋めるのに要るのは
    **`--move` 1回（50単位）**。ところが門の文面は
    「同じ単位で**詰め直しが 70本**できます」と言い、`--spread` は
    「1日 10本を超えている日はありません」と答えます ——
    **勧めている代替案の側が、その大きさでは存在しません。**
    そして穴を1本の `--move` で埋めた瞬間、門は開き、
    **ショート 58本 ＝ 2,900単位**がここから黙って出ていきます。

    **本当の理由は穴ではなく面のほうです**（`LONG_FORM_SEC` の上の註）:

        再生の 99.9% は `SHORTS_FEED` ＝ **サムネイルの出ない面**
        門2a（4,000時間）に入るのは長尺だけで、そこは **CTR が縛っている**
        （実測 1.44% ／ 要る 19.2%）。**サムネイルはその CTR そのもの**

    だから `only_long=True` で呼びます。**穴の有無に左右されません**
    （`only_long` は穴の門を通しません）。単位は投稿（`videos.insert`）と
    詰め直し（`videos.update`）と分け合うので、**0.1% の面のために
    2,900単位 を先に持っていかせないこと。**

    **覆る条件**: `SHORTS_FEED` 以外の面が再生の1割を超えたら、ここを素の
    `push_missing()` に戻すこと（`thumbnail_yield_to_schedule` の註と同じ条件）。
    人手で押したいときは `python scripts/refresh_thumbnail.py --missing` が
    そのまま残っています。**検査は `tests/test_thumbnail_long_only.py`。**
    """
    try:
        import refresh_thumbnail

        if not upload_cap.day_quota().open and not upload_cap.worth_a_try():
            return                      # 観測済みで閉じている。撃つだけ無駄
        refresh_thumbnail.push_missing(only_long=True)
    except Exception as exc:                                   # noqa: BLE001
        print(f"[batch] サムネイルの押し直しは飛ばします: {str(exc)[:120]}", flush=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="複数本をまとめて作って予約する")
    ap.add_argument("--count", type=int, default=2, help="作る本数（既定 2）")
    ap.add_argument("--hour", type=int, default=None,
                    help="予約時刻（JST の時。既定 ショート 9／**長尺 20**）。"
                         "埋まっていれば翌日へ送られる")
    ap.add_argument("--date", default="",
                    help="YYYY-MM-DD。**その日に釘づけして時刻をずらす**＝1日にN本。"
                         "無ければ従来どおり1日ずつ後ろへ積む（1日1本）")
    ap.add_argument("--hours", default="",
                    help="--date と一緒に使う。時刻をカンマ区切りで明示"
                         "（既定は --hour から1時間ずつ）")
    ap.add_argument("--step-min", type=int, default=60,
                    help="--date と一緒に使う。予約の間隔（分・60の約数）。"
                         "既定の60は1日11枠まで（9〜19時）＝投稿枠92本の1/8。"
                         "30 にすると1日22枠。--hours とは併用できません")
    ap.add_argument("--force-window", action="store_true",
                    help="M14 の比較の窓に置くことを承知で続ける（測定が壊れます）")
    ap.add_argument("--topics", default="",
                    help="テーマIDをカンマ区切りで明示する（--count より優先）")
    ap.add_argument("--long", action="store_true",
                    help="長尺で作る（既定はショート）")
    ap.add_argument("--skip-upload", action="store_true",
                    help="作るだけで予約しない。**この場合コンテナと一緒に消えます**")
    ap.add_argument("--jobs", type=int, default=DEFAULT_JOBS,
                    help=f"同時に作る本数（既定 {DEFAULT_JOBS}）。**予約はいつも1本ずつ**")
    ap.add_argument("--per-calc", type=int, default=DEFAULT_PER_CALC,
                    help=f"1つの calc から取ってよい本数（既定 {DEFAULT_PER_CALC}）。"
                         "**節はいつも全部ちがいます。**1 にすると昔の"
                         "「calc が全部ちがう」に戻り、1回の上限が calc の本数になります")
    ap.add_argument("--no-retry", action="store_true",
                    help="落ちた本を作り直さない（既定は1回だけ作り直す。"
                         "実測 54%% が2回目で通り、テーマ在庫は減りません）")
    ap.add_argument("--stop-on-error", action="store_true",
                    help="1本落ちたらそこで止める（**予約の段だけ**。"
                         "作る段は並列なので、落ちた1本の巻き添えで他を捨てません）")
    ap.add_argument("--report", action="store_true",
                    help="台帳を jobs 別に並べるだけ（**生成も予約もしません**・数秒）")
    ap.add_argument("--pick-only", action="store_true",
                    help="`pick()` を通して**選んだ本と置き先と A/B の群を出して終わる**"
                         "（生成も予約もしない・API 0単位）。`--report` とは別物："
                         "あちらは台帳を並べるだけで `pick()` を通しません")
    args = ap.parse_args(argv)

    # **`--hour` を書いたかどうか**を、既定を入れる前に覚えます。
    # 書いた回は「その時刻に置け」という指示なので、帯の探索に掛けません
    # （`slots(live=…)`／`live_ring()`）。**明示は常に通す**。
    hour_given = args.hour is not None
    if args.hour is None:
        args.hour = LONG_HOUR_JST if args.long else 9

    if args.report:
        return report()

    # ---- 0. **日付は、生成の前にここで正す**（2026-08-19 08:1x に9本ぶん捨てて足した）----
    #
    # `--date 08/23` は、この道具の中では**最後まで通ります** ——
    # `slots()` は文字を組み立てるだけ、印字も `08/23 の1日に入れます` と出るので、
    # **渡した側からは正しく動いているように見えます。** 形を見るのは
    # `uploader.next_publish_at`（`videos.insert` の直前）だけで、そこは
    # **9本の生成が全部終わったあと**です。実測: 約20分ぶんを作ってから
    # **9本とも予約で落ちました**（`予約できたのは 0 / 9 本`）。
    #
    # **落ちること自体は正しい。落ちる場所が20分先だったのが欠陥です。**
    try:
        args.date = uploader.normalize_date_jst(args.date)
    except ValueError as exc:
        print(f"[batch] {exc}")
        return 2

    # ---- 0.0 **撃つ前に、道具が入っているか**（2026-08-22 に足した。理由は
    # `ensure_toolchain` の docstring）------------------------------------
    if not ensure_toolchain():
        return 1

    # ---- 0. **撃つ前に、1日の投稿本数の枠を見る**（2026-08-17 に足した）----
    #
    # 下の「2. 予約する」には、429 に当たったら止まる門が既にあります。
    # **あれは作り終えたあとにしか効きません。** 10:5x の回は6本を作ってから当たり、
    # **6本とも `build/` ごと捨てました**（コンテナが畳まれると消えます）。
    #
    # ここは **API を1単位も使いません**（控えと観測の記録だけ）。だから
    # **Data API の日枠が切れている回でも効きます** —— そういう回は1日13時間あり、
    # 撃てるかどうかを口に訊く道がそもそもありません。
    explicit = [i.strip() for i in args.topics.split(",") if i.strip()]
    # ---- 0.5 **50単位の手を、投稿より先に押す**（2026-08-17 22:4x／08-26 03:2x）--
    #
    # 順は **入れ替え → サムネイル → 投稿**。どれも同じ日枠から出ていて、
    # `videos.insert` だけが 1本 1,600単位 だからです。**先に撃つ順が、
    # そのまま優先順位**になります（下の2つの註が、その理由）。
    #
    # **投稿の本数枠（429）より前に置くこと**（2026-08-26 03:4x に直した）。
    # ここは長らく `cap.remaining <= 0` の `return 1` の**後ろ**にありました ——
    # つまり**「今日はもう92本 上げた」だけで、50単位の手まで丸ごと落ちて**いました。
    # `src/upload_cap.py` の頭がそのことを書いています ——
    # **「投稿を止める枠は2つあります。片方しか数えていませんでした」**:
    #
    #     Data API の日枠   10,000単位  403 quotaExceeded    ← 50単位の手を止めるのはこちら
    #     投稿の本数枠      1日92本     429 rateLimitExceeded ← `videos.insert` だけの枠
    #
    # **別の枠です。**片方が閉じても、もう片方は開いています。
    #
    # **順番がすべてです。** Data API の単位枠は 10,000単位で、
    # `videos.insert` は 1本 1,600単位 —— **7本で 11,200単位**。1周で7〜8本
    # 上げているので、**窓が開いた直後の1周が、その窓の単位を丸ごと使い切ります。**
    # `thumbnails.set` は 50単位しか要らないのに、**いつも投稿の後ろに並んでいた**ので
    # 一度も順番が回ってきませんでした。
    #
    #     待ち行列は 8/17 の1日で 28 → 33本にふえ、
    #     `missing_thumbnail` は **15回鳴って当たり2回**
    #
    # 一覧が悪いのではありません。**押せる時刻に、押す手順が無かった**だけです。
    # 5本ぶんで 250単位（投稿0.16本ぶん）なので、**投稿の本数は減りません。**
    # **`--pick-only` の回は、この2つを撃ちません**（2026-08-29 13:4x に足した）。
    # どちらも単位を使う手で、**見るだけの回が単位を減らすと、
    # 同じ窓の投稿がそのぶん減ります**（`videos.insert` は 1本 1,600単位）。
    if not args.pick_only:
        _pull_verdicts_first()
        _push_thumbnails_first()

    if not args.skip_upload and not args.pick_only:
        cap = upload_cap.state()
        print(f"[batch] {cap.line}", flush=True)
        if cap.remaining <= 0:
            print("[batch] **作りません。**（予約せずに作るだけなら "
                  "`--skip-upload`。枠が戻ってから "
                  '`upload_only.py <ID> "" <日付>@<時>` で打てます）', flush=True)
            return 1
        want = len(explicit) if explicit else args.count
        if cap.remaining < want:
            print(f"[batch] 要求 {want} 本を **{cap.remaining} 本に縮めます**"
                  "（残りは作っても撃てず、`build/` ごと消えるだけなので）。",
                  flush=True)
            if explicit:
                explicit = explicit[:cap.remaining]
            else:
                args.count = cap.remaining


    # **この回の本が「どこへ着くか」を先に出す**（2026-08-29 に踏んで足した）。
    #     `_queue_tail_calcs` は着地点のまわりを見ます —— 今日を中心に見ると、
    #     `--date` の回も既定の回（実測 8〜11日後に着地）も窓の外になり、
    #     **同じ calc の長尺が続けて並びます**（この回は 6本 中 bunkatsu 3・mishikyu 3）。
    land: date | None = None
    if args.date:
        try:
            land = date.fromisoformat(args.date)
        except ValueError:
            land = None
    else:
        try:
            # **長尺とショートでは、置き先の帯そのものが別です**
            # （2026-08-29 に踏んで足した。それまでは長尺の回も `live_plan()` を
            #  読んでいて、**着地点が 13日 ずれた**まま門を掛けていました ——
            #  印字 2026-09-06 に対し、実際に着いたのは 2026-09-19。
            #  実測と再現は `long_plan()` の docstring）。
            #
            #     `--long`（時刻を明示していない回）  `long_plan()`  18〜22時 の輪
            #     それ以外                            `live_plan()`  09:00〜13:30 の帯
            #
            # **時刻を明示した回（`--hour` / `--hours`）は、輪を使いません** ——
            # `slots()` がその時刻を全本に配り、`next_publish_at()` が
            # 「その時刻が空いている最初の日」を1本ずつ返します。
            # `long_plan()` に1つだけの輪を渡すと、そこも同じ形になります。
            want = args.count if not explicit else len(explicit)
            given = [int(h) for h in args.hours.split(",") if h.strip()]
            if args.long:
                ring0 = tuple(given) if given else (
                    (args.hour,) if hour_given else _long_ring())
                # `long_plan()` は (時, 置く日) を返します（docstring）。
                plan = [(str(h), d) for h, d in long_plan(want, ring0)]
            else:
                # `live_plan()` は (時刻, 置く日) を返します（docstring）。
                plan = live_plan(want)
            if plan:
                land = min(d for _, d in plan)
        except Exception as exc:                              # noqa: BLE001
            print(f"[pick] 着地点が読めませんでした（今日を中心に見ます）: "
                  f"{str(exc)[:120]}")
    if land is not None:
        print(f"[pick] この回の本が着くのは **{land.isoformat()}** ごろ ——"
              f" 同じ calc を避けるのは、その前後 {QUEUE_TAIL_DAYS}日 です")
    topics = pick(args.count if not explicit else len(explicit), explicit,
                  per_calc=args.per_calc, long_form=args.long, land=land)
    if not topics:
        print("[batch] 作れるテーマがありません。config/topics.yaml を足すこと。")
        return 1

    if args.date:
        check_window(args.date, args.force_window)
    hours = [int(h) for h in args.hours.split(",") if h.strip()]
    # **長尺は、同じ日に `LONG_PER_DAY` 本まで詰めます**（2026-08-26 に足した）。
    # `--date` を渡した回は今までどおり（あちらは日を釘づけする別の道）。
    # `--hours` を明示した回も触りません（**明示は常に通す**）。
    #
    # **`--hour` を書いた回も、輪は使いません**（2026-08-29 に踏んで足した）。
    # すぐ上の `hour_given` の註が「**明示は常に通す**」と書いているのに、
    # ここだけ `--hours`（複数形）しか見ておらず、`--hour 20` と書いた回に
    # **18〜22時 の輪で黙って上書き**していました。実測: `--count 4 --long --hour 20`
    # が 09/19 の 19/20/21/22時 へ4本 —— 頼んだのは「20時に1日1本」です。
    # 長尺の穴（`eta.py` が名指しする「長尺の予約が0本の日」）を **1日ずつ**
    # 埋めにいく回は、この道しかありません。**輪は既定のままです**（何も書かない回）。
    ring = None
    if args.long and not args.date and not hours and not hour_given:
        ring = _long_ring()
        if ring and len(ring) > 1:
            days = (len(topics) + len(ring) - 1) // len(ring)
            print(f"[batch] 長尺 {len(topics)}本 を **1日 {len(ring)}本** で置きます"
                  f"（{days}日ぶん・時刻 {list(ring)} JST）。"
                  " **4,000時間の門に入るのは長尺だけ**なので、"
                  "散らすとその門だけが止まります", flush=True)
    # **帯の空きから選ぶのは、時刻を何も指定しなかった回だけ**です。
    # `--date`（日に釘づけ）・`--hours`（時の明示）・`--hour`（時の明示）・
    # `ring`（長尺の輪）は、どれも「置き先を指示された」回なので触りません。
    live = not args.date and not hours and not ring and not hour_given
    when = slots(len(topics), args.hour, args.date or None, hours,
                 step_min=args.step_min, ring=ring, live=live,
                 long_form=bool(args.long))
    # ---- 0.7 **1日の本数の上限を、ここで当てる**（2026-08-30。解除条件4）--------
    #
    # **置き先を決める道は5本ありますが、出口はここ1本です**（`cap_by_density()` の
    # docstring に、どれが `_per_day_soft()` を素通りするかの一覧）。
    # **生成の前**に当てるので、落とした本は1秒も作りません（題材は在庫に残ります）。
    #
    # **`--skip-upload` の回は当てません** —— 予約しない回は、その日の公開本数を
    # 1本も増やさないからです（作るだけで `build/` ごと消えます）。
    if not args.skip_upload:
        _keep, _cap_notes = cap_by_density(when)
        for _line in _cap_notes:
            print(_line, flush=True)
        if len(_keep) < len(when):
            topics = [topics[i] for i in _keep]
            when = [when[i] for i in _keep]
        if not topics:
            print("[batch] **この回は1本も置けません**（行き先の日が全部 "
                  f"{density_cap()}本/日 で埋まっています）。"
                  " `--date` で先の日を指すか、次の回に回すこと。"
                  " **生成はしていません。**", flush=True)
            return 0
    # **枠と題材の対応を、IDのハッシュで配り直す**（`_ab_slot_order()` の docstring）。
    #     `live` の回だけ ＝ 置き先を指示されていない回だけ。
    #     **落ちてもこの回を止めないこと** —— 配り直しは実験で、投稿は本体です。
    if live:
        try:
            when = _ab_slot_order(topics, when)
        except Exception as _exc:                              # noqa: BLE001
            print(f"[batch] 枠の配り直しを飛ばしました（続行）: {_exc}", flush=True)

    if args.date:
        # **`+ ':00'` と書かないこと**（2026-08-18 に直した）。`--step-min` を
        # 足すまで時しか無かったので足していましたが、いまは `10:30` が来ます。
        # **日をまたいだら、そう言うこと**（2026-08-29）。`_show_slot()` は
        # 日付を落とすので、`_band_walk()` が次の日の帯へ回した回は
        # 「**{date} の1日に**入れます」と印字したまま、実際は別の日に着きます
        # —— この repo が通算11回 踏んでいる「言っている所と、している所が別」。
        days = sorted({w.split("@")[0] for w in when if "@" in w})
        if len(days) > 1:
            shown = ", ".join(f"{w.split('@')[0]} {_show_slot(w)}" for w in when)
            print(f"[batch] {len(topics)} 本を **{len(days)}日に分けて**入れます"
                  f"（{shown} JST）　—— {args.date} の帯が埋まっているぶんです")
        else:
            shown = ", ".join(_show_slot(w) for w in when)
            print(f"[batch] {len(topics)} 本を **{args.date} の1日に**入れます"
                  f"（{shown} JST）")
    else:
        # **`args.hour` を印字しないこと**（2026-08-27）。`live` の回は
        # `slots()` が帯の空きから別の時刻を選んでいるので、ここが `9:00` と
        # 言っていると**印字と実際がまた食い違います**（`live_ring()` の docstring）。
        print(f"[batch] {len(topics)} 本を作ります"
              f"（予約は {', '.join(sorted(set(_show_slot(w) for w in when)))} JST の空き枠へ）")
    for t in topics:
        print(f"        {t['id']}  calc={t['calc']}  {t['title_seed'][:38]}")

    if args.pick_only:
        _print_ab_groups(topics)
        _print_live_days()
        print("[batch] **`--pick-only` なので、ここで終わります**"
              "（生成も予約もしていません）。"
              " この並びでよければ、同じ引数から `--pick-only` を外して撃つこと。")
        return 0

    # ---- 1. 作る（**ここだけ並列**）----------------------------------------
    #
    # 1本の11分は、ほぼ全部が `claude -p` の待ち時間です（生成中の CPU は 2〜4%）。
    # **待ち時間は重ねられます。** 直列だと 8本で90分、3本ずつなら30分台。
    # M14 が測ろうとしている「1日あたりの本数」は、ここが律速でした。
    jobs = max(1, min(args.jobs, len(topics)))
    began = datetime.now(JST)
    if jobs > 1:
        print(f"\n[batch] **{jobs} 本ずつ同時に作ります**"
              f"（待ち時間を重ねるだけなので、予約は下で1本ずつやります）", flush=True)

    # ---- 0. **この本数の行き先を、足りない腕へ寄せる**（本数は1本も増やしません）----
    #     `motion_shortfall()` の docstring に理由と実測があります。
    explicit = os.environ.get(_MOTION_ENV) is not None
    _need, _why = (0, "") if explicit else motion_shortfall()
    motion = motion_plan(len(topics), shortfall=None if explicit else (_need, _why))
    if any(m is False for m in motion):
        n_off = sum(1 for m in motion if m is False)
        print(f"\n[batch] **{n_off} 本を `opening_motion` の対照（動きなし）で作ります**"
              f" —— {_why}", flush=True)
        print("        処置(動きあり)の側は既に床を越えているので、"
              "そちらへ足しても判定は1日も早まりません"
              "（`scripts/batch_build.motion_shortfall`）。", flush=True)
        # **同じ段落が、同じ数について2つのことを言わないこと**（2026-08-27 に踏んだ）。
        #     `_why` の末尾は `motion_shortfall` の答え（＝**盤面が要る本数**）で、
        #     頭の `n_off` は `motion_plan` の答え（＝**この回で実際に対照にする本数**）。
        #     （この註で `motion_shortfall` を呼び出しの字で書かないこと ——
        #      `tests/test_motion_fill.py` が「1回の生成で2回 数えていないか」を
        #      **この節のソースの字**で数えています）
        #     `motion_plan` は `off = min(need, max(1, n // 2))` で
        #     **1回の半分まで**しか対照にしません（同じ JST 日に両群が居ないと
        #     `motion_groups.paired()` が標本に数えないため。理由はあちらの docstring）。
        #     実測 2026-08-27: `--count 2` の回の出力が
        #     「**1 本を…作ります** —— …→ **この回で作るのは 2本**」と、
        #     **同じ行の中で 1 と 2 の両方**を言っていました。
        #     読んだ側は「2本 埋まった」と思い、床はまだ 1本 空いたまま残ります。
        if _need > n_off:
            print(f"        [!] **残り {_need - n_off}本 は、この回では作りません。**"
                  " 対照は1回の半分まで（同じ日に両群が居ないと `paired()` が"
                  "標本に数えないため）。**この回で床まで埋めたいなら"
                  f" `--count {2 * _need}`** —— そうでなければ、"
                  f"**あと {_need - n_off}本 は次の回に残ります。**", flush=True)
    elif explicit:
        print(f"\n[batch] `{_MOTION_ENV}` が明示されているので、腕はそれに従います"
              f"（この回では選び直しません）", flush=True)
    elif "置き先" in _why:
        # **黙って既定に戻らないこと。** ここで何も言わないと、この回は
        # 「対照が足りている」のか「置く所が無くて作れない」のかを区別できません。
        # **足りないのが本なのか枠なのかは、次の手をまるごと変えます。**
        print(f"\n[batch] [!] `opening_motion` の対照は作りません —— {_why}", flush=True)

    # **配色の起点は、この回で1度だけ読む**（`theme_base()` に実測と理由）。
    # 本ごとに +1 するので、1回で作った本が同じ色になりません
    # （実測 08/27 21:56 は **8本すべて同じ色**でした）。
    _base = theme_base()
    # **この回で作る本の A/B の名札を、作る前に焼く**（2026-08-28・API 0単位）。
    #
    # 腕はテーマIDの純関数なので、**作る前に確定しています。**
    # 焼いておかないと、`SLOW_PACE_SHARE = 0`（`config/hypotheses.yaml` が
    # 書いている畳み方）を撃った回に、その本の群が消えます
    # （`src/ab_split.group_of` に実測 —— 凍結なしなら 遅い 7 → 0）。
    #
    # **ここに置く理由**: 焼く場所を1か所にしないと、名札は必ず古くなります。
    # 実測 2026-08-28 —— 焼いた 30分 後に主実行が 2本 作り、
    # `tests/test_ab_labels_frozen.py` が **遅い 9 → 7** で落ちました
    # （新しい2本が名札を持っていない ＝ 生の関数へ落ちる）。
    #
    # **競合について**: 同じ枝で複数の回が走ると、読んで書くあいだに
    # 別の回の追記が消えることがあります。**足すだけなので、
    # 消えても次の回がもう一度 足します**（`freeze_labels` は上書きしません）。
    try:
        from src import ab_split as _ab

        _ab.freeze_labels([t["id"] for t in topics])
    except Exception as _exc:                                  # noqa: BLE001
        print(f"[batch] A/B の名札を焼けませんでした（続行）: {_exc}", flush=True)
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        results = list(pool.map(
            lambda tm: build_one(tm[0][0], args.long, tm[0][1], _base + tm[1]),
            zip(zip(topics, motion), range(len(topics)))))

    # ---- 1b. 落ちた本を、その場でもう一度だけ作る ---------------------------
    #
    # **落ちる理由は、テーマではなく回でした**（2026-08-19 19:2x に
    # `data/batch_runs.jsonl` の 449本を数えた）:
    #
    #     直前が失敗 → 次の試行が成功   **46/85 = 54%**
    #     （`生成が失敗` に絞っても 38/70 = 54%）
    #     落ち2回以上のテーマ 16件のうち、**13件は最後に通って投稿済み**
    #
    # つまり「必ず落ちるテーマ」はほぼ無く（成功0回は1件）、失敗の半分は
    # **その回かぎりのぶれ**です。だから門（`pick` から外す）は効きません ——
    # **測ってから足すこと**、の答えがこれです。効くのは撃ち直しのほう。
    #
    # **在庫が律速なので、撃ち直しは「多めに作る」より強い。**
    # 8枠に10本つっこむ手は、余った2本ぶんの**テーマを1回で使い切ります**
    # （いま未投稿の在庫は 18件）。撃ち直しは**同じテーマを使う**ので
    # 在庫を1件も減らしません。歩留まり 86.7% → 約 94% の見込み。
    #
    # **1回だけ**です（2回目の期待値は同じ54%だが、時間は線形に増える）。
    # `--no-retry` で従来どおりになります。
    retry_at = [n for n, r in enumerate(results)
                if not r.get("built") and not args.no_retry]
    if retry_at:
        print(f"\n[batch] **{len(retry_at)} 本を、もう一度だけ作り直します**"
              f"（実測 54% が2回目で通ります。テーマは減りません）", flush=True)
        with ThreadPoolExecutor(max_workers=max(1, min(jobs, len(retry_at)))) as pool:
            # **撃ち直しは、同じ腕で作ること。** ここで腕を選び直すと、
            # 同じテーマが `data/build_flags.jsonl` に両方の値で並び、
            # `motion_groups.motion_by_topic()` が**そのテーマを両群から落とします**。
            # **撃ち直しも同じ番号で。** 番号を振り直すと、1回目に作った本と
            # 色がぶつかりえます（起点は同じなので、位置だけが色を決めます）。
            again = list(pool.map(
                lambda n: build_one(topics[n], args.long, motion[n], _base + n),
                retry_at))
        recovered = 0
        for n, row in zip(retry_at, again):
            row["retried"] = True
            # **落ちたほうの時間も残す。** 撃ち直しは只ではないので、
            # 次の回が「割に合っているか」を数字で見られるようにしておく。
            row["first_build_sec"] = results[n].get("build_sec")
            if row.get("built"):
                recovered += 1
            else:
                # 2回とも落ちた ＝ そのテーマ側の可能性が上がる。台帳に残す。
                row["error"] = (row["error"] or "生成が失敗") + "（2回とも）"
            results[n] = row      # **同じ位置に戻す**（枠の対応は並び順で決まる）
        print(f"[batch] 作り直しで {recovered} / {len(retry_at)} 本が通りました",
              flush=True)

    built = sum(1 for r in results if r.get("built"))
    wall_sec = round((datetime.now(JST) - began).total_seconds(), 1)
    spent = wall_sec / 60
    print(f"\n[batch] 作れたのは {built} / {len(topics)} 本（{spent:.1f}分・同時 {jobs}）",
          flush=True)

    # **重なりを、その場で出す。** 台帳に残すだけだと誰も読みません
    # （`--jobs` が4回持ち越されたのは、まさにそれです）。
    # **作り直した本は、落ちた1回目の時間も足すこと**（2026-08-19 に足した）。
    # 足さないと直列相当が過少になり、`speedup` が実際より大きく出ます。
    serial_sec = round(sum(float(r.get("make_sec") or r.get("build_sec") or 0.0)
                           + float(r.get("first_build_sec") or 0.0)
                           for r in results), 1)
    speedup = round(serial_sec / wall_sec, 2) if wall_sec > 0 else None
    per_book = [float(r["build_sec"]) for r in results if r.get("build_sec")]
    if per_book and jobs > 1:
        mean = sum(per_book) / len(per_book)
        print(f"[batch] 直列なら {serial_sec/60:.1f}分 → **{speedup} 倍**"
              f"（同時 {jobs}）／1本あたり {mean/60:.1f}分", flush=True)
        print("[batch] **1本あたりが jobs を上げるほど伸びていたら、そこが上限です**"
              "（`--report` で並べて見ること）", flush=True)

    # ---- 2. 予約する（**必ず直列**）----------------------------------------
    #
    # `upload_only.py` は `next_publish_at` と待ち行列という共有の状態を触るので、
    # 同時に走らせると予約時刻がぶつかります。**ここを並列にしないこと。**
    # 順番も `topics` のまま＝`when[n-1]` の対応が崩れません。
    for n, row in enumerate(results, 1):
        tid = row["topic"]
        if not row.get("built"):
            print(f"[batch] **{tid} は作れませんでした。** 予約しません。", flush=True)
            continue
        if args.skip_upload:
            row["error"] = (row["error"] + " / " if row["error"] else "") \
                + "予約していません（--skip-upload）"
            continue

        code, out = run(
            [sys.executable, "scripts/upload_only.py", tid, "", when[n - 1]],
            UPLOAD_TIMEOUT, tid,
        )
        vid = video_id_of(out)
        row["video_id"] = vid
        if not vid:
            row["error"] = f"予約が失敗（exit {code}）"
        elif code != 0:
            # 投稿は済んでいるが材料を残せなかった場合（upload_only.py の 1）。
            row["error"] = "投稿済み。ただし独立評価の材料を残せていない"

        # **1日の投稿本数の枠に当たったら、そこで止めること**（2026-08-17 に踏んだ）。
        #
        # この枠は Data API の10,000単位とは別で、**当たったら残り全部が必ず落ちます。**
        # ところがここは1本ずつ独立に撃つので、**6本を撃って6本とも同じ429**で捨てました。
        # `--stop-on-error` は既定で off なので、旗に頼ると次も同じことが起きます。
        # **「次も必ず落ちる」と分かっている失敗だけは、旗によらず止めます。**
        if not vid and auth.is_upload_cap(RuntimeError(out)):
            # **観測は `src/uploader._note_cap` が既に残しています**（2026-08-17）。
            # ここで重ねて書かないこと —— 予約は `upload_only.py` を**子プロセス**で
            # 叩くので、向こうの中で `videos.insert` が落ちた時点で記録されています。
            # 両方で書くと、1回の 429 が「2回観測した」に見えます。
            rest = [r["topic"] for r in results[n:] if r.get("built")]
            print(f"[batch] **1日の投稿本数の枠に当たりました**（HTTP 429・"
                  "Data API の10,000単位とは別の枠）。"
                  "**残りを撃っても全部落ちるので、ここで止めます。**", flush=True)
            print(f"[batch] 戻るのは **JST 16:00 ごろ**（太平洋時間の0時）。", flush=True)
            if rest:
                print(f"[batch] **作ってあるのに predicate できていない本が {len(rest)}本**"
                      "。`build/` に残っているので、枠の戻った回に打ち直せます:", flush=True)
                for tid in rest:
                    print(f"[batch]     python scripts/upload_only.py {tid} "
                          f'"" <日付>@<時>', flush=True)
            for r in results[n:]:
                if r.get("built") and not r.get("video_id"):
                    r["error"] = "投稿本数の枠で撃っていません（build/ に残っています）"
            break

        if code != 0 and not vid and args.stop_on_error:
            break

    for row in results:
        row.pop("built", None)

    stamp = datetime.now(JST).isoformat(timespec="seconds")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    # **腕が混ざった回に、回ぜんぶの旗を1個 書かないこと**（2026-08-26）。
    #
    # `src/motion_groups.motion_by_topic()` は、回の旗を**その回の全テーマ**に
    # 貼ります。1本ごとの旗（`data/build_flags.jsonl`）と食い違うと、
    # そのテーマは `len(flags) == 1` に落ちないので**両群から捨てられます** ——
    # つまり回の旗を1個 書いた瞬間、**その回の本が全部 標本から消えます。**
    # 混ざった回は書かないこと。1本ごとの旗と `results[].opening_motion` が本体です。
    _arms = {r.get("opening_motion") for r in results if "opening_motion" in r}
    _run_flag: dict[str, object] = ({} if len(_arms) > 1
                                    else {"opening_motion": renderer.opening_motion_on()
                                          if not _arms else _arms.pop()})
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(
            {"at": stamp, "hour": args.hour, "date": args.date or None,
             "slots": when,
             # **`jobs` と秒数は、この台帳にしか残りません。**
             # `build/` もセッションの画面も、次の回には無い。
             "jobs": jobs, "count": len(topics),
             "wall_sec": wall_sec, "serial_sec": serial_sec, "speedup": speedup,
             "long": bool(args.long),
             # **作ったときの設定を、作った本と一緒に残す**（2026-08-23 に足した）。
             # これが無いと、A/B の群を**作った日でしか割れません**。実装は在庫より
             # 先に効き、在庫は数週間先まで予約されているので、**実装日で割ると
             # 両群の中身が同じになります**（8/19 の ab_split と 8/23 の
             # 「冒頭0.9秒の動き」で2回踏んだ。後者は対照群が 405本中 0本だった）。
             #
             # **腕が混ざった回では、この欄そのものが消えます**（上の `_run_flag`）。
             # 群は `results[].opening_motion` と `data/build_flags.jsonl` から読みます。
             **_run_flag,
             "results": results},
            ensure_ascii=False) + "\n")

    ok = [r for r in results if r["video_id"]]
    print("\n=== まとめ ===")
    for r in results:
        mark = "✓" if r["video_id"] else "✗"
        print(f"  {mark} {r['topic']:<18} {r['video_id'] or '—':<12} {r['error']}")
        # **理由も、まとめの中に出す。** 上の1行は「exit 1」しか言いません。
        # 端末はコンテナと一緒に消えるので、**読まれる場所に理由を置くこと**。
        if r.get("error_reason"):
            print(f"      ↳ {r['error_reason']}")
    print(f"  予約できたのは {len(ok)} / {len(topics)} 本")
    print(f"  記録: {LOG.relative_to(ROOT)}")
    # **2026-08-21、ここは「独立評価が待ち行列に積まれています」でした。**
    # その評価のゲートは同日 falsified で外れています
    # （`config/hypotheses.yaml`・順位相関 -0.27／しきい値 +0.40）。
    # **積むこと自体は続けます**（材料は投稿直後にしか残らないので）が、
    # **次の手として勧めるのはやめました。** 勧める先は腕 `density` です。
    return 0 if ok or args.skip_upload else 1


if __name__ == "__main__":
    raise SystemExit(main())
