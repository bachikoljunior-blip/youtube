"""**枠の機会費用の門**（`src/slot_cost.py`）の検査。API 0単位・実物のデータは読みません。

この門が守るのは1つだけ ——
**「規則1（1日1本）の下では、枠を1つ食う試しは、当たったときの見込みが
その枠の機会費用以上でなければ、当たっても枠のぶんを払えない」。**

**この検査が落ちたときに疑うこと**: 形の禁止を書き足していないか。
`slot_cost` は**禁止しません**。数を返し、`daily_pick.lines()` が印字するだけです。
"""
from __future__ import annotations

import pytest

from src import slot_cost


def _cmp(short_rule=1049, short_n=15, long_rule=1, long_n=7,
         short_all=164, long_all=1) -> dict:
    return {
        "rule": {
            "ショート": {"n": short_n, "median": short_rule, "p90": 1508, "max": 1777},
            "長尺": {"n": long_n, "median": long_rule, "p90": 3, "max": 4},
        },
        "all": {
            "ショート": {"n": 216, "median": short_all, "p90": 1109, "max": 1864},
            "長尺": {"n": 36, "median": long_all, "p90": 7, "max": 73},
        },
    }


def test_slot_value_uses_the_rule_density_not_the_mixed_number():
    """**枠の値は「規則の密度の日だけ」で決まること。**

    混ぜた数（164回）は 8本以上/日 の日の本に引かれた数で、規則の下の枠の値ではない。
    ここが混ぜた数へ戻ると、枠を ×6.4 小さく見積もる元の壊れ方に戻ります。
    """
    s = slot_cost.slot_value(_cmp())
    assert s["best"] == "ショート"
    assert s["cost"] == 1049                      # 混ぜた 164 ではない
    assert s["forms"]["ショート"]["mixed_median"] == 164


def test_experiment_below_the_slot_cost_does_not_pay():
    """**当たりの門が機会費用より小さい試しは、当たっても払えない。**（09/04-05 の長尺）"""
    v = slot_cost.verdict(100.0, form="長尺", cmp=_cmp())
    assert v["ok"] is False
    assert v["cost"] == 1049
    assert v["ratio"] == pytest.approx(100 / 1049)
    assert "1/10" in v["why"]
    assert "×25" in v["why"]                       # 長尺の規則の密度での最大 4回 の ×25


def test_experiment_above_the_slot_cost_pays():
    """**門が機会費用以上なら通ること。**（開いているショートの前提・門 10,000回）"""
    v = slot_cost.verdict(10_000.0, form="ショート", cmp=_cmp())
    assert v["ok"] is True
    assert v["ratio"] > 1


def test_gate_flips_by_measurement_not_by_forbidding_a_form():
    """**形の禁止ではないこと。**

    長尺が規則の密度で中央値を上げたら、`best` は自分で長尺へ倒れ、
    さっき落ちた門 100回 が**同じコードのまま通ります。**
    """
    c = _cmp(long_rule=80, long_n=12)
    s = slot_cost.slot_value(c)
    assert s["best"] == "長尺" or s["cost"] == 1049  # ショートがまだ上ならそのまま
    c2 = _cmp(short_rule=50, long_rule=80, long_n=12)
    s2 = slot_cost.slot_value(c2)
    assert s2["best"] == "長尺"
    assert slot_cost.verdict(100.0, form="長尺", cmp=c2)["ok"] is True


def test_thin_samples_are_named_not_dropped():
    """**薄い標本は落とさず名指しすること。**

    落とすと「標本が無いから比べない」になり、枠がまた黙って消えます。
    """
    s = slot_cost.slot_value(_cmp())
    assert "長尺" in s["thin"]                     # n=7 < MIN_N
    assert s["forms"]["長尺"]["n"] == 7


def test_no_measurement_returns_none_not_a_pass():
    """**測れないときは「通った」ではなく `None` を返すこと。**"""
    empty = {"rule": {}, "all": {}}
    v = slot_cost.verdict(100.0, form="長尺", cmp=empty)
    assert v["ok"] is None


def test_lines_carry_both_forms_on_the_same_ruler():
    """**印字は両方の形を同じ物差しで並べること。**（元の欠陥はここ）"""
    out = "\n".join(slot_cost.lines(_cmp()))
    assert "ショート" in out and "長尺" in out
    assert "1,049" in out and "枠の機会費用" in out


def test_open_slot_experiments_reads_the_real_yaml():
    """**実物の `config/hypotheses.yaml` から、枠を食う前提の門が読めること。**

    読めなかった門は `win=None` で返り、**黙って落ちない**こと ——
    落とすと門の無い前提だけがこの検査を素通りします。
    """
    rows = slot_cost.open_slot_experiments()
    assert rows, "枠を食う前提が1つも読めていません"
    wins = {r["form"]: r["win"] for r in rows if r.get("form")}
    assert wins.get("長尺") == 100.0
    assert wins.get("ショート") == 10_000.0


def test_daily_pick_prints_the_gate():
    """**主実行の読み物に、この門が出ること。**（`daily_pick.lines()` に配線した1か所）"""
    import inspect

    from src import daily_pick as dp
    src = inspect.getsource(dp.lines)
    assert "slot_cost" in src, "daily_pick.lines() から枠の機会費用の行が外れています"


def test_override_notes_answer_the_two_arguments_that_actually_took_the_slot():
    """**実際に枠を取った2つの言い分に、数で答えが出ること。**

    出典は `data/daily_pick.jsonl`（09/04 22:24／22:54／23:24 の `why`）——
    (1)「既に使った枠が捨てになる」(2)「比べる相手の分母が処置0本」。
    **門を置いても、言い分に答えが無ければ次の回が同じ手で通します。**
    """
    notes = slot_cost.override_notes(100.0, cmp=_cmp())
    assert len(notes) == 2
    joined = "\n".join(notes)
    assert "捨てになる" in joined and "処置0本" in joined
    assert "1,049" in joined and "100" in joined
    # 沈んだ費用は次の枠の値を上げない、と明言していること
    assert "次の枠の値を1回も上げません" in joined


def test_override_notes_are_silent_without_a_threshold():
    assert slot_cost.override_notes(None, cmp=_cmp()) == []
