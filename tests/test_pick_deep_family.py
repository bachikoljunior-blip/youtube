"""**ショートの回が、族を空にする一手を先に取らないこと**（2026-08-26 12:0x に測って足した）。

## 何を固定しているか

`s-` で始まらない題（＝「深い題」）は、そのまま**長尺の在庫**でもあります。
7日ぶんの長尺の上限は **族の数 × 2本**（`--per-calc`）なので、
**族の最後の1件をショートに回すと、上限が丸ごと2本 落ちます。**

2026-08-26 09:5x の回が、そこに**値札**を出しました
（`_warn_long_stock_eaten`）。ですが値札は**選んだ後**に出ます ——
同じ日の `pick(60)` は深い題を9件 取り、**5族ぶんを空にして上限を 10本**
落としていました。実測でそのとき残っていたのは:

    使っていない深い題        31件 / 族 12
    族の残りが1件だけ         2族（`jutaku` `nenkin`）
    族を空にせず使える題      **19件**

**19件で足りていました。** 落ちた族のうち4つ（`kouki` `shougai` `izoku`
`kakyu`）は**残り2件**で、`per_calc=2` がちょうど飲み干していただけです。
つまり **判断が要る場面ではなく、並べ方の穴**でした。

## ここで固定する3つ

1. 残り2件の族を、ショートの回が**飲み干さない**（`per_calc=2` でも1件 残す）
2. 族を空にしない題が尽きたら、**2周目で取る** ——
   在庫切れで投稿を止めないこと（`CLAUDE.md`「投稿を途切れさせない」）
3. `--long` の回には**効かない**（長尺は非 `s-` からしか取らないので、
   ここで守ると自分自身を止めます）

## これは「深い題をショートに出さない」ではありません

`deep_shorts` の前提（腕 `rpm`・期限 2026-09-03）は、
**深い題のショートが 16本 溜まるのを待っています**（08/26 時点 9本）。
止めれば永久に判定できません。**同じ本数を、族を殺さない側から取る**だけです。
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

from scripts import batch_build  # noqa: E402


def _stub(monkeypatch, topics: list[tuple[str, str]]) -> None:
    """`(id, calc)` の並びを在庫にする。控えも `build/` も空にする。"""
    from src import config, dupes

    pool = {"topics": [{"id": i, "calc": c, "score": 1.0,
                        "calc_sections": [f"節 {i}"]} for i, c in topics]}
    monkeypatch.setattr(config, "load_topics", lambda: pool)
    monkeypatch.setattr(batch_build, "_posted_including_ledger", lambda: set())
    monkeypatch.setattr(batch_build, "_drop_doomed", lambda u, p: u)
    monkeypatch.setattr(batch_build, "_drop_queue_tail_calcs", lambda u, p: u)
    monkeypatch.setattr(dupes, "ledger_rows", lambda: [])


def test_残り2件の族を飲み干さない(monkeypatch):
    """**この検査が、この直しの理由そのものです。**

    `alpha` は深い題が2件。`per_calc=2` なので、守りが無ければ2件とも取られ、
    族が消えて 7日ぶんの長尺の上限が 2本 落ちます。
    ショート向けの題が在庫にあるので、**そちらへ逃げられるはず**です。
    """
    _stub(monkeypatch, [("alpha-1", "alpha"), ("alpha-2", "alpha"),
                        ("s-bravo-1", "bravo"), ("s-bravo-2", "bravo")])
    got = [t["id"] for t in batch_build.pick(3, [])]
    deep = [i for i in got if not i.startswith("s-")]
    assert len(deep) == 1, f"族 alpha を飲み干しました: {got}"
    assert len(got) == 3, got


def test_族が3件あれば2件まで取る(monkeypatch):
    """**守っているのは「族が消えること」だけ**で、深い題そのものではありません。"""
    _stub(monkeypatch, [("alpha-1", "alpha"), ("alpha-2", "alpha"),
                        ("alpha-3", "alpha")])
    got = [t["id"] for t in batch_build.pick(3, [])]
    assert len(got) == 2, got            # `per_calc=2` の上限。族は1件 残る


def test_他に取れる題が無ければ2周目で取る(monkeypatch):
    """**在庫切れで投稿を止めないこと。** 守りは1周目だけです。"""
    _stub(monkeypatch, [("alpha-1", "alpha")])
    got = [t["id"] for t in batch_build.pick(1, [])]
    assert got == ["alpha-1"], got


def test_長尺の回には効かない(monkeypatch):
    """長尺は非 `s-` からしか取りません。ここで守ると自分自身を止めます。"""
    _stub(monkeypatch, [("alpha-1", "alpha"), ("alpha-2", "alpha")])
    got = [t["id"] for t in batch_build.pick(2, [], long_form=True)]
    assert len(got) == 2, got


def test_値札と選ぶ側が同じ数え方をする(monkeypatch):
    """`_warn_long_stock_eaten` と `_deep_left` が **同じ `_deep_used`** から引くこと。

    片方だけ直すと、値札が「上限は動きません」と言いながら実際は落ちます
    （逆も同じ）。**ずれていたら、次に読む側は値札を信じます。**
    """
    _stub(monkeypatch, [("alpha-1", "alpha"), ("alpha-2", "alpha")])
    from src import config

    pool = config.load_topics()["topics"]
    left = batch_build._deep_left(pool, set(), {"alpha-1"})
    assert left == {"alpha": 1}, left     # `build/` に在るぶんは残りから引く
    assert "alpha-1" in batch_build._deep_used(set(), {"alpha-1"})
