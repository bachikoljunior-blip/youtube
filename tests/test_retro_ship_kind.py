"""**`retro.py` の「出したもの」は、帳面の `ship_kind` で数える。散文の頭の語ではない。**

## なぜ要るか（2026-09-01 09:2x に踏んだ）

`data/runs.jsonl` の `ship_kind` は、**2026-08-26 にこの問題のために足された欄**です
（散文の頭の語では読めなかった実測: ship 381件 のうち **155件（41%）が「その他」**）。
**`retro.ship_summary()` だけが、その欄を無視して散文へ戻っていました。**

実測（この回の直近8件）:

    帳面（`ship_kind`）   fix **7** ／ improve 1        ＝ fix **87.5%**
    直す前の印字          fix 6（75%）／ improve 1 ／ **`eta` 1**

**`eta` は5つの種別のどれでもありません。** 散文が「eta: 天井を作る min() が…」で
始まっていただけで、その行の `ship_kind` は `fix` です。
**無い種別を1つ作り、`fix` の比を 12.5ポイント 低く出していました**
（前の回は `fix(手順)` という別の幻も出しています）。

**見た目の問題ではありません。** すぐ下の「**〜 に偏っています**」はこの数から出て、
**その1行が、その回に何を出すかを決めています。** 比が低く出れば警告は遅れます。

## 覆る条件

- 種別が増えたら `run_marker.SHIP_KINDS` に足すこと。**あちらが正本**で、
  下の1件目が2つの一致を見ています
- `run_marker` が `ship_kind` を書かなくなったら、落とし口（散文）だけが残ります
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import retro  # noqa: E402
import run_marker  # noqa: E402


def test_種別の一覧がrun_markerと同じ() -> None:
    """**正本は `run_marker.SHIP_KINDS`。** 写しがずれたら、幻の種別がまた出ます。"""
    assert tuple(sorted(retro.SHIP_KINDS)) == tuple(sorted(run_marker.SHIP_KINDS))


def _write(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "runs.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                 encoding="utf-8")
    return p


def test_散文の頭の語ではなくship_kindを数える(tmp_path, monkeypatch) -> None:
    """**この回が実際に踏んだ形**（`what` は `eta:` で始まり、`ship_kind` は `fix`）。"""
    rows = [
        {"at": "2026-09-01T09:10:00+09:00", "kind": "ship",
         "ship_kind": "fix", "what": "eta: 天井を作る min() が…"},
        {"at": "2026-09-01T09:05:00+09:00", "kind": "ship",
         "ship_kind": "improve", "what": "improve: 次の1本の計算を厚くした"},
    ]
    monkeypatch.setattr(retro, "RUNS", _write(tmp_path, rows))
    kinds, _ = retro.ship_summary(8)
    assert kinds == Counter({"fix": 1, "improve": 1}), (
        f"散文の頭の語で数えています: {dict(kinds)}")
    assert "eta" not in kinds, "**幻の種別**が出ています"


def test_幻の種別を作らない(tmp_path, monkeypatch) -> None:
    """`fix(手順):` のような頭の語も、5つのどれかか「その他」にしか落ちない。"""
    rows = [
        {"at": "2026-09-01T00:00:00+09:00", "kind": "ship",
         "ship_kind": "fix(手順)", "what": "fix(手順): §6 を直した"},
        {"at": "2026-09-01T00:01:00+09:00", "kind": "ship",
         "what": "なにか: 頭の語が種別でない"},
    ]
    monkeypatch.setattr(retro, "RUNS", _write(tmp_path, rows))
    kinds, _ = retro.ship_summary(8)
    for k in kinds:
        assert k in retro.SHIP_KINDS or k == "その他", f"幻の種別: {k}"


def test_欄の無い古い行は_頭の語へ落ちる(tmp_path, monkeypatch) -> None:
    """**2026-08-26 より前の行**だけがここへ来ます（欄そのものが無い）。"""
    rows = [
        {"at": "2026-08-20T00:00:00+09:00", "kind": "ship",
         "what": "verdict: M9 を実データで判定した"},
        {"at": "2026-08-20T00:01:00+09:00", "kind": "ship",
         "what": "長尺1本を 09/07 20:00 JST に予約"},
    ]
    monkeypatch.setattr(retro, "RUNS", _write(tmp_path, rows))
    kinds, _ = retro.ship_summary(8)
    assert kinds == Counter({"verdict": 1, "その他": 1})


def test_ship以外の行は数えない(tmp_path, monkeypatch) -> None:
    rows = [
        {"at": "2026-09-01T00:00:00+09:00", "kind": "run"},
        {"at": "2026-09-01T00:01:00+09:00", "kind": "fix_gate", "run_len": 9},
        {"at": "2026-09-01T00:02:00+09:00", "kind": "ship",
         "ship_kind": "fix", "what": "fix: 1件"},
    ]
    monkeypatch.setattr(retro, "RUNS", _write(tmp_path, rows))
    kinds, recent = retro.ship_summary(8)
    assert kinds == Counter({"fix": 1})
    assert len(recent) == 1
