"""`run_marker.py --claim` —— **いま取りかかっているものを、他の回に見せる。**

## なぜ要るか（2026-08-26 21:xx、この回が 30分 払った）

サブ `agent-a323162c3542b8640` は `scripts/drift.py` を 30分 かけて直し、
push の直前に **きょうだいが同じ 20分間に同じ所を直していた**ことを知りました
（merge conflict）。あちらのほうが広かったので、**こちらのぶんを捨てています。**

**`git fetch` では防げません。** 着手前に fetch は撃っていて、
そのとき向こうはまだ push していませんでした。**同時に走っています。**

そして当たるべくして当たっています —— `retro.py` の持ち越し1位と
`status.py` の「[!] 外れています」は**どの回にも同じ形で見えている**ので、
**上位の1件は複数の回が同時に取りにいきます。**
直近7日の周は 115、ship は 305件。**重なりは事故ではなく既定の状態です。**

読む場所を `--write`（§1・**その回のいちばん最初のコマンド**）にしたのは、
**何をやるか決める前**でないと払った時間が戻らないからです。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import run_marker as rm  # noqa: E402


def _seed(tmp_path, monkeypatch, rows):
    p = tmp_path / "runs.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                 encoding="utf-8")
    monkeypatch.setattr(rm, "MARKS", p)
    return p


def _row(minutes_ago: int, session: str, what: str) -> dict:
    at = datetime.now(rm.JST) - timedelta(minutes=minutes_ago)
    return {"at": at.isoformat(timespec="seconds"), "session": session,
            "kind": rm.CLAIM_KIND, "what": what}


def test_他の回の直近の取りかかりを返す(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch, [
        _row(5, "session_X#agent-b", "drift.py の期限まわり"),
        _row(5, "session_X#agent-me", "こちらのぶん"),
    ])
    got = rm.claims(me="session_X#agent-me")
    assert [r["what"] for r in got] == ["drift.py の期限まわり"]


def test_窓の外は落とす(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch, [
        _row(5, "session_X#agent-b", "新しい"),
        _row(999, "session_X#agent-c", "古い"),
    ])
    got = rm.claims(me="session_X#agent-me")
    assert [r["what"] for r in got] == ["新しい"]


def test_自分のぶんは出さない(tmp_path, monkeypatch):
    """**自分の印を自分に見せても、何も避けられません。**"""
    _seed(tmp_path, monkeypatch, [_row(1, "session_X#agent-me", "こちらのぶん")])
    assert rm.claims(me="session_X#agent-me") == []


def test_ship_や_start_は拾わない(tmp_path, monkeypatch):
    """**種別で絞ること。** `runs.jsonl` は4種類が同居しています。"""
    at = datetime.now(rm.JST).isoformat(timespec="seconds")
    _seed(tmp_path, monkeypatch, [
        {"at": at, "session": "session_X#agent-b", "kind": "start"},
        {"at": at, "session": "session_X#agent-b", "kind": "ship",
         "what": "fix: 何か", "lever": "none", "moves": 0},
        _row(1, "session_X#agent-b", "取りかかり"),
    ])
    got = rm.claims(me="session_X#agent-me")
    assert [r["what"] for r in got] == ["取りかかり"]


def test_write_が他の回の取りかかりを印字する(tmp_path, monkeypatch, capsys):
    """**§1（この回のいちばん最初のコマンド）で見えること。**

    決めた後に見せても、払った時間は戻りません。
    """
    _seed(tmp_path, monkeypatch, [_row(3, "session_X#agent-b", "drift.py の期限まわり")])
    monkeypatch.setattr(rm, "actor_id", lambda: "session_X#agent-me")
    monkeypatch.setattr(rm, "is_parent", lambda: False)
    rm.write()
    out = capsys.readouterr().out
    assert "走った印を付けました" in out
    assert "drift.py の期限まわり" in out
    assert "予約ではありません" in out


def test_取りかかりが無い回は何も足さない(tmp_path, monkeypatch, capsys):
    """**空の見出しを出さないこと。**（毎周1行ずつ増えると、頭3行が押し出されます）"""
    _seed(tmp_path, monkeypatch, [])
    monkeypatch.setattr(rm, "actor_id", lambda: "session_X#agent-me")
    monkeypatch.setattr(rm, "is_parent", lambda: False)
    rm.write()
    out = capsys.readouterr().out
    assert "取りかかると書いたもの" not in out


def test_claim_は行を1つ足す(tmp_path, monkeypatch):
    p = _seed(tmp_path, monkeypatch, [])
    monkeypatch.setattr(rm, "actor_id", lambda: "session_X#agent-me")
    monkeypatch.setattr(rm, "is_parent", lambda: False)
    assert rm.claim("これから触るところ") == 0
    rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert rows[-1]["kind"] == rm.CLAIM_KIND
    assert rows[-1]["what"] == "これから触るところ"


def test_中身の無い_claim_は断る(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch, [])
    assert rm.claim("   ") == 2
