"""**検出できない反証条件を、機械で捕まえられているか。**

2026-08-24、「ショートの最後で登録を頼むな」という規則が、
**主張どおりの効きがあっても7割は「外れ」と出る門**を証拠にして入っていた。
同じ形が戻らないよう門を置く。
"""
import math

from src import verdict_power as vp

BASE = 0.000318          # 実測（47,102再生 → 15人）


def test_8月08日の門は主張の効きがあっても外れと出る():
    """alpha は小さいのに beta が大きい。**片側だけ見ると通ってしまう。**"""
    q = vp.power(BASE, 3000, gate=3, target=3.1)
    assert q["alpha"] < 0.10          # 効きなしで生き残る率は小さい
    assert q["beta"] > 0.40           # **主張どおりでも4割は外れと出る**
    assert q["detects_nothing"] is True


def test_開け直した門は両側とも1割で見分けられる():
    q = vp.power(BASE, 30000, gate=14, target=2.0)
    assert q["alpha"] <= 0.20 and q["beta"] <= 0.20
    assert q["detects_nothing"] is False


def test_大きい倍率を狙う門を2倍の物差しで測らない():
    """10倍を狙う設計を「見分けられない」と誤って挙げない。"""
    assert vp.power(BASE, 1000, gate=2, target=10.0)["detects_nothing"] is False
    assert vp.power(BASE, 1000, gate=2, target=2.0)["detects_nothing"] is True
    assert vp.claimed_target("長尺の登録率はショートより1桁以上高い", "") == 10.0
    assert vp.claimed_target("3倍になる", "") == 3.0
    assert vp.claimed_target("上がる", "") == 2.0


def test_0人が否定できるのは実測の何倍までか():
    z = vp.zero_means(BASE, 2720)
    assert z["p_zero_if_no_effect"] > 0.35     # **3回に1回は素で起きる**
    assert z["rules_out_multiple"] > 3.0       # 3倍超しか否定できない
    assert vp.n_for(BASE, 1.5) > vp.n_for(BASE, 2.0) > vp.n_for(BASE, 3.0)


def test_人数で置いた門を率より優先して読む():
    """率で読むと、地の文の実測値を拾う。**実際に一度誤読した。**"""
    hit = [r for r in vp.scan_hypotheses() if "登録を直接1回頼む" in r["claim"]]
    assert hit, "開け直した前提が読めていません"
    assert hit[0]["n"] == 30000 and hit[0]["gate"] == 14
    assert hit[0]["gate_label"] == "14人未満"


def test_実測の率は借りてきた一般値ではない():
    base, views, subs = vp.baseline_rate()
    assert views > 1000 and subs >= 0
    assert base < 0.003, "0.3% は業界の一般値。**ここに入っていたら壊れています**"
    assert math.isclose(base, subs / views)


# ---------------------------------------------------------------------------
# **n が足りないのか、門の置き場所が悪いのか**（2026-08-28 に足した）
#
# `power()` は「駄目だ」しか言わず、道具は「N再生 要ります」だけを出していた。
# 実測では、駄目な門 4件 のうち **2件 は n が足りていて門だけが外れて**おり、
# しかも印字は **既に持っている再生数より小さい数**を「要ります」と言っていた
# （22,549再生 持っている前提に「9,425再生 要ります」）。
# ---------------------------------------------------------------------------

def test_門が平均どおりに置かれるとalphaはほぼ半分():
    """**これが 4件 の共通の形。** 率で門を書くと、実測の率と同じ所に置かれる。"""
    q = vp.power(BASE, 22549, gate=8, target=2.0)      # 0.0355% × 22,549 ≒ 8
    assert q["alpha"] > 0.40, "門が null の期待値の上なら、半分は素で生き残る"
    assert q["beta"] < 0.10, "beta は小さい ＝ **片側だけ見ると通ってしまう**"
    assert q["detects_nothing"] is True


def test_nが足りている件は門を動かすだけで直る():
    """**再生を1回も足さずに直せる。** 待つ必要はない。"""
    for n, bad_gate in ((22549, 8), (30000, 10)):
        assert vp.power(BASE, n, bad_gate, 2.0)["detects_nothing"] is True
        g = vp.gate_for(BASE, n, 2.0)
        assert g is not None, f"n={n} は足りているのに門が見つからない"
        assert g > bad_gate, "直した門は、いまの門より厳しい側にある"
        assert vp.power(BASE, n, g, 2.0)["detects_nothing"] is False


def test_gate_forはいちばん緩い側の門を返す():
    """**厳しすぎる門を返さないこと** —— beta（見落とし）が上がる。"""
    g = vp.gate_for(BASE, 30000, 2.0)
    assert vp.power(BASE, 30000, g - 1, 2.0)["detects_nothing"] is True
    q = vp.power(BASE, 30000, g, 2.0)
    assert q["alpha"] <= vp.MAX_ERR and q["beta"] <= vp.MAX_ERR


def test_本当にnが足りない件はNoneを返す():
    """**「門を直せ」と言ってはいけない件がある。** ここを混ぜると嘘になる。"""
    assert vp.gate_for(BASE, 13015, 2.0) is None    # 族べつの登録率
    assert vp.gate_for(BASE, 3000, 2.0) is None     # 2026-08-08 の判定
    assert vp.gate_for(BASE, 0, 2.0) is None
    assert vp.gate_for(0.0, 30000, 2.0) is None


def test_同じnの隣の前提が既に正しい門を持っていた():
    """**答えは1件 隣に在りました。** n=30,000 で 14人 は通っている。"""
    assert vp.power(BASE, 30000, gate=14, target=2.0)["detects_nothing"] is False
    assert vp.gate_for(BASE, 30000, 2.0) <= 14


def test_直せる件は道具の印字に出る(monkeypatch, capsys):
    """**診断だけで終わらせない。** 出口（`main`）まで通っていること。

    **台帳の中身に依存させないこと**（2026-08-28）——
    ここは実物を読んでいたので、**台帳を直した瞬間に落ちました。**
    落ちたのは枝が壊れたからではなく、**該当が無くなったから**です。
    """
    monkeypatch.setattr(vp, "scan_hypotheses", lambda: [{
        "claim": "作り物・片側の門", "n": 30000, "gate": 10,
        "gate_label": "0.0318%未満", "target": 2.0,
        "two_group": False, "margin": 1, "outcome": "",
    }])
    vp.main()
    out = capsys.readouterr().out
    assert "再生を1回も足さずに直せます" in out


def test_片側の門の直しかたも印字に出る(monkeypatch, capsys):
    """**いまの台帳に該当が無いだけで、枝は生きていること。**

    2026-08-28 に括弧の読みを直した結果、片側の門で「n は足りている」に
    当たる前提が台帳から消えた（唯一の該当が 2群 の前提だった）。
    **台帳の中身で枝が死んだように見えるので、ここは差し替えて撃つ。**
    """
    monkeypatch.setattr(vp, "scan_hypotheses", lambda: [{
        "claim": "作り物・片側の門", "n": 30000, "gate": 10,
        "gate_label": "0.0318%未満", "target": 2.0,
        "two_group": False, "outcome": "",
    }])
    vp.main()
    out = capsys.readouterr().out
    assert "門の置き場所が外れています" in out
    assert "人数で書き直すこと" in out
    assert "再生を1回も足さずに直せます" in out


# ---------------------------------------------------------------------------
# **括弧の中を標本の大きさだと読んでいた**（2026-08-28 に踏んだ）
#
# 診断だけの頃は「N再生 要ります」が少しずれるだけだった。
# **門の数字を名指しするようになった以上、ここがずれると嘘を出す。**
# ---------------------------------------------------------------------------

def test_括弧の中の参照母集団を標本と読まない():
    """M22 の標本は **15,000**。22,549 は 05-01〜08-17 の参照母集団。"""
    hit = [r for r in vp.scan_hypotheses() if "チャンネルのホーム" in r["claim"]]
    assert hit, "M22 の前提が読めていません"
    assert hit[0]["n"] == 15000, "括弧の中の 22,549 を拾っています"


def test_括弧を落としても他の前提の標本は動かない():
    ns = [r["n"] for r in vp.scan_hypotheses()]
    assert 30000 in ns, "n=30,000 の前提が消えました"
    assert 1000 in ns, "n=1,000 の前提が消えました"


def test_n_for_gateはいま持っている数より小さい答えを返さない():
    """**ここがこの道具の壊れ方そのもの。** 15,000 に「9,425 要ります」と言っていた。"""
    for start in (3000, 15000, 30000):
        need = vp.n_for_gate(BASE, 2.0, start=start)
        assert need is None or need > start, f"start={start} に {need} を返しました"


def test_n_for_gateは崖の上を答えにしない():
    """**増やすと見分けられなくなる n がある**（ポアソンは整数の門しか置けない）。

    実測: n=14,293 は門 7人 が通る（beta 19.94%）が、**n=15,000 は通らない**。
    """
    assert vp.gate_for(BASE, 14293, 2.0) is not None
    assert vp.gate_for(BASE, 15000, 2.0) is None      # **増やしたのに駄目になる**
    need = vp.n_for_gate(BASE, 2.0, start=3000)
    assert vp.gate_for(BASE, need, 2.0) is not None
    assert vp.gate_for(BASE, int(need * 1.05), 2.0) is not None


def test_n_for_gateとn_forは別の問いに答えている():
    """**混ぜると、既に足りている前提に「足りない」と言う。**"""
    assert vp.n_for_gate(BASE, 2.0, start=0) > vp.n_for(BASE, 2.0)


def test_見分けられない件に足りない再生数が出る(capsys):
    vp.main()
    out = capsys.readouterr().out
    assert "門で見分けられるようになるのは" in out
    assert "9,425再生 要ります" not in out, "`n_for` を門の答えに使っています"


# ---------------------------------------------------------------------------
# **2群を比べる前提に、片側の門の数字を出していた**（2026-08-28）
#
# 「途中の依頼」は処置群 対 対照群。そこへ `gate_for()` の答え
# （「門を 13人未満 に」）を出すと、**別の実験に化ける。**
# ---------------------------------------------------------------------------

def test_上回れば通るは効きが無くても半分通る():
    """**2つの独立なポアソンは、引き分け以外は半々。**"""
    q = vp.two_group_power(BASE, 30000, margin=1, target=2.0)
    assert 0.40 < q["alpha"] < 0.50, "余白ゼロの alpha は約 45%"
    assert q["beta"] < 0.10
    assert q["detects_nothing"] is True


def test_余白を置くと2群でも見分けられる():
    m = vp.margin_for(BASE, 30000, 2.0)
    assert m is not None and m > 1, "余白ゼロのままでは門になりません"
    q = vp.two_group_power(BASE, 30000, m, 2.0)
    assert q["alpha"] <= vp.MAX_ERR and q["beta"] <= vp.MAX_ERR
    # **いちばん緩い余白**（1つ手前は通らない）
    assert vp.two_group_power(BASE, 30000, m - 1, 2.0)["detects_nothing"] is True


def test_2群の余白は片側の門の数字とは別物():
    """**ここを混ぜたのが、この直しの理由。**"""
    assert vp.margin_for(BASE, 30000, 2.0) != vp.gate_for(BASE, 30000, 2.0)


def test_2群の前提を2群として読んでいる():
    rows = {r["claim"][:24]: r for r in vp.scan_hypotheses()}
    mid = [r for k, r in rows.items() if "途中にも1回" in r["claim"]]
    assert mid and mid[0]["two_group"] is True
    one = [r for k, r in rows.items() if "チャンネルのホーム" in r["claim"]]
    assert one and one[0]["two_group"] is False


def test_2群には片側の門の指示を出さない(monkeypatch, capsys):
    """**余白ゼロの2群**を出口まで通し、片側の門の指示が出ないことを見る。"""
    monkeypatch.setattr(vp, "scan_hypotheses", lambda: [{
        "claim": "作り物・2群・余白ゼロ", "n": 30000, "gate": 10,
        "gate_label": "0.0318%未満", "target": 2.0,
        "two_group": True, "margin": 1, "outcome": "",
    }])
    vp.main()
    out = capsys.readouterr().out
    assert "対照を 5人 以上 上回る" in out
    assert "余白がゼロなのが外れです" in out
    assert "片側の門の数字（N人未満）をここに書かないこと" in out
    assert "門を 13人未満 に直せば" not in out, "2群に片側の門の数字を出しています"


def test_台帳に置いた余白を読む():
    """**道具と台帳が同じ数を見ていること。**

    余白を台帳に書いても道具が 1 と決め打っていた間は、
    直した後も「見分けられません」と鳴り続けた（2026-08-28）。
    """
    mid = [r for r in vp.scan_hypotheses() if "途中にも1回" in r["claim"]]
    assert mid, "途中の依頼の前提が読めていません"
    assert mid[0]["margin"] == 5, "台帳の『5人 以上 上回』を読めていません"
    q = vp.two_group_power(BASE, mid[0]["n"], mid[0]["margin"], mid[0]["target"])
    assert q["detects_nothing"] is False, "直した条件が、まだ見分けられません"


def test_余白の書いていない2群は余白ゼロとして数える():
    """**書き忘れを「1人でも上回れば通る」と読む。** 甘い側へ倒さない。"""
    rows = [r for r in vp.scan_hypotheses() if r["two_group"]]
    assert rows, "2群の前提が1件もありません"
    for r in rows:
        assert r["margin"] >= 1


def test_直した前提は道具の一覧で見分けられる側に出る(capsys):
    """**台帳の実物**を読む。直した条件が、見分けられる側に出ていること。"""
    vp.main()
    out = capsys.readouterr().out
    assert "対照を 5人 以上 上回れば通る" in out
    block = out.split("途中にも1回")[-1].split("\n\n")[0]
    assert "見分けられます" in block and "**見分けられません**" not in block
