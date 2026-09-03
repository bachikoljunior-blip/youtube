"""`src/sub_ask.py` —— 登録の依頼が、説明欄とコメントに**実際に入るか**。

**「既知の当たり」を先に固定してあります**（`docs/trigger_main.md` §4）——
この回に実測した「入っていなかった」ほうを、そのまま検査にしています:

* `src/pipeline.build_description()` の出す説明欄の**先頭**に依頼が在ること
* `config/channel.yaml` の footer には依頼が**無い**こと（＝ 先頭が唯一の場所）
* `src/descriptions.body()` が、その依頼を**本文として数えない**こと
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, descriptions, sub_ask  # noqa: E402


def test_依頼には登録の語が入っている():
    assert "登録" in sub_ask.HEAD
    assert "登録" in sub_ask.COMMENT_TAIL


def test_リポジトリの存在は書かない():
    """A2。説明欄・コメントのどちらにも出さない。"""
    low = (sub_ask.HEAD + sub_ask.COMMENT_TAIL).lower()
    for word in ("github", "リポジトリ", "repository", "claude", "ソースコード", "http"):
        assert word not in low


def test_説明欄の先頭に入る():
    out = sub_ask.with_head("本文です")
    assert out.startswith(sub_ask.HEAD)
    assert "本文です" in out


def test_二度掛けても増えない():
    once = sub_ask.with_head("本文です")
    assert sub_ask.with_head(once) == once


def test_空の説明欄でも依頼だけは残る():
    assert sub_ask.with_head("") == sub_ask.HEAD
    assert sub_ask.with_head(None) == sub_ask.HEAD


def test_コメントの末尾に入る_冪等():
    once = sub_ask.with_comment_ask("要点3行")
    assert once.endswith(sub_ask.COMMENT_TAIL)
    assert sub_ask.with_comment_ask(once) == once


def test_コメントが上限を越えるなら足さない():
    """本編の要点のほうを削らない。"""
    long = "あ" * 100
    assert sub_ask.with_comment_ask(long, limit=50) == long


def test_空のコメントには足さない():
    assert sub_ask.with_comment_ask("") == ""


def test_本文の勘定に定型を混ぜない():
    """`descriptions.body()` は依頼を落とす（footer を落としているのと同じ理由）。"""
    desc = sub_ask.with_head("本文です") + "\n\n▼ 目次\n0:00 はじめに\n"
    assert descriptions.body(desc).strip() == "本文です"


def test_footerには依頼が無い():
    """**この検査が、この回の起点です。** footer に依頼が入ったら、先頭は要らなくなる。"""
    footer = config.load_channel()["publish"]["footer"]
    assert "登録" not in footer


def test_組み上がった説明欄の先頭が依頼である():
    """`build_description()` を通した実物で見る（呼び出し側の配線ごと）。"""
    from src import pipeline
    from src.script_writer import Chapter, VideoScript

    script = VideoScript.model_construct(
        description_body="本文です",
        chapters=[Chapter.model_construct(segment_index=0, label="はじめに")],
    )
    out = pipeline.build_description(
        script, [(0.0, 1.0)],
        {"publish": {"footer": "─────────────\n※ 注意書き\n"}},
        "test-topic",
    )
    assert out.startswith(sub_ask.HEAD)
    assert "本文です" in out
    assert "▼ 目次" in out
