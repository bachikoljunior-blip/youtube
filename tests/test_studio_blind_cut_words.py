"""**連なりを数える口を足す回は、増える枝と切れる枝の両方に印字を置くこと。**

2026-09-13 17:0x・optimizer・Opus。**API 0単位** —— 台帳を1行も読まず、形だけをその場で組む。

**踏んだ形（実物）**: 16:0x の周は `blind == grew` が **1周** 続き、§7「いまの数」はその 1周 を
写した。16:4x の周で伸びが確かめられ（`proves_alive is True`）連なりは **0** に切れたのに、
`channel_line` / `channel_line_short` が `blind_run_words` を呼ぶのは
**`blind` が立っている枝**と **`proves_alive is False` の枝**の 2つ だけで、
**連なりを切る枝（`flat_alive`）は 1字も言わない** ＝ §7 は「1周」を写し続ける。
`blind_run_words` の註が数えた 教訓の形 7つ目 の **4例目**（向きだけが逆 ＝ 立った周ではなく切れた周）。

**陽性対照**（壊したら落ちるまで撃つ・教訓の形 3つ目。`__pycache__` を消してから撃った）:
`channel_line` の `flat_alive` の枝から `blind_cut_words` を外すと **1件**／
短い行から外すと **1件**／`run`/`false_run` が 0 でないときも喋る形にすると **1件**／
`laps == 0` で空文字を返さない形にすると **1件**。
"""
from __future__ import annotations

from studio import trend

DAY = "2026-09-10"


def _t(hh: float) -> str:
    h = int(hh)
    m = int(round((hh - h) * 60))
    return f"{DAY}T{h:02d}:{m:02d}:00+09:00"


def _ch(hh: float, views: int) -> dict:
    return {"at": _t(hh), "id": "UCxxx", "event": "channel",
            "subs": 28, "views": views, "videos": 269}


def _vid(hh: float, views: int) -> dict:
    return {"at": _t(hh), "id": "newone", "event": "measured",
            "views": views, "age_h": round(hh, 1)}


def _alive_laps() -> list[dict]:
    """**平らの中で伸びが確かめられた周**（`proves_alive is True` ＝ 連なりを切る枝）。

    平らの頭は 13:00・遅れ（`REPLICA_LAG_H` ＝ 2.8時間）の後に読みが **2点 以上**在るので
    抑え `min(late)` が窓の中に落ち、`sum_confirmed` が正になる。
    """
    rows = [_ch(h, 84781) for h in (10.0, 11.0, 12.0)]
    rows.append(_ch(13.0, 86406))                      # 刻み ＝ 平らの頭
    rows += [_ch(h, 86406) for h in (14.0, 15.0, 16.0, 16.5, 17.0)]
    rows.append(_vid(12.5, 0))                         # 窓の頭の手前 ＝ 基準
    rows.append(_vid(16.0, 100))
    rows.append(_vid(16.5, 150))
    rows.append(_vid(17.0, 176))
    return rows


def test_切る周では_2つ_とも_0_で言う() -> None:
    rows = _alive_laps()
    g = trend.flat_video_gain(rows)
    assert g["proves_alive"] is True                   # この枝であることを先に押さえる
    b = trend.blind_run(rows)
    assert b["run"] == 0 and b["false_run"] == 0
    out = trend.blind_cut_words(rows)
    assert "0/3周" in out and "blind_run" in out


def test_full_の線が_切ったことを言う() -> None:
    """**増える側だけに印字を置くと、写した側が古いまま残ります。**"""
    line = trend.channel_line(_alive_laps())
    assert "連なりを切ります" in line
    assert "0/3周" in line


def test_短い行も_同じ口から言う() -> None:
    """`channel_line_short` の覆る条件 (2)（2つ が違う verdict を言ったら片方を消す）。"""
    short = trend.channel_line_short(_alive_laps())
    assert "連なりは 2つ とも切れました" in short
    assert "0/3周" in short


def _blind_laps() -> list[dict]:
    """**連なりが立っている周**（`blind == grew` ＝ 切る枝ではない側）。"""
    rows = [_ch(h, 84781) for h in (10.0, 11.0, 12.0)]
    rows.append(_ch(13.0, 86406))
    rows += [_ch(h, 86406) for h in (14.0, 15.0, 16.0, 16.2, 16.4)]
    rows.append(_vid(12.5, 0))
    rows.append(_vid(14.0, 100))
    rows.append(_vid(16.0, 176))                       # 遅れの後の唯一の点 ＝ blind
    return rows


def test_立っている周では_この口は何も言わない() -> None:
    """覆る条件 (1) ＝ 枝の前提が崩れている回は、**静かに黙る**（別の口が喋る側）。"""
    rows = _blind_laps()
    assert trend.blind_run(rows)["run"] > 0
    assert trend.blind_cut_words(rows) == ""
    assert trend.blind_cut_words(rows, short=True) == ""


def test_台帳に周が無ければ空() -> None:
    assert trend.blind_cut_words([]) == ""
