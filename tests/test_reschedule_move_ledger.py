"""**実物を動かしたのに、控えに書き戻していない口を、全部まとめて塞ぐ。**

2026-08-18 に実測で踏みました。`reschedule.py --move` を6本撃つと、
YouTube 側の `publishAt` は動くのに、控え（`data/uploaded.jsonl`）は
**6本とも 09/27 のまま**でした。`--compact` は控えだけを見るので、
次の回は**動かした後の姿を知らないまま**割り当てを組みます。

**同じ形が、これで3回目です。**

    8/18 16:0x  `--compact` が控えから予約を書き戻していた（実測8/10が復活）
    8/18 16:0x  `unschedule` が控えに書き戻していなかった
    8/18 16:3x  `--move` と `reschedule.py --unschedule` が書き戻していなかった ← ここ

1件ずつ塞いでも、**素通りさせている側**が同じなら次も出ます。
だからここでは「この呼び出しが在るか」ではなく、
**`_update()` を呼ぶ場所は必ず `dupes.retime()` も呼ぶ**という形そのものを見ます。
新しく口を足した回も、この検査に当たります。
"""
from __future__ import annotations

import ast
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "reschedule.py"


def _calls(body: list[ast.stmt]) -> set[str]:
    """このブロックが直接呼んでいる名前（入れ子の関数定義には入らない）。"""
    names: set[str] = set()
    for stmt in body:
        for node in ast.walk(stmt):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if isinstance(node, ast.Call):
                f = node.func
                if isinstance(f, ast.Name):
                    names.add(f.id)
                elif isinstance(f, ast.Attribute):
                    base = f.value
                    if isinstance(base, ast.Name):
                        names.add(f"{base.id}.{f.attr}")
    return names


def test_実物を動かす場所は必ず控えにも書き戻している():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    bad = []
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list):
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name == "_update":
            continue          # 定義そのものは対象外
        names = _calls(body)
        if "_update" in names and "dupes.retime" not in names:
            bad.append(getattr(node, "lineno", "?"))
    assert not bad, (
        f"scripts/reschedule.py の {bad} 行目のブロックが `_update()` を呼ぶのに "
        "`dupes.retime()` を呼んでいません。**実物だけ動いて控えが古いまま**になり、"
        "`--compact` が次の回に古い時刻で割り当てを組みます")


def test_move_と_unschedule_の両方に書き戻しがある():
    """**片方だけ直す**が3回続いているので、両方あることを名指しで見る。"""
    src = SCRIPT.read_text(encoding="utf-8")
    assert "dupes.retime(vid, iso)" in src, \
        "--move が控えに書き戻していない"
    assert "dupes.retime(args.unschedule, None)" in src, \
        "reschedule.py --unschedule が控えに書き戻していない"
