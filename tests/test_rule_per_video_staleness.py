"""**`per_video` の標本が止まっていることを、検査が捕まえるか。**

## なぜ要るか

2026-09-02 夕・最適化の回に踏んだ実物の欠陥です。

`rule_per_video.per_video()` は「その日 2本以下しか出さなかった日」の本だけで
1本あたり再生を測ります（密度の交絡を切るため。弾力性 -0.733・t=-4.26）。
**その帯に出口がありませんでした** —— 08-19 以降は毎日 3本以上 出していたので、
**標本は 08-18 で止まり、15日間 1本も入らなかった。**

止まった数は下がりません。**上がって見えることさえあります**（実測
`data/eta.jsonl`: `per_video_now` 08-30 603 → 08-31 942。同じ窓で実物は 839 → 121）。

**発火したことのない検査は検査ではない**（`docs/GOAL.md`）ので、
ここでは**故障を注入して**発火を確かめます。
"""
from datetime import date, timedelta

from src import rule_per_video as R


def _e(at_rule=1000.0, b=-0.733, band=2):
    return {"ok": True, "band": band, "at_rule": at_rule,
            "elasticity": {"ok": True, "b": b}}


def _rows(days):
    """`{日: [再生, ...]}` を `_settled()` と同じ形へ。"""
    out = []
    for d, vals in days.items():
        for i, v in enumerate(vals):
            out.append((d, f"{d}-{i}", v))
    return out


def test_止まった標本を捕まえる():
    """**故障の注入**: 帯（≤2本/日）の最後の日を、今日から 15日 前に置く。"""
    today = date.today()
    days = {today - timedelta(days=15): [1000, 1100]}          # 帯の中
    for k in range(14, 0, -1):                                  # ここから全部 帯の外
        days[today - timedelta(days=k)] = [100] * 10
    s = R.staleness(e=_e(), rows=_rows(days))
    assert s["ok"], s
    assert s["stale"] is True, s
    assert s["age_days"] == 15, s
    assert s["sample_last"] == today - timedelta(days=15), s
    assert s["outside_days"] == 14, s
    lines = R.stale_lines(s)
    assert lines, "止まっているのに 0行 —— 頭に何も出ません"
    assert "止まっています" in lines[0], lines[0]


def test_帯に新しい日が入ったら黙る():
    """**覆る条件そのもの。** 規則（1日1本）どおりに出た日は必ず帯に入る。"""
    today = date.today()
    days = {today - timedelta(days=15): [1000, 1100]}
    for k in range(14, 0, -1):
        days[today - timedelta(days=k)] = [100] * 10
    days[today - timedelta(days=1)] = [500]                     # 規則どおりの1日1本
    s = R.staleness(e=_e(), rows=_rows(days))
    assert s["sample_last"] == today - timedelta(days=1), s
    assert s["stale"] is False, s
    assert R.stale_lines(s) == [], "黙るはずの回で行が出ています"


def test_残差は本数で直してから見る():
    """**密度を崖と読み違えないこと。**

    帯の外の日を「本数の効き（`at_rule × n^b`）ちょうど」で作れば、
    残差は 1.0 付近に並び、**傾きは 0 をまたぐ ＝ `cliff` は立たない。**
    """
    today = date.today()
    b, at_rule = -0.733, 1000.0
    days = {today - timedelta(days=15): [at_rule, at_rule]}
    for k in range(14, 0, -1):
        n = 10
        days[today - timedelta(days=k)] = [round(at_rule * (n ** b))] * n
    s = R.staleness(e=_e(at_rule, b), rows=_rows(days))
    assert s["stale"] is True, s
    assert abs(s["recent_ratio"] - 1.0) < 0.02, s
    assert s["cliff"] is False, s      # 本数で説明が付く ＝ 崖ではない


def test_本数で説明が付かない落ちは立つ():
    """**故障の注入**: 本数を一定にしたまま、1本あたりを日ごとに削る。"""
    today = date.today()
    b, at_rule = -0.733, 1000.0
    days = {today - timedelta(days=15): [at_rule, at_rule]}
    base = at_rule * (10 ** b)
    for i, k in enumerate(range(14, 0, -1)):
        days[today - timedelta(days=k)] = [max(1, round(base * (0.8 ** i)))] * 10
    s = R.staleness(e=_e(at_rule, b), rows=_rows(days))
    assert s["cliff"] is True, s
    assert s["fit"]["hi"] < 0, s["fit"]
    lines = R.stale_lines(s)
    assert any("0 をまたぎません" in x for x in lines), lines


def test_実物でも撃てる():
    """**この repo の実データで落ちないこと**（形が変わったら気づく）。"""
    s = R.staleness()
    assert s["ok"] in (True, False)
    if s["ok"]:
        assert isinstance(R.stale_lines(s), list)
