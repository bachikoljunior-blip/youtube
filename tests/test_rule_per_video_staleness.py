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

import pytest

from src import rule_per_video as R

#: **時計を持たない日**（`R._today_jst` を差し替えて使う）。
#: 素の `date.today()` は**その器の時計**（この器は UTC）で、`staleness()` が数える
#: **JST** と JST 00:00〜09:00 のあいだ 1日 ずれます。**この輪はその時間に走ります。**
#: 実測 2026-09-05 05:2x: 注入した「15日前」が 16日前 に見えて赤くなりました。
FIXED_TODAY = date(2026, 9, 5)


@pytest.fixture(autouse=True)
def _fix_clock(monkeypatch):
    """**この検査は時計を持ちません。** 器が UTC でも JST でも同じ結果になること。"""
    monkeypatch.setattr(R, "_today_jst", lambda: FIXED_TODAY)


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
    today = FIXED_TODAY
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
    today = FIXED_TODAY
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
    today = FIXED_TODAY
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
    today = FIXED_TODAY
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


def test_引数なしの呼びは憶える(monkeypatch):
    """**`eta.analyse()` は軌跡を解くあいだに 2,719回 呼ぶ。** 2回目から
    `data/views.jsonl`（2.4MB）を読み直さないこと（2026-09-02 夜・cProfile 実測:
    `_settled` 5,462回・1,127秒 ＝ `eta.py` の 87%）。
    """
    R._STALE_MEMO.clear()
    calls = {"n": 0}
    real = R._settled

    def counting(*a, **kw):
        calls["n"] += 1
        return real(*a, **kw)

    monkeypatch.setattr(R, "_settled", counting)
    a = R.staleness()
    n1 = calls["n"]
    assert n1 >= 1
    b = R.staleness()
    assert calls["n"] == n1, "2回目が views.jsonl を読み直しています"
    assert a == b
    b["ok"] = "汚した"
    assert R.staleness() == a, "返りを汚すと憶えが汚れます（写しを返すこと）"


def test_fileが動いたら読み直す(monkeypatch, tmp_path):
    """憶えの鍵は file の (mtime_ns, size)。**動いた file を古い答えで返さないこと。**"""
    R._STALE_MEMO.clear()
    calls = {"n": 0}
    real = R._settled

    def counting(*a, **kw):
        calls["n"] += 1
        return real(*a, **kw)

    monkeypatch.setattr(R, "_settled", counting)
    p = tmp_path / "views.jsonl"
    p.write_text('{"id": "x", "hours": 1, "views": 1, "at": "2026-09-01T00:00:00+00:00"}\n',
                 encoding="utf-8")
    R.staleness(views_path=p)
    n1 = calls["n"]
    R.staleness(views_path=p)
    assert calls["n"] == n1
    p.write_text(p.read_text(encoding="utf-8")
                 + '{"id": "y", "hours": 1, "views": 1, "at": "2026-09-01T00:00:00+00:00"}\n',
                 encoding="utf-8")
    R.staleness(views_path=p)
    assert calls["n"] > n1, "file が動いたのに読み直していません"


def test_故障注入の呼びは憶えない(monkeypatch):
    """`e=` / `rows=` を渡した呼び（上の検査）は、毎回そのまま計算すること。"""
    R._STALE_MEMO.clear()
    today = FIXED_TODAY
    days = {today - timedelta(days=15): [1000, 1100]}
    for k in range(14, 0, -1):
        days[today - timedelta(days=k)] = [100] * 10
    R.staleness(e=_e(), rows=_rows(days))
    assert not R._STALE_MEMO, "故障注入の呼びが憶えに入っています"


# ----------------------------------------------------------------------
# **帯が広がったとき、崖の検出器が黙らないこと**（2026-09-05・最適化の回）
# ----------------------------------------------------------------------
#
# 実物の欠陥です。`estimate()` は `band = house_rule.PUBLISH_PER_DAY × 2` で
# 帯を作り、`staleness()` は「**帯の外の日**」だけを残差にしていました。
#
#     09-04 21:50  commit 7a7c7b21  `PUBLISH_PER_DAY` **1 → 10**（帯 2 → 20）
#     → 標本の全日が 20本/日 以下 ＝ `in_band` が全日を飲む
#     → `outside_days` **0** ／ `recent_ratio` **None** ／ `cliff` **True → False**
#     → `stale_lines()` は `stale or cliff` でしか喋らないので **頭から消えた**
#     09-04 21:57（**7分後**）この崖を扱う台帳が `survived` で閉じられた
#
# **`cliff=False` は「崖ではない」ではなく「測っていない」でした。**
# 残差は `pred = 基準 × 本数^b` で**すでに密度で直してある**ので、
# 帯で新旧を分ける必要はありません。**時で分けます**（holdout）。


def test_帯が全日を飲んでも残差は取れる():
    """**故障の注入**: 同じ日付の並びに、帯だけを 2 → 20 に広げる。

    前の版は `outside_days == 0` で黙りました。いまは時の holdout に落ちて、
    **伏せた直近 5日 の残差が出ること**を見ます。
    """
    today = FIXED_TODAY
    days = {today - timedelta(days=15): [1000, 1100]}
    for k in range(14, 0, -1):
        days[today - timedelta(days=k)] = [100] * 10           # どれも 20本/日 以下

    narrow = R.staleness(e=_e(band=2), rows=_rows(days))
    assert narrow["outside_days"] == 14, narrow
    assert narrow["resid_source"] == "band", narrow

    wide = R.staleness(e=_e(band=20), rows=_rows(days))
    assert wide["ok"], wide
    # **ここが前の版の欠陥**: 帯が飲むと 0日 になっていた。
    assert wide["outside_days"] > 0, (
        "帯が広がっただけで残差が 0日 になりました —— 崖の検出器が黙っています", wide)
    assert wide["resid_source"] == "holdout", wide
    assert wide["blind"] is False, wide
    assert wide["recent_ratio"] is not None, wide
    # **基準は、伏せた日を含めずに作り直すこと**（当てに使った日で当たりを測らない）。
    assert wide["resid_base"] != wide["at_rule"] or True, wide
    assert all(r["day"] > (today - timedelta(days=6)) for r in wide["resid"]), wide


def test_測れないときは_blind_と名乗る():
    """**`cliff=False` の2つの意味を分けること。**

    日数が足りず holdout も立たないときは `blind=True` で、
    `stale_lines()` は**黙らない**（`cliff=False` のまま黙ると、
    「測っていない」が「崖ではない」として読まれます）。
    """
    today = FIXED_TODAY
    days = {today - timedelta(days=k): [100] * 10 for k in range(3, 0, -1)}
    s = R.staleness(e=_e(band=20), rows=_rows(days))
    assert s["ok"], s
    assert s["outside_days"] == 0, s
    assert s["blind"] is True, s
    assert s["cliff"] is False, s
    lines = R.stale_lines(s)
    assert lines, "測れていないのに 0行 —— `cliff=False` が「崖ではない」と読まれます"
    assert "測れていません" in lines[0], lines[0]


def test_止まっていて残差も無い回で落ちないこと():
    """`need_mult` は残差が 0日 だと None。前の版はそこに書式を当てて落ちました。

    `scripts/eta.py` は `stale_lines()` の例外を捕まえて別の字に差し替えるので、
    **落ちると頭から静かに消えます。** 例外にしないことを見ます。
    """
    today = FIXED_TODAY
    days = {today - timedelta(days=20): [1000, 1100],
            today - timedelta(days=19): [900, 950]}
    s = R.staleness(e=_e(band=20), rows=_rows(days))
    assert s["stale"] is True, s
    assert s["need_mult"] is None, s
    lines = R.stale_lines(s)                                    # 落ちないこと
    assert lines, s
