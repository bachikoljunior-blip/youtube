"""**既に絵が載っている本の、サムネイルを差し替える道**（2026-09-05 に足した）。

`rebuild_stash()` の註は「載せるのは窓が戻った回の `--missing --video <ID>`」と
名指ししていますが、**その1行は絵が既に載っている本には効きません** ——
`critique_queue.missing_thumbnail()` が返すのは `thumbnail_set is False` の本だけで、
**焼き上がって絵まで載った本（＝規則3 が「次の枠まで良くし続けろ」と言う当の本）は
一覧に出ない**からです。実測 2026-09-05 00:5x に `GFvAcxvDmYM` で踏みました。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import refresh_thumbnail as rt  # noqa: E402


def _stash(tmp_path, video_id, *, thumbnail_set):
    (tmp_path / f"{video_id}.json").write_text(json.dumps(
        {"video_id": video_id, "topic": "t", "thumbnail_set": thumbnail_set,
         "stashed_at": "2026-09-04T21:31:26+09:00"}, ensure_ascii=False),
        encoding="utf-8")
    (tmp_path / f"{video_id}.thumb.jpg").write_bytes(b"jpeg-bytes")


def test_stash_row_reads_a_video_that_already_has_a_thumbnail(tmp_path, monkeypatch):
    import critique_queue
    monkeypatch.setattr(critique_queue, "STASH", tmp_path)
    _stash(tmp_path, "AAA", thumbnail_set=True)
    # `missing_thumbnail()` からは見えない（載っているので）
    assert [r["video_id"] for r in critique_queue.missing_thumbnail()] == []
    # `stash_row()` からは見える
    row = rt.stash_row("AAA")
    assert row is not None
    assert row["video_id"] == "AAA" and row["topic"] == "t"
    assert row["thumb"] == tmp_path / "AAA.thumb.jpg"


def test_stash_row_is_none_without_bytes(tmp_path, monkeypatch):
    import critique_queue
    monkeypatch.setattr(critique_queue, "STASH", tmp_path)
    (tmp_path / "BBB.json").write_text('{"video_id":"BBB"}', encoding="utf-8")
    assert rt.stash_row("BBB") is None      # 絵が無い
    assert rt.stash_row("") is None
    assert rt.stash_row("NOPE") is None


def test_replace_needs_a_single_video(tmp_path, monkeypatch, capsys):
    import critique_queue
    monkeypatch.setattr(critique_queue, "STASH", tmp_path)
    _stash(tmp_path, "AAA", thumbnail_set=True)
    # 束には渡さない
    assert rt.push_missing(dry_run=True, replace=True) == 2
    assert "--video" in capsys.readouterr().out


def test_replace_picks_up_the_already_set_video(tmp_path, monkeypatch, capsys):
    import critique_queue
    monkeypatch.setattr(critique_queue, "STASH", tmp_path)
    _stash(tmp_path, "AAA", thumbnail_set=True)
    # `--replace` 無しでは「控えにありません」で 1
    assert rt.push_missing(dry_run=True, only_video="AAA") == 1
    assert "控えにありません" in capsys.readouterr().out
    # `--replace` を付けると 1本 拾って dry-run で止まる（API は叩かない）
    assert rt.push_missing(dry_run=True, only_video="AAA", replace=True) == 0
    out = capsys.readouterr().out
    assert "差し替え" in out and "AAA" in out


def test_replace_says_so_when_the_stash_has_no_image(tmp_path, monkeypatch, capsys):
    import critique_queue
    monkeypatch.setattr(critique_queue, "STASH", tmp_path)
    assert rt.push_missing(dry_run=True, only_video="ZZZ", replace=True) == 1
    assert "控えにありません" in capsys.readouterr().out


def test_replace_does_not_disturb_the_missing_list(tmp_path, monkeypatch):
    import critique_queue
    monkeypatch.setattr(critique_queue, "STASH", tmp_path)
    _stash(tmp_path, "AAA", thumbnail_set=False)   # まだ載っていない本
    # 既に一覧に居る本は、`--replace` を付けても二重に入らない
    rows = critique_queue.missing_thumbnail()
    assert [r["video_id"] for r in rows] == ["AAA"]
    assert rt.push_missing(dry_run=True, only_video="AAA", replace=True) == 0
