"""`trend.flats`（平らな区間が伸びを取り戻したか）の検査（2026-09-10 08:4x・optimizer・Opus）。

**なぜ**: 冒頭の註「平らは『止まった』ではない」の覆る条件（「一度も伸びない本が 3本」）を
**数える所がどこにも無く**、しかも文字どおり読むと**落ち着いた本は全部そこに当たり**ました
（どの本も最後は平らで終わる）。＝ 引けない条件ではなく、**いつでも引けてしまう条件**。
**陽性対照つき** —— 開いている平らを長さで見ない形へ戻すと落ちる。
**門 `FLAT_STOP_H` は 20.9時間（`EkNqtkK49Bw` が平らのあとに伸びた長さ）より上**でなければならない。
"""
from __future__ import annotations

import datetime as dt

from studio import trend


def _rows(vals: list[tuple[float, int]], vid: str = "V1") -> list[dict]:
    base = dt.datetime(2026, 9, 9, 10, 0, tzinfo=trend.JST)
    out: list[dict] = [{"event": "scheduled", "video_id": vid, "at": base.isoformat()}]
    out += [{"event": "measured", "id": vid, "age_h": a, "views": v,
             "at": (base + dt.timedelta(hours=a)).isoformat()} for a, v in vals]
    return out


def test_伸びを取り戻した平らを数える():
    """実物の形（`lQHX9LJ80Sg` 齢 30.3→33.2h の 468 が 5点 続き、34.0h で 501）。"""
    got = trend.flats(_rows([(30.3, 468), (31.3, 468), (32.2, 468), (33.2, 468), (34.0, 501), (45.6, 536)]))
    assert got["resumed"] == 1
    assert got["stayed"] == []


def test_短い平らは数えない():
    """陰性対照: 測りの間隔（床 41分）と区別が付かない長さは平らと呼ばない。"""
    got = trend.flats(_rows([(30.3, 468), (30.9, 468), (31.5, 501), (45.0, 536)]))
    assert got["resumed"] == 0


def test_まだ見ている途中の平らは_戻らないままに数えない():
    """**陽性対照の当のもの**: 開いている平らを長さで見ずに `stayed` へ入れると、
    毎周それが入って「3件」がすぐ埋まる（＝ いつでも引けてしまう条件に戻る）。"""
    got = trend.flats(_rows([(17.4, 927), (18.8, 927), (20.2, 927), (21.6, 927)]))
    assert got["stayed"] == []
    assert got["open"] == 1


def test_24時間を越えて戻らなければ数える():
    got = trend.flats(_rows([(17.4, 927), (25.0, 927), (35.0, 927), (44.0, 927)]))
    assert len(got["stayed"]) == 1
    assert got["stayed"][0]["views"] == 927
    assert got["resumed"] == 0


def test_48hを越えた平らは数えない():
    """陰性対照: 48h 超の平らは「止まり」と読んでよい側（比べる相手が無い）。"""
    got = trend.flats(_rows([(50.0, 66), (55.0, 66), (60.0, 66), (69.6, 66)]))
    assert got["stayed"] == [] and got["resumed"] == 0


def test_こちらの作りの本だけ数える():
    rows = _rows([(17.4, 927), (18.8, 927), (20.2, 927), (30.0, 927)])
    rows = [r for r in rows if r.get("event") != "scheduled"]  # scheduled が無い ＝ 旧作り
    assert trend.flats(rows)["stayed"] == []


# ---- 2026-09-10 09:2x に足した（optimizer・Opus）。**陽性対照 3つ を撃って落とした** ----
# 08:4x の形は `stayed` を **1件も** 数えられませんでした（門が平らの「終わり」に在った）。
# 下の 3件 は、その直しを戻すと 1件ずつ落ちます。


def test_48hの手前で始まり48hを越えて続く平らを数える():
    """**陽性対照の当のもの**（実物 `nQbVxuWpWw8` 齢 8.6→70.2h・61.6時間・66回）。

    伸びが戻らない平らは、定義から**並びの最後の点まで続く**ので、`ages[j]` は必ず「いまの齢」。
    門を平らの**終わり**（`ages[j] < 48.0`）に置くと、落ち着いた本の平らは 1件も通らない。
    **08:4x の検査データには、この形が1つも無かった**（`test_48hを越えた平らは数えない` は
    始まりも 50h）——だから 08:4x は緑のまま、`stayed` は永久に空だった。
    """
    got = trend.flats(_rows([(8.6, 66), (20.0, 66), (37.1, 66), (55.0, 66), (70.2, 66)]))
    assert got["resumed"] == 0
    assert [r["id"] for r in got["stayed"]] == ["V1"]
    assert abs(got["stayed"][0]["len_h"] - 61.6) < 0.05


def test_門は定数ではなく実測でいちばん長い戻った平ら():
    """**陽性対照**: `FLAT_STOP_H`（24時間）を直に門にすると、この 26時間 の平らが
    `stayed` に入ってしまう。実測では **30時間 平らのあとに伸びた本**が同じ台帳に居るので、
    26時間 では「止まった」と言えない（覆る条件 (2) を、手ではなく道具が引く）。"""
    rows = _rows([(5.0, 100), (35.0, 100), (36.0, 200), (60.0, 200)], vid="V1")  # 30.0h 戻った
    rows += _rows([(5.0, 40), (14.0, 50), (31.0, 50), (40.0, 50)], vid="V2")     # 26.0h 戻らない
    got = trend.flats(rows)
    assert got["longest_resumed_h"] >= 30.0
    assert got["thresh_h"] >= 30.0
    assert got["stayed"] == []          # 26時間 < 30時間 ＝ まだ言えない
    # V2 の 26時間 と、V1 自身の終わりの平ら（36.0→60.0h ＝ 24時間）の 2件 が「まだ言えない」側。
    assert got["open"] == 2


def test_境目の2つを印字する():
    """**陽性対照**: 印字が `ENVELOPE_LAG_H`（6時間・別の道具の定数）を読んでいると落ちる。
    2026-09-10 09:2x まで、門は 24時間 なのに **「6時間 以上 見た」と印字**していた。"""
    rows = _rows([(8.6, 66), (37.1, 66), (70.2, 66)], vid="V1")
    rows += _rows([(9.6, 127), (30.5, 127), (31.5, 140), (94.2, 140)], vid="V2")
    line = [ln for ln in trend.lines(rows) if "平らは「止まった」ではない" in ln][0]
    assert "24.0時間 より長く見た" in line
    assert "20.9時間" in line and "61.6時間" in line
    assert f"{trend.ENVELOPE_LAG_H:.0f}時間 以上 見た" not in line
