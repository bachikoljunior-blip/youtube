"""**「届きません」の隣に、天井を全部 引いたあとの残りが出ていること。**（2026-08-31）

## なぜ要るか（この回に撃って出た数）

`scripts/eta.py` は「**どの帯でも届きません**」と、そのすぐ上に
「ショート 高 は **×196.3** 遠い」を出していました。**どちらも
「いまの1本あたり再生（566回）から見た距離」**です。
ところが `config/hypotheses.yaml` は `per_video` の天井を
**もう測って持っています**（`ceiling.value: 1891`）。その天井を当てると:

    1,891回/本 × 1本/日（規則）× 30日 × RPM ¥2,000（帯の上端）
      = **¥113,460/月 ＝ 目標の 56.7%**  →  残り **×1.76**

**×196.3 と ×1.76 は同じ穴の別の測り方**で、後者だけが
「まだ引いていない腕のぶん」を含みません。**手を決めるのに使えるのは後者**です。

`CLAUDE.md` の「**(イ) 裸の『届きません』を出さないこと** —— 何を固定したせいで
そう出たのかを同じ行に並べる」の、いちばん芯にあたる行です。

## この検査が落ちる条件（＝**直し方**）

- 残りの倍率が印字から消えたら → `residual_lines()` が `report()` から
  外れています。**戻すこと**（消すのではなく）
- 残りが 1.0 を切ったら（＝天井を当てれば届く）→ 印字は
  「**天井を当てれば届きます**」に変わります。**そのときは
  `docs/MEANS.md` M23 の「どの帯でも届きません」を書き直すこと**
- 天井の出どころが `hypotheses.yaml` でなくなったら → `residual_gap()` の
  docstring の「覆る条件」を書き直すこと
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _eta():
    spec = importlib.util.spec_from_file_location("etamod", ROOT / "scripts" / "eta.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def eta():
    return _eta()


@pytest.fixture(scope="module")
def a(eta):
    """**積んである最後の点**で解く（API 0単位）。"""
    points = eta._points()
    if not points:
        pytest.skip("data/eta.jsonl に点がありません")
    return eta.analyse(points[-1], points)


def test_残りの倍率は天井を全部当てたあとの距離である(eta, a):
    r = eta.residual_gap(a)
    assert r is not None, "`per_video` の天井が台帳から読めていません"
    # **上限は、天井 × 規則の本数 × 30日 × 帯の上端**。写しではなく、掛け直して確かめる。
    want = r["per_video_ceiling"] * r["per_day"] * 30 / 1000 * r["rpm"]
    assert r["yen"] == pytest.approx(want)
    assert r["residual"] == pytest.approx(eta.TARGET_YEN / r["yen"])


def test_天井は台帳の_per_video_のものを読んでいる(eta, a):
    """**この行を、その場の定数で書かないこと。** 台帳が更新されたら自動で追うこと。"""
    from src import arm_speed

    c = arm_speed.ceilings().get("per_video")
    assert c and c.get("value"), "`hypotheses.yaml` に `per_video` の `ceiling` がありません"
    assert eta.residual_gap(a)["per_video_ceiling"] == pytest.approx(float(c["value"]))


def test_本数は規則から来ている(eta, a):
    """**1日1本は固定その2**（`src/house_rule.py`）。ここが観測値に戻ったら落とす。"""
    from src import house_rule

    r = eta.residual_gap(a)
    assert r["per_day"] <= float(house_rule.PUBLISH_PER_DAY), (
        "残りの倍率が、規則より多い本数の上に立っています"
    )


def test_残りの倍率は_いまの1本あたりから割った倍率より小さい(eta, a):
    """**×196.3 と ×1.76 が入れ替わったら落とす。**

    後者が前者以上になるのは、`per_video` の天井が「いま」より下に来たとき ＝
    **天井のほうが古い**という意味です。そのときは天井を測り直すこと。
    """
    r = eta.residual_gap(a)
    nearest = min(a["per_video_ratio"], key=lambda k: a["per_video_ratio"][k])
    assert r["residual"] < a["per_video_ratio"][nearest], (
        f"残り ×{r['residual']:.2f} が、いまから割った ×{a['per_video_ratio'][nearest]:.2f} "
        "以上になっています —— 天井のほうが古い可能性があります"
    )


def test_報告の本文に残りの倍率が出ている(eta, a):
    lines = eta.residual_lines(a)
    assert lines, "`residual_lines()` が何も返していません"
    body = "\n".join(lines)
    assert "[!]" in lines[0], "尾へ運ぶ印（`[!]`）が行頭にありません（`flagged()` が拾えません）"
    assert "腕の天井を全部" in body
    r = eta.residual_gap(a)
    if not r["reaches"]:
        # **2つの定数を必ず名指しすること**（(イ) の本文）
        assert "`per_video` の天井" in body
        assert "RPM_SCENARIOS" in body
        assert f"{r['per_video_needed']:,.0f}回/本" in body


def test_届かない回は本文に残りの倍率が並んでいる(eta, a):
    """**`report()` から外れたら落とす。** 印字は本文と尾の両方に出ること。"""
    m = eta._points()[-1]
    said = eta.report(m, a)
    reaches = any(a["ceiling"][k] >= eta.TARGET_YEN for k in eta.RPM_SCENARIOS)
    if reaches:
        pytest.skip("上限で届く帯があるので、この行は出ません")
    assert any("腕の天井を全部" in s for s in said), (
        "「どの帯でも届きません」の隣に、天井を全部 引いたあとの残りが出ていません"
    )
