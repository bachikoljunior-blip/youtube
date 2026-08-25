"""**節から届く道が無い引数**を、`src/calc/` から拾う。

## なぜ要るか（2026-08-18 23:0x。**実物を1件踏んでから測って足しています**）

`shobyo.premiums()` は `health_rate` と `pension_rate` を**引数で受け取れました**。
ところが呼ぶ側の `net_month()` が渡しておらず、**節から率を動かす道がありませんでした。**
道を繋いだら、その場で節が1つ書け（「率が1ポイント違うと546日でいくら」）、
**繋いだ瞬間に1円の欠陥も出ました**（`int(標準報酬 × 率)` の float 切り捨て）。

**この形は掃引（`src/section_sweep.py`）に見えません。** 掃引は関数を実際に呼んで
数字の形を見ますが、**呼べない軸は最初から視野の外**です。`src/premise.py` も
「印字されない引数」は見ますが、**渡されない引数**は見ていません。

## 何を「届かない」と呼ぶか

引数 `a`（既定値つき）が、次の3つを全部満たすとき:

1. **どの呼び出しも `a` を渡していない**（キーワードでも位置でも）
2. その関数が **`__main__` から直接呼ばれていない**（＝節が直に触れない）
3. **呼ぶ側のどれもが、同じ名前の引数を持っていない**（＝上へ通す道も無い）

3 が本体です。呼ぶ側が同名の引数を持っていれば、**節はそこ経由で届きます**。

## 実測（2026-08-18・calc 54本）

    素朴に「渡されていない引数」        281件 / 46表   ← **多すぎて選べない**
    節を出す関数に限る                  210件 / 37表   ← まだ多い
    **上の3つを全部満たすもの**          63件 / 25表   ← これ

**候補です。意味と正しさは人が決めます**（`section_sweep` と同じ扱い。
数字の出どころにしないこと）。
"""
from __future__ import annotations

import ast
from pathlib import Path

CALC_DIR = Path(__file__).resolve().parent / "calc"

# **節ではない関数**。`check_tables` は制度の値の検査で、節を1つも出しません。
# ここを節と数えると、`check_tables` が触っただけの引数が「届いている」ことになり、
# **本物が消えます**（`shobyo.net_month` の率がそれで消えました）。
NOT_A_SECTION = {"check_tables", "main"}


def _kwargs(fn: ast.FunctionDef) -> list[str]:
    """既定値を持つ引数（＝呼ぶ側が省ける軸）だけ。"""
    with_default = fn.args.args[len(fn.args.args) - len(fn.args.defaults):]
    return [a.arg for a in with_default] + [a.arg for a in fn.args.kwonlyargs]


def _all_params(fn: ast.FunctionDef) -> set[str]:
    return {a.arg for a in fn.args.args + fn.args.kwonlyargs}


def scan_source(source: str) -> list[dict]:
    """1つのモジュールの中身から、届かない引数を拾う。"""
    tree = ast.parse(source)
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    mains = [n for n in tree.body
             if isinstance(n, ast.If) and "__main__" in ast.dump(n.test)]

    from_main: set[str] = set()
    for m in mains:
        for n in ast.walk(m):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
                from_main.add(n.func.id)

    passed: dict[str, set[str]] = {}
    callers: dict[str, set[str]] = {}
    scopes: list[tuple[str, ast.AST]] = [(k, v) for k, v in funcs.items()]
    scopes += [("__main__", m) for m in mains]
    for owner, node in scopes:
        # **`check_tables` から渡されていても「届いている」とは数えません。**
        # あそこは制度の値の検査で節を1つも出さないので、そこだけで動く軸は
        # **節から見れば塞がったまま**です（実物でここを数えて本物が消えました）。
        counts_as_reach = owner not in NOT_A_SECTION
        for n in ast.walk(node):
            if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)):
                continue
            target = funcs.get(n.func.id)
            if target is None:
                continue
            callers.setdefault(n.func.id, set()).add(owner)
            got = passed.setdefault(n.func.id, set())
            if not counts_as_reach:
                continue
            names = [a.arg for a in target.args.args]
            got.update(k.arg for k in n.keywords if k.arg)
            got.update(names[i] for i in range(len(n.args)) if i < len(names))

    out = []
    for name, fn in funcs.items():
        if name.startswith("_") or name in NOT_A_SECTION or name in from_main:
            continue
        cs = callers.get(name, set())
        if not cs:
            continue
        for arg in _kwargs(fn):
            if arg in passed.get(name, set()):
                continue
            # 呼ぶ側が同じ名前の引数を持っていれば、節はそこ経由で届く
            if any(c in funcs and arg in _all_params(funcs[c]) for c in cs):
                continue
            out.append({"func": name, "arg": arg, "callers": sorted(cs)})
    return out


def scan_all(calc_dir: Path = CALC_DIR) -> list[dict]:
    rows = []
    for p in sorted(calc_dir.glob("*.py")):
        if p.name.startswith("_"):
            continue
        for r in scan_source(p.read_text(encoding="utf-8")):
            rows.append({"calc": p.stem, **r})
    return rows


if __name__ == "__main__":
    rows = scan_all()
    tables = sorted({r["calc"] for r in rows})
    print(f"**節から届く道が無い引数**: {len(rows)}件 / 表 {len(tables)}本")
    print("**候補です。意味と正しさは人が決めます**（数字の出どころにしないこと）\n")
    for r in rows:
        print(f"  {r['calc']:14s} {r['func']:22s} {r['arg']:18s} "
              f"← {','.join(r['callers'])}")
