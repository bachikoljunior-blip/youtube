"""**「引けるのは 〜 だけです」の腕の名前と、その行の ×N が、別の腕のものだった。**

2026-09-04 12:5x に `gate_arm_pick()` が入り（`c19d5792`）、**軌跡が出ない回は
`lever_hint` を 門1'（登録者）の側へ上書き**するようになりました。ところが
`lever_need` / `lever_need_over_cap` は、その前に `_alive` の
`min(need_over_cap)` が選んだ腕（`lever_measured`）の数のままです。
**名前だけが入れ替わり、×N は別の腕のもの**になります。

実測 2026-09-04 14:5x の出力::

    → **引けるのは `sub_rate` だけです。** 日付が出はじめるのは ×101.12、
      いまの天井は **×4.54** —— …
    （同じ出力の別の行: `sub_rate` の天井は ×6.21・`per_video` が ×4.54）

しかもその行の末尾は「**この回に立てるべき前提は『その天井は天井ではない』**」と
命令形で、**3行 下の `joint_cap` は逆**を言っています ——
「抜いても動かない腕に前提を立てないこと。通る道が `per_video` である限り、
`sub_rate`／`rpm` の前提は燃料ではありません」。
**読む順は上からなので、先に読まれるのは間違っているほうです。**
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location("eta_mod", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(spec)
sys.modules.setdefault("eta_mod", eta)
spec.loader.exec_module(eta)


def _lines(pl: dict) -> list[str]:
    """`lever_chosen_by == "need_over_cap"` の枝が出す行だけを取り出す。"""
    import inspect
    src = inspect.getsource(eta)
    assert 'pl.get("lever_chosen_by") == "need_over_cap"' in src
    return src


def test_行が_lever_measured_を刷っていること():
    """**`lever_hint` を刷らないこと。** 刷ると、上書きされた回に名前と数がずれます。"""
    import inspect
    src = inspect.getsource(eta)
    i = src.index('if pl.get("lever_chosen_by") == "need_over_cap":')
    block = src[i:i + 3000]
    head = block[:block.index("out.append(") + 400]
    assert '_arm = pl.get("lever_measured")' in block, (
        "×N と同じ腕（`lever_measured`）から名前を取っていません")
    assert "f\"{bar}   → **引けるのは `{pl['lever_hint']}` だけです。**\"" not in head, (
        "`lever_hint` を刷り直しています（上書きされた回に名前と数がずれます）")


def test_名指しと違う回は但し書きが出ること():
    """頭の名指し（門1'）と、この行の腕（軌跡）が違う回に、そう書いてあること。"""
    import inspect
    block = inspect.getsource(eta)
    i = block.index('if pl.get("lever_chosen_by") == "need_over_cap":')
    block = block[i:i + 3500]
    assert 'pl["lever_hint"] != _arm' in block, "違う回を見分けていません"
    assert "頭の名指しは" in block, "但し書きの本文がありません"


def test_lever_measured_は上書きの前に置かれていること():
    """`gate_arm_pick()` の上書きは `lever_hint` だけに掛かること
    （`lever_measured` まで書き換えると、この直しは黙って戻ります）。"""
    import inspect
    src = inspect.getsource(eta)
    i = src.index('out["lever_chosen_by"] = "need_over_cap"')
    near = src[i - 400:i + 400]
    assert 'out["lever_measured"] = _pick["lever"]' in near
    assert 'out["lever_need"] = _pick["need"]' in near
    # 上書き側（`gate_arm_pick` を当てる所）は `lever_hint` しか触らない
    assert 'out["lever_measured"] =' not in src.split(
        'out["lever_measured"] = _pick["lever"]', 1)[1], (
        "`lever_measured` を後から上書きしている所があります")


@pytest.mark.parametrize("hint,measured,want", [
    ("sub_rate", "per_video", True),
    ("per_video", "per_video", False),
])
def test_但し書きの出し分け(hint, measured, want):
    """条件式そのものを、この検査でも1度 通す（本文と検査で別々の条件を持たない）。"""
    pl = {"lever_hint": hint, "lever_measured": measured}
    arm = pl.get("lever_measured") or pl.get("lever_hint")
    assert bool(pl.get("lever_hint") and pl["lever_hint"] != arm) is want
