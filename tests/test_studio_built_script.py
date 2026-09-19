"""**焼いた台本を mp4 の隣に写す**（2026-09-20 00:xx・optimizer）。

守っているのは 1つ: **指紋の相手が消えないこと。**

実測（この周が踏んだ）: `2026-09-20-nenkin-tedori-hayamihyou` の mp4 は `3:0ff130dd52b0` を
刻んでいるのに、commit された台本から引くと `3:0653fadbdbec` でした —— 焼いたのは前の周の
worktree に在った**まだ commit されていない台本**で、**その台本は worktree ごと消えました。**
`status` は永久に「焼き直しが要る」と言い、次の回は毎回 **19分** を払い直します。
"""
import json

import pytest

from studio import render, script


def _mini(vid: str = "test-built-script") -> script.Script:
    return script.Script(
        id=vid,
        date="2026-09-20",
        title="ためし",
        takeaway="ためしの1文です",
        segments=[script.Segment(say="ためしにはなします。", show="ためし")],
    )


def test_built_script_reads_back_what_was_written(tmp_path, monkeypatch):
    """写した台本が、そのまま読み戻せること（**ここが全部**）。"""
    d = tmp_path / "test-built-script"
    d.mkdir()
    monkeypatch.setattr(render, "workdir", lambda vid: d)
    s = _mini()
    (d / "script.json").write_text(s.model_dump_json(indent=1), encoding="utf-8")

    back = render.built_script("test-built-script")
    assert back is not None
    assert back.id == s.id
    assert [g.say for g in back.segments] == [g.say for g in s.segments]
    # **指紋に入る物は全部 残っていること**（`build_sig` が読む 4つ）
    assert back.voice == s.voice and back.rate == s.rate
    assert back.yomi == s.yomi and back.kana_in_voice == s.kana_in_voice


def test_the_copy_reproduces_the_signature(tmp_path, monkeypatch):
    """**写しから引いた指紋が、焼いた指紋と同じであること。**

    これが成り立たないと写しは証拠になりません（別の物を写していることになる）。
    """
    d = tmp_path / "test-built-script"
    d.mkdir()
    monkeypatch.setattr(render, "workdir", lambda vid: d)
    s = _mini()
    (d / "script.json").write_text(s.model_dump_json(indent=1), encoding="utf-8")

    assert render.built_script("test-built-script").build_sig(None) == s.build_sig(None)


def test_missing_copy_is_none_not_a_crash(tmp_path, monkeypatch):
    """写す前の版で焼いた本（在庫のほとんど）で落ちないこと。"""
    d = tmp_path / "nope"
    d.mkdir()
    monkeypatch.setattr(render, "workdir", lambda vid: d)
    assert render.built_script("nope") is None


def test_broken_copy_is_none_not_a_crash(tmp_path, monkeypatch):
    """壊れた写しは None（**読めないより、嘘のほうが高い**）。"""
    d = tmp_path / "broken"
    d.mkdir()
    (d / "script.json").write_text("{これは json ではありません", encoding="utf-8")
    monkeypatch.setattr(render, "workdir", lambda vid: d)
    assert render.built_script("broken") is None


def test_copy_is_json_and_human_readable(tmp_path, monkeypatch):
    """次の回が `cat` で読める形であること（証拠は読めないと意味がありません）。"""
    d = tmp_path / "test-built-script"
    d.mkdir()
    monkeypatch.setattr(render, "workdir", lambda vid: d)
    s = _mini()
    (d / "script.json").write_text(s.model_dump_json(indent=1), encoding="utf-8")
    raw = (d / "script.json").read_text(encoding="utf-8")
    assert json.loads(raw)["id"] == "test-built-script"
    assert "\n" in raw            # indent つき ＝ 1行 に潰れていない
