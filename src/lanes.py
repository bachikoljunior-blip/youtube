"""**同じ分に2本置いてしまうのを、共有の状態なしで避ける。**

    from src import lanes
    lanes.order([540, 570, 600, 630], step_min=30)   # → 自分の車線から先に並べ替えた分

## なぜ要るか（2026-08-25 に実測。前の回 2383a69 が見つけて、直せずに残した）

控えを1本1行にたたんで 08/27 を並べたら、**同じ分に別の動画が2本**いました。

    09:00  CfzcVmRncPg ／ 09:00  EszlAOjkQ2o      09:30  D7jrLXinFDo ／ 09:30  OW7wZKVojUw
    10:00  A1PLXzC4Uv8 ／ 10:00  GLcYZgHwNfc      10:30  aalN6AHdB98 ／ 10:30  v6gZIFynjpc
    11:00  3Avf3SCfPug ／ 11:00  OviZcV_PqbM

この回に数え直すと、これから公開ぶんで **8本**が重なりの側にいます
（08/27 に5組・09/06 に3組）。

`batch_build.ledger_minutes()` は埋まった分を避けるので、**本来ぶつかりません。**
避けられなかったのは、**控えがそのコンテナの中にしか無い**からです。
きょうだいの回は別のコンテナで走っていて、`git` で配られるのは push のあと ——
**同じ回の中で置いた本は、互いに見えません。** 08/24 は4つの回が同時に走っていました。

**なぜ捨て置けないか**: `src/day_cap.py` の `MIN_GAP_MIN=30` は「08/21 に :15/:45 で
出した7本が 0〜2再生」という実測から来ています。**同じ分に2本なら、少なくとも
片方はその側**です。しかも 08/27 は**窓の切り分けの測定日**で、
そこで死んだ本は「1日10本の上限」の証拠と見分けが付きません。

## どう避けるか —— **相談しないで分ける**

口も git も要らない方法は1つだけです: **相手を見ずに、自分の取り分を決める。**

    その分の車線 = (0時からの分 ÷ step_min) % lanes

セッションIDから車線を1つ引き、**自分の車線の分から先に取ります。**
控えの中身に依存しない（分そのものから決まる）ので、**きょうだいの控えが
こちらと食い違っていても、車線が違えば同じ分は選ばれません。**

**`LANES = 2` にしてあります。** 大きいほど衝突は減りますが、
**自分の本どうしの間隔が `step_min × lanes` に広がります。**
いまの目盛り（30分）で 2 なら 60分間隔 —— 1回に5本置く回なら 09:00〜13:00 で、
**13:30 の窓（`src/measure_window.py` の切り分け）の内側に収まります。**
4 にすると 2時間間隔になり、5本目が 17:00 まで落ちて窓の外へ出ます。
**衝突を減らすために、窓の実験を壊すほうが高い**ので 2 です。

**3つ以上が重なった回は、車線が足りません。** そのときは自分の車線を使い切って
となりへ回り込みます（`order()` の後半）—— **そこは今までどおり衝突しえます。**
残ったぶんは `src/collisions.py` が数えて `status.py` に出すので、
**日枠の戻る回が `reschedule.py --move` で片づけられます。**
"""
from __future__ import annotations

import hashlib
import os

# **車線の数**。理由は上の docstring（30分きざみ × 2 = 60分間隔 ＝ 窓の内側）。
LANES = 2


def session_id() -> str:
    """自分のセッションID。**推測しないこと**（`run_marker.session_id()` と同じ読み）。"""
    raw = os.environ.get("CLAUDE_CODE_REMOTE_SESSION_ID", "")
    return raw.strip()


def lane(sid: str | None = None, lanes: int = LANES) -> int:
    """このセッションの車線（0〜lanes-1）。**同じIDなら毎回同じ数**を返す。

    `hash()` を使わないのはわざとです —— Python の文字列ハッシュは
    プロセスごとに種が変わる（`PYTHONHASHSEED`）ので、**同じ回の中でも
    呼ぶプロセスが違えば別の車線**になります。それでは分けたことになりません。
    """
    if lanes < 1:
        raise ValueError(f"lanes は1以上: {lanes}")
    raw = session_id() if sid is None else sid
    if not raw:
        return 0          # IDが読めない回は 0 番。**止めない**（投稿が最優先）
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return digest[0] % lanes


def lane_of(minute: int, step_min: int, lanes: int = LANES) -> int:
    """0時からの分 `minute` が、どの車線に属するか。

    **控えの中身を見ません。** 分そのものから決まるので、きょうだいと控えが
    食い違っていても同じ答えになります —— それがこの分け方の要点です。
    """
    if step_min < 1:
        raise ValueError(f"step_min は1以上: {step_min}")
    return (minute // step_min) % max(1, lanes)


def order(grid: list[int], *, step_min: int, lanes: int = LANES,
          lane_no: int | None = None) -> list[int]:
    """空いている分 `grid` を、**自分の車線から先**に並べ替えて返す。

    捨てません（長さは変わりません）。自分の車線を使い切ったら、
    となりの車線へ順に回り込みます —— **3つ以上が重なった回は、そこで
    ぶつかりえます**（docstring の最後）。

    `lanes=1` なら**何もしません**（今までどおりの並び）。
    """
    if lanes <= 1:
        return list(grid)
    mine = lane(lanes=lanes) if lane_no is None else lane_no % lanes
    return sorted(grid, key=lambda m: ((lane_of(m, step_min, lanes) - mine) % lanes, m))
