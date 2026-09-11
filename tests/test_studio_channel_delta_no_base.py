"""**窓の中で公開された本を、`sum_confirmed` からも外していた。**

2026-09-11 23:0x・optimizer・Opus。**API 0単位** —— 台帳を読まず、形だけをその場で組みます。

**踏んだ形（実物）**: 同じ台帳の同じ刻で、窓 **31.6時間** の `sum_confirmed` が **+44**、
その**部分集合**である平ら **8.05時間** の `sum_confirmed` が **+265** ＝ **短いほうが大きい**。
伸びは足されるだけなので、部分集合が本体を越えることは起こり得ません。
出どころは `sum_confirmed` の輪が `a`（窓の頭の点）を要る側に入っていたこと ——
窓の中で公開された本は `a` が無いので `skipped` で `continue` し、**分子に 1回も入りません**。
実物は `mja40GJ-GHU`（09/11 10:00 公開・確かめられる伸び **917回**）で、窓の分子は 44 → **961**
（`over` は False のまま ＝ 門は偽で引きません）。

**抑えは `a` ではなく `min(late)`** で、それは本が窓の頭に在ったかを要りません:
`v(s) >= true(s - 遅れ) >= true(t0)` は `true(t0)` が **0（まだ公開されていない）**でも成り立ちます。
＝ **(m) の門（合計 ＞ チャンネル ＝ 説明の付かない唯一の向き）は、
いちばん速く伸びる本だけを構造的に見ていませんでした。**

**きょうの状態を不変条件として書かないこと**（METHOD §5 教訓の形 6つ目）＝ 刻はその場で組みます。

**陽性対照**（壊したら落ちるまで撃つ・教訓の形 3つ目。`.pyc` を消してから撃った）:
`a is None` を `skipped` + `continue` に戻すと **2件**（分子・単調）／
`b - (a if a is not None else 0)` を `b - a` に戻すと **3件**（`a` が `None` で `TypeError`）／
`out["no_base"]` を数えない形に戻すと **1件**。
"""
from __future__ import annotations

import datetime as dt

from studio import trend


def _vid(at: str, vid: str, views: int, age_h: float) -> dict:
    """**`age_h` は点ごとに違えること** —— `trend.series` は齢 0.1 刻みで畳みます。"""
    return {"at": at, "id": vid, "event": "measured", "views": views, "age_h": age_h}


def _rows() -> list[dict]:
    """窓の頭 09-10 12:00 → 末 09-11 12:00（24時間・遅れ 2.8時間 より長い）。

    `newone` は窓の中（09-11 01:00）から点が始まり、**窓の頭に点を持ちません**。
    `oldone` は窓の手前に基準を持ち、窓の中で 540 → 560 に伸びます。
    """
    rows: list[dict] = []
    for h, v in ((10, 500), (14, 510), (20, 540)):
        rows.append(_vid(f"2026-09-10T{h:02d}:00:00+09:00", "oldone", v, age_h=100.0 + h))
    rows.append(_vid("2026-09-11T11:00:00+09:00", "oldone", 560, age_h=125.0))
    for h, v in ((1, 0), (4, 40), (8, 300)):
        rows.append(_vid(f"2026-09-11T{h:02d}:00:00+09:00", "newone", v, age_h=float(h)))
    rows.append(_vid("2026-09-11T11:00:00+09:00", "newone", 900, age_h=11.0))
    return rows


_T0 = dt.datetime.fromisoformat("2026-09-10T12:00:00+09:00")
_T1 = dt.datetime.fromisoformat("2026-09-11T12:00:00+09:00")


def test_窓の中で公開された本は_合計からだけ外れる() -> None:
    vd = trend.channel_video_delta(_rows(), _T0, _T1)
    assert vd["n"] == 1 and vd["skipped"] == 1 and vd["no_base"] == 1
    # 生の合計は基準を持つ本だけ（`oldone` の包絡 窓の頭 500 → 末 560）
    assert vd["sum"] == 60


def test_窓の中で公開された本が_確かめられた伸びに入る() -> None:
    vd = trend.channel_video_delta(_rows(), _T0, _T1)
    # `newone` の抑えは `min(late)` ＝ 0（09-11 01:00 の読み）→ 900 が丸ごと入る。
    # `oldone` の抑えは 540（遅れ 2.8時間 の外のいちばん小さい生の読み）→ 560 - 540 ＝ 20。
    assert vd["grew"] == 2
    assert vd["sum_confirmed"] == 920
    assert vd["blind"] == 0


def test_部分集合の窓が_本体を越えない() -> None:
    """**単調**: 同じ末で頭を後ろへ寄せた窓は、確かめられた伸びを増やせない。"""
    rows = _rows()
    whole = trend.channel_video_delta(rows, _T0, _T1)["sum_confirmed"]
    part = trend.channel_video_delta(
        rows, _T1 - dt.timedelta(hours=8), _T1)["sum_confirmed"]
    assert whole is not None and part is not None
    assert part <= whole


def test_窓が遅れより短ければ_確かめられない() -> None:
    vd = trend.channel_video_delta(_rows(), _T1 - dt.timedelta(hours=1), _T1)
    assert vd["sum_confirmed"] is None
