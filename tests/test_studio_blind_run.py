"""**「N周 続いたら」と書いてある覆る条件は、その連なりを数える口と一緒に置くこと。**

2026-09-12 16:0x・optimizer・Opus。**API 0単位** —— 台帳を読むだけ。

**踏んだ形**: `channel_video_delta` の覆る条件 (4)（`blind == grew` が **3周**）・(5)（`blind == 0` が
**7周**）と、`flat_video_gain` の `blind` の側の覆る条件（`proves_alive is False` が **3周**）は、
**どれも周を数える条件なのに、数える口がどこにも在りませんでした**
（`grep blind studio/ scripts/` ＝ 印字はその周の 1点 だけ）。
実物: この回の台帳で `blind == grew` は **2周** 続いており、**門まで あと 1周** でした ——
**誰も数えていないので、届いた回に誰も気づけません。**

**きょうの状態を不変条件として書かないこと**（METHOD §5 教訓の形 6つ目）＝
この検査は実物の台帳を1行も読まず、形だけをその場で組みます。

**陽性対照**（壊したら落ちるまで撃つ・教訓の形 3つ目。`.pyc` を消してから撃った）:
`_count` が「何も言えない周」で `break` する形にすると **1件**／
`grew > 0` を要らない形（`blind == grew` を 0 == 0 でも数える）にすると **1件**／
周ごとに切らず、いまの台帳ぜんたいで数える形にすると **6件**／
`channel_line` が連なりを印字しない形にすると **1件**。
"""
from __future__ import annotations

from studio import trend

DAY = "2026-09-10"


def _t(hh: float) -> str:
    h = int(hh)
    m = int(round((hh - h) * 60))
    return f"{DAY}T{h:02d}:{m:02d}:00+09:00"


def _ch(hh: float, views: int, subs: int = 28) -> dict:
    return {"at": _t(hh), "id": "UCxxx", "event": "channel",
            "subs": subs, "views": views, "videos": 269}


def _vid(hh: float, vid: str, views: int) -> dict:
    """**`age_h` は点ごとに違えること** —— `trend.series` は齢 0.1 刻みで畳みます。"""
    return {"at": _t(hh), "id": vid, "event": "measured",
            "views": views, "age_h": round(hh, 1)}


def _blind_laps() -> list[dict]:
    """刻みのあと平らが続き、**確かめられる部分に本の読みが 1点 しか無い**周を 3周 作る。

    平らの頭は 13:00。遅れ（`REPLICA_LAG_H` ＝ 2.8時間）を足した **15:48 以降**の読みは
    16:00 の 1点 だけなので、抑え `min(late)` は最後の読みそのもの ＝ `sum_confirmed` は 0、
    けれど本は窓の中で 0 → 176 に伸びている ＝ **`blind == grew`**。
    """
    rows = [_ch(h, 84781) for h in (10.0, 11.0, 12.0)]
    rows.append(_ch(13.0, 86406))                      # 刻み ＝ 平らの頭
    rows += [_ch(h, 86406) for h in (14.0, 15.0, 16.0, 16.2, 16.4)]
    rows.append(_vid(12.5, "newone", 0))               # 窓の頭の手前 ＝ 基準
    rows.append(_vid(14.0, "newone", 100))
    rows.append(_vid(16.0, "newone", 176))             # 遅れの後の唯一の点
    return rows


def test_blind_が_grew_と同じ周は_連なりで数える() -> None:
    b = trend.blind_run(_blind_laps())
    assert b["run"] == 3, b["run"]
    assert b["need"] == 3 and b["drawn"] is True
    assert b["span_h"] is not None and b["span_h"] > 0


def test_逆を言った周で連なりは切れる() -> None:
    """いちばん新しい周で伸びが**確かめられた**ら、連なりは 0 に戻る。"""
    rows = _blind_laps()
    rows.append(_ch(17.0, 86406))
    rows.append(_vid(17.0, "newone", 300))             # 遅れの後に 2点目 ＝ 抑えが下がる
    b = trend.blind_run(rows)
    assert b["marks"][-1]["proves_alive"] is True
    assert b["run"] == 0 and b["drawn"] is False


def test_訊けていない周は飛ばす_切らない() -> None:
    """平らが遅れより短い周（`confirmed is None`）は、**連なりを切りません**。

    ＝ `channel_video_delta` の覆る条件 (5) が「`sum_confirmed is None` の回を外す」と
    書いているのと同じ向き（**数えない**であって、**切る**ではない）。
    """
    rows = _blind_laps()
    rows.append(_ch(17.0, 88000))                      # 新しい刻み ＝ 平らが 0 に戻る
    rows.append(_ch(17.5, 88000))                      # 平ら 0.5時間 ＝ 遅れより短い
    b = trend.blind_run(rows)
    assert b["marks"][-1]["confirmed"] is None
    assert b["skipped"] >= 1
    assert b["run"] == 3, b["run"]                     # 飛ばした先の 3周 がまだ見えている


def test_連なりは_その周までの台帳で数える() -> None:
    """**いまの窓を過去へ延ばして数えないこと**（`quota.margin_series` と同じ「その周が見た数」）。

    古い周は平らがまだ短く `confirmed is None`・新しい周は数が出る ＝
    **周ごとに切っていなければ、この 2つ は同じ値になります。**
    """
    b = trend.blind_run(_blind_laps())
    assert b["marks"][0]["confirmed"] is None
    assert b["marks"][-1]["confirmed"] == 0
    assert b["marks"][-1]["grew"] == 1


def _zero_laps() -> list[dict]:
    """伸びが**確かめられる**周（`blind == 0`）を 2周（その手前の周は、遅れの後の読みが
    1点 しか無いので `blind` の側）。"""
    rows = [_ch(h, 84781) for h in (10.0, 11.0, 12.0)]
    rows.append(_ch(13.0, 86406))
    rows += [_ch(h, 86406) for h in (14.0, 15.0, 16.0, 16.5, 17.0)]
    rows.append(_vid(12.5, "newone", 0))
    rows.append(_vid(16.0, "newone", 100))
    rows.append(_vid(16.5, "newone", 150))
    rows.append(_vid(17.0, "newone", 176))
    return rows


def test_zero_run_は_訊けていない周を外して数える() -> None:
    b = trend.blind_run(_zero_laps())
    assert b["marks"][-1]["blind"] == 0
    assert b["zero_run"] >= 2 and b["zero_need"] == 7
    assert b["zero_drawn"] is False                    # 門は 7周


def test_印字が連なりを言う() -> None:
    """**覆る条件を註に書いたら、その条件を読む印字も一緒に作ること**（§5 教訓の形 7つ目）。"""
    rows = _blind_laps()
    line = trend.channel_line(rows)
    assert "blind_run" in line
    assert "3周" in line
    short = trend.blind_run_words(rows, short=True)
    assert "3/3周" in short and "blind_run" in short


def test_台帳に周が無ければ_0_を返す() -> None:
    b = trend.blind_run([])
    assert b["laps"] == 0 and b["run"] == 0 and b["drawn"] is False


def _no_grower_lap() -> list[dict]:
    """**伸びた本が 0本 の周**（`grew == 0`・`confirmed` は出る）を、いちばん新しい周に置く。

    ここを `blind == grew` の側で数えると **0 == 0 が真**になり、
    「伸びた本が 1本 も確かめられない周」でない回まで連なりに入ります。
    """
    rows = _blind_laps()
    rows.append(_ch(18.0, 90000))                      # 新しい刻み ＝ 窓が切り替わる
    rows += [_ch(h, 90000) for h in (19.0, 20.0, 21.0)]
    for h in (18.5, 19.0, 20.0, 21.0):
        rows.append(_vid(h, "newone", 176))            # 新しい窓の中では 1回も伸びない
    return rows


def test_伸びた本が0本の周は_連なりに数えない() -> None:
    b = trend.blind_run(_no_grower_lap())
    assert b["marks"][-1]["grew"] == 0
    assert b["marks"][-1]["confirmed"] == 0            # 訊けてはいる（`None` ではない）
    assert b["run"] == 3, b["run"]                     # その周は飛ばし、手前の 3周 だけ
