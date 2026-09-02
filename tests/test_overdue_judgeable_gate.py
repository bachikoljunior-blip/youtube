"""**期限が来ていて、いま閉じられる前提が在る回は、`fix` / `means` を通さない。**

2026-09-02（最適化の回）に足した門の検査です。**この検査を消さないと戻せません。**

## この門が立った理由（**その回に自分で撃った数**）

    data/eta.jsonl  reflect 614行（08/20〜） …… days_to_target が
                    **610行 到達不能のまま**／残り 4行 は 156.9日 → 到達不能
                    ＝ **1度も近づいていない**
    data/runs.jsonl ship 306件 …… fix **223件（73%）** ／ verdict **21件（6.9%）**
                    `lever_hint` に従った回 **72件（23.5%）**

`scripts/eta.py` は毎回「**軌跡の腕が動くのは前提を1件 閉じたときだけ**」と
印字しています。既に在った `FIX_RUN_CAP`（`fix` は2連まで）は**順番の門**で、
`premise` や `upload` で満たせるため、**閉じられる前提が置き去りになる形**は
塞いでいませんでした（実測 09/02: 12:05 に立った `kind: now` の前提が、
その後の ship 4件 を挟んで期限日の夕方まで開いたまま）。

**発火を確かめること**（`docs/GOAL.md`「発火したことのない検査は検査ではない」）。
"""
from __future__ import annotations

import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import deadline_check as dc  # noqa: E402


def _item(claim: str, deadline: str) -> dict:
    return {
        "claim": claim,
        "opened_on": "2026-09-01",
        "deadline": deadline,
        "lever": "per_video",
        "needs": [{"kind": "now", "what": "手元だけ", "data_file": "data/views.jsonl"}],
        "falsified_if": "x",
    }


def test_期限が来て手元で閉じられる前提を拾う():
    """**故障の注入**: 期限=今日・`kind: now` の前提は、必ずここに出ること。"""
    on = datetime.date(2026, 9, 2)
    got = dc.overdue_judgeable([_item("A", "2026-09-02")], as_of=on)
    assert [c for c, _ in got] == ["A"], got


def test_閉じた前提と先の期限は拾わない():
    """**通す側が既定です。** ここが空でないと、直しが全部止まります。"""
    on = datetime.date(2026, 9, 2)
    closed = _item("B", "2026-09-02")
    closed["closed_on"] = "2026-09-02"
    assert dc.overdue_judgeable([closed], as_of=on) == []
    assert dc.overdue_judgeable([_item("C", "2026-09-30")], as_of=on) == []


def test_読めなければ断らない():
    """「読めない」と「無い」は別（`levers.blocked()` と同じ約束）。"""
    assert dc.overdue_judgeable([{"claim": "D", "deadline": "こわれた日付"}]) == []


def test_run_marker_の門が_fix_と_means_だけを断る():
    """**門は `ship()` の中に在り、`upload` / `improve` を素通しにすること。**

    オーナー固定その2 の規則1（1日1本）・規則3（次の1本を改善し続ける）を
    止める門にしないこと。文言ではなく、**実際の分岐**を読みます。
    """
    src = (ROOT / "scripts" / "run_marker.py").read_text(encoding="utf-8")
    assert 'if rec["ship_kind"] in ("fix", "means"):' in src, \
        "門の分岐が無い（種別を見ずに断る／断らない形になっていないか）"
    assert "_overdue_judgeable()" in src, "門が台帳を読んでいない"
    # **upload / improve を条件に入れないこと**（入れた瞬間に公開が止まりうる）
    tail = src.split('if rec["ship_kind"] in ("fix", "means"):')[1][:400]
    assert '"upload"' not in tail


def test_門の理由が_repo_の中の数で書かれていること():
    """**書き置かれた結論ではなく、撃って出た数**が根拠として残っていること。"""
    doc = dc.overdue_judgeable.__doc__ or ""
    for token in ("614", "610", "306", "223", "21"):
        assert token in doc, f"{token} が根拠から消えている"
