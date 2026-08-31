"""**同じファイルを、同じ走りの中で 1,700回 パースし直さないこと**（2026-08-31）。

## なぜ要るか（実測。`cProfile` で撃ってから足しています）

`python scripts/eta.py` は **375秒** かかっていました。その内訳:

    deadline_check.check()          297.3秒   ← 全体の **79%**
      latest_views()                285.1秒   （1,665回 呼ばれる）
        _rows()                     211.9秒   （1,705回）
          json.loads                197.8秒   **37,991,128回**

`data/views.jsonl` は **21,055行**。21,055 × 1,705 ≒ 3,590万 —— 上の回数と合います。
**API ではありません**（`--offline` でも同じ）。`_rows` に `lru_cache` を掛けて
**1分51秒 → 47秒**（3行の見出しは一字も変わらず）。

## **この repo で2度目の、同じ形です**

`CLAUDE.md` に前の1件が書いてあります —— `eta.py --reflect` が
**1分37秒 → 8.5秒** になったとき、原因は「`day_cap.cap()`
（`data/views.jsonl` を丸ごと読む・59ms）を1回の走りで 1,000回 前後 呼び直していた」。
**同じファイル・同じ形・別の入口**で、**直したのは片方だけでした。**
だからこの検査は「速いこと」ではなく「**読み直していないこと**」を見ます。

## この検査が覆る条件

**同じプロセスで `data/*.jsonl` に追記してから読み直す**手ができたら、
そこは `_rows.cache_clear()` を呼ぶ必要があります。そのときこの検査は
「キャッシュが効いている」を見たままでよく、**追記の側に別の検査を足すこと。**
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import deadline_check as _DC  # noqa: E402


def _dc():
    """**普通の import で取ること。**

    `importlib.util.spec_from_file_location` で読むと `sys.modules` に載らず、
    `dataclasses` の型解決が `sys.modules.get(cls.__module__)` で `None` を引いて
    落ちます（2026-08-31 に踏んだ。5件とも同じ `AttributeError`）。
    """
    return _DC


def test_rows_は同じ名前を二度読まない():
    """**この検査の中心。** 2回目が実際にファイルを読んだら赤。"""
    dc = _dc()
    reads: list[str] = []
    real_read = Path.read_text

    def counting_read(self, *a, **kw):
        if self.name.endswith(".jsonl"):
            reads.append(self.name)
        return real_read(self, *a, **kw)

    Path.read_text = counting_read
    try:
        dc._rows.cache_clear()
        dc._rows("views.jsonl")
        dc._rows("views.jsonl")
        dc._rows("views.jsonl")
    finally:
        Path.read_text = real_read
    assert reads.count("views.jsonl") == 1, f"読み直しています: {reads}"


def test_同じ物を返す():
    """キャッシュしても中身が変わらないこと（**同一オブジェクトでよい**）。"""
    dc = _dc()
    dc._rows.cache_clear()
    a = dc._rows("uploaded.jsonl")
    b = dc._rows("uploaded.jsonl")
    assert a is b
    assert isinstance(a, list)


def test_名前ごとに別に持つ():
    """`maxsize` を1にすると、2つのファイルを交互に読む所で効きません。"""
    dc = _dc()
    dc._rows.cache_clear()
    dc._rows("views.jsonl")
    dc._rows("uploaded.jsonl")
    dc._rows("views.jsonl")
    assert dc._rows.cache_info().hits >= 1
    assert dc._rows.cache_info().maxsize is None or dc._rows.cache_info().maxsize >= 4


def test_無いファイルは空を返す():
    """**例外にしないこと。** 台帳がまだ無い環境で `eta.py` が落ちます。"""
    dc = _dc()
    assert dc._rows("does-not-exist-ぜったい無い.jsonl") == []


def test_cache_clear_が生きている():
    """覆る条件（同じプロセスで追記する手）が来たときの逃げ道が在ること。"""
    dc = _dc()
    assert hasattr(dc._rows, "cache_clear")
    dc._rows.cache_clear()
    assert dc._rows.cache_info().currsize == 0
