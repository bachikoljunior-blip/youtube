"""**実験の「側」の札が、黙って消えないこと。**

## なぜ要るか（2026-08-29・最適化の回に足した）

`src/arm_speed.sides()` は、閉じた前提を **配信の側 / 中身の側** で割って
「次の1件をどちらに立てるか」を出します。実測 2026-08-29 で
**配信の側は中身の側の 13.9倍**（`p·log(g)` 比）でした。

この検査が守るのは3つだけです。**数そのものは固定しません**
（台帳が増えれば動くのが正しい）:

1. **腕の付いた閉じた前提に、`side:` の空欄が無いこと**
   —— 空欄は `sides()` の分母から**黙って**落ちます。落ちた件は
   `missing` に出ますが、**誰も読まない所に出しても意味がありません**
2. **`side` が既定の3語のどれかであること** —— 綴りちがいは
   `SIDES` に入らないので、やはり黙って落ちます
3. **この数が到達日の入力に入っていないこと** —— 1/11 対 3/8 は
   フィッシャー p≈0.13 で有意ではありません。`trajectory()` の
   引数にも `arm()` の返りにも `side` が現れないこと。
   **有意でない標本で日付を動かさない**のが、このリポジトリの規則です

## 覆る条件

- **どちらかの側が n=20 に届いたら** 3 は引き直してよい
  （`sides()` の docstring「覆る条件」）。そのときはこの検査も書き換えること
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import arm_speed  # noqa: E402


def _doc() -> dict:
    return yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text())


def test_closed_armed_rows_all_carry_a_side() -> None:
    """閉じていて腕の付いた前提は、全部 `side:` を持っていること。"""
    sd = arm_speed.sides()
    assert sd["missing"] == 0, (
        f"閉じた前提 {sd['missing']}件 に `side:` がありません。"
        " その件は配信/中身の比から黙って消えます"
        "（`config/hypotheses.yaml` の `side` の節）"
    )


def test_open_rows_all_carry_a_side() -> None:
    """開いている前提も全部 `side:` を持っていること（**枠の内訳がそこから出ます**）。"""
    sd = arm_speed.sides()
    assert sd["open_unlabelled"] == 0, (
        f"開いている前提 {sd['open_unlabelled']}件 に `side:` がありません。"
        " 「いま開いているのは 配信N件 ／ 中身N件」がその件数ぶん嘘になります"
    )


def test_side_values_are_from_the_fixed_set() -> None:
    """綴りちがいは黙って落ちるので、既定の3語に閉じること。"""
    doc = _doc()
    bad = []
    for key in ("hypotheses", "confirmed"):
        for h in doc.get(key) or []:
            if not isinstance(h, dict):
                continue
            s = h.get("side")
            if s is not None and s not in arm_speed.SIDES:
                bad.append((str(h.get("claim"))[:40], s))
    assert not bad, f"`side` が {arm_speed.SIDES} 以外: {bad}"


def test_sides_does_not_feed_the_target_date() -> None:
    """**この札で到達日を動かさないこと**（有意ではないため）。

    `arm()` の返りに `side` が現れたら、側べつの `p`/`g` が
    軌跡へ流れ込んでいる疑いがあります。そのときは
    `sides()` の「覆る条件」を先に満たしたかを確かめること。
    """
    a = arm_speed.arm("per_video")
    assert "side" not in a, (
        "`arm()` が `side` を返しています —— 側べつの p/g が軌跡に入ると、"
        " n=8 と n=11 の標本で到達日が動きます"
    )
    src = (ROOT / "scripts" / "eta.py").read_text()
    assert "sides()" in src, "`eta.py` が `sides()` を1度も呼んでいません（印字が消えています）"


def test_every_running_ab_carries_a_side() -> None:
    """**走っている A/B にも札があること。**

    台帳の枠より、A/B の枠のほうが希少です（4件が同じ本の流れに同時に乗る）。
    札が無い実験は「配信 0件」の数え上げから**黙って消えます** ——
    そのとき「速いほうの枠が空いていない」という所見が、
    見た目だけ解消します。
    """
    from src import ab_split  # noqa: PLC0415

    bad = [n for n, e in ab_split.EXPERIMENTS.items()
           if e.side not in arm_speed.SIDES]
    assert not bad, f"`side` の無い A/B: {bad}（`src/ab_split.EXPERIMENTS`）"
    assert sum(ab_split.side_counts().values()) == len(ab_split.EXPERIMENTS)


def test_side_lines_name_both_sides_and_the_open_counts() -> None:
    """印字が「比」と「いま開いている件数」の両方を持つこと。

    **片方だけでは決められません** —— 比だけなら「で、いま何件そっちに
    乗っているのか」が分からず、件数だけなら「それが速いのか」が分かりません。
    """
    lines = arm_speed.side_lines()
    text = "".join(lines)
    assert "配信の側" in text and "中身の側" in text
    assert "いま開いているのは" in text
    assert "日付は動かしていません" in text
