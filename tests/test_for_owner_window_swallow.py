"""`scripts/for_owner.py` —— **窓が、手前の窓に飲み込まれていないこと**。

**2026-09-19 05:5x・optimizer・opus・1周 1体。** derivation は `docs/JOURNAL.md` 同刻。

**なぜこの検査が在るか（実物を踏んだ・commit `6308651e`）**:
その回は 09/19 09:00 の窓へ 【3】（handle の変更）を足しました。**足した字が、
次の窓の見出し `### 出す 2026-09-19 20:00〜21:00 JST` を上書きして消しました。**
見出しが消えると、その窓の本文（`>` の塊）は **手前の窓の本文の続き**になります:

    親が 09:00 に出す  1件 → **4件**（頭の字は「お願いは3つ、合わせて3分です」のまま。
                       飲み込まれた 4件目 は 15〜20分・「なぜ、いま一番これなのか」つき
                       ＝ 同じ文の中に「いちばん大事」が 2つ 立つ）
    親が 20:00 に出す  1件 → **0件**（窓がもう無い）

**`--check` は 3つ とも通していました**（重なり無し・長すぎ無し・空の本文 無し）。
**窓が 1つ 減ったことを見る目が、どこにも在りませんでした。**

**陽性対照つき**（落ちるまで撃つ）: 壊れた形で **必ず** NG が出ること・
健全な `docs/FOR_OWNER.md` では **1件も** 出ないことの両方を見ます。
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "for_owner", ROOT / "scripts/for_owner.py")
for_owner = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(for_owner)

_A = "### 出す 2026-09-19 09:00〜10:00 JST"
_B = "### 出す 2026-09-19 20:00〜21:00 JST"


def _md(body: str) -> str:
    return "## 出す\n\n" + body + "\n\n## 出した（記録）\n"


def test_健全な2つの窓は問題を出さない():
    """**陰性対照** —— 見出しが在れば、塊は窓ごとに 1つずつ。"""
    md = _md(f"{_A}\n\n> あ\n\n{_B}\n\n> い\n")
    blocks, problems = for_owner.parse(md)
    assert len(blocks) == 2
    assert problems == []


def test_見出しが消えた窓は飲み込みとして名指しされる():
    """**陽性対照** —— `6308651e` が作った形そのもの（`_B` の見出しだけ落とす）。"""
    md = _md(f"{_A}\n\n> あ\n\n> い\n")
    blocks, problems = for_owner.parse(md)
    assert len(blocks) == 1, "窓が 1つ に減っていること（＝踏んだ形）"
    assert len(problems) == 1, problems
    assert "飲み込んだ" in problems[0]
    assert _A in problems[0], "どの窓が飲み込んだ側かを名指しすること"


def test_飲み込まれた本文は手前の窓から出てしまう():
    """**なぜ害か** —— 出ないのではなく、**別の刻に、別の頭の字で出ます**。"""
    md = _md(f"{_A}\n\n> あ\n\n> い\n")
    blocks, _ = for_owner.parse(md)
    assert "い" in blocks[0].body, "飲み込まれた側が手前の窓の本文に混ざること"


def test_引用の空行でつないだ1塊は問題にしない():
    """**覆る条件 (1)** —— `>` だけの行でつなげば 1塊 のまま書けます。"""
    md = _md(f"{_A}\n\n> あ\n>\n> い\n")
    _, problems = for_owner.parse(md)
    assert problems == []


def test_いまの_FOR_OWNER_は飲み込みを持たない():
    """**実物**（この検査を足した回に直した側）。"""
    md = (ROOT / "docs/FOR_OWNER.md").read_text(encoding="utf-8")
    blocks, problems = for_owner.parse(md)
    swallow = [p for p in problems if "飲み込んだ" in p]
    assert swallow == [], swallow
    assert all(for_owner.quote_runs(b.lines) == 1 for b in blocks)


def test_quote_runs_は塊を数える():
    assert for_owner.quote_runs([]) == 0
    assert for_owner.quote_runs(["> a", "> b"]) == 1
    assert for_owner.quote_runs(["> a", "", "> b"]) == 2
    assert for_owner.quote_runs(["> a", "素の行", "> b"]) == 2
    assert for_owner.quote_runs(["> a", ">", "> b"]) == 1
