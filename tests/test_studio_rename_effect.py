"""`trend.rename_effect` —— **題を変えた前後で登録の伸びがどう動いたか**（2026-09-19 03:xx）。

`peers.persona` の註 (1) が 2026-09-16 から名指ししていた「相関と因果を割る唯一の手」
（**うちが名前を付けて、前後を測る**）の読み出しです。実験は 2026-09-18 20:2x に
オーナーが Studio で `お金と仕事の教科書` → `カワウソの年金計算室` に変えて始まりました。

**陽性対照を先に置いています** —— 伸びが変わらない台帳では比が 1.0、
後ろだけ伸ばすと比が上がること。**先に「動くこと」を測ってから実データを見ます。**

**この検査が守っている、この回に踏んだ 2つ の欠陥**:

 (1) **窓の端を「窓じゅうの最大」で採ると、頭が伸びを食う** ——
     揃えた前の窓が 34→35 なのに **+0人** と出て、比が 4.0倍 → **17.3倍** に化けました。
     ＝ **自分の仮説の側へ倒れる向き**の誤りです（`test_揃えた前の窓の伸びを頭が食わない`）。
 (2) **「後ろの窓に出た本」を『初めて測った刻』で数えると、前の日の本が後ろに入る** ——
     `measure` は日枠が戻った周にまとめて撃つため。実測で **7本 → 0本**
     （`test_本の数は初めて測った刻ではなく公開の刻で数える`）。

**並びの検査が本体です**（`test_升の判定の行と前後の実測の行が隣り合う`）——
升の判定（`title_identity_line`）だけを読んだ回は、相関を因果として使います。
"""
from __future__ import annotations

import datetime as dt

import pytest

from studio import trend

JST = dt.timezone(dt.timedelta(hours=9))
B_FROM = dt.datetime(2026, 9, 18, 17, 30, tzinfo=JST)
B_TO = dt.datetime(2026, 9, 18, 20, 31, tzinfo=JST)


def _mark():
    return {"at": B_TO.isoformat(), "id": "-", "event": "channel_renamed", "by": "owner",
            "before": "お金と仕事の教科書", "after": "カワウソの年金計算室",
            "bound_from": B_FROM.isoformat(), "bound_to": B_TO.isoformat()}


def _ch(t: dt.datetime, subs: int, views: int = 90000, title: str = "カワウソの年金計算室"):
    return {"at": t.isoformat(), "id": "UCtest", "event": "channel",
            "subs": subs, "views": views, "title": title}


def _series(spd_before: float, spd_after: float, hours: float = 6.0, start_subs: int = 30):
    """前 `hours` 時間 と 後 `hours` 時間 を、それぞれ一定の速さで埋めた台帳。"""
    rows = [_mark()]
    n = 12
    for i in range(n + 1):                                    # 前（b_from で終わる）
        t = B_FROM - dt.timedelta(hours=hours * (1 - i / n))
        rows.append(_ch(t, start_subs + round(spd_before / 24 * hours * i / n)))
    base = start_subs + round(spd_before / 24 * hours)
    for i in range(n + 1):                                    # 後（b_to で始まる）
        t = B_TO + dt.timedelta(hours=hours * i / n)
        rows.append(_ch(t, base + round(spd_after / 24 * hours * i / n)))
    return rows


def test_陽性対照_伸びが同じなら比は1_後ろだけ伸ばすと比が上がる():
    same = trend.rename_effect(_series(24.0, 24.0))
    assert same["marked"] is True
    assert same["spd_match"] == pytest.approx(same["spd_after"], rel=0.25)

    faster = trend.rename_effect(_series(24.0, 96.0))
    assert faster["spd_after"] > faster["spd_match"] * 2


def test_刻が台帳に無ければ判定しない():
    rows = [_ch(B_TO + dt.timedelta(hours=i), 30 + i) for i in range(4)]
    assert trend.rename_effect(rows)["marked"] is False
    assert "刻が台帳に在りません" in trend.rename_effect_line(rows)


def test_揃えた前の窓の伸びを頭が食わない():
    """**この回に踏んだ欠陥 (1)**。端を「窓じゅうの最大」で採ると +0人 になります。"""
    rows = [_mark()]
    # 前: 11:14 に 34 → 12:37 以降ずっと 35（窓の頭は 11:53 ＝ 揃えた前は 34 → 35 ＝ +1人）
    for t, s in [((11, 4), 34), ((11, 14), 34), ((12, 37), 35), ((14, 4), 35),
                 ((16, 2), 35), ((17, 17), 35), ((17, 30), 35)]:
        rows.append(_ch(dt.datetime(2026, 9, 18, *t, tzinfo=JST), s))
    # 後: 5.6時間 で 35 → 39
    for t, s in [((20, 35), 37), ((22, 0), 38), ((2, 8), 39)]:
        d = 19 if t[0] < 12 else 18
        rows.append(_ch(dt.datetime(2026, 9, d, *t, tzinfo=JST), s))
    d = trend.rename_effect(rows)
    assert d["subs_match"] == 1, "頭が伸びを食っている（窓じゅうの最大を端に使った）"
    assert d["subs_after"] == 4
    assert 3.0 < d["spd_after"] / d["spd_match"] < 6.0, "比が化けている"


def test_本の数は初めて測った刻ではなく公開の刻で数える():
    """**この回に踏んだ欠陥 (2)**。`measure` は日枠が戻った周にまとめて撃ちます。"""
    rows = _series(24.0, 24.0)
    # 境目の **前** に出た本を、境目の **後** で初めて測った行
    rows.append({"at": (B_TO + dt.timedelta(hours=3)).isoformat(), "id": "vid_old",
                 "event": "measured", "views": 500, "age_h": 12.0})
    assert trend.rename_effect(rows)["new_videos_after"] == 0, "前の日の本を後ろに数えている"
    # 境目の **後** に出た本
    rows.append({"at": (B_TO + dt.timedelta(hours=4)).isoformat(), "id": "vid_new",
                 "event": "measured", "views": 10, "age_h": 1.0})
    assert trend.rename_effect(rows)["new_videos_after"] == 1


def test_分母が床に届かないうちは1000再生あたりを出さない():
    rows = _series(24.0, 48.0)
    rows.append({"at": (B_TO + dt.timedelta(hours=1)).isoformat(), "id": "v1",
                 "event": "measured", "views": 10, "age_h": 1.0})
    line = trend.rename_effect_line(rows)
    assert "1,000再生あたりは出せません" in line
    assert f"{trend.RENAME_MIN_VIEWS:,}" in line


def test_門に届くまで判定を出さない_届いたら出す():
    short = trend.rename_effect(_series(1.0, 20.0, hours=6.0))
    assert short["enough"] is False
    assert "まだ判定を出しません" in trend.rename_effect_line(_series(1.0, 20.0, hours=6.0))

    long = _series(1.0, 20.0, hours=trend.RENAME_AFTER_MIN_H + 1)
    d = trend.rename_effect(long)
    assert d["after_h"] >= trend.RENAME_AFTER_MIN_H
    assert d["subs_after"] >= trend.RENAME_AFTER_MIN_SUBS
    assert d["enough"] is True
    assert "門に届きました" in trend.rename_effect_line(long)


def test_窓が閉じるまで題を触るなと毎周_言う():
    """YouTube は題の変更を 14日 に 3回 まで ＝ 実験の窓は作り直せません。"""
    assert "題を触らないこと" in trend.rename_effect_line(_series(1.0, 20.0))


def test_升の判定の行と前後の実測の行が隣り合う():
    """**この検査が本体** —— 離すと、升の判定（相関）だけを読んだ回が因果として使います。"""
    from studio.common import ledger_rows
    lines = trend.lines(ledger_rows())
    idx_id = [i for i, s in enumerate(lines) if "title_identity" in s]
    idx_re = [i for i, s in enumerate(lines) if "rename_effect_line" in s]
    assert idx_id and idx_re, (idx_id, idx_re)
    assert 0 < idx_re[0] - idx_id[0] <= 2, "升の判定と前後の実測が離れている"
