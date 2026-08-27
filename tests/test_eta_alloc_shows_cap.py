"""`--alloc` は**天井の遠さで順位を決める**。ならば天井を印字すること。

## この検査が守っているもの（2026-08-27 に踏んだ）

`scripts/eta.py` の `alloc_search` は docstring で自分でこう言っています ——
**「その2本の順位は天井の遠さだけで決まっています」**。
それなのに、2026-08-27 まで **`--alloc` の出力に天井が1つも出ていませんでした。**

同じ日の同じプログラムが、軌跡の側ではこう印字しています:

    天井 `sub_rate` ×3,231.43 …… 登録率 100%（定義上の上限）← **実測の天井ではありません**
    天井 `density`  ×1.00 …… **引き代なし。この腕は何をしても上の日付を1日も動かしません**

`--alloc` の側では、その `density` が `per_video` と**同じ日付で同着**に並び、
「引き代0」とは1文字も書いてありませんでした。実測 `data/runs.jsonl` の
直近8件の ship のうち **2件が `lever=density`**（同じ行に `"lever_cap": 1.0`）。
**機械は知っていて、選ぶ側には見えていませんでした。**

だからここで固定するのは3つだけです:

1. 天井 ×1.00 の腕は「**引き代なし**」と名指しされる
2. 天井が実測でない腕は「**実測の天井ではありません**」と名指しされる
3. **正本は1か所**（`cap_lines`）。軌跡側と `--alloc` 側で別々に書かない
   —— この輪は「同じことを2か所が別々に言っていて、片方が古い」で
   何度も外しています（`docs/JOURNAL.md`）。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import scripts.eta as eta  # noqa: E402


ARMS = {
    "per_video": {"cap": 3.18, "cap_why": "実測の天井 1,891（1本あたり再生）",
                  "cap_measured": True, "n": 10},
    "sub_rate": {"cap": 3231.43, "cap_why": "登録率 100%（定義上の上限）",
                 "cap_measured": False, "n": 2},
    "rpm": {"cap": 64.53, "cap_why": "実測の混ざり方 ¥20.4 → ¥1,319",
            "cap_measured": False, "n": 1},
    "density": {"cap": 1.0, "cap_why": "1日に再生が付く上限 10本 ÷ いま 20.1本/日",
                "cap_measured": True, "n": 4},
}


def _lines() -> dict[str, str]:
    return {k.split("`")[1]: k for k in eta.cap_lines(ARMS)}


def test_引き代のない腕は名指しされる() -> None:
    line = _lines()["density"]
    assert "引き代なし" in line
    assert "1日も動きません" in line


def test_実測でない天井は名指しされる() -> None:
    for arm in ("sub_rate", "rpm"):
        assert "実測の天井ではありません" in _lines()[arm], arm


def test_実測の天井には何も足さない() -> None:
    """**印を付けすぎると、印が意味を失います。**"""
    line = _lines()["per_video"]
    assert "実測の天井ではありません" not in line
    assert "引き代なし" not in line


def test_引き代0が優先される() -> None:
    """×1.00 かつ「実測」の腕は、**引き代の話**を先に出すこと。

    `density` は `cap_measured=True`（10本/日 は実測）ですが、
    そこで言うべきは「測った天井です」ではなく
    **「立てても日付が動きません」**のほう。
    """
    line = _lines()["density"]
    assert "引き代なし" in line
    assert "実測の天井ではありません" not in line


def test_天井の無い腕は行を出さない() -> None:
    assert eta.cap_lines({"x": {"n": 0}}) == []
    assert eta.cap_lines({"x": {"cap": 2.0}}) == []       # cap_why が無い


def test_正本は1か所_軌跡側も同じ関数を通る() -> None:
    """**書き写しを2つ作らないこと。**

    軌跡側（`_trajectory_lines`）が自前で `天井 \\`{lever}\\`` を組み立てて
    いたら、この検査が落ちます —— 片方だけ直して片方が古くなる形は、
    この輪がいちばん多く踏んでいる壊れ方です。
    """
    src = (ROOT / "scripts" / "eta.py").read_text(encoding="utf-8")
    # 組み立てている f 文字列は `cap_lines` の中だけ
    assert src.count('天井 `{lever}` ×') == 1
