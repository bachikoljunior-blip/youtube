"""**同じ calc の長尺を続けて並べない門は、着地点を見ていなかった。**

## 何が起きたか（2026-08-29 に踏んだ）

`batch_build._queue_tail_calcs()` は「これから公開される長尺の calc」を返して、
`pick()` がその calc を避けます。**同じ計算の長尺が続けて並ぶのを止める門**で、
docstring はこう書いています（2026-08-25 に踏んだときの記録）:

    次の長尺6本のうち4本が同じ計算で、題名の頭まで同一でした。これは
    `CLAUDE.md` が引いているポリシー本文そのもの ——「**同じチャンネルの動画を
    続けて数本視聴した後、繰り返しのように感じられる可能性のあるコンテンツ**」は
    **収益化の対象外**。

そして正しく「**着地点の隣は避けられない**」とも書いています。
**ところが窓は `now` 〜 `now + 7日` の固定でした** ——
**着地点が今日から7日以内だ、という前提が確かめられていません。**

実測 2026-08-29（**両方の道で外れます**）:

    `--date` を渡した回   釘づけした日（09/14〜09/16）に着く。
                        窓は 08/29〜09/05 を見ていた ＝ **完全に外**
    既定（`live_ring`）   `queue_lag.py` の実測で着地は **8〜11日後**。
                        窓は 7日 なので、**これも外**

結果、09/12〜09/16 の長尺 **6本 が bunkatsu 3・mishikyu 3** になりました。
**門は1本も止めていません**（窓の中の calc を15件も並べて「避けました」と印字しながら、
避ける必要のある2件は窓の外にありました）。

## 直し

`land`（この回の本が着地する日）を受け取り、**その前後 `QUEUE_TAIL_DAYS` 日**を見る。
`main()` は `--date` か `live_plan()` の先頭から `land` を出して渡します。

**覆る条件**: 未投稿の calc が偏って `pick` が毎回 空になるなら、
`QUEUE_TAIL_DAYS` を下げること（呼び出し側が、空になった回は避けずに通します）。
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _bb():
    spec = importlib.util.spec_from_file_location(
        "batch_build_under_test", ROOT / "scripts" / "batch_build.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_land_を渡すとその日のまわりを見ること():
    """**渡した日の隣の calc が返ること。** 今日のまわりではない。"""
    bb = _bb()
    from src import config, dupes

    pool = config.load_topics()["topics"]
    calc_of = {t["id"]: (t.get("calc") or "") for t in pool}
    rows = [r for r in dupes.ledger_rows()
            if r.get("at") and r.get("topic")
            and "#Shorts" not in (r.get("title") or "")]
    if not rows:
        pytest.skip("控えが読めません")

    # **控えの中から、いちばん本数の多い長尺の公開日を選ぶ。**
    #     そこを `land` にすれば、その日の calc が必ず返るはず。
    by_day: dict[dt.date, set[str]] = {}
    now = dt.datetime.now(dt.timezone.utc)
    for r in rows:
        try:
            when = dt.datetime.fromisoformat(r["at"].replace("Z", "+00:00"))
        except ValueError:
            continue
        if when <= now + dt.timedelta(days=bb.QUEUE_TAIL_DAYS + 2):
            continue                      # 今日の窓と重なる日は、区別が付かない
        c = calc_of.get(r["topic"], "")
        if c:
            by_day.setdefault(when.date(), set()).add(c)
    if not by_day:
        pytest.skip("今日の窓の外にある長尺の予約がありません")

    land = max(by_day, key=lambda d: len(by_day[d]))
    got = bb._queue_tail_calcs(pool, land=land)
    want = by_day[land]
    assert want <= got, (
        f"{land} を `land` に渡したのに、その日の calc {sorted(want - got)} が"
        "返っていません。**窓が着地点のまわりになっていません**")


def test_land_を渡さなければ今日のまわりを見ること():
    """**前と同じ動き。** 渡さない呼び手を壊していないこと。"""
    bb = _bb()
    from src import config

    pool = config.load_topics()["topics"]
    a = bb._queue_tail_calcs(pool)
    b = bb._queue_tail_calcs(pool, land=None)
    assert a == b, "land=None が既定と違う答えを返しています"


def test_遠い日を渡すと今日の窓とは別の答えになること():
    """**固定窓に戻ったら落ちる。** これがこの検査の本体です。"""
    bb = _bb()
    from src import config

    pool = config.load_topics()["topics"]
    today = bb._queue_tail_calcs(pool)
    far = bb._queue_tail_calcs(
        pool, land=dt.date.today() + dt.timedelta(days=40))
    if not today and not far:
        pytest.skip("控えに長尺の予約がありません")
    assert today != far, (
        "今日の窓と 40日 先の窓が同じ答えを返しています。"
        "**`land` が効いていません**（固定窓に戻っています）")
