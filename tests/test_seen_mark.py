"""**「見にいった。拾うものは無かった」を残せること。**（2026-08-18 に足した）

`sibling_check.silent_runs()` が名指しする回のうち、**中身がゼロだった側**
（`nosrc` で題名が既定のまま／`apifail` で1ターン目に死んだ回）には、
判定を残す場所がありませんでした。

黙らせる道は `data/inbox.jsonl` に本文ごと入れることだけで、
**中身ゼロの題名をそこへ落とすのは `docs/trigger_main.md` §0 が禁じています**
（空の依頼が1件ふえ、次の回がそれを閉じる仕事をするだけなので）。

結果、**判定済みの1件が 25件の窓から落ちるまで毎回鳴りました** ——
08/18 の 14:5x・17:0x・18:2x が、同じ `session_01CbJXLKu2La79BPj66zTyre` を
3回見にいっています。日誌には3回とも書いてあります。**機械が読まないだけです。**

**故障注入つき**（印を外すと鳴る側も見る。片側だけでは「効いている」と言えない）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import run_marker                                             # noqa: E402
import sibling_check                                          # noqa: E402


ME = "session_me"
NOW = "2026-08-18T09:18:25.000000Z"
SILENT = "session_silent"


def _sess(sid, born, *, status="SESSION_STATUS_ARCHIVED", tags=(sibling_check.TAG,)):
    return {"id": sid, "created_at": born, "session_status": status, "tags": list(tags)}


@pytest.fixture
def marks(tmp_path, monkeypatch):
    """`data/runs.jsonl` を差し替える。**実物を書き換えないこと。**"""
    path = tmp_path / "runs.jsonl"
    monkeypatch.setattr(run_marker, "MARKS", path)
    monkeypatch.setattr(run_marker, "PARENT_SESSIONS", {"session_parent"})
    monkeypatch.setenv("CLAUDE_SESSION_ID", ME)
    return path


@pytest.fixture
def sessions():
    return [
        _sess(ME, NOW, status="SESSION_STATUS_RUNNING"),
        _sess("session_ok", "2026-08-18T00:13:21.000000Z"),
        _sess(SILENT, "2026-08-18T04:11:50.000000Z"),
    ]


def _start(path, sid, at="2026-08-18T09:00:00+09:00"):
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": at, "session": sid, "kind": "start"},
                            ensure_ascii=False) + "\n")


def test_見にいった印を付けると名指しが止まる(marks, sessions):
    _start(marks, "session_ok")
    assert [s["id"] for s in sibling_check.silent_runs(sessions, ME)] == [SILENT], \
        "**印を付ける前から黙っています。**この検査は何も見ていません"

    assert run_marker.main(["--seen", SILENT, "--why", "題名が既定のまま＝中身ゼロ"]) == 0
    assert sibling_check.silent_runs(sessions, ME) == [], \
        "**見にいった印を付けても、まだ名指ししています**"


def test_故障注入_印を消すとまた鳴る(marks, sessions):
    """**当たりの側でだけ黙る**形になっていないか（両向き）。"""
    _start(marks, "session_ok")
    run_marker.main(["--seen", SILENT, "--why", "題名が既定のまま"])
    assert sibling_check.silent_runs(sessions, ME) == []

    rows = [json.loads(x) for x in marks.read_text(encoding="utf-8").splitlines() if x.strip()]
    rows = [r for r in rows if r.get("kind") != "seen"]
    marks.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                     encoding="utf-8")
    assert [s["id"] for s in sibling_check.silent_runs(sessions, ME)] == [SILENT], \
        "**印を消しても黙ったままです。**黙らせているのは印ではありません"


def test_黙らせるのは名指しだけで印の無い事実は消えない(marks, sessions):
    """`--seen` は `kind` が別なので、**走った印としては数えません。**

    ここを混ぜると「1周も走っていないのに走ったことになる」壊れ方をします。
    """
    _start(marks, "session_ok")
    run_marker.main(["--seen", SILENT, "--why", "中身ゼロ"])
    recs = run_marker._records()
    starts = {r.get("session") for r in recs if r.get("kind", "start") == "start"}
    assert SILENT not in starts, "**見にいった印が、走った印として数えられています**"
    assert any(r.get("kind") == "seen" and r.get("saw") == SILENT for r in recs)


def test_理由の無い印は受け付けない(marks, sessions):
    """**理由の書いていない黙らせ方は、次に来た側が判断できません。**"""
    _start(marks, "session_ok")
    assert run_marker.main(["--seen", SILENT, "--why", "   "]) == 2
    assert [s["id"] for s in sibling_check.silent_runs(sessions, ME)] == [SILENT], \
        "理由が空なのに黙りました"
    assert run_marker.main(["--seen", SILENT]) == 2


def test_セッションIDに見えないものは受け付けない(marks):
    _start(marks, "session_ok")
    assert run_marker.main(["--seen", "silent", "--why", "中身ゼロ"]) == 2


def test_二重に打っても1行しか増えない(marks, sessions):
    _start(marks, "session_ok")
    run_marker.main(["--seen", SILENT, "--why", "中身ゼロ"])
    before = marks.read_text(encoding="utf-8")
    assert run_marker.main(["--seen", SILENT, "--why", "もう一度"]) == 0
    assert marks.read_text(encoding="utf-8") == before, \
        "**同じ回に2行入りました。**帳簿が二重に数えます"


def test_ship_や_write_と混ぜない(marks):
    with pytest.raises(SystemExit):
        run_marker.main(["--seen", SILENT, "--why", "x", "--write"])
    with pytest.raises(SystemExit):
        run_marker.main(["--why", "x"])


def test_他の回は黙らない(marks, sessions):
    """**1件だけ黙らせる**こと（まとめて黙ると、次の穴が見えなくなります）。"""
    _start(marks, "session_ok")
    other = _sess("session_other", "2026-08-18T05:11:50.000000Z")
    run_marker.main(["--seen", SILENT, "--why", "中身ゼロ"])
    got = [s["id"] for s in sibling_check.silent_runs(sessions + [other], ME)]
    assert got == ["session_other"], f"黙らせすぎ／足りません: {got}"
