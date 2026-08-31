"""**待ちは「車線」で数えること**（2026-08-26 11:5x に実測で踏んだ）。

`placement_days()` は 03:5x の回に `depth()`（＝予約のいちばん後ろ・32日）から
`min/median`（＝予約表に出てくる時刻ぜんぶの最短と中央値・1〜2日）へ替わりました。
**どちらも、実際に置かれる日ではありません。**

実測（この検査を書いた回）。`batch_build --count 8` を撃った結果:

    実際に取った枠   2026-10-06 〜 10-13 の **09:00 JST**（1日1本）＝ **41〜48日後**
    同じ回の印字     **2〜2日後**

**20倍。** 向きは「実験は速い」と言う側なので、
「実験を1つ増やす」判断を**ずっと軽く**見積もらせます。

理由は探し方のちがいです。`uploader.next_publish_at(hour_jst, ...)` は
**渡された時刻ひとつだけ**を 1日ずつ後ろへ試します（`target += timedelta(days=1)`
だけで、**時刻は一度も動きません**）。そして `batch_build` が渡すのは
**ショート 09:00 ／ 長尺 20:00 の2つに固定**。
**空きが手前にあっても、その車線が埋まっていれば届きません。**

ここで固定するのは3つ:

1. `lane_days` が **09:00 と 20:00 の2つだけ**を持つこと
2. 片方の車線が埋まっていたら、`lane_min`/`lane_max` がそれを見せること
   （`min_days`/`median_days` は手前のままでも）
3. 車線の時刻を**写さない**こと —— `batch_build.LONG_HOUR_JST` から引く
"""
from __future__ import annotations

import pathlib
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

from scripts import queue_lag  # noqa: E402

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 8, 26, 12, 0, tzinfo=JST)


def _rows(*stamps: tuple[int, int, int]) -> list[dict]:
    """`(月, 日, 時)` の並びを予約の行にする。"""
    return [{"at": datetime(2026, mo, d, h, 0, tzinfo=JST)} for mo, d, h in stamps]


def test_車線は_09時と20時の2つだけ():
    place = queue_lag.placement_days(_rows((8, 27, 9)), now=NOW)
    assert sorted(place["lane_days"]) == [(9, 0), (20, 0)], place["lane_days"]


def test_車線の時刻は写さずに実物から引く():
    """`--hour` の既定が動いたら、ここも一緒に動くこと。"""
    from scripts import batch_build

    assert (int(batch_build.LONG_HOUR_JST), 0) in queue_lag.placement_days(
        _rows((8, 27, 9)), now=NOW)["lane_days"]


def test_09時が埋まっていれば_その待ちを見せる():
    """**この検査が、この直しの理由そのものです。**

    09:00 を 30日ぶん埋め、**空いている 14:00 を1つだけ**置く。
    `min_days` は 14:00 を拾って手前を指しますが、
    `batch_build` は 14:00 を**一度も渡しません。**
    """
    rows = _rows(*[(8, 26, 9)], *[(9, d, 9) for d in range(1, 26)])
    rows += _rows((9, 1, 14))          # 空いている車線ではない時刻
    # 09/26 まで 09:00 が埋まっている（08/26 のぶんは今日なので効かない）
    rows += _rows(*[(8, d, 9) for d in range(27, 32)])
    place = queue_lag.placement_days(rows, now=NOW)

    # 20:00 が「1日後」ではなく 2日後 なのは、**08/27 が測定の窓**だからです
    # （`_first_free` は `next_publish_at` と同じく窓の日を飛ばします）。
    assert place["lane_days"][(9, 0)] >= 30, place["lane_days"]
    assert place["lane_days"][(20, 0)] <= 3, place["lane_days"]
    assert place["lane_max"] >= 30, place["lane_days"]
    # **ここが本体**: 埋まっている車線を、`min_days` は隠す
    assert place["min_days"] < place["lane_max"] / 10, place


def test_予約が無ければ全部ゼロ():
    place = queue_lag.placement_days([], now=NOW)
    assert place["lane_min"] == 0 and place["lane_max"] == 0
    assert place["lane_days"] == {}


def test_印字は車線の数を出す():
    rows = _rows(*[(8, d, 9) for d in range(27, 32)],
                 *[(9, d, 9) for d in range(1, 26)])
    out = "\n".join(queue_lag.lag_lines(rows, now=NOW))
    assert "09:00→" in out and "20:00→" in out, out
    # **参考の数には「判断に使うな」を必ず添えること**
    assert "この数を判断に使わないこと" in out
