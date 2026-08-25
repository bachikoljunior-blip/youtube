"""`nenkin.by_base_grid()` の**主張そのもの**を固定する（2026-08-16 に足した節）。

この節が動画で言うのは、次の3つです。**どれも既存の5節の外側にあります**
（既存の節は全部「年額180万円の1人ぶん」しか出していません）。

1. **額面の分岐点は、年金額を変えても1か月も動かない** —— 全員おなじ 81歳10か月。
   両方に同じ倍率が掛かるだけなので、比の交点が動かないため
2. **手取りの分岐点だけが動く** —— 83歳3か月〜84歳2か月。
   動く理由は `_clamp_rate` の折れ線が非線形だから、という一点だけ
3. **生涯手取りの差は、年額に対して単調ではない** —— 年額78万円の人（+495,643円）が
   120万円の人（+424,080円）より**多く増えます。**
   78万円は繰り下げても手取り率が 1.000→0.969 でほとんど落ちないため

そして**出さない組がある**こと自体も主張です。繰下げ後の年額が
`NET_RATE_POINTS` の上端（500万円）を超えると `_clamp_rate` が平らになり、
**ずれが 0 か月**になります。これは「差が無い」ではなく「前提が届いていない」で、
**見分けが付かない数字を画面に出さない**ために行ごと落としています。

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


def test_額面の分岐点は年額を変えても動かない():
    rows = nenkin.by_base_grid()
    assert len({r["分岐点_額面"] for r in rows}) == 1
    assert rows[0]["分岐点_額面"] == "81歳10か月"


def test_手取りの分岐点は年額で動く():
    rows = nenkin.by_base_grid()
    got = [r["分岐点_手取り"] for r in rows]
    assert len(set(got)) >= 2, got
    # 年額が上がるほど後ろへ（頭打ちはするが、前へは戻らない）
    months = [r["ずれ_月"] for r in rows]
    assert months == sorted(months), months
    assert all(m > 0 for m in months)


def test_前提の外_年額500万円を超える組は行ごと落ちる():
    top = nenkin.NET_RATE_POINTS[-1][0]
    rate = nenkin.rate_for(60)
    rows = nenkin.by_base_grid()
    assert all(r["繰下げ後の年額_万"] <= top for r in rows)
    # 500万円の行は「差0か月」で通ってしまうので、**入っていないこと**が要点
    assert 500.0 * rate > top
    assert 500.0 not in {r["65歳の年額_万"] for r in rows}
    # 落としたのは1行だけ。表そのものが痩せていないこと
    assert len(rows) == len(nenkin.NET_RATE_POINTS) - 1


def test_生涯手取りの差は年額に対して単調でない():
    """**ここが動画の主役です。** 単調になったら、言うことが1つ消えます。"""
    rows = {r["65歳の年額_万"]: r["差_円"] for r in nenkin.by_base_grid()}
    assert rows[78.0] > rows[120.0], rows
    assert rows[120.0] < rows[180.0] < rows[250.0] < rows[350.0], rows


def test_表に金額が入っている():
    """`net_tilt` が2回続けて `topic_forge` に落とされた形（年齢しか無かった）。

    書き手は「◯◯円得する」という題を立てるので、**金額が表に無いと
    `realign` が裏の取れない数字として弾きます。** 節は在庫に数えられるのに
    一度も動画にできない、という状態になります。
    """
    for row in nenkin.by_base_grid():
        assert row["差_円"] > 0
        assert row["生涯手取り_繰下げ_円"] > row["生涯手取り_65歳受給_円"] > 0


def test_節が_main_の出力に出ている():
    import io
    import contextlib
    import runpy

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        runpy.run_module("src.calc.nenkin", run_name="__main__")
    heads = [ln for ln in buf.getvalue().splitlines() if ln.startswith("=== ")]
    # `topic_forge` が節として数えるのは `=== 見出し ===` の行だけ。
    # **件数の一致では書かない**（2026-08-17 に直した）。ここは長らく
    # `len(heads) == 6` で、節を4つ足した回がこれで落ちています。
    # 落ちる向きが逆で、**節が消えたときではなく増えたときに落ちていました。**
    # 見たいのは「この節が出ているか」なので、名前で見ます。
    for want in ("年金額べつ", "いちばん多くもらえる開始年齢", "4年半飛ぶ",
                 "あと1か月だけ待つ", "あと1か月だけ早める"):
        assert any(want in h for h in heads), (want, heads)
    # 見出しが重なると `topic_forge` が節を取り違えるので、そこだけは件数で見る
    assert len(set(heads)) == len(heads), heads


# --------------------------------------------------------------------------
# 故障注入。**壊したときに `check_tables()` が落ちること**を確かめる。
# --------------------------------------------------------------------------

def test_故障注入_手取り率を一律にすると落ちる(monkeypatch):
    """一律の率なら分岐点は動かない ＝ この節は何も言っていない状態になる。

    **落とすのは既存の門です**（`手取り率が額によらず一定`）。ここで確かめたいのは
    「この節が何も言わなくなる形は、既に誰かが見張っている」ことなので、
    自分の門で二重に受けようとせず、**実際に落ちる場所の文言をそのまま書きます。**
    """
    monkeypatch.setattr(nenkin, "_clamp_rate", lambda annual_man: 0.9)
    with pytest.raises(ValueError, match="手取り率が額によらず一定"):
        nenkin.check_tables()


def test_故障注入_手取りの分岐点が動かなくなったら落ちる(monkeypatch):
    """上の門をすり抜けて、表の側だけが潰れた場合（列の取り違え・写し間違い）。"""
    real = nenkin.by_base_grid

    def flat(*a, **k):
        rows = real(*a, **k)
        head = rows[0]["分岐点_手取り"]
        return [{**r, "分岐点_手取り": head} for r in rows]

    monkeypatch.setattr(nenkin, "by_base_grid", flat)
    with pytest.raises(ValueError, match="手取りの分岐点が年額で動いていない"):
        nenkin.check_tables()


def test_故障注入_前提の外を落とさなくなると落ちる(monkeypatch):
    """上端の切り落としを外すと、500万円の行（ずれ0か月）が入ってくる。"""
    real = nenkin.by_base_grid

    def leaky(months_from_65: int = 60, until_age: int = 85):
        rows = real(months_from_65, until_age)
        rate = nenkin.rate_for(months_from_65)
        base = 500.0
        gross = nenkin.break_even(months_from_65, base, net=False)
        netbe = nenkin.break_even(months_from_65, base, net=True)
        rows.append({
            "65歳の年額_万": base,
            "繰下げ後の年額_万": round(base * rate, 1),
            "手取り率_65歳": round(nenkin._clamp_rate(base), 3),
            "手取り率_繰下げ後": round(nenkin._clamp_rate(base * rate), 3),
            "分岐点_額面": f"{gross[0]}歳{gross[1]}か月",
            "分岐点_手取り": f"{netbe[0]}歳{netbe[1]}か月",
            "ずれ_月": (netbe[0] * 12 + netbe[1]) - (gross[0] * 12 + gross[1]),
            "生涯手取り_65歳受給_円": 1,
            "生涯手取り_繰下げ_円": 2,
            "差_円": 1,
        })
        return rows

    monkeypatch.setattr(nenkin, "by_base_grid", leaky)
    with pytest.raises(ValueError, match="手取り率の前提の外"):
        nenkin.check_tables()


def test_故障注入_表が空でも通してしまわない(monkeypatch):
    monkeypatch.setattr(nenkin, "by_base_grid", lambda *a, **k: [])
    with pytest.raises(ValueError, match="年金額べつの表が空"):
        nenkin.check_tables()


def test_故障注入_ずれが前に来たら落ちる(monkeypatch):
    real = nenkin.by_base_grid

    def flipped(*a, **k):
        rows = real(*a, **k)
        rows[0] = {**rows[0], "ずれ_月": -1}
        return rows

    monkeypatch.setattr(nenkin, "by_base_grid", flipped)
    with pytest.raises(ValueError, match="手取りの分岐点が額面より前"):
        nenkin.check_tables()


def test_故障注入_差が0以下なら落ちる(monkeypatch):
    real = nenkin.by_base_grid

    def zeroed(*a, **k):
        rows = real(*a, **k)
        rows[-1] = {**rows[-1], "差_円": 0}
        return rows

    monkeypatch.setattr(nenkin, "by_base_grid", zeroed)
    with pytest.raises(ValueError, match="生涯手取りが増えていない"):
        nenkin.check_tables()
