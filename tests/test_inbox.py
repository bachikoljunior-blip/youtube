"""受け取り帳（`src/inbox.py`）——**運ばれてきた依頼を、着いた瞬間に残す**。

## なぜ要るか（2026-08-16）

同じ直しが**3回**運ばれ、**2回は作業中の死で落ちました**（push 前に停止）。
落ちた依頼を次に届ける経路は「**親が覚えていること**」しかなく、
親は文脈が要約されるので覚えていられません。**リポジトリ側に残す必要があります。**

`retro.py` の持ち越しでは拾えません。あちらは**日誌の散文**を読むので、
**日誌を1行も書かずに死んだ回は、最初から一覧に入りません**
（`src/alerts.py` の「一覧が当たりを含まないまま育つ」と同じ形）。

## 押さえているもの

- 同じ本文は**同じ ID に積む**（＝何回運ばれたかが機械の側から言える）
- **閉じたものが再び来たら開き直す**（直っていない証拠を消さない）
- 閉じるまで `open_items()` に残る ＝ **作業の成否と独立**
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import inbox  # noqa: E402


def _ledger(tmp_path: Path) -> Path:
    return tmp_path / "inbox.jsonl"


def test_same_text_counts_deliveries(tmp_path, monkeypatch):
    p = _ledger(tmp_path)
    monkeypatch.setattr(inbox, "LEDGER", p)
    for _ in range(3):
        inbox.add("親の Stop フックを黙らせること")
    items = inbox.items(p)
    assert len(items) == 1
    assert items[0]["deliveries"] == 3
    assert "×3回運ばれた" in inbox.render(p)


def test_open_survives_until_closed(tmp_path, monkeypatch):
    p = _ledger(tmp_path)
    monkeypatch.setattr(inbox, "LEDGER", p)
    rec = inbox.add("`—` をやめる")
    assert [it["id"] for it in inbox.open_items(p)] == [rec["id"]]
    inbox.close(rec["id"][:4], "最小の1文字に置き換えた", path=p)
    assert inbox.open_items(p) == []
    assert "開いているものはありません" in inbox.render(p)


def test_closed_item_reopens_when_delivered_again(tmp_path, monkeypatch):
    """**閉じたはずのものがまた来るのは「直っていない」ことの証拠。**"""
    p = _ledger(tmp_path)
    monkeypatch.setattr(inbox, "LEDGER", p)
    rec = inbox.add("同じ直し")
    inbox.close(rec["id"], "直したつもり", path=p)
    inbox.add("同じ直し")
    opened = inbox.open_items(p)
    assert len(opened) == 1
    assert opened[0]["reopened"] is True
    assert "一度閉じたのに再び来た" in inbox.render(p)


def test_id_ignores_whitespace_only_differences(tmp_path, monkeypatch):
    p = _ledger(tmp_path)
    monkeypatch.setattr(inbox, "LEDGER", p)
    a = inbox.add("親を  黙らせる")
    b = inbox.add("親を 黙らせる\n")
    assert a["id"] == b["id"]


def test_close_unknown_id_raises(tmp_path, monkeypatch):
    p = _ledger(tmp_path)
    monkeypatch.setattr(inbox, "LEDGER", p)
    inbox.add("何か")
    try:
        inbox.close("ffffffff", "", path=p)
    except KeyError:
        return
    raise AssertionError("開いていない ID を閉じられてしまった")
