"""**追記の字下げを決め打ちにしない。** 2026-08-25 に `topics.yaml` を壊した。

`to_yaml()` は長らく **2字下げ決め打ち**で項目を書いていました。ところが
`config/topics.yaml` の項目は **503件すべてが0字下げ**（`- id:` が行頭）で、
`--count 5` が足した5件だけが2字下げになり、**ファイル全体が読めなくなりました。**

    yaml.parser.ParserError: while parsing a block mapping
      expected <block end>, but found '-'

**書いた直後の読み直しは、これを「捕まえる」だけで「戻す」ことはしません。**
壊れた `topics.yaml` はそのまま残り、次の回の `status.py` も
`src.pipeline` も、テーマを読むもの全部が止まります。

**決め打ちを反対側（0字下げ）に変えても同じことが起きます。**
どちらが正しいかは、そのときのファイルにしか書いていません。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "topic_forge", ROOT / "scripts" / "topic_forge.py")
forge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(forge)

ROWS = [{
    "id": "s-test-indent-1",
    "title_seed": "字下げの検査に使う題",
    "angle": "1行目\n2行目",
    "calc": "kokuho",
    "calc_sections": ["ある節: 引用符が要る見出し"],
}]

FLUSH = "topics:\n- id: a\n  title_seed: あ\n  calc: kokuho\n  score: 1.0\n"
NESTED = "topics:\n  - id: a\n    title_seed: あ\n    calc: kokuho\n    score: 1.0\n"


def test_行頭の台帳を読める形のまま伸ばす():
    assert forge.list_indent(FLUSH) == ""
    got = FLUSH + forge.to_yaml(ROWS, forge.list_indent(FLUSH))
    parsed = yaml.safe_load(got)
    assert [t["id"] for t in parsed["topics"]] == ["a", "s-test-indent-1"]
    assert parsed["topics"][-1]["calc_sections"] == ["ある節: 引用符が要る見出し"]


def test_字下げの台帳でも読める形のまま伸ばす():
    assert forge.list_indent(NESTED) == "  "
    got = NESTED + forge.to_yaml(ROWS, forge.list_indent(NESTED))
    parsed = yaml.safe_load(got)
    assert [t["id"] for t in parsed["topics"]] == ["a", "s-test-indent-1"]


def test_決め打ちの2字下げは実物の台帳を壊す():
    """**直す前の姿を、そのまま検査に置く。** 戻したら赤になります。"""
    broken = FLUSH + forge.to_yaml(ROWS, "  ")
    try:
        yaml.safe_load(broken)
    except yaml.YAMLError:
        return
    raise AssertionError("行頭の台帳に2字下げで足しても壊れなかった（検査が効いていない）")


def test_実物の_topics_yaml_に足しても読める():
    """**本物に当てる。** 決め打ちのままだと、ここが落ちます。"""
    text = (ROOT / "config" / "topics.yaml").read_text(encoding="utf-8")
    got = text + forge.to_yaml(ROWS, forge.list_indent(text))
    parsed = yaml.safe_load(got)
    assert parsed["topics"][-1]["id"] == "s-test-indent-1"
