"""`trend.channel_over_blocks` / `channel_over_streak` の検査
（2026-09-10 21:4x・optimizer・Opus。**API 0単位**）。

**なぜ足したか**: §7 (m) は「`sum_confirmed` が 0 でない窓で総再生が動かない回が **3周** 続いたら、
(m) の当て所ごと作り直す」と書いていたが、**その 3周 を数える口がどこにも無く**、
しかも `channel_growth` の窓は**台帳の `channel` の行の両端**なので周が進むほど伸びるだけで、
`sum_confirmed` は**単調に増えるだけ**だった（`cut = t0 + REPLICA_LAG_H` の `t0` が動かない ＝
`late` は増える一方で `min(late)` は下がる一方・包絡 `b` は上がる一方）。
＝ **1度 引かれた門は、新しい証拠が 1つも無くても次の周・その次の周と引かれ続ける。**
実測（21:2x の回に 11周 を1周ずつ再生した）: `over` は 10周 とも False で、21:20 の周に初めて True。
その中身は `gv1u7n_pCAQ` の **930 → 932（+2回）** 1本 だけで、**同じ +2 が次の周もこの窓に居る**。

→ 数えるのは**重ならない塊**（1塊 ＝ 遅れの 2倍）。下の `test_positive_control_*` は、
道具を壊すと落ちる形で書いてある。
"""
from __future__ import annotations

import datetime as dt

from studio import trend


def _row(at: str, subs: int, views: int) -> dict:
    return {"at": at, "id": "UCxxx", "event": "channel",
            "subs": subs, "views": views, "videos": 269}


def _m(at: str, vid: str, views: int, age_h: float) -> dict:
    return {"at": at, "id": vid, "event": "measured", "views": views, "age_h": age_h}


def _hourly(n: int, views_at: dict[int, int], *, ch_views: int = 84781) -> list[dict]:
    """0時 から n-1時 まで 1時間おきの周。`views_at` は「その周からの本の読み」。"""
    rows: list[dict] = []
    cur = views_at[0]
    for h in range(n):
        at = f"2026-09-10T{h:02d}:00:00+09:00"
        cur = views_at.get(h, cur)
        rows.append(_row(at, 28, ch_views))
        rows.append(_m(at, "aaa", cur, 50.0 + h))
    return rows


# 21周（00:00〜20:00）・本の読みは最後の周だけ +2 ＝ **証拠は 1回 だけ**
_ONE_EVENT = _hourly(21, {0: 100, 20: 102})


def test_窓ぜんたいの門は1回の証拠で引かれる():
    """まず、いまの `over` がこの形で True になることを固定する（実測 21:20 の形）。"""
    g = trend.channel_growth(_ONE_EVENT)
    assert g["d_views"] == 0
    assert g["vid_sum"] == 2 and g["vid_confirmed"] == 2
    assert g["over"] is True


def test_同じ1回の証拠は次の周も窓に居る():
    """**この検査が、足した理由そのもの** —— 周を1つ足しても（新しい伸びは 0）、
    窓ぜんたいの `over` は True のまま ＝ 周で数えると 3周 が勝手に埋まる。"""
    rows = list(_ONE_EVENT)
    for h in (21, 22):
        at = f"2026-09-10T{h:02d}:00:00+09:00"
        rows += [_row(at, 28, 84781), _m(at, "aaa", 102, 50.0 + h)]
        assert trend.channel_growth(rows)["over"] is True   # 新しい証拠は 0 なのに毎周 True
    # **塊で数えれば、証拠は 1つ のまま**
    assert trend.channel_over_streak(rows)["streak"] == 1


def test_塊は重ならず長さは遅れの2倍以上():
    bs = trend.channel_over_blocks(_ONE_EVENT)
    assert len(bs) == 3
    for b in bs:
        assert b["span_h"] >= trend.CHANNEL_BLOCK_MIN_H
    # 返るのは新しい順・塊どうしは重ならない
    for newer, older in zip(bs, bs[1:]):
        assert older["t1"] < newer["t0"]


def test_連なりは1のまま_塊が3つ_そろっても引かれない():
    st = trend.channel_over_streak(_ONE_EVENT)
    assert st["blocks"] == 3 and st["ready"] is True
    assert st["streak"] == 1 and st["drawn"] is False
    line = trend.channel_line(_ONE_EVENT)
    assert "いま 1/3 塊" in line
    assert "「1周ぶん」と数え足さないこと" in line


def test_塊ごとに証拠が在れば連なりは埋まる():
    """3塊 とも「遅れの外で確かめられた伸び」が在る形 ＝ 16.8時間 ぶんの重ならない証拠。"""
    rows = _hourly(21, {0: 100, 6: 102, 13: 104, 20: 106})
    st = trend.channel_over_streak(rows)
    assert st["blocks"] == 3 and st["streak"] == 3 and st["drawn"] is True
    assert "引かれました ＝ (m) の当て所ごと作り直すこと" in trend.channel_line(rows)


def test_over_でない塊が入ると連なりは切れる():
    """いちばん新しい塊に証拠が在っても、その 1つ前が静かなら連なりは 1 で止まる。"""
    rows = _hourly(21, {0: 100, 6: 102, 20: 104})   # まん中の塊（07:00〜13:00）は動かない
    st = trend.channel_over_streak(rows)
    assert st["blocks"] == 3 and st["streak"] == 1 and st["drawn"] is False


def test_総再生が動いた塊は引かれない():
    """門は片側だけ ＝ 総再生が本ごとの合計を受け取っていれば、その塊は over ではない。"""
    rows = _hourly(21, {0: 100, 20: 102}, ch_views=84781)
    # いちばん新しい塊のあいだに総再生も +2 動かす
    rows = [r for r in rows if not (r["event"] == "channel" and r["at"] >= "2026-09-10T20:00")]
    rows.append(_row("2026-09-10T20:00:00+09:00", 28, 84783))
    st = trend.channel_over_streak(rows)
    assert st["streak"] == 0


def test_点が足りなければ塊は切れない():
    """窓が 1塊 の長さに届かないうちは `blocks` 0 ＝ **まだ言えない**（0 を「引けない」と読める形）。"""
    rows = _hourly(5, {0: 100, 4: 102})     # 4時間 ＜ 5.6時間
    st = trend.channel_over_streak(rows)
    assert st["blocks"] == 0 and st["streak"] == 0 and st["ready"] is False


def test_positive_control_周で数えると同じ1回の証拠で連なりが埋まる():
    """**陽性対照（別の実装で数え直す）**: 「窓ぜんたいの `over` を周ごとに数える」——
    直した前の形をここに組んで、`_ONE_EVENT`（証拠 1回）でも **3周 で門に着く**ことを見る。

    METHOD §5 の教訓の形 1つ目（「確かめる手は、元の手と違う物を見ているか」）に従い、
    判定は `channel_over_blocks` を**通さず** `channel_growth` の `over` から直に組む。
    塊で数える側は、同じ 3周 のあいだ **1 のまま**であること。
    """
    rows = list(_ONE_EVENT)
    by_lap, by_block = 0, []
    for h in (21, 22, 23):
        at = f"2026-09-10T{h:02d}:00:00+09:00"
        rows += [_row(at, 28, 84781), _m(at, "aaa", 102, 50.0 + h)]   # 新しい伸びは 0
        if trend.channel_growth(rows)["over"]:
            by_lap += 1                       # ← **直す前の数え方**
        by_block.append(trend.channel_over_streak(rows)["streak"])
    assert by_lap == trend.CHANNEL_FLAT_LAPS  # 周で数えると、証拠 1回 で門に着く
    # 塊で数えれば **1 を越えず**、しかも証拠が古くなると**自分で手を放します**
    # （3周目 で 0 ＝ 20:00 の +2 が塊の「遅れの外」の区間に飲まれ、
    #  102 の読みが 塊の頭の真の値を 102 まで上から抑える ＝ 確かめられる伸びが 0 になる）。
    assert by_block == [1, 1, 0]


def test_positive_control_塊の長さを遅れちょうどにすると伸びを数えられない():
    """**陽性対照（定数の側）**: 1塊 を `REPLICA_LAG_H` ちょうどにすると、塊の中の
    「遅れの外の読み」は末尾の 1点 だけになり、`sum_confirmed` は伸びではなく
    **複製の揺れ**を数える ＝ `_ONE_EVENT` の +2 が消えること。
    """
    laps = trend._channel_laps(trend._channel_rows(_ONE_EVENT))
    t1 = trend._at(laps[-1][-1])
    t0 = t1 - dt.timedelta(hours=trend.REPLICA_LAG_H)
    a = [l[0] for l in laps if trend._at(l[0]) <= t0][-1]
    g = trend._channel_gate(_ONE_EVENT, a, laps[-1][-1])
    assert g["vd"]["sum"] == 2          # 伸びは在る
    assert g["conf"] == 0               # なのに「確かめられた」は 0 ＝ この長さでは数えられない
    assert trend.CHANNEL_BLOCK_MIN_H == 2 * trend.REPLICA_LAG_H
