"""**実物を撃たなかった回に、控えだけ動かす口を、全部まとめて塞ぐ。**

2026-09-01 にオーナーが画面で踏みました —— **控えは「予約はもう 09/02 以降
だけ」と言っているのに、実物には 09/01 18:00〜21:00 に4本 残っていた。**

原因は `reschedule._update()` の返りです。**False を返す道が2つ**あり、
片方（`upload_cap.move_hold`）は **YouTube を1文字も変えていません。**
それでも呼ぶ側が `dupes.retime()` を撃つと、**控えだけが動きます。**

    控え   09/29 09:30 に動いた（と書いてある）
    実物   もとの時刻のまま。**その時刻に公開されます**

**同じ形が、これで2回目です。**

    2026-08-29  `--move` を直した（`if wrote:` の枝）
    2026-09-01  `--spread` / `--compact` / `pool_drain --apply` は
                **素通りのまま**だった ← ここ

1件ずつ塞ぐと次も出ます（この repo が通算12回 踏んでいる「片方だけ」の形）。
だからここでは「その関数を直したか」ではなく、
**`_update()` を呼ぶ場所は、その返りを見てから `retime()` する**という
形そのものを、`scripts/reschedule.py` と `scripts/pool_drain.py` の両方で見ます。
**新しく口を足した回も、この検査に当たります。**

**姉妹の検査**: `tests/test_reschedule_move_ledger.py` は逆向き ——
「実物を動かしたのに控えへ書き戻していない」を見ます。**両方 要ります。**
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = [ROOT / "scripts" / "reschedule.py", ROOT / "scripts" / "pool_drain.py"]


def _name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def test_撃たなかった回に控えだけ動かす口が無い():
    """**返りを捨てている `_update()` の呼び出しが1つも無いこと。**

    捨てている形は1つだけです —— **文がまるごと式**（`ast.Expr`）のとき。
    受けていれば `Assign`（`wrote = _update(...)`）か
    `If`（`if not _update(...): continue`）になるので、この1点で足ります。
    **入れ子の深さは見ません**（`for` の中でも `try` の中でも同じ形）。
    """
    bad: list[str] = []
    for path in FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Expr):
                continue
            if isinstance(node.value, ast.Call) \
                    and _name(node.value.func).endswith("_update"):
                bad.append(f"{path.name}:{node.lineno}")
    assert not bad, (
        f"{bad} で `_update()` の返りを見ずに撃っています。"
        "**False を返す道が2つあり、片方（`upload_cap.move_hold`）は"
        " YouTube を1文字も変えていません。** そのまま `dupes.retime()` を"
        "撃つと、**控えだけが動いて、実物はもとの時刻のまま公開されます**"
        "（2026-09-01 にオーナーが画面で踏んだ形・実測 4本）。"
        "`wrote = _update(...)` で受けて、`if wrote:` の中で `retime` すること")


def test_三つの口すべてに枝がある():
    """**片方だけ直す**が2回続いているので、3つとも名指しで見る。"""
    resched = (ROOT / "scripts" / "reschedule.py").read_text(encoding="utf-8")
    pool = (ROOT / "scripts" / "pool_drain.py").read_text(encoding="utf-8")
    assert "if wrote:" in resched, "--move の枝が消えている"
    assert resched.count("撃っていないので、控えも直しません") >= 2, \
        "--spread / --compact のどちらかに枝がありません"
    assert "撃っていないので、控えも直しません" in pool, \
        "pool_drain --apply に枝がありません"


def test_幻を数える道具が在って_配線されている():
    """**撃たれない道具の効果はゼロ**なので、`status.py` から呼ばれていることまで見る。"""
    assert (ROOT / "src" / "ledger_truth.py").is_file(), \
        "src/ledger_truth.py が消えています（幻を数えるのはここだけです）"
    status = (ROOT / "scripts" / "status.py").read_text(encoding="utf-8")
    assert "print_ledger_truth()" in status, \
        "status.py が print_ledger_truth() を呼んでいません。" \
        "**塞いだ穴の在庫は、鳴らなければ誰も直しません**"
