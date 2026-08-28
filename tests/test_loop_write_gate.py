"""**輪の中で何十本も書く口は、輪の中で門に訊くこと**（2026-08-28 の2周目）。

`upload_cap.reserve_hold()` は `spent >= floor - RESERVE_UNITS` で止めます。
`spent` は**その輪が自分で増やしている数**なので、
**輪の手前で1回だけ訊く門は、門になりません** —— 一度 通れば、
そのあと何十本 書いても二度と訊かれません。

実測 2026-08-28 の時点で、そうなっていた口は2つ:

    scripts/link_longform.py   `videos.update` を1回で何十本（各 50単位）
    scripts/refresh_thumbnail.py:push_missing  `thumbnails.set` を1回で何十本

`scripts/reschedule.py` は正しく、門が `_update()` の中（＝1本ごと）にあります。

**この検査は AST で「輪の中に門があるか」を見ます。** 字で並べないこと ——
同じ日の朝、入口を字で2つ並べた検査が **6つ中4つ**を素通ししています。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

#: 「1回で何十本も書く」口。**書き込みが `for` の中にあるファイル**を見ます。
WRITE_CALLS = {("videos", "update"), ("thumbnails", "set"),
               ("playlistItems", "insert"), ("commentThreads", "insert"),
               ("playlists", "insert")}


def _loops_with_writes(path: Path):
    """`for`/`while` の本体に書き込みがある輪を返す。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.For, ast.While, ast.AsyncFor)):
            continue
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Call):
                continue
            fn = inner.func
            if not isinstance(fn, ast.Attribute):
                continue
            recv = fn.value
            if not (isinstance(recv, ast.Call)
                    and isinstance(recv.func, ast.Attribute)):
                continue
            if (recv.func.attr, fn.attr) in WRITE_CALLS:
                out.append((node, f"{recv.func.attr}.{fn.attr}"))
                break
    return out


def _body_text(path: Path, node) -> str:
    src = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(src[node.lineno - 1:(node.end_lineno or node.lineno)])


def test_何十本も書く輪は_輪の中で門に訊いていること():
    bad = []
    for base in ("src", "scripts"):
        for path in sorted((ROOT / base).glob("*.py")):
            for node, name in _loops_with_writes(path):
                if "reserve_hold" not in _body_text(path, node):
                    bad.append(f"{path.relative_to(ROOT)}:{node.lineno} {name}")
    assert not bad, (
        "**輪の中で書いているのに、門が輪の外にあります**:\n  "
        + "\n  ".join(bad)
        + "\n\n門が読む `spent` は、その輪が自分で増やしている数です。"
          "**手前で1回だけ訊くと、通ったあとに残りを全部 焼けます。**"
          "\n書き込みの直前で `upload_cap.reserve_hold()` を訊き、"
          "**止めるときは「どこまでやったか」と「次の窓で続けられること」を印字**すること。")


def test_この検査が_輪を1つも見つけられないなら赤にすること():
    """**見つからないことを「輪が無い」と読まないこと。**

    呼び出しの書き方が `X.videos().update(...)` の形でなくなったら、
    `_loops_with_writes()` は静かに 0件 を返します。
    """
    found = sum(len(_loops_with_writes(p))
                for base in ("src", "scripts")
                for p in (ROOT / base).glob("*.py"))
    assert found >= 2, (
        f"書き込みのある輪が {found}件 しか見つかりません。"
        " 呼び出しの書き方が変わったなら `_loops_with_writes()` を直すこと。")
