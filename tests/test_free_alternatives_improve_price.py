"""**`improve` の値札を、最後まで書くこと**（`run_marker._improve_swap_note`）。

## なぜこの検査が要るか（2026-09-01 11:3x。**前の回が名指しして、直せなかった1件**）

`free_alternatives()` の `improve` の行は「**0単位**」としか書いていませんでした。
**0単位 で買えるのは `src/calc/` や `src/script_writer` を直すところまで**で、
**焼き直した本を同じ枠へ差し替える2手**（`reschedule.py --unschedule` → `--move`）は
`videos.update` ×2 ＝ `next_slot.SWAP_UNITS` 単位、**日枠が要ります。**

**この一覧は `fix` の連の門が読む唯一の入力です**
（`tests/test_fix_gate_free_alternatives.py`）。値札が半分だと、
**門は「0単位で撃てる手が在る」と言って `fix` を止め、止められた側が向かった先は
「良くしたのに本には入らない」**になります。

## 実測（2026-09-01）

きょうだい2回が 09:04（`guard_grid`）と 10:08（`compound_grid`）に
`src/calc/hendo.py` を厚くして `improve` で ship しましたが、
**その2件はどちらも今夜 22:00 に出る本に入っていません** ——
焼いたのは 08/31 20:26 で、差し替えの2手が 403 だったからです。
11:2x の `split_grid` を入れて **4件**。

同じ repo の `next_slot.swap_cost_lines()` は、この代金を**正しく印字しています。**
ズレていたのは門が読むほうの一覧だけでした。

## 覆る条件

- `reschedule` が `videos.update` を使わない道を持ったら、この検査ごと落とすこと
  （`next_slot.swap_cost_lines()` の同じ「覆る条件」と一緒に）
- **次に公開される1本が無い窓では `improve` の行そのものが出ません。**
  そのときこの検査は飛ばします（`free_alternatives()` の作り）
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import run_marker  # noqa: E402

from src import next_slot  # noqa: E402


def _improve_line() -> str | None:
    for line in run_marker.free_alternatives():
        if line.startswith("`improve`"):
            return line
    return None


def test_improveの行が0単位だけで終わらない() -> None:
    line = _improve_line()
    if line is None:
        return  # 次の枠が無い窓（`free_alternatives()` の作り）
    assert "コードの側だけ" in line, (
        "`improve` の値札が「0単位」で終わっています —— "
        "焼き直した本を同じ枠へ差し替える2手は日枠が要ります"
    )
    assert f"{next_slot.SWAP_UNITS}単位" in line, (
        f"差し替えの2手の単位（{next_slot.SWAP_UNITS}）が行に出ていません"
    )
    assert "videos.update" in line


def test_単位はnext_slotから引いている() -> None:
    """**同じ数を2か所に書かないこと。**

    `next_slot.SWAP_UNITS` を直したら、この行も一緒に動くこと。
    """
    src = (ROOT / "scripts" / "run_marker.py").read_text(encoding="utf-8")
    assert "next_slot.SWAP_UNITS" in src, (
        "差し替えの単位を run_marker 側に写しています —— "
        "`next_slot.SWAP_UNITS` から引くこと"
    )


def test_枠の状態を言い分けている() -> None:
    """枠が在る窓と、403 の窓で、行の後半が変わること。"""
    line = _improve_line()
    if line is None:
        return
    out, _ = run_marker.quota_is_out()
    if out:
        assert "403" in line, "枠が尽きているのに 403 と言っていません"
        assert "オーナー規則1" in line, (
            "焼き直しだけ撃つと同じ枠に2本 出ることを言っていません"
        )
    else:
        assert "枠が在ります" in line


def test_improveを止める行にしないこと() -> None:
    """**規則3（出る瞬間まで良くし続けろ）を、値札で殺さないこと。**

    足したのは値札の後半だけで、`improve` は一覧に残り続けます ——
    残らないと `fix` の連の門が免除に倒れます。
    """
    kinds = [line.split("`")[1] for line in run_marker.free_alternatives()]
    if "improve" not in kinds:
        # 次の枠が無い窓。そのときは upload も出ていないはず
        assert "upload" not in kinds
        return
    assert "premise" in kinds, "0単位 の手が一覧から消えています"


def test_帳面が読めない回でも落ちない() -> None:
    """**推測で手を止めないこと**（`swap_cost_lines()` と同じ姿勢）。"""
    note = run_marker._improve_swap_note()
    assert isinstance(note, str)
