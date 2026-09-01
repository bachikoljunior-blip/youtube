"""**燃料の残量を、生きている腕のぶんだけで数えること。**（2026-09-01 夕・最適化の回）

## なぜ要るか

`deadline_check.ledger_drain()` は、開いた前提を**全部 燃料として数えます。**
**その全部が燃料ではありません。**

`src/levers.lever_notes()` は、`--ship` が**宣言した腕**が「無限大にしても 0日」
だったときにこう叱ります —— **「ここが黙ると、次の回は『天井を上げる前提を1件
立てよう』に向かい、無限大でも 0日 の腕について、閉じても日付が動かない前提を
積みます」**。**その叱りは、出す瞬間の1件にしか掛かっていませんでした。**
**積み上がった台帳のほうは、誰も見ていません。**

実測（2026-09-01 12:4x・`dead_ledger()` を書いた回に数えた。開いている 23件）:

    sub_rate 6件（`arm_dead_at_inf`）／ density 2件（規則）／ none 2件
    → **10/23（43%）が、どう閉じても到達日を1日も動かさない**

**この数はここに写しません**（写した瞬間に古びます）。検査するのは**規則**のほう。
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import deadline_check as dc                        # noqa: E402
from src import levers                             # noqa: E402

AS_OF = date(2026, 9, 1)

# **本番と同じ形の腕の状態**（`levers.arm_state()` が返す鍵だけ）。
STATE = {
    "caps": {"per_video": 4.16, "sub_rate": 6.64, "rpm": 36.7, "density": 1.0},
    "dead_at_inf": ("sub_rate",),
    "dead_why": {"density": levers.RULE_DEAD + "（オーナーが固定した 1日1本）",
                 "per_video": "天井まで引いても届かない",
                 "sub_rate": "天井まで引いても届かない",
                 "rpm": "天井まで引いても届かない"},
    "hint": "per_video",
}

ITEMS = [
    {"claim": "登録の依頼", "lever": "sub_rate", "deadline": "2026-10-02"},
    {"claim": "ホームに紹介動画", "lever": "sub_rate", "deadline": "2026-09-09"},
    {"claim": "置く位置", "lever": "density", "deadline": "2026-10-07"},
    {"claim": "収益化の審査", "lever": "none", "deadline": "2026-09-30"},
    {"claim": "腕が空", "deadline": "2026-09-30"},
    {"claim": "題を問いの形に", "lever": "per_video", "deadline": "2026-09-22"},
    {"claim": "長尺の面", "lever": "rpm", "deadline": "2026-09-05"},
    {"claim": "閉じた1", "lever": "per_video", "closed_on": "2026-08-30"},
    {"claim": "閉じた2", "lever": "rpm", "closed_on": "2026-08-29"},
]


def _run(items=None, state=None):
    return "\n".join(dc.dead_ledger(items if items is not None else ITEMS,
                                    state=STATE if state is None else state,
                                    as_of=AS_OF, window=7))


def test_無限大でも0日の腕の前提は燃料から外れる():
    out = _run()
    # 開いている 7件 のうち sub_rate 2 ＋ density 1 ＋ none 2 ＝ 5件 が動かない
    assert "開いている **7件**" in out
    assert "**5件（71%）**" in out
    assert "燃料は **2件** です" in out
    assert "`sub_rate` **2件**" in out


def test_規則で死んだ腕は天井と同じ字で叱らない():
    """**「天井」は『測り直せば上がる』と読めます。規則はそうではありません。**"""
    out = _run()
    assert "天井ではなく規則で止まっています" in out
    assert "外せるのはオーナーだけです" in out
    assert "`density` **1件**" in out


def test_腕の付いていない前提は別に数える():
    """`lever:` が空か `none` は θ に入りませんが、**捨てるものでもありません。**"""
    out = _run()
    assert "腕が付いていません" in out
    assert "`none` **2件**" in out
    assert "捨てないこと" in out


def test_空になる日を生きた燃料だけで引き直す():
    """`ledger_drain()` の日付より**必ず手前**になること。"""
    out = _run()
    all_out = "\n".join(dc.ledger_drain(ITEMS, as_of=AS_OF, window=7))
    assert "空になるのは 2026-09-25" in all_out      # 7 ÷ (2/7) = 24日
    assert "2026-09-08" in out                       # 2 ÷ (2/7) = 7日
    assert "**17日 早い**" in out


def test_読めない回は死んだ前提が無いとは言わない():
    """**`levers.arm_state` と同じ約束。**「読めない」と「無い」は別。"""
    out = _run(state={})
    assert "読めない" in out
    assert "燃料は" not in out
    assert "件（" not in out


def test_燃料が0件なら前提を立てろと言う():
    items = [{"claim": "a", "lever": "sub_rate", "deadline": "2026-10-02"},
             {"claim": "x", "lever": "per_video", "closed_on": "2026-08-30"}]
    out = _run(items=items)
    assert "燃料は 0件 です" in out
    assert "`premise` を立てること" in out


def test_故障を注入すると落ちる():
    """**発火したことのない検査は検査ではない。**

    `dead_at_inf` を空にする（＝ `eta.py` が ×10^9 を撃たなくなった版に戻る）と、
    `sub_rate` の2件は**燃料として数えられます。** そのとき残量は 1.5倍 に見えます。
    """
    broken = {**STATE, "dead_at_inf": ()}
    out = _run(state=broken)
    assert "燃料は **4件** です" in out              # sub_rate 2件 が戻ってくる
    assert "無限大にしても 0日" not in out
    assert "`sub_rate` **2件**" not in out
    # **生きている腕としては出ます。** そこが「読めない」と「無い」の境目です。
    assert "生きている腕: `per_video` / `rpm` / `sub_rate`" in out
