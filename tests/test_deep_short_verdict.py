"""**門と、判定の手順が、同じ母集団を数えていること**（2026-08-29 06:3x）。

2026-08-29 04:0x、`scripts/deadline_check.py` は

    [OK] 08-29  深い題（…）をショートとして出すと、1本あたり再生が …
           要 8 ／ いま **15** → 足りています
           要 3 ／ いま **3** → 足りています
           → 判定できるのは 08-29。**期限とちょうど同じ**です

と出し、`scripts/drift.py` は

    [!] **外れています。** いま判定できる前提の期限が来ているのに、
        直近20回で1件も判定していません。

と鳴っていました。**ところが `falsified_if` の手順をそのまま解くと、
判定できません** —— 処置 **4本**（要 8本）／使える日 **2日**（要 3日）。

門が落としていたのは、`falsified_if` が明記している3つです:

    1. その日の**生きた帯**の中だけ（`day_cap.live_ids`。帯の外は0再生）
    2. **齢48時間 の読み**が在ること（`data/views.jsonl`）
    3. その公開日に**処置と対照が両方 居る**こと

**門は「作った／公開した」を、手順は「比べられる」を数えていました。**
そのまま進めば、この前提は**判定できない標本で閉じられます** ——
同じ台帳の `falsified_if` が、2026-08-26 に**符号が反転する割り方**で
一度 測られた記録を持っています。

`src/deep_short.py` に寄せて、**門の `count_expr` が判定と同じ関数を呼ぶ**
ようにしました。ここはそれが離れないようにする門です。
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src import deep_short as D  # noqa: E402


def _claim() -> dict:
    doc = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    for h in doc["hypotheses"]:
        if str(h.get("claim", "")).startswith("深い題"):
            return h
    raise AssertionError("「深い題」の前提が台帳から消えています")


def test_門の_count_expr_が判定と同じ関数を呼ぶこと():
    """**2か所が別々に同じ問いを解かないこと**（`_ans_group_key` と同じ合流）。"""
    exprs = [str(n.get("count_expr") or "") for n in _claim().get("needs") or []
             if isinstance(n, dict)]
    joined = " ".join(exprs)
    assert "deep_short_arm" in joined, (
        "**群の本数を、`uploaded` の数え上げに戻しています。**"
        " `falsified_if` の群は「生きた帯 ＋ 齢48時間 ＋ ショート分類」です"
        f": {exprs}")
    assert "deep_short_usable_days" in joined, (
        "**使える日を `deep_short_days()` に戻しています。**"
        " あれは分類だけを見ていて、生きた帯と齢48時間 を落とします"
        f": {exprs}")


def test_門が読む数と_判定が読む数が一致すること():
    """`deadline_check` の名前空間から呼んでも、同じ数が返ること。"""
    import deadline_check as J

    m = D.measure()
    assert J.EXPR_NS["deep_short_arm"]("処置") == m["n_treat"]
    assert J.EXPR_NS["deep_short_arm"]("対照") == m["n_ctrl"]
    assert J.EXPR_NS["deep_short_usable_days"]() == m["days"]


def test_古い数え方より厳しい側に居ること():
    """**`deep_short_days()` は、使える日を必ず同数か多めに数えます。**

    落ちたら、条件を1つ落としたのに数が減っています ＝ どちらかの実装が
    別のものを数えています。
    """
    import deadline_check as J

    assert J.deep_short_days() >= D.usable_days(), (
        "**古い数え方のほうが少ない**"
        f": days={J.deep_short_days()} usable={D.usable_days()}")


def test_床を満たさないうちは判定を返さないこと():
    """**「まだ分からない」で閉じないこと**（`falsified_if` の原文）。"""
    m = D.measure()
    if m["n_treat"] < D.MIN_PER_ARM or m["days"] < D.MIN_DAYS:
        assert m["verdict"] is None, (
            "**床を満たしていないのに判定を返しています**: "
            f"処置 {m['n_treat']}／日 {m['days']}／verdict {m['verdict']}")
        assert m["blocked"], "止めた理由を返していません"


def test_合格点と床を_falsified_if_から動かしていないこと():
    """定数が散文とずれたら、そこで台帳と道具の答えが割れます。"""
    body = str(_claim().get("falsified_if") or "")
    assert "1.2倍" in body and D.BAR == 1.2, body[:200]
    assert "8本" in body and D.MIN_PER_ARM == 8, body[:200]
    assert "3日" in body and D.MIN_DAYS == 3, body[:200]
    assert "48時間" in body and D.AGE_H == 48.0, body[:200]
