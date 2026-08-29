"""`pick()` は **`build/` に作ってある本も「使った」に数える**。

## なぜ（2026-08-23 に実際に踏んだ）

対照群8本を `--skip-upload` で作った直後、動きあり8本を同じ引数で作ったら
**8/8 が同じテーマ**だった。`--skip-upload` の本は投稿の記録に入らないので、
`pick()` から見て「まだ使っていない」ままだったため。

結果、`build/` は上書きされ、**ディスクの中身は動きあり・記録の1件目は動きなし**という
食い違いが生まれた。A/B の群だけが静かに嘘になる形で、
**8/19・8/23 に潰したのと同じ失敗**（群をあとから推定しようとして壊れる）。
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location("bb", ROOT / "scripts" / "batch_build.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_pick_excludes_topics_already_built(tmp_path, monkeypatch) -> None:
    bb = _load()
    pool = [{"id": "s-a", "calc": "x", "score": 1.0}, {"id": "s-b", "calc": "y", "score": 1.0}]
    monkeypatch.setattr(bb.config, "load_topics", lambda: {"topics": pool}, raising=False)
    monkeypatch.setattr(bb, "_posted_including_ledger", lambda: set(), raising=False)
    monkeypatch.setattr(bb, "_drop_doomed", lambda u, p, posted=None: u, raising=False)
    built = tmp_path / "build"
    (built / "s-a").mkdir(parents=True)
    monkeypatch.setattr(bb, "ROOT", tmp_path, raising=False)
    got = [t["id"] for t in bb.pick(2, [])]
    assert "s-a" not in got, "作ってある本を選び直すと build/ を上書きする"


def test_explicit_topics_still_win(tmp_path, monkeypatch) -> None:
    """**`--topics` で名指ししたものは通す。** 作り直しを禁じるわけではない。"""
    bb = _load()
    pool = [{"id": "s-a", "calc": "x", "score": 1.0}]
    monkeypatch.setattr(bb.config, "load_topics", lambda: {"topics": pool}, raising=False)
    built = tmp_path / "build"
    (built / "s-a").mkdir(parents=True)
    monkeypatch.setattr(bb, "ROOT", tmp_path, raising=False)
    got = [t["id"] for t in bb.pick(1, ["s-a"])]
    assert got == ["s-a"]
