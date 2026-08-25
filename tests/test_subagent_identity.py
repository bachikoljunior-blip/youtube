"""**サブエージェントの回が、親と同一人物に見えていた。**（2026-08-25 22:0x）

2026-08-25 の夜に、毎時の回は「親が `create_session` で立てる子」から
**「親セッションの中のサブエージェント」**へ移りました
（`docs/trigger_parent.md` 第1節 —— `create_session` が人のタップを待つので、
夜のあいだ鎖が止まったため）。

**そこで1つ壊れました。** サブエージェントは親と同じコンテナで走るので、
`CLAUDE_CODE_REMOTE_SESSION_ID` が**親のもの**です。つまり:

  - `run_marker.py --write` が「**親からは印を付けません**」で拒否する
    → 心音が1つも残らない → `stop_check.sh` は「印の無い回」として黙って通し、
      `sessions_compact.py` は「印を1つも残していない回」として数える
  - `--ship` は書けるが、`_records()` の親フィルタが**丸ごと落とす**
    → `run_marker.py`（引数なし）に1行も出ない

実測（この検査を書いた回）: `data/runs.jsonl` の ship 378件のうち **14件**が
親IDで、落ちた中に **upload が2件**（「在庫の穴(08/30)へ長尺2本を予約」
「長尺2本追加＋同calc連続4本を組み替え」）ありました。
それでも道具は「**周は回っています**」と印字していました。
**8/25 夜以降は全部の回が親IDになるので、放っておけば 100% 落ちます。**

見分けは**作業コピー（worktree）の道**でやります —— サブエージェントは必ず
`…/.claude/worktrees/<名前>` で走り、親は共有チェックアウトで走るからです。
**IDの直書きより腐りません**（`config/parents.txt` は交代のたびに手で足す必要がある）。

**故障注入つき**: 直す前の姿（素のセッションIDで書く／`kind` を問わず落とす）に
戻したら鳴ることを、同じ検査の中で見ます。**片側だけでは「効いている」と言えません。**
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import run_marker                                             # noqa: E402


PARENT = "session_01PARENTPARENTPARENT"
TAG = "agent-deadbeef"


@pytest.fixture
def marks(tmp_path, monkeypatch):
    """`data/runs.jsonl` を差し替える。**実物を書き換えないこと。**"""
    path = tmp_path / "runs.jsonl"
    monkeypatch.setattr(run_marker, "MARKS", path)
    monkeypatch.setattr(run_marker, "JOURNAL", tmp_path / "JOURNAL.md")
    monkeypatch.setattr(run_marker, "PARENT_SESSIONS", {PARENT})
    monkeypatch.setenv("CLAUDE_CODE_REMOTE_SESSION_ID", PARENT)
    return path


def _rows(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _as_subagent(monkeypatch):
    monkeypatch.setattr(run_marker, "worktree_tag", lambda: TAG)


def _as_parent(monkeypatch):
    monkeypatch.setattr(run_marker, "worktree_tag", lambda: "")


# ---------------------------------------------------------------- 見分けそのもの

def test_worktree_tag_は道から名前を拾う():
    """**実物で見ます。** この検査は作業コピーで走っていることも、
    共有チェックアウトで走っていることもあり、**どちらでも正しい**。
    見るのは「道に `.claude/worktrees/<名前>` が在れば、その名前が出る」ことだけ。
    """
    tag = run_marker.worktree_tag()
    parts = Path(run_marker.__file__).resolve().parent.parent.parts
    if ".claude" in parts and "worktrees" in parts:
        assert tag and tag == parts[parts.index("worktrees") + 1]
    else:
        assert tag == ""


def test_サブエージェントは親ではない(marks, monkeypatch):
    _as_subagent(monkeypatch)
    assert run_marker.session_id() == PARENT      # 環境変数は親のまま。ここは変わらない
    assert run_marker.is_parent() is False
    assert run_marker.actor_id() == f"{PARENT}#{TAG}"


def test_共有チェックアウトの親は今までどおり親(marks, monkeypatch):
    _as_parent(monkeypatch)
    assert run_marker.is_parent() is True
    assert run_marker.actor_id() == PARENT


# ---------------------------------------------------------------- 心音（--write）

def test_サブエージェントの心音は残る(marks, monkeypatch):
    _as_subagent(monkeypatch)
    assert run_marker.write() == 0
    rows = _rows(marks)
    assert len(rows) == 1
    assert rows[0]["kind"] == "start"
    assert rows[0]["session"] == f"{PARENT}#{TAG}"
    # **落とされないこと。** ここが本体（落ちると「周が回っていない」に見える）
    assert run_marker._records() == rows


def test_親の心音は今までどおり残らない(marks, monkeypatch):
    """**足切りを消したわけではありません。** 親が居るだけで
    「周が回っている」に見えるのを潰す、という狙いはそのままです。"""
    _as_parent(monkeypatch)
    assert run_marker.write() == 0
    assert not marks.exists() or _rows(marks) == []


def test_故障注入_素のIDで書くと親フィルタに落ちる(marks, monkeypatch):
    """直す前の姿。**`actor_id()` を `session_id()` に戻すと、こうなります。**"""
    _as_subagent(monkeypatch)
    run_marker._append({"at": "2026-08-25T22:00:00+09:00", "session": PARENT, "kind": "start"})
    assert _rows(marks)                      # 書けてはいる
    assert run_marker._records() == []       # **誰にも見えない**


# ---------------------------------------------------------------- 出したもの（ship）

def test_親IDで書かれた過去の_ship_も見える(marks, monkeypatch):
    """**8/25 夜に既に書かれてしまった 14件**が、これで戻ります。

    足切りは `start`（心音）にだけ効かせる、と狭めました ——
    `ship` は「出したもの」の主張で、落とすと **upload が消えます。**
    そして `src/levers.py` の `recent()` は元から落としていません。
    **同じ台帳を読む2つが、違うものを見ていました。**
    """
    run_marker._append({"at": "2026-08-25T18:23:52+09:00", "session": PARENT,
                        "kind": "ship", "what": "在庫の穴へ長尺2本を予約",
                        "lever": "density", "moves": 0})
    run_marker._append({"at": "2026-08-25T18:24:00+09:00", "session": PARENT,
                        "kind": "start"})
    seen = run_marker._records()
    assert [r["kind"] for r in seen] == ["ship"]


def test_サブエージェントの_ship_は自分の名で残る(marks, monkeypatch):
    _as_subagent(monkeypatch)
    assert run_marker.ship("直した", lever="none", moves=0, reflect=False) == 0
    row = [r for r in _rows(marks) if r["kind"] == "ship"][-1]
    assert row["session"] == f"{PARENT}#{TAG}"
    assert row["lever"] == "none"
    assert row["moves"] == 0


def test_同じ親の別のサブエージェントの_ship_を掴まない(marks, monkeypatch):
    """**素のIDだと2人が同一人物になります。**

    `--closes-add` は「この回の最後の ship」に足すので、素のIDのままだと
    **隣で同時に走っている回の ship に足しにいきます。**
    """
    _as_subagent(monkeypatch)
    run_marker.ship("こちらの回", lever="none", moves=0, reflect=False)
    # 隣のサブエージェント（同じ親・別の作業コピー）が、後から出した
    run_marker._append({"at": "2026-08-25T23:00:00+09:00", "session": f"{PARENT}#agent-other",
                        "kind": "ship", "what": "隣の回"})
    run_marker.closes_add(["carry_over"])
    rows = [r for r in _rows(marks) if r["kind"] == "ship"]
    mine = [r for r in rows if r["what"] == "こちらの回"][0]
    theirs = [r for r in rows if r["what"] == "隣の回"][0]
    assert mine.get("closes") == ["carry_over"]
    assert "closes" not in theirs
