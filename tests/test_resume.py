"""`scripts/resume.py`。**会話履歴なしで、repo だけから状態を復元する。**

守っているのは2つ:

1. **閉じた依頼を「未処理」に数えない**（`kind` が `open`/`close` の2行で1件）
   —— 最初これを在りもしない `state` 欄で書き、**22件すべてを未処理と出した**
2. **予約済みの本を「予約していない本」に数えない**（`build/` は投稿後も残る）
"""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load(tmp_root: Path):
    spec = importlib.util.spec_from_file_location("resume", ROOT / "scripts" / "resume.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.ROOT = tmp_root
    return mod


def _write(p: Path, rows: list[dict]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


def test_closed_requests_are_not_open(tmp_path: Path) -> None:
    m = _load(tmp_path)
    _write(tmp_path / "data" / "inbox.jsonl", [
        {"at": "1", "kind": "open", "id": "aaa", "text": "済んだ依頼"},
        {"at": "2", "kind": "close", "id": "aaa"},
        {"at": "3", "kind": "open", "id": "bbb", "text": "まだの依頼"},
    ])
    got = m.open_requests()
    assert len(got) == 1 and "bbb" in got[0]


def test_reserved_builds_are_not_listed(tmp_path: Path) -> None:
    m = _load(tmp_path)
    (tmp_path / "build" / "s-done").mkdir(parents=True)
    (tmp_path / "build" / "s-todo").mkdir(parents=True)
    _write(tmp_path / "data" / "uploaded.jsonl", [{"video_id": "V", "topic": "s-done"}])
    assert m.unreserved_builds() == ["s-todo"]


def test_missing_files_do_not_raise(tmp_path: Path) -> None:
    """**材料が無い repo でも落ちない。** 復元の入口が落ちると、回そのものが止まる。"""
    m = _load(tmp_path)
    assert m.open_requests() == []
    assert m.unreserved_builds() == []
    assert m.journal_heads() == []
