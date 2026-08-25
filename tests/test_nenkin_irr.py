"""`nenkin.deferral_irr()` 以下の**主張そのもの**を固定する（2026-08-21 に足した5節）。

繰下げの説明は世の中では「1か月あたり0.7パーセント増える」で止まっていて、
**増える率**しか言っていません。増額は終身ですが、**待っているあいだの受給を
差し出して買っている**ので、率だけでは損得になりません。
そこでこの5節は、繰下げを投資として見たときの**内部収益率（年利）**を出します。

この節が動画で言うのは、次の5つです。**どれも既存の13節の外側にあります**
（既存は分岐点の「年齢」と生涯の「総額」だけで、**率**は1つも出していません）。

1. **待つほど年利は下がる** —— 66歳開始 5.19% → 73歳開始 0.08%（85歳まで・額面）。
   増える率は一定なのに年利が落ちるのは、差し出す月数が増えるから
2. **手取りにすると 1.6〜1.8ポイント落ちる** —— 71歳から先は 85歳までに元が取れない
3. **元が取れる最後の月が、額面73歳1か月 → 手取り70歳10か月へ 27か月ぶん前へ動く**
4. **同じ「70歳まで繰下げ」でも、寿命で年利が 0.09%〜6.20% と 69倍ちがう**
5. **手取りの年利の谷は端ではなく 246万円**（下は課税されないので額面と同じ、
   上は手取り率が頭打ちで一定になるのでやはり額面に戻る。**間だけ落ちる**）

そして **6つ目に、年利で選ぶ開始（65歳1か月）と総額で選ぶ開始（69歳1か月）が
別の月になる** ——「どちらが正しいか」ではなく**問いが違う**、が節の主題です。

**既知の当たり（この道具が正しければ必ず当てるはずの1件）**:
`break_even()` は累計の追い越しで、`irr_zero_age()` は正味現在価値の符号です。
**別々に書いてあるので、同じ年齢に着くことが両方の裏取り**になります。

**`check_tables()` が緑であることは、ここでは証拠になりません**
（自分を呼んで自分を確かめているだけ）。式を壊したときに本当に落ちるかは、
外から壊してみないと分かりません —— 下の故障注入がそれです。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.calc import nenkin  # noqa: E402


def test_制度の値の検査は通る():
    nenkin.check_tables()


def test_既知の当たり_分岐点と年利がゼロになる寿命は一致する():
    """**別々の道から同じ年齢に着くこと。** ここが外れたらどちらかが壊れている。"""
    for months in (1, 12, 60, 96, 120):
        be = nenkin.break_even(months, 180.0)
        got = nenkin.irr_zero_age(months, 180.0)
        want = be[0] + (1 if be[1] > 0 else 0)
        assert got == want, (
            f"繰下げ{months}か月: 分岐点 {be[0]}歳{be[1]}か月 に対して "
            f"年利がプラスに変わるのが {got}歳（{want}歳のはず）")


def test_待つほど年利は下がる():
    seq = [r["年利_額面"] for r in nenkin.irr_grid(180.0, 85, 12)
           if r["年利_額面"] is not None]
    assert len(seq) >= 5
    assert seq == sorted(seq, reverse=True), seq
    # 節が名指ししている両端（66歳開始と73歳開始）
    assert seq[0] == pytest.approx(5.19, abs=0.02)
    assert seq[-1] == pytest.approx(0.08, abs=0.02)


def test_手取りにすると年利は落ちる():
    for r in nenkin.irr_grid(180.0, 85, 12):
        if r["年利_額面"] is None or r["年利_手取り"] is None:
            continue
        assert r["年利_手取り"] < r["年利_額面"], r
        assert 1.4 <= r["差_ポイント"] <= 2.0, r


def test_元が取れる最後の月は手取りのほうが前():
    g = nenkin.irr_last_month(180.0, 85, net=False)
    n = nenkin.irr_last_month(180.0, 85, net=True)
    assert g["最後の開始"] == "73歳1か月", g
    assert n["最後の開始"] == "70歳10か月", n
    assert g["最後の月数"] - n["最後の月数"] == 27


def test_額面の年利は年金額によらない():
    """割引率の式で額が約分されるので、**どの年額でも同じ値**になる。"""
    vals = [nenkin.deferral_irr(60, float(x), 85) for x in (78, 120, 246, 350, 500)]
    assert all(v == pytest.approx(vals[0], abs=1e-6) for v in vals), vals


def test_手取りの年利の谷は端ではなく内側():
    w = nenkin.irr_worst_base(60, 85, step_man=2)
    assert w["谷の年額_万"] == 246.0, w
    assert w["谷の年利_手取り"] < w["下の端の年利_手取り"]
    assert w["谷の年利_手取り"] < w["上の端の年利_手取り"]
    # 両端で額面に戻る側（上の端）は、額面と一致するところまでが主張
    assert w["上の端の年利_手取り"] == pytest.approx(w["年利_額面"], abs=0.01)


def test_寿命で年利が何十倍も動く():
    rows = [r for r in nenkin.irr_by_lifespan(60, 180.0, 80, 100, 2)
            if r["年利_額面"] is not None]
    assert rows[0]["年利_額面"] == pytest.approx(0.09, abs=0.02)
    assert rows[-1]["年利_額面"] == pytest.approx(6.20, abs=0.02)


def test_年利で選ぶ開始と総額で選ぶ開始は別の月():
    """**問いが違う**ことが節の主題。同じ月に揃ったら節ごと書き直すこと。"""
    by_irr = nenkin.irr_best_months(180.0, 85, net=False)["月数"]
    by_total = nenkin.best_start(85 * 12, 180.0, net=False)
    assert by_irr == 1, by_irr
    assert by_total != by_irr, (by_irr, by_total)


def test_分岐点の手前では年利が出ない():
    """総額で追いついていないのに率を出すと、**符号の無い数字**になる。"""
    assert nenkin.deferral_irr(60, 180.0, 80) is None
    assert nenkin.deferral_irr(0, 180.0, 100) is None
    assert nenkin.deferral_irr(-12, 180.0, 100) is None


def test_節が_main_の出力に出ている():
    """**画面に出ない計算は、この作りでは無いのと同じ**（前提と式を出すのが根幹）。"""
    import io
    import contextlib
    import runpy

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        runpy.run_module("src.calc.nenkin", run_name="__main__")
    out = buf.getvalue()
    for head in ("繰下げを「投資」とみなしたときの年利",
                 "繰下げが元を取れる最後の月",
                 "年利がいちばん低くなる年金額",
                 "年利がいちばん高い開始と、総額がいちばん多い開始は別の月"):
        assert head in out, head
    assert "246万円" in out
    assert "内部収益率" in out


def test_故障注入_手取り率を一律にすると谷が消えて落ちる(monkeypatch):
    """手取り率が額によらなければ、**谷は消える**。消えたのに通ったら検査が眠っている。"""
    monkeypatch.setattr(nenkin, "NET_RATE_POINTS",
                        [(78.0, 0.900), (500.0, 0.900)])
    with pytest.raises(ValueError):
        nenkin.check_tables()


def test_故障注入_年利の符号を反転すると分岐点との一致が壊れる(monkeypatch):
    """`irr_zero_age` の当たりが、**本当に `break_even` と噛んでいるか**を外から壊して見る。"""
    real = nenkin.deferral_irr

    def flipped(months, base=180.0, until_age=85, net=False):
        v = real(months, base, until_age, net=net)
        return None if v is not None else 0.0

    monkeypatch.setattr(nenkin, "deferral_irr", flipped)
    with pytest.raises(ValueError, match="年利がプラスに変わる"):
        nenkin.check_tables()
