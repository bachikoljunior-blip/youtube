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


# --- 数え直し（2026-09-10 08:0x・optimizer・Opus）------------------------------------
# **なぜ**: 台帳の 5本 で、生が包絡を **32.4〜95.4時間** 下回ったまま戻っていない（`envelope` の註）。
# 複製の遅れの実測は 最大 2.8時間 なので、遅れでは説明できない ＝ YouTube の数え直し（-1〜-2回）。
# 素の包絡はそれを永久に上げたままにし、§7 (E) は「2本目の最終は 66 ではなく 68」と書いていた。


def test_遅れの窪みは今までどおり上げる():
    """陰性対照: 6時間 以内に戻る窪み（＝ 遅れている複製）は、峰を落とさない。"""
    pts = _rows([(9.1, 711), (9.2, 637), (9.4, 829), (10.0, 886)])
    assert trend.envelope(pts) == [711, 711, 829, 886]
    assert trend.ceiling(pts) == 886


def test_戻らない減りは数え直しとして包絡を落とす():
    """実物の形（`nQbVxuWpWw8` 68 → 66 が 32.4時間）。**峰は 2点 続く**。"""
    pts = _rows([(36.0, 60), (37.1, 68), (37.2, 68), (37.3, 66), (50.0, 66), (69.6, 66)])
    assert trend.ceiling(pts) == 66
    # 峰 68 は天井 66 まで落ちる（＝ 数え直しは「起きた所」に出る。6時間 遅れて段は付かない）
    assert trend.envelope(pts) == [60, 66, 66, 66, 66, 66]


def test_峰が2点続いても落とせること():
    """**陽性対照ではありません**（この回に撃って確かめた）: `ceiling` の `>=` を `==` に変えても
    この検査は落ちず、実物 45本 とも天井は同じでした ＝ 効いているのは「降順に水準で見る」ほうだけ。
    見張りとしては残す（点ごとに見る形へ戻したら、峰が 2点 続くこの入力で落ちる）。"""
    two = _rows([(36.0, 68), (37.0, 68), (38.0, 66), (60.0, 66)])
    one = _rows([(36.0, 68), (38.0, 66), (60.0, 66)])
    assert trend.ceiling(two) == trend.ceiling(one) == 66


def test_まだ6時間経っていない峰は落とさない():
    """陰性対照: 伸び中の本の最新の点は、いつもここに当たる（落としたら伸びが消える）。"""
    pts = _rows([(20.0, 900), (20.7, 927), (21.4, 926), (21.6, 926)])
    assert trend.ceiling(pts) == 927
    assert trend.envelope(pts)[-1] == 927


def test_数え直しを並べる():
    rows = _rows([(36.0, 68), (37.1, 68), (37.3, 66), (69.6, 66)])
    got = trend.recounts(rows)
    assert len(got) == 1
    r = got[0]
    assert (r["id"], r["from"], r["to"]) == ("V1", 68, 66)
    assert r["hours_below"] > trend.ENVELOPE_LAG_H
    assert r["points_below"] == 2


def test_遅れの窪みは数え直しに数えない():
    """陽性対照: 上の `recounts` が「減った組」を素で拾っていたら、ここが落ちる。"""
    rows = _rows([(9.1, 711), (9.2, 637), (9.4, 829), (16.0, 886)])
    assert trend.recounts(rows) == []


def test_数え直した本の最終は生の水準になること():
    """§7 (E) の「2本目の最終は 66 ではなく 68」を、この直しが元へ戻すこと。"""
    pts = _rows([(37.1, 68), (37.3, 66), (69.6, 66)])
    assert trend.envelope(pts)[-1] == 66
