"""`trend.channel_steps` の検査（2026-09-11 02:2x・optimizer・Opus。**API 0単位**）。

**なぜ足したか（この回に実物で踏んだ）**: `channel_line` は窓の両端から
**`views_per_h`（回/時）**を出す。**総再生が刻みで動くとき、その数は率ではない** ——
実測 2026-09-11 02:12 JST: `viewCount` は **18周・10.2〜10.8時間** ずっと **84,781** で、
**02:12 の 1点 で +1,625** して 86,406 になった。同じ窓の `channel_line` は
**+150.5回/時** と印字するが、**その 150.5 が実際に立った瞬間は 1つ も無い**
（窓のほとんどは +0回/時・最後の 1点 だけが +1,625）。

**陽性対照**（下の `test_positive_control_*`）は、道具を壊すと落ちる形で書いてある:
刻みを畳む／`one_step` の門を外す、で 1件ずつ落ちる。
"""
from __future__ import annotations

from studio import trend


def _row(at: str, views: int, subs: int = 28) -> dict:
    return {"at": at, "id": "UCxxx", "event": "channel",
            "subs": subs, "views": views, "videos": 269}


def _flat_then_jump() -> list[dict]:
    """この回の実物の形: 10時間 同じ読み → 最後の 1点 で +1,625。"""
    rows = [_row(f"2026-09-10T{h:02d}:24:42+09:00", 84781) for h in range(15, 24)]
    rows += [_row(f"2026-09-11T{h:02d}:24:42+09:00", 84781) for h in range(0, 2)]
    rows.append(_row("2026-09-11T02:12:43+09:00", 86406))
    return rows


def test_one_step_is_named() -> None:
    """刻みが 1つ の窓では、その 1つ と平らの長さが返る。"""
    st = trend.channel_steps(_flat_then_jump())
    assert len(st["steps"]) == 1
    L = st["last"]
    assert L["d"] == 1625
    assert L["flat_laps"] == 11                      # 15:24〜01:24 の 11周
    assert 9.9 < L["flat_h_lo"] < 10.1               # 最初の読み → 最後の同じ読み
    assert L["flat_h_hi"] > L["flat_h_lo"]           # → 新しい値の最初の読み（上端）
    assert st["n_values"] == 2
    assert st["one_step"] is True


def test_line_says_the_rate_is_not_a_rate() -> None:
    """`channel_line` は「回/時 は率ではない」と自分で言う（次の回は覚えていなくてよい）。"""
    line = trend.channel_line(_flat_then_jump())
    assert "総再生は刻みで動きます" in line
    assert "+1625回 が 1点 で" in line
    assert "率ではなく" in line


def test_smooth_window_is_not_called_one_step() -> None:
    """**陰性対照**: 毎周 動く窓では刻みらしさが立たない（刻みではなく伸び）。"""
    rows = [_row(f"2026-09-10T{h:02d}:00:00+09:00", 84781 + 40 * i)
            for i, h in enumerate(range(10, 20))]
    st = trend.channel_steps(rows)
    assert st["n_values"] == 10
    assert st["one_step"] is False
    assert len(st["steps"]) == 9
    assert st["move_rate"] == 1.0                      # 9区間 のうち 9区間 で動いた
    assert st["stepwise"] is False
    assert "率ではなく" not in trend.channel_line(rows)


def test_never_moved_has_no_step() -> None:
    """1度も動いていない窓は `last is None`（**0 を返さないこと**）。"""
    rows = [_row(f"2026-09-10T{h:02d}:00:00+09:00", 84781) for h in range(10, 20)]
    st = trend.channel_steps(rows)
    assert st["steps"] == []
    assert st["last"] is None
    assert st["one_step"] is False
    assert "総再生は刻みで動きます" not in trend.channel_line(rows)


def test_same_round_rows_are_one_lap() -> None:
    """同じ周の 2体 が数十秒 差で書いた 2行 は **1周**（`_channel_laps` と同じ畳み方）。"""
    rows = [_row("2026-09-10T15:24:42+09:00", 84781),
            _row("2026-09-10T15:24:58+09:00", 84781),
            _row("2026-09-11T02:12:43+09:00", 86406),
            _row("2026-09-11T02:12:59+09:00", 86406)]
    st = trend.channel_steps(rows)
    assert st["laps"] == 2
    assert st["last"]["flat_laps"] == 1


def test_positive_control_collapsing_the_step_is_caught() -> None:
    """**陽性対照**: 刻みを畳んで「ずっと同じ」にすると、上の 2件 が落ちる形になる。"""
    rows = _flat_then_jump()
    broken = [dict(r, views=84781) for r in rows]     # 刻みを消す
    st = trend.channel_steps(broken)
    assert st["last"] is None                          # ＝ test_one_step_is_named が落ちる
    assert "総再生は刻みで動きます" not in trend.channel_line(broken)


def test_two_steps_still_say_the_rate_is_not_a_rate() -> None:
    """**2026-09-12 23:2x に向きを直した**（optimizer・Opus）。

    もとは「刻みが 2つ 在る窓で `one_step` が立つなら門が壊れている ＝ 3値 は
    **率として読み始めてよい側**」と書いてあり、**その字が欠陥そのもの**だった ——
    `n_values` は台帳が伸びれば積もるだけなので、**2本目 の刻みが載った刻から
    印字が消え、次の回は裸の「回/時」を読む**ことになっていた（`channel_steps` の覆る条件 (3)）。
    **12区間 のうち動いたのは 2区間 ＝ 刻みは 1つ のときより濃くなっている。**
    """
    rows = _flat_then_jump()
    rows.append(_row("2026-09-11T03:12:43+09:00", 88000))
    st = trend.channel_steps(rows)
    assert len(st["steps"]) == 2
    assert st["n_values"] == 3
    assert st["one_step"] is False                     # 残してあるだけ（写し）
    assert st["moved"] == 2 and st["gaps"] == 12
    assert st["move_rate"] < trend.CHANNEL_SMOOTH_RATE
    assert st["stepwise"] is True
    assert "率ではなく" in trend.channel_line(rows)


def test_move_rate_does_not_move_with_the_window() -> None:
    """**この回の欠陥の当のもの**: 刻みらしさは**窓の長さでは動かない**こと。

    同じ形（12時間 ごとに 1度 動く）を **2倍 の長さ**で並べても、`move_rate` は同じ帯に
    留まる。`n_values`（＝ 刻み ＋1）は **倍に増える** —— そちらで門を引いていたのが欠陥。
    """
    def _at(h: int) -> str:
        return f"2026-09-{10 + h // 24:02d}T{h % 24:02d}:30:00+09:00"

    def _steppy(n_blocks: int) -> list[dict]:
        """12周 同じ読み → +1,000 を `n_blocks` 回 くり返す（1時間 に 1周）。"""
        return [_row(_at(i), 84781 + 1000 * (i // 12))
                for i in range(12 * n_blocks)]

    short = trend.channel_steps(_steppy(2))
    long = trend.channel_steps(_steppy(4))
    assert long["n_values"] > short["n_values"]         # 窓で動く数
    assert short["stepwise"] is True and long["stepwise"] is True
    assert abs(long["move_rate"] - short["move_rate"]) < 0.05   # 窓では動かない


def test_positive_control_gate_on_n_values_is_caught() -> None:
    """**陽性対照**: 門を `n_values` の側（もとの形）へ戻すと、上の 2件 が落ちる。

    もとの形 ＝ `one_step`（`n_values <= 2`）。刻みが 2本 以上 の窓では **必ず偽**なので、
    印字が消える ＝ `test_two_steps_still_say_the_rate_is_not_a_rate` が落ちる。
    """
    rows = _flat_then_jump()
    rows.append(_row("2026-09-11T03:12:43+09:00", 88000))
    st = trend.channel_steps(rows)
    assert st["stepwise"] != st["one_step"]            # 2つ の門は、この窓で答えが違う


def test_positive_control_smooth_gate_is_not_always_true() -> None:
    """**陽性対照**: `stepwise` を「刻みが 1本 でも在れば真」にすると落ちる形。

    毎周 動く窓（伸び）では **偽**でなければならない —— 真になるなら、
    `views_per_h` を率として読める窓が二度と来ない（覆る条件 (3-a) が永久に引けない）。
    """
    rows = [_row(f"2026-09-10T{h:02d}:00:00+09:00", 84781 + 40 * i)
            for i, h in enumerate(range(10, 20))]
    st = trend.channel_steps(rows)
    assert st["steps"] != [] and st["stepwise"] is False
