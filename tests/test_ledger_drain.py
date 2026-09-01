"""**台帳の残量を、毎周 数で出すこと。**（2026-09-01・最適化の回）

## なぜ要るか

`scripts/eta.py` は毎周こう印字します ——
**「軌跡の腕が動くのは、`config/hypotheses.yaml` の前提を1件 閉じたときだけ。
作る・出す・直すは、軌跡の入力に入りません」。**
**台帳は、到達日を動かす唯一の燃料です。** その残量を、どの道具も出していませんでした。

実測（2026-09-01・git から数えた。**この数はここに写しません** ——
写した瞬間に古びます。**毎周その場で数えるほうが `ledger_drain()` です**）:

    08/20 → 08/29   claim 28 → 52件（+2.7件/日）／ 開いている 17 → 32件
    08/29 → 09/01   claim 52 → 53件（**+0.33件/日**）／ 開いている 32 → **21件**

**立てるほうが 8分の1 に落ち、閉じるほうは 2.7件/日 のまま。**
差し引き −2.3件/日 で、開いている 21件 は 9日 で尽きます。
**尽きた回は `verdict` を選べません**（§4 の5択のうち、到達日を動かす唯一の手）。
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import deadline_check as dc                        # noqa: E402

AS_OF = date(2026, 9, 1)


def test_残量と空になる日を出す():
    items = [{"claim": "a"}, {"claim": "b"}, {"claim": "c"}, {"claim": "d"},
             {"claim": "x", "closed_on": "2026-08-30"},
             {"claim": "y", "closed_on": "2026-08-29"}]
    out = "\n".join(dc.ledger_drain(items, as_of=AS_OF, window=7))
    assert "開いている 4件" in out
    assert "直近7日に閉じた **2件**" in out
    assert "0.29件/日" in out                       # 2 / 7
    assert "空になるのは 2026-09-15" in out          # 4 / 0.2857 = 14日
    assert "あと 14日" in out


def test_1件も閉じていない窓では日付を作らない():
    """**割れないものを、推測で割らないこと。**"""
    items = [{"claim": "a"}, {"claim": "b"},
             {"claim": "z", "closed_on": "2026-07-01"}]   # 窓の外
    out = "\n".join(dc.ledger_drain(items, as_of=AS_OF, window=7))
    assert "1件も閉じていません" in out
    assert "空になるのは" not in out


def test_立てた速さは台帳から数えられないと言う():
    """`opened_on:` が無いことを、**黙って推測で埋めない**。"""
    items = [{"claim": "a"}, {"claim": "x", "closed_on": "2026-08-30"}]
    out = "\n".join(dc.ledger_drain(items, as_of=AS_OF, window=7))
    assert "opened_on" in out


def test_実物の台帳でも出る():
    """**この道具が撃たれる先は実物です。**読めなくなったら、ここが落ちます。"""
    out = "\n".join(dc.ledger_drain(dc.load()))
    assert "台帳の残量" in out


def test_主実行が撃つ道にも出る():
    """**主実行が撃つのは `--fit` のほうです**（`docs/trigger_main.md` §2.6 の1行目）。

    引数なしの道にだけ置いた版は、**毎周の手順から1度も読まれませんでした。**
    `pool_drain` が「道具は在るのに撃つ側がどこにも書かれていない」で塞がれたのと
    同じ形の3件目です（2026-09-01 に踏んだ）。

    **覆る条件**: §2.6 が `--fit` を撃たなくなったら、この検査は別の道を見ること。
    """
    src = (ROOT / "scripts" / "deadline_check.py").read_text(encoding="utf-8")
    i = src.index("if a.shrink or a.extend or a.fit:")
    j = src.index("if a.gate:", i)
    assert "ledger_drain(" in src[i:j], (
        "`--fit` の道に台帳の残量が出ていません。"
        "**主実行が撃つのはこの道です** —— 引数なしの道にだけ置くと、"
        "毎周の手順からは1度も読まれません")
    assert "deadline_check.py --fit" in (
        ROOT / "docs" / "trigger_main.md").read_text(encoding="utf-8"), (
        "§2.6 が `--fit` を撃たなくなりました。この検査の当てどころを直すこと")
