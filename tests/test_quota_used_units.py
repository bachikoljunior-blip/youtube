"""`quota_ledger.used_units()` —— 枠の残りを刷る口は「通った行だけ」を読む（2026-09-03）。

実測 09/03 06:4x の窓: `spent()["data"]` 15,688 対 `["data_ok"]` 12,881。
7か所が高いほうで「枠が尽きています（15,675 / 10,000）」と刷っていた。
"""
from __future__ import annotations

import pathlib
import re

from src import quota_ledger


def _rows(*items):
    return [dict(api="data", method="videos.update", units=u, ok=ok, by="t") for u, ok in items]


def test_used_units_counts_only_ok_rows(monkeypatch):
    monkeypatch.setattr(quota_ledger, "rows", lambda now=None: _rows((9_000, True), (1_500, False)))
    s = quota_ledger.spent()
    assert s["data"] == 10_500 and s["data_ok"] == 9_000
    assert quota_ledger.used_units() == 9_000          # 弾かれた 1,500 は枠を使っていない


def test_used_units_falls_back_when_spent_is_patched(monkeypatch):
    monkeypatch.setattr(quota_ledger, "spent", lambda now=None: {"data": 4_321})
    assert quota_ledger.used_units() == 4_321


def test_no_reader_uses_the_gross_figure():
    """`spent(...)["data"]` で枠を判定する口を、もう1つも作らないこと。"""
    root = pathlib.Path(__file__).resolve().parents[1]
    pat = re.compile(r'spent\([^)]*\)\.get\("data"\)|spent\([^)]*\)\["data"\]')
    hits = []
    for d in ("src", "scripts"):
        for f in (root / d).glob("*.py"):
            if f.name == "quota_ledger.py":
                continue
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.lstrip().startswith("#"):        # 註（`upload_cap` 945行）は口ではない
                    continue
                if pat.search(line):
                    hits.append(str(f.relative_to(root)))
                    break
    assert hits == [], f"`quota_ledger.used_units()` を読むこと: {hits}"
