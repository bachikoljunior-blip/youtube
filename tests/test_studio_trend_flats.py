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


# ---- 2026-09-10 08:2x に足した（optimizer・Opus）。**陽性対照 3つ を撃って落とした** ----
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
    2026-09-10 08:2x まで、門は 24時間 なのに **「6時間 以上 見た」と印字**していた。"""
    rows = _rows([(8.6, 66), (37.1, 66), (70.2, 66)], vid="V1")
    rows += _rows([(9.6, 127), (30.5, 127), (31.5, 140), (94.2, 140)], vid="V2")
    line = [ln for ln in trend.lines(rows) if "平らは「止まった」ではない" in ln][0]
    assert "24.0時間 より長く見た" in line
    assert "20.9時間" in line and "61.6時間" in line
    assert f"{trend.ENVELOPE_LAG_H:.0f}時間 以上 見た" not in line


# ---- 2026-09-13 18:0x に足した（optimizer・Opus）----
# **ずっと 0回 の本は `resumed` に構造として入れない**（`env[-1] > env[i]` が 0 > 0 で必ず偽）
# ＝ 混ぜると境目の**上端だけ**が毎周 下がり、測っていないのに幅が狭まる。


def test_ずっと0回の本は境目に入れない():
    """**陽性対照の当のもの**（実物 `2YZ_4FXC-XI` 齢 0.3→79.7h・ずっと 0回）。

    絞りを外すと、この本が `shortest_stayed_h` を 79.4時間 へ引き下げ、
    **「79.4時間 平らなら止まった」の唯一の根拠が、1度も配られなかった本**になる。
    """
    rows = _rows([(5.0, 100), (35.0, 100), (36.0, 200), (60.0, 200)], vid="V1")   # 30.0h 戻った
    rows += _rows([(8.0, 300), (40.0, 300), (60.0, 300), (120.0, 300)], vid="V2")  # 112h 戻らない
    rows += _rows([(0.3, 0), (20.0, 0), (50.0, 0), (79.7, 0)], vid="Z1")           # ずっと 0回
    got = trend.flats(rows)
    assert got["zero_view"] == ["Z1"]
    assert [r["id"] for r in got["stayed"]] == ["V2"]
    assert abs(got["shortest_stayed_h"] - 112.0) < 0.05   # 79.4 ではない


def test_0回でも伸び始めた本は数える():
    """**陰性対照**（覆る条件 (4)）: 外しているのは**ずっと 0回**の本だけ。
    1回でも付いた本は、頭が 0回 の平らでもそのまま数える。"""
    rows = _rows([(0.3, 0), (20.0, 0), (50.0, 0), (60.0, 12)], vid="Z2")
    got = trend.flats(rows)
    assert got["zero_view"] == []
    assert got["resumed"] == 1


def test_外した本を印字する():
    """**陽性対照**: 黙って外すと、次の回は「境目が広がった」理由を台帳から引けない。"""
    rows = _rows([(5.0, 100), (35.0, 100), (36.0, 200), (60.0, 200)], vid="V1")
    rows += _rows([(0.3, 0), (20.0, 0), (50.0, 0), (79.7, 0)], vid="Z1")
    line = [ln for ln in trend.lines(rows) if "平らは「止まった」ではない" in ln][0]
    assert "ずっと 0回 の本 1本" in line and "Z1" in line


# ---- 2026-09-14 12:1x に足した（optimizer・Opus）----
# **覆る条件 (4) が引かれた回**（`2YZ_4FXC-XI` が 齢 95.5〜97.1h で初めて 1回 配られ、
# 絞りを抜けて `longest_resumed_h` を 60.4 → 95.2時間 へ押し上げた）。
# **下端は `hold` / `views_streak` の `growing` の門そのもの** ＝ 再生 1回 で
# 35時間 ぶんの「まだ伸びている」が全部の本に足される。**手で外さない・黙らせない。**


def test_下端を持つ平らと戻りの大きさを返す():
    """**陽性対照**: `longest_resumed_h`（数）だけを返す形に戻すと落ちる。
    数だけでは、次の回は「なぜ 35時間 動いたか」を台帳から引き直すことになる。"""
    rows = _rows([(0.3, 0), (20.0, 0), (95.5, 0), (97.1, 1)], vid="Z3")   # 95.2h・戻り +1
    rows += _rows([(5.0, 100), (35.0, 100), (36.0, 200), (60.0, 200)], vid="V1")  # 30.0h・戻り +100
    got = trend.flats(rows)
    assert abs(got["longest_resumed_h"] - 95.2) < 0.05
    h = got["longest_resumed"]
    assert h["id"] == "Z3" and h["views"] == 0 and h["gain"] == 1
    assert got["thin"] is True


def test_戻りが大きい下端は名指しだけで註意を出さない():
    """**陰性対照**（覆る条件 (6)）: 註意が出るのは**戻りが `FLAT_THIN_GAIN` 以下**の回だけ。
    いつも出すと、次の回は「!!」を読み飛ばすようになる。"""
    rows = _rows([(5.0, 100), (40.0, 100), (41.0, 300), (60.0, 300)], vid="V1")  # 35.0h・戻り +200
    got = trend.flats(rows)
    assert got["thin"] is False
    line = [ln for ln in trend.lines(rows) if "平らは「止まった」ではない" in ln][0]
    assert "持ち主 **V1**" in line and "**戻りは +200回**" in line
    assert "戻り 1回 の平らが持っています" not in line


def test_戻り1回の下端は行で名指しされる():
    """**陽性対照の当のもの**（実物 `2YZ_4FXC-XI` 0回 → 1回）。
    名指しを外すと、次の回は 95.2時間 を 140回 の本が持っていると読む。"""
    rows = _rows([(0.3, 0), (20.0, 0), (95.5, 0), (97.1, 1)], vid="Z3")
    rows += _rows([(8.0, 300), (60.0, 300), (120.0, 300), (170.0, 300)], vid="V2")  # 上端（戻らない）
    line = [ln for ln in trend.lines(rows) if "平らは「止まった」ではない" in ln][0]
    assert "持ち主 **Z3**" in line and "平らのときの再生 **0回**" in line
    assert "**戻りは +1回**" in line
    assert "戻り 1回 の平らが持っています" in line
    # **註意は境目を言い終えたあと**（数の途中に割り込むと、幅の一文が読めなくなる）。
    assert line.index("まだ測れていません") < line.index("戻り 1回 の平らが持っています")


def test_下端が床のうちは註意を出さない():
    """**陰性対照**: `longest_resumed_h` が `FLAT_STOP_H`（24時間）に届かない回は、
    門は床のほうで決まっている ＝ その 1件 は何も決めていない。"""
    rows = _rows([(0.3, 0), (2.0, 0), (5.0, 0), (6.0, 1)], vid="Z4")   # 4.7h・戻り +1
    got = trend.flats(rows)
    assert got["thin"] is False
    assert abs(got["thresh_h"] - trend.FLAT_STOP_H) < 0.05
