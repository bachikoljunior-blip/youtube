"""`studio/trend.lap_cost` / `lap_value` / `lap_value_line` —— **分母を枠から周へ**。

**2026-09-19 07:xx・optimizer（Opus 5・ultracode・1周 1体）。** derivation は `docs/JOURNAL.md` 同刻。

**なぜ在るか**: `slot_value` の分母は **枠**（1日 5本）です。**枠は余っています**
（在庫 13本 ＞ 5本/日）。余っている側を分母にすると「どちらを枠に入れるか」しか訊けません。
足りないのは **周**（期限 85日 ÷ 1周 約1時間 ＝ 残り 約2,000周）で、そちらを分母にすると
同じ台帳で **131倍**（枠を分母にすると 18.7倍）になり、
**作りの周の 76% が 3桁 負けている側に行っている**ことが出ます。

**陽性対照つき**（落ちるまで撃つ）: 周/本 を入れ替えたら順が入れ替わること・
在庫が枠を下回ったら「枠が縛る」と言うこと の両方を見ます。
"""
import json
from pathlib import Path

import pytest

from studio import trend

ROOT = Path(__file__).resolve().parent.parent


# --- lap_cost（実物の git の台帳）-------------------------------------------

def test_lap_cost_は両方の形を数える():
    c = trend.lap_cost()
    if not c:
        pytest.skip("git の台帳が引けない所")
    for f in ("short", "long"):
        assert f in c, c.keys()
        assert c[f]["n"] > 0
        assert c[f]["laps_per"] > 0
        assert c[f]["revs_per"] > 0
    assert c["_lap"]["since"] == trend.LAP_SINCE


def test_周は本より高くつく側が長尺():
    """**この回の実測** —— long 5.0周/本 対 short 0.7周/本。

    **数はここへ写しません**（毎周 引き直す ＝ 覆る条件 (3)）。見るのは**向き**だけ。
    """
    c = trend.lap_cost()
    if not c:
        pytest.skip("git の台帳が引けない所")
    assert c["long"]["laps_per"] > c["short"]["laps_per"], c


# --- lap_value（割り算そのもの）---------------------------------------------

def _fake(monkeypatch, per_slot, laps_per):
    monkeypatch.setattr(trend, "slot_value", lambda *a, **k: {
        "short": {"perf_yen": per_slot["short"], "mean": 100.0},
        "long": {"perf_yen": per_slot["long"], "mean": 10.0},
        "_gate": {},
    })
    monkeypatch.setattr(trend, "lap_cost", lambda **k: {
        "short": {"n": 10, "laps": 7, "laps_per": laps_per["short"], "revs_per": 3.0},
        "long": {"n": 10, "laps": 50, "laps_per": laps_per["long"], "revs_per": 8.0},
        "_lap": {"mixed": 2, "total": 59, "since": "2026-09-15"},
    })


def test_円_周_は_円_枠_を_周_本_で割った数(monkeypatch):
    _fake(monkeypatch, {"short": 1400.0, "long": 75.0}, {"short": 0.7, "long": 5.0})
    d = trend.lap_value([])
    assert d["short"]["per_lap"] == pytest.approx(1400.0 / 0.7)
    assert d["long"]["per_lap"] == pytest.approx(75.0 / 5.0)


def test_周_本_を入れ替えると順も入れ替わる(monkeypatch):
    """**陽性対照** —— この行が本当に `laps_per` を読んでいること。"""
    _fake(monkeypatch, {"short": 1400.0, "long": 75.0}, {"short": 0.7, "long": 5.0})
    assert trend.lap_value([])["short"]["per_lap"] > trend.lap_value([])["long"]["per_lap"]
    _fake(monkeypatch, {"short": 1400.0, "long": 75.0}, {"short": 500.0, "long": 0.01})
    d = trend.lap_value([])
    assert d["long"]["per_lap"] > d["short"]["per_lap"], "周/本 が逆なら順も逆になること"


def test_測れない側は_None_で_0_ではない(monkeypatch):
    _fake(monkeypatch, {"short": None, "long": 75.0}, {"short": 0.7, "long": 5.0})
    d = trend.lap_value([])
    assert d["short"]["per_lap"] is None


# --- lap_value_line（印字）---------------------------------------------------

def test_行は倍率と_長尺に行った周の割合を出す(monkeypatch):
    _fake(monkeypatch, {"short": 1400.0, "long": 75.0}, {"short": 0.7, "long": 5.0})
    s = trend.lap_value_line([], inventory=13)
    assert "分母は枠ではなく周" in s
    assert "133倍" in s or "倍" in s
    assert "long に行っています" in s
    assert "API 0単位" in s


def test_在庫が枠を下回ったら_枠が縛ると言う(monkeypatch):
    """**覆る条件 (1)** —— 在庫が尽きた日は、分母を枠に戻してよい。"""
    _fake(monkeypatch, {"short": 1400.0, "long": 75.0}, {"short": 0.7, "long": 5.0})
    assert "枠が縛る側です" in trend.lap_value_line([], inventory=1)
    assert "縛っているのは周です" in trend.lap_value_line([], inventory=99)


def test_git_が引けない所では黙って枠の行へ送る(monkeypatch):
    monkeypatch.setattr(trend, "lap_cost", lambda **k: {})
    s = trend.lap_value_line([])
    assert "周が数えられません" in s
    assert "枠の行だけで読むこと" in s


# --- 在庫の上端 --------------------------------------------------------------

def test_在庫の上端は_台帳に出ていない台本を数える(tmp_path):
    d = tmp_path / "scripts"
    d.mkdir()
    for slug in ("a", "b", "c"):
        (d / f"{slug}.json").write_text("{}", encoding="utf-8")
    rows = [{"event": "scheduled", "id": "a"}]
    assert trend._inventory_upper(rows, d) == 2


def test_在庫の上端は_実物の_出せる_より少なくない():
    """**上端であること** —— `status` の「出せる」は焼きと輪まで見るので、必ずこちら以下。"""
    rows = [json.loads(x) for x in
            (ROOT / "data/studio/ledger.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    up = trend._inventory_upper(rows)
    n_scripts = len(list((ROOT / "data/studio/scripts").glob("*.json")))
    assert up is not None and 0 <= up <= n_scripts


# --- 毎周の行に入っていること ------------------------------------------------

def test_毎周の行に入っている():
    src = (ROOT / "studio/trend.py").read_text(encoding="utf-8")
    assert "out.append(lap_value_line(rows))" in src
    i = src.index("out.append(slot_value_line(rows))")
    j = src.index("out.append(lap_value_line(rows))")
    assert j > i, "枠の行のすぐ後に置くこと（分母の話が 2行 続く）"


# --- `status` の「形の順」の行にも出ること -----------------------------------

def test_status_の形の順の行にも_円_周_が出る():
    """**読む側が毎周 見るのは `status`** —— `trend` の並びだけに置くと届きません。"""
    from studio import cli
    t = cli._form_gap_phrase()
    if "円/枠" not in t:
        pytest.skip("齢の帯で片側が FORM_MIN_N 未満の回（数が出ない）")
    assert "分母（枠）は余っています" in t or "枠が縛る" in t
    assert "/周" in t
    assert "METHOD §5 2026-09-19 07:xx" in t


def test_status_の行は_周が数えられない所でも落ちない(monkeypatch):
    """**この行のために周を止めないこと** —— `lap_cost` が空でも枠の行は出ること。"""
    from studio import cli
    monkeypatch.setattr(trend, "lap_cost", lambda **k: {})
    t = cli._form_gap_phrase()
    assert "再生の差は" in t or "いま引けません" in t
