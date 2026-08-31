"""**`scripts/eta.py` が `src/*` を、実物と合わない引数で呼んでいないか。**（API 0単位・静的）

## なぜ要るか（2026-09-01・最適化の回に踏んで足した）

`eta.py` の助手は、ほぼ全部この形をしています ——

    try:
        from src import long_ceiling
        return long_ceiling.lines(m)[1:]
    except Exception:                      # noqa: BLE001 — 回を止めない
        return []

**`long_ceiling.lines()` は引数を取りません。** 毎周 `TypeError` が出て、
すぐ下の `except` が飲み、**画面には空が出ていました** —— 判定の4行

    → **判定できます。外れです**（`falsified`）—— 22本中 2本・符号検定 **p=0.0001**

が、**1度も印字されないまま**台帳の側だけが閉じています。

**`except Exception` は「回を止めない」ためのもので、正しい。**
壊れているのは、**呼び方の間違いが、その中に混ざって見えなくなる**ことです。
実行時には出ません（画面が静かに短くなるだけ）。**だから静的に見ます。**

`eta.py` の頭3行は `CLAUDE.md` が「読むのはここだけ」と書いている場所で、
**そこが黙って短くなる欠陥は、次の回からは見えません。**

## 何を見るか

`eta.py` の中の `<モジュール>.<関数>(...)` を全部ひろい、**本物の署名に当てます**
（`inspect.signature().bind_partial`）。`*args` / `**kwargs` を渡している呼びは飛ばします。
**モジュールは `from src import ...` で読めたものだけ** —— 関数の中の遅い import も拾います
（見つけた欠陥がまさにそれでした）。

## 覆る条件

引数の**型**は見ていません（数と名前だけ）。`long_ceiling.lines(m)` は
数で捕まりましたが、`f(x)` に別の型を渡す形はここでは出ません。
**そこまで要るようになったら、この検査ではなく呼び先の側に門を置くこと。**
"""
from __future__ import annotations

import ast
import importlib
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _imported_modules(tree: ast.AST) -> dict[str, str]:
    """`eta.py` が読んでいる `src.*` の別名 → 完全名。**関数の中の import も拾う。**"""
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "src":
            for a in node.names:
                out[a.asname or a.name] = "src." + a.name
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith("src."):
                    out[a.asname or a.name.split(".")[-1]] = a.name
    return out


def test_eta_の呼び出しが呼び先の署名と合っている():
    src = (ROOT / "scripts" / "eta.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    loaded = {}
    for alias, full in _imported_modules(tree).items():
        try:
            loaded[alias] = importlib.import_module(full)
        except Exception:                                      # noqa: BLE001
            continue          # 読めないモジュールは、この検査の対象外
    assert loaded, "`src/*` を1つも読めていません（この検査が空回りします）"

    bad: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if not (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)):
            continue
        mod = loaded.get(f.value.id)
        if mod is None:
            continue
        fn = getattr(mod, f.attr, None)
        if not callable(fn) or inspect.isclass(fn):
            continue
        try:
            sig = inspect.signature(fn)
        except (ValueError, TypeError):
            continue
        # `*args` / `**kwargs` を渡している呼びは、数が読めないので飛ばす
        if any(isinstance(a, ast.Starred) for a in node.args):
            continue
        if any(k.arg is None for k in node.keywords):
            continue
        pos = len(node.args)
        kw = [k.arg for k in node.keywords if k.arg]
        try:
            sig.bind_partial(*[None] * pos, **{k: None for k in kw})
        except TypeError as e:
            bad.append(f"eta.py:{node.lineno}  {f.value.id}.{f.attr}{sig}"
                       f"  ← 位置 {pos}件 / 名前 {kw}   {e}")

    assert not bad, (
        "**`except Exception` が飲む呼び違いです。**"
        " 実行時には出ません（画面が黙って短くなるだけ）:\n  " + "\n  ".join(bad))
