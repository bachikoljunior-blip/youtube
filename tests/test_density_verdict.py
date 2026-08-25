"""`src/density_verdict.py` の検査。

**先に「既知の当たり」を1件固定してあります**（`docs/trigger_main.md` §4）——
この道具が置いた熟成 24時間 の根拠そのもの、つまり
**「ショートは12時間で伸びきっている」が実データで出ること**です。
ここが出ないなら、熟成も判定できる日も全部ただの勘になります。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src import density_verdict as dv

JST = dv.JST
UTC = timezone.utc


# --- 既知の当たり（実データ） ---------------------------------------------

def test_既知の当たり_12時間で伸びきっている():
    """同じ本の 12〜18h と 30〜44h を突き合わせると、倍率の中央値は 1.0 付近。

    ここが 1.0 から大きく外れたら、**熟成 24時間 は短すぎます**
    （＝まだ伸びる本を「伸びきった」として群に入れている）。
    """
    fz = dv.freeze_ratio(dv.observations())
    if fz["n"] < 8:
        pytest.skip(f"両方の帯に観測がある本が {fz['n']}本しかありません")
    assert 0.95 <= fz["median"] <= 1.05, fz


def test_既知の当たり_熟成は伸びきる時刻より後ろにある():
    assert dv.RIPE_H >= 18.0


# --- 帯の取り方 -------------------------------------------------------------

def test_若い観測は捨てる_0回は0回ではない():
    """実測: 08/20 公開ぶんは 6〜10時間の帯に「0」と「1111」が同居していた。

    若い 0 を混ぜると、詰めた日が実際より悪く出る（＝前提を外れの側へ倒す）。
    """
    obs = {"young": [(6.0, 0), (9.0, 0)], "ripe": [(14.0, 900)]}
    vals, dropped = dv.banded(obs)
    assert vals == {"ripe": 900}
    assert dropped == 1


def test_帯の中では最大を取る():
    # `viewCount` は減らない。減って見えるのは観測のほうの揺れ。
    obs = {"a": [(13.0, 500), (17.0, 480), (16.0, 620)]}
    vals, _ = dv.banded(obs)
    assert vals == {"a": 620}


def test_帯より上の観測も落とす():
    obs = {"a": [(200.0, 5000)]}
    vals, dropped = dv.banded(obs, lo=12.0, hi=48.0)
    assert vals == {} and dropped == 1


# --- 熟成した日 -------------------------------------------------------------

def test_熟成はその日の最後の1本で決まる():
    """朝の1本が熟成しても、**夜の1本がまだなら、その日はまだ若い。**

    先頭で決めると、25本置いた日が「熟成ずみ」になって中央値が下振れします。
    """
    now = datetime(2026, 8, 21, 6, 0, tzinfo=UTC)
    pub = {
        "morning": datetime(2026, 8, 20, 0, 0, tzinfo=UTC),   # 30時間前
        "evening": datetime(2026, 8, 20, 10, 0, tzinfo=UTC),  # 20時間前
    }
    assert dv.ripe_days(pub, now) == set()
    pub.pop("evening")
    assert dv.ripe_days(pub, now) == {"2026-08-20"}


def test_公開日はJSTの暦日で切る():
    # UTC 2026-08-20T16:00 は JST では 08/21 01:00。
    pub = {"a": datetime(2026, 8, 20, 16, 0, tzinfo=UTC)}
    assert dv.by_day(pub, {"a": 10}) == {"2026-08-21": [10]}


# --- 判定 -------------------------------------------------------------------

def test_詰めた日が3日そろうまで判定しない():
    counts = {"2026-08-20": 25, "2026-08-19": 8}
    per_day = {"2026-08-20": [100, 120], "2026-08-19": [1000, 1200]}
    res = dv.verdict(counts, per_day, set(counts))
    assert res["outcome"] == "undecided"
    assert "3日" in res["why"]


def test_半分未満なら外れ():
    counts = {f"2026-08-{d}": 25 for d in (18, 19, 20)}
    counts["2026-08-10"] = 10
    per_day = {f"2026-08-{d}": [300, 400] for d in (18, 19, 20)}
    per_day["2026-08-10"] = [1000, 1200]
    res = dv.verdict(counts, per_day, set(counts))
    assert res["outcome"] == "falsified"
    assert res["ratio"] == pytest.approx(350 / 1100)


def test_同値は外れとみなさない():
    counts = {f"2026-08-{d}": 25 for d in (18, 19, 20)}
    counts["2026-08-10"] = 10
    per_day = {f"2026-08-{d}": [500] for d in (18, 19, 20)}
    per_day["2026-08-10"] = [1000]
    res = dv.verdict(counts, per_day, set(counts))
    assert res["outcome"] == "survived" and res["ratio"] == 0.5


def test_1時間きざみの日が無ければ判定しない():
    counts = {f"2026-08-{d}": 25 for d in (18, 19, 20)}
    per_day = {f"2026-08-{d}": [300] for d in (18, 19, 20)}
    res = dv.verdict(counts, per_day, set(counts))
    assert res["outcome"] == "undecided"


def test_熟成していない日は群に入れない():
    counts = {f"2026-08-{d}": 25 for d in (18, 19, 20)}
    counts["2026-08-10"] = 10
    per_day = {f"2026-08-{d}": [300] for d in (18, 19, 20)}
    per_day["2026-08-10"] = [1000]
    ripe = {"2026-08-18", "2026-08-19", "2026-08-10"}   # 08/20 はまだ若い
    res = dv.verdict(counts, per_day, ripe)
    assert res["outcome"] == "undecided" and "2日" in res["why"]


# --- 判定できる日 -----------------------------------------------------------

def test_判定できる日は3日目の最後の1本から熟成ぶん後ろ():
    pub = {}
    for i, day in enumerate((19, 20, 21)):
        for j in range(dv.TIGHT_MIN):
            pub[f"v{i}-{j}"] = datetime(2026, 8, day, 3 + j % 8, 0, tzinfo=UTC)
    now = datetime(2026, 8, 21, 6, 0, tzinfo=UTC)
    counts = dv.day_counts(pub, now)
    when = dv.next_settle(counts, pub, now)
    # 3日目（JST 08/21）の最後は UTC 08/21 10:00 → +24h → JST 08/22 19:00
    assert when.isoformat() == "2026-08-22"


def test_詰めた日が足りなければ判定できる日は出ない():
    pub = {f"v{j}": datetime(2026, 8, 20, 3 + j, 0, tzinfo=UTC)
           for j in range(dv.TIGHT_MIN)}
    now = datetime(2026, 8, 21, 6, 0, tzinfo=UTC)
    assert dv.next_settle(dv.day_counts(pub, now), pub, now) is None


def test_予約ぶんの先の日も数える():
    """**予約は実行されます。** 先の日を数えないと「判定できる日」が出ません。"""
    pub = {}
    for i, day in enumerate((20, 22, 23)):
        for j in range(dv.TIGHT_MIN):
            pub[f"v{i}-{j}"] = datetime(2026, 8, day, 3, 0, tzinfo=UTC)
    now = datetime(2026, 8, 21, 6, 0, tzinfo=UTC)
    counts = dv.day_counts(pub, now)      # 過去ぶんは 08/20 だけ
    assert set(counts) == {"2026-08-20"}
    assert dv.next_settle(counts, pub, now).isoformat() == "2026-08-24"


# --- **上限を外して数え直す側**（2026-08-25 に足した） -------------------------
#
# 生の中央値は、16本以上の日で「上限の外に出た本の 0」を拾います
# （`src/day_cap.py` の実測: 1日に再生が付くのは10本、11本目から先は 0〜3）。
# **それは間隔のせいではありません。** `live_band()` で両群をそろえます。

def _pub(day: str, times: list[str]) -> dict[str, datetime]:
    out = {}
    for i, hhmm in enumerate(times):
        h, m = int(hhmm[:2]), int(hhmm[3:])
        out[f"{day}-{i}"] = datetime.fromisoformat(f"{day}T{h:02d}:{m:02d}:00+09:00")
    return out


def test_live_band_は先頭から上限ぶんだけ残す():
    times = [f"{9 + i // 2:02d}:{(i % 2) * 30:02d}" for i in range(14)]   # 09:00〜15:30
    published = _pub("2026-08-20", times)
    values = {vid: (500 if i < 10 else 0) for i, vid in enumerate(published)}
    band = dv.live_band(published, values, cap_n=10)
    assert band["2026-08-20"] == [500] * 10          # **0 の4本は帯の外**


def test_live_band_は間隔で落ちるぶんを先に落とす():
    """30分未満で挟んだ本は、上限を数える前に落とす（`day_cap._spaced` と同じ）。"""
    published = _pub("2026-08-20", ["09:00", "09:15", "09:30", "09:45", "10:00"])
    values = {vid: (300 if i % 2 == 0 else 0) for i, vid in enumerate(published)}
    band = dv.live_band(published, values, cap_n=10)
    assert band["2026-08-20"] == [300, 300, 300]     # :15/:45 は落ちる


def test_上限を外すと倍率が変わる_生の側は上限のぶんを見ている():
    """**同じ日を2通りに数えると、片方だけが 0 を拾う。**"""
    counts, published, values = {}, {}, {}
    for d in (18, 19, 20):
        day = f"2026-08-{d}"
        counts[day] = 20
        times = [f"{9 + i // 2:02d}:{(i % 2) * 30:02d}" for i in range(20)]
        pub = _pub(day, times)
        published.update(pub)
        for i, vid in enumerate(pub):
            values[vid] = 400 if i < 10 else 0       # 上限の外は 0
    day = "2026-08-10"
    counts[day] = 10
    pub = _pub(day, [f"{9 + i // 2:02d}:{(i % 2) * 30:02d}" for i in range(10)])
    published.update(pub)
    for vid in pub:
        values[vid] = 800
    ripe = set(counts)

    raw = dv.verdict(counts, dv.by_day(published, values), ripe)
    band = dv.verdict(counts, dv.live_band(published, values, cap_n=10), ripe)
    # 生の側は 20本中10本が 0 なので中央値 200（＝ 0 と 400 の平均）→ 800 との比 0.25
    assert raw["outcome"] == "falsified" and raw["ratio"] == pytest.approx(0.25)
    # 上限を外すと 400 対 800 ＝ ×0.5 ＝ **同値なので外れではない**
    assert band["ratio"] == pytest.approx(0.5) and band["outcome"] == "survived"


def test_render_は2つの倍率を並べて出す():
    rep = {
        "verdict": {"outcome": "falsified", "ratio": 0.0,
                    "tight_median": 2, "hourly_median": 1000},
        "cap_free": {"outcome": "survived", "ratio": 0.6,
                     "tight_median": 600, "hourly_median": 1000},
        "per_day": {}, "counts": {}, "ripe": set(), "freeze": {"n": 0},
    }
    text = dv.render(rep)
    assert "上限" in text and "×0.60" in text
    assert "間隔について" in text          # 向きが違うので、強い断りが出る
    assert "2026-08-27" in text            # 切り分けの日を必ず指す
