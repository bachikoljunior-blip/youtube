"""`trend.envelope`（単調な包絡）の検査（2026-09-09 20:0x・optimizer・Opus）。

**なぜ**: `videos.list` は伸びている本を遅れの違う **3つ** の複製から返す（`trend.envelope` の註）。
生の並びは偽の減り（-74回）と偽の平らを出す。**陽性対照つき** —— 包絡を外すと落ちる形にしてある。
"""
from __future__ import annotations

import datetime as dt

from studio import trend


def _pt(age: float, views: int, at: str = "2026-09-09T20:00:00+09:00") -> dict:
    return {"event": "measured", "id": "V1", "age_h": age, "views": views, "at": at}


def _rows(vals: list[tuple[float, int]]) -> list[dict]:
    base = dt.datetime(2026, 9, 9, 10, 0, tzinfo=trend.JST)
    return [{"event": "measured", "id": "V1", "age_h": a, "views": v,
             "at": (base + dt.timedelta(hours=a)).isoformat()} for a, v in vals]


def test_包絡はそれまでの最大を返す():
    pts = [_pt(1, 543), _pt(2, 711), _pt(3, 637), _pt(4, 829)]
    assert trend.envelope(pts) == [543, 711, 711, 829]


def test_包絡は一度も下げない():
    """陽性対照: 生の並びには減りが在る（＝ この検査は「減りが無い入力」で通っていない）。"""
    pts = [_pt(1, 100), _pt(2, 90), _pt(3, 80), _pt(4, 95)]
    raw = [int(p["views"]) for p in pts]
    assert any(b < a for a, b in zip(raw, raw[1:]))  # 入力には減りが在る
    env = trend.envelope(pts)
    assert all(b >= a for a, b in zip(env, env[1:]))
    assert env == [100, 100, 100, 100]


def test_平らな本は包絡でも動かない():
    """陰性対照: 落ち着いた本（10回 読んで差 0）は 1点も上がらない。"""
    pts = [_pt(50, 66), _pt(51, 66), _pt(52, 66)]
    assert trend.envelope(pts) == [66, 66, 66]


def test_伸びは包絡で数える_偽の減りを出さない():
    """09/09 19:09 の実物（711 → 637 ＝ -74回）。生で数えると負、包絡なら +0。"""
    pts = [_pt(8.2, 711), _pt(9.1, 637)]
    assert "-74回" in trend._growth(pts)                      # 生（＝ 直す前の形）
    assert "+0回" in trend._growth(pts, trend.envelope(pts))   # 包絡


def test_lines_は上げた点に生の値を添える():
    rows = _rows([(8.2, 711), (9.1, 637), (9.2, 829)])
    rows.append({"event": "scheduled", "video_id": "V1"})
    out = "\n".join(trend.lines(rows, within_h=72,
                               now=dt.datetime(2026, 9, 9, 20, 0, tzinfo=trend.JST)))
    assert "9.1h 711(生 637)" in out          # 上げた点は生も見える
    assert "8.2h 711 →" in out                # 上げていない点はそのまま
    assert "(生 711)" not in out               # 上げていない点には付かない


def test_drops_は生のまま数え続ける():
    """包絡は台帳を書き換えない —— §7 が引いている生の減りは残ること。"""
    rows = _rows([(8.2, 711), (9.1, 637)])
    n_pairs, n_dec, worst, _ = trend.drops(rows)
    assert n_dec == 1 and worst == -74
