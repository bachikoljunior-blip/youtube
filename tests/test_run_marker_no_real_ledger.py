"""**検査を撃つだけで、本物の `data/runs.jsonl` に行が入らないこと**
（2026-09-09 09:5x JST・optimizer・Opus）。

実測（この日）: `python -m pytest tests/test_premise_ledger_gate.py` を撃つだけで、
本物の控えに **6行**（`kind="verdict_gate"`）入った。

**守りは在ったのに、届いていませんでした。** `tests/conftest.py` の
`_alerts_ledger_to_tmp` は `import scripts.run_marker as _rm` として `_rm.MARKS` を
tmp へ向けます（2026-09-05 06:5x に、まさにこの穴を塞ぐために足された段落）。
ところが `tests/test_premise_ledger_gate.py` と `tests/test_kinds_allowed.py` は
`sys.path` に `scripts/` を足して **`import run_marker`（裸）**で読みます。
Python はこれを**別のモジュール**として持つので（撃って確かめた:
`scripts.run_marker is run_marker` → **False**・`MARKS` は 2つ とも本物を向く）、
**conftest が差し替えるのは 2つ のうち 1つ だけ**でした。

    conftest が向けた    scripts.run_marker.MARKS  → tmp
    検査が使っていた      run_marker.MARKS          → **本物**

これは 09/09 00:1x の「死んだ当て先を monkeypatch していた 4件」と同じ族で、
**当て先が生きているか死んでいるかではなく、当て先が 2つ あった**形。
`_ship_stub` が `ship`・`premise_opened_today`・`note_premise_gate` の 3つを
差し替えて「この検査は控えに書きません」と註を付けていたのも同じ理由で外れます
——`main()` はそのあと足された **4つ目の `note_verdict_gate()`** も撃つ。

→ 守りを**呼ぶ側から、書く側へ**移しました（`run_marker._marks_blocked()`）。
モジュールが何個 在っても、どの検査が何を差し替え忘れても、
**書く直前に「いま向いている先が本物か」を見る**ので漏れません
（`scripts/next_round.log_wake()` の門と同じ形・同じ理由。§8 06:5x の続き）。

**この見張りは、必ず裸の `import run_marker` で撃つこと** ——
`scripts.run_marker` で撃つと conftest が tmp へ向けてしまい、
**門を外しても通ってしまいます**（この検査を書いた回に、実際に1度そうなった。
陽性対照が通ってしまい、門ではなく conftest が守っていたことに気づいた）。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import run_marker as rm  # noqa: E402  ← **裸で読む。ここが漏れていた当て先**


def _sites():
    return [
        ("_append", lambda: rm._append(
            {"at": "2026-09-09T00:00:00+09:00", "kind": "ship", "what": "検査"})),
        ("note_premise_gate", lambda: rm.note_premise_gate("検査", 1.0)),
        ("note_verdict_gate", lambda: rm.note_verdict_gate("検査", 1)),
        ("note_fix_gate", lambda: rm.note_fix_gate("検査", 1)),
    ]


def test_conftestが差し替えたのは別のモジュールだった_これが踏んだ形():
    """**陽性対照の土台** —— 2つ在ることと、裸のほうが本物を向いていることを見せる。"""
    import scripts.run_marker as scoped
    assert scoped is not rm, "1つになったなら、この検査ごと外してよい"
    assert rm.MARKS == rm._MARKS_REAL, "裸の側は conftest に差し替えられていない"


@pytest.mark.parametrize("name,call", _sites(), ids=[n for n, _ in _sites()])
def test_本物の控えは1バイトも動かない(name, call):
    real = rm._MARKS_REAL
    before = real.read_bytes() if real.exists() else None
    call()
    after = real.read_bytes() if real.exists() else None
    assert after == before, f"{name} が本物の {real} に書いた"


def test_差し替えた検査は書いてよい(tmp_path, monkeypatch):
    """ここを止めると、控えを読む検査そのものが書けなくなる。"""
    p = tmp_path / "runs.jsonl"
    monkeypatch.setattr(rm, "MARKS", p)
    rm.note_verdict_gate("検査", 1)
    assert p.exists() and "verdict_gate" in p.read_text(encoding="utf-8")
