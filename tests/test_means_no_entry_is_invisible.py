"""**`docs/MEANS.md` の項が、1件も `status.py` から消えないこと。**

## なぜこの検査が要るか（2026-08-26・最適化の回）

`scripts/status.py` の `print_means()` は、状態の一行を
**未着手／未検討 → 保留 → 却下／待ち** の3つに振り分け、
**どれにも当たらなかった項を黙って捨てていました。**

実測（2026-08-26 18:2x）: **22件のうち 16件（73%）が印字されていません。**
そのあいだ同じ節は「**未着手が0件です。これは達成ではありません**」と
出していました —— **台帳は持っていて、この節が見せていなかった**という、
同じ関数の中に2回 書いてある壊れ方の3回目です（M3・M11 に続く）。

実害: **M22（チャンネルのホーム＝腕 `sub_rate`）が 08/20 から 6日 消えていました。**
そのあいだに詰まりの中身は「この環境の判定」から「API の日枠」へ変わっており、
**叩き直せば通る状態**でしたが、どの回の目にも入っていません。

## この検査が守っているのは「札を足さないこと」です

前の2回は **札を1つ足して**塞ぎました（保留・却下）。その形だと
**次に出る新しい言い回しがまた丸ごと落ちます。** だから
`print_means()` は落ちた項を**落ちたまま数えて出す**ようにしてあります。
**この検査は、その受け皿が消えていないことだけを見ます。**

## 覆る条件

`docs/MEANS.md` の状態欄が自由文をやめ、決まった語彙になったら
（＝振り分けが全件を必ず捕まえられるようになったら）この検査は要りません。
そのときは「全件が3つのどれかに入る」を代わりに置くこと。
"""

from __future__ import annotations

import io
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import status  # noqa: E402


def _entries() -> list[str]:
    text = (ROOT / "docs" / "MEANS.md").read_text(encoding="utf-8")
    return re.findall(r"^### (M\d+)\. ", text, re.M)


def test_全部の項が印字に名前を出す() -> None:
    """**1件でも消えたら落ちる。** 振り分けの札を増やしても、増やさなくてもよい。"""
    buf = io.StringIO()
    with redirect_stdout(buf):
        status.print_means()
    out = buf.getvalue()

    missing = [code for code in _entries()
               if not re.search(rf"^\s+{re.escape(code)} ", out, re.M)]
    assert not missing, (
        f"`docs/MEANS.md` の {len(missing)}件 が `status.py` から消えています: "
        f"{'・'.join(missing)}。**札を足して塞がないこと** —— "
        "どの札にも当たらなかった項を、落ちたまま数えて出すこと"
        "（`print_means()` の `unlabelled`）"
    )


def test_受け皿そのものが消えていない() -> None:
    """**札を3つに戻す改修が入ったら、ここで止める。**"""
    src = (ROOT / "scripts" / "status.py").read_text(encoding="utf-8")
    assert "unlabelled" in src, (
        "`print_means()` の受け皿（どの札にも当たらない項）が消えています。"
        "**2026-08-26 に 16/22件 が消えていたのは、この受け皿が無かったからです**"
    )
