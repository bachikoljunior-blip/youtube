"""**平らの中で本が伸びていたら、その平らは「チャンネルが止まった」と読めない。**

2026-09-11 13:2x・optimizer・Opus。**API 0単位** —— 台帳を読むだけ。

**踏んだ形（この回の実物）**: 総再生は **20周・10.8時間** 同じ読みで、
`flat_readable`（平らが手本の挟みの上端 **10.793時間** を越えたか）が **この回に初めて True** になり、
`channel_line` は「**引かれました ＝ 本の題や形を疑う前に、チャンネルの側が止まっていないかを
外すこと**」と印字しました。**ところが同じ平らの中で 6本目 `mja40GJ-GHU` が 0 → 176回 に伸びています**
（平らの中の確かめられた伸びは **+22回**・本 46本）。＝ **チャンネルは止まっていません。
平らなのは `viewCount` の読みのほうです。**

時間の門（`flat_h` 対 `step_flat_h_hi`）は **手本 1例 からの挟み**で引く弱い門ですが、
`flat_video_gain` は**同じ台帳の中の反証**なので手本を要りません。**向きは片側だけ** ——
伸びが 0 でも「止まった」の証拠にはなりません（`measure` が触るのは 19本 だけ）。

**きょうの状態を不変条件として書かないこと**（METHOD §5 教訓の形 6つ目）＝
この検査は実物の台帳を1行も読まず、形だけをその場で組みます。

**陽性対照**（壊したら落ちるまで撃つ・教訓の形 3つ目。`.pyc` を消してから撃った）:
`flat_video_gain` が `sum`（見えるようになった分）を返す形に戻すと **1件**（短い平らの回。
**伸びている本の回では 2つ が同符号なので、そこでは見分けが付きません** —— だから
短い平らの側を残してあります）／平らの窓を台帳ぜんたいへ広げると **3件**／
`channel_line` が `flat_alive` を印字しない形に戻すと **1件**。
"""
from __future__ import annotations

from studio import trend


def _ch(at: str, views: int, subs: int = 28) -> dict:
    return {"at": at, "id": "UCxxx", "event": "channel",
            "subs": subs, "views": views, "videos": 269}


def _vid(at: str, vid: str, views: int, age_h: float) -> dict:
    """**`age_h` は点ごとに違えること** —— `trend.series` は齢 0.1 刻みで畳みます
    （同じ齢の行を並べると 1点 になり、伸びが 0 になる。この回に 1度 踏んだ）。"""
    return {"at": at, "id": vid, "event": "measured", "views": views, "age_h": age_h}


def _flat_with_a_growing_video() -> list[dict]:
    """刻み（+1,625）のあと、**平らが 12時間**。その平らの中で 1本 が 0 → 176回。"""
    rows = [_ch(f"2026-09-10T{h:02d}:00:00+09:00", 84781) for h in range(2, 14)]
    rows.append(_ch("2026-09-10T14:00:00+09:00", 86406))     # 刻み
    rows += [_ch(f"2026-09-11T{h:02d}:00:00+09:00", 86406) for h in range(0, 3)]
    # 平らは 09-10 14:00 → 09-11 02:00（12時間）。その中で伸びる本 1本 と、動かない本 1本。
    # **窓の頭に点を持たない本は外されます**（`channel_video_delta` の `skipped`）＝
    # 基準の点（13:00）を窓の手前に置くこと。
    for h, v in ((13, 0), (16, 0), (20, 40), (23, 120)):
        rows.append(_vid(f"2026-09-10T{h:02d}:05:00+09:00", "newone", v, age_h=float(h)))
    rows.append(_vid("2026-09-11T02:05:00+09:00", "newone", 176, age_h=26.0))
    for h in (13, 20):
        rows.append(_vid(f"2026-09-10T{h:02d}:05:00+09:00", "oldone", 500, age_h=100.0 + h))
    rows.append(_vid("2026-09-11T02:05:00+09:00", "oldone", 500, age_h=126.0))
    return rows


def test_平らの中の伸びを_平らの窓だけで数える() -> None:
    rows = _flat_with_a_growing_video()
    fv = trend.flat_video_gain(rows)
    assert fv["h"] is not None and 11.5 < fv["h"] < 12.5
    assert fv["proves_alive"] is True
    assert fv["confirmed"] > 0
    # **刻みの手前の平ら（09-10 02:00〜13:00）は、この窓に入れないこと**
    assert fv["t0"].day == 10 and fv["t0"].hour == 14


def test_線は_止まっていないと自分で言う() -> None:
    line = trend.channel_line(_flat_with_a_growing_video())
    assert "この平らの中で、本は" in line
    assert "チャンネルは止まっていません" in line
    assert "この平らを『本の 0回』の説明に使わないこと" in line


def test_伸びが0でも_止まったとは読ませない() -> None:
    """**向きは片側だけ**（`measure` が触るのは 19本 だけ ＝ 0 は証拠にならない）。"""
    rows = [_ch(f"2026-09-10T{h:02d}:00:00+09:00", 84781) for h in range(2, 14)]
    rows.append(_ch("2026-09-10T14:00:00+09:00", 86406))
    rows += [_ch(f"2026-09-11T{h:02d}:00:00+09:00", 86406) for h in range(0, 3)]
    for h in (13, 20):
        rows.append(_vid(f"2026-09-10T{h:02d}:05:00+09:00", "oldone", 500, age_h=100.0 + h))
    rows.append(_vid("2026-09-11T02:05:00+09:00", "oldone", 500, age_h=126.0))
    fv = trend.flat_video_gain(rows)
    assert fv["proves_alive"] is False and fv["confirmed"] == 0
    line = trend.channel_line(rows)
    assert "確かめられた本の伸びは 0回" in line
    assert "「だから止まった」とは読めません" in line
    assert "チャンネルは止まっていません" not in line


def test_平らが無ければ言わない() -> None:
    """毎周 動く窓には平らが無い ＝ `None`（**0 を返さないこと**）。"""
    rows = [_ch(f"2026-09-10T{h:02d}:00:00+09:00", 84781 + 40 * i)
            for i, h in enumerate(range(2, 14))]
    fv = trend.flat_video_gain(rows)
    assert fv["proves_alive"] is None and fv["h"] is None
    assert "チャンネルは止まっていません" not in trend.channel_line(rows)


def test_平らが遅れより短い回は_言えないと返す() -> None:
    """`REPLICA_LAG_H` より短い平らでは抑えが取れない ＝ `None`（覆る条件 (2)）。"""
    rows = [_ch("2026-09-10T14:00:00+09:00", 86406),
            _ch("2026-09-10T14:20:00+09:00", 86406)]
    rows.append(_vid("2026-09-10T13:00:00+09:00", "newone", 0, age_h=13.0))
    rows.append(_vid("2026-09-10T14:10:00+09:00", "newone", 176, age_h=14.2))
    fv = trend.flat_video_gain(rows)
    assert fv["h"] is not None and fv["h"] < trend.REPLICA_LAG_H
    assert fv["confirmed"] is None and fv["proves_alive"] is None


def test_channel_growth_が同じ口を通す() -> None:
    """**2つの実装を持たないこと**（`_channel_gate` の註と同じ族）。"""
    rows = _flat_with_a_growing_video()
    g = trend.channel_growth(rows)
    fv = trend.flat_video_gain(rows)
    assert g["flat_alive"] is fv["proves_alive"]
    assert g["flat_vid_confirmed"] == fv["confirmed"]


# ---------------------------------------------------------------------------
# **`confirmed == 0` の 2つ の意味**（2026-09-11 19:5x・optimizer・Opus。**実物で踏んだ**）
#
# 平ら 4.35時間 の窓で `sum_confirmed` は **0**、`proves_alive` は **False** と出ていました。
# ところが同じ窓で 6本目 は **294 → 654回**（+360）伸びています。
# 理由は本ではなく**測り**: 確かめられる部分は `平ら − 遅れ 2.8時間 ＝ 1.55時間` しかなく、
# そこに入った `measure` は **1回 だけ**。抑え `min(late)` は最後の読み（＝ `b`）そのものになり、
# `b - min(late)` は**恒等的に 0** になります。
# ＝ その 0 は「伸びなかった」ではなく **「測れなかった」**。
# §7 (m) は「平らの中の伸びが 0 の回（＝ そのとき初めて時間の門が独りで立つ）」を
# 次に見る所に挙げているので、**この 2つ を分けないと、測れなかっただけの回で門が引かれます。**
#
# **陽性対照**（`.pyc` を消してから撃った・METHOD §5 教訓の形 6つ目）: `flat_video_gain` の
# `alive` を `False` に戻すと **1件** 落ちる／`channel_video_delta` の `blind` の数えを外すと
# **2件** 落ちる（判定と、線の字の両方）。
# ---------------------------------------------------------------------------


def _flat_with_one_late_read() -> list[dict]:
    """平ら 4.4時間・**確かめられる部分（1.6時間）に `measure` が 1回 だけ**。本は +360回 伸びている。"""
    rows = [_ch(f"2026-09-11T{h:02d}:00:00+09:00", 86406) for h in (10, 11, 12, 13)]
    rows.append(_ch("2026-09-11T14:00:00+09:00", 86446))     # 刻み
    # 平らは 14:00 → 18:24（4.4時間）。cut ＝ 16:48。
    rows += [_ch("2026-09-11T15:00:00+09:00", 86446),
             _ch("2026-09-11T16:00:00+09:00", 86446),
             _ch("2026-09-11T17:00:00+09:00", 86446),
             _ch("2026-09-11T18:24:00+09:00", 86446)]
    for h, m, v, age in ((13, 30, 294, 3.5), (15, 30, 402, 5.5), (16, 10, 566, 6.2),
                         (17, 40, 654, 7.7)):
        rows.append(_vid(f"2026-09-11T{h:02d}:{m:02d}:00+09:00", "sixth", v, age_h=age))
    return rows


def test_読みが1つ_しか無い窓は_伸び0ではなく測れないと返す() -> None:
    rows = _flat_with_one_late_read()
    fv = trend.flat_video_gain(rows)
    assert fv["h"] is not None and fv["h"] > trend.REPLICA_LAG_H   # 窓そのものは遅れより長い
    assert fv["grew"] == 1 and fv["blind"] == 1
    assert fv["confirmed"] == 0
    # **`False`（伸びなかった）に倒さないこと** —— 測れていないので `None`
    assert fv["proves_alive"] is None


def test_線は_測れなかったと言う() -> None:
    line = trend.channel_line(_flat_with_one_late_read())
    assert "この窓では確かめられません" in line
    assert "「伸びが 0 だった」ではなく「測れなかった」" in line
    # 反証も断定もしない
    assert "チャンネルは止まっていません" not in line
    assert "確かめられた本の伸びは 0回" not in line


def test_読みが2つ_在れば_伸びを確かめられる() -> None:
    """**同じ窓に `measure` が 2回 入れば、同じ本で伸びが立ちます**（`blind` は 0）。"""
    rows = _flat_with_one_late_read()
    rows.append(_vid("2026-09-11T18:10:00+09:00", "sixth", 776, age_h=8.2))
    fv = trend.flat_video_gain(rows)
    assert fv["blind"] == 0 and fv["confirmed"] > 0 and fv["proves_alive"] is True


def test_伸びた本が_1本も無い回は_これまでどおり_0回と言う() -> None:
    """**`blind` は「伸びた本」だけを数えます** —— 伸びが無い窓の `False` は動かしません。"""
    rows = [_ch(f"2026-09-10T{h:02d}:00:00+09:00", 84781) for h in range(2, 14)]
    rows.append(_ch("2026-09-10T14:00:00+09:00", 86406))
    rows += [_ch(f"2026-09-11T{h:02d}:00:00+09:00", 86406) for h in range(0, 3)]
    for h in (13, 20):
        rows.append(_vid(f"2026-09-10T{h:02d}:05:00+09:00", "oldone", 500, age_h=100.0 + h))
    rows.append(_vid("2026-09-11T02:05:00+09:00", "oldone", 500, age_h=126.0))
    fv = trend.flat_video_gain(rows)
    assert fv["grew"] == 0 and fv["blind"] == 0 and fv["proves_alive"] is False
