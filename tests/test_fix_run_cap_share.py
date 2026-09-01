"""**`fix` の連のしきいは、`fix` 比の天井を `N/(N+1)` に固定します。**

## なぜ要るか（2026-09-01 夕・最適化の回に測って足した）

`scripts/run_marker.FIX_RUN_CAP` は 2026-08-31 16:45 に **4** で入りました。
理由は「連の長さは実測で 中央 2・平均 3.8。しきい 4 なら普通の連は触らない」——
**連の分布から決めていて、比のほうを見ていませんでした。**

連のしきい `N` が通せる最悪の並びは `fix`×N → 他1 → `fix`×N → 他1 …… で、
**`fix` 比の上限は `N/(N+1)`**。`N=4` なら **80%** です。
**門を入れる前の実測は 72.8%** でした（ship 217件・`fix` 158件）。

    **完全に効いても、直そうとしていた比を下げられない設計でした。**

実測（`fix_share()` をこの回に撃った）: 門の後は **83.2%**（107件中 89件）。
同じ窓の `kind="fix_gate"` は 27件、うち **19件 が `waived`**。

この検査が止めるのは1つだけです ——
**しきいを、その時点の `fix` 比より高い天井へ戻すこと。**
`N` を上げたくなったら、**先に `N/(N+1)` を出して、いまの比と比べること。**

**覆る条件**: `fix` 比が 30日 continuous で天井を十分に下回ったら
（＝ 門が縛っていない）、`FIX_RUN_CAP` ごと外してよく、この検査も要りません。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_marker as rm  # noqa: E402


def test_しきいの天井は比の形で出せる() -> None:
    """`N/(N+1)` が `fix_share()` の `cap_share` と一致すること。"""
    r = rm.fix_share()
    assert r["cap_share"] == rm.FIX_RUN_CAP / (rm.FIX_RUN_CAP + 1)


def test_門の天井が_門を入れる前の比より低いこと() -> None:
    """**この検査が本体です。**

    しきい `N` の天井（`N/(N+1)`）が、**門が無かったころの `fix` 比**より
    高いなら、その門は「完全に効いても比を下げられません」。
    `N=4` は 80% で、実測の 72.8% より高い ＝ **効かない門**でした。

    比較の相手は「門が入る前」の実測です（`FIX_GATE_AT` より前の ship）。
    **窓が細い回**（手元に履歴がほとんど無い・検査用の空の repo）は、
    比べる相手が無いので飛ばします。
    """
    r = rm.fix_share()
    before = r["before"]
    if before["n"] < 30:
        return                                  # 比べる相手がありません
    assert r["cap_share"] < before["share"], (
        f"しきい {rm.FIX_RUN_CAP} の天井は {r['cap_share']:.1%} で、"
        f"門が入る前の `fix` 比 {before['share']:.1%} より高い —— "
        "**完全に効いても、この比は下がりません。**"
        " しきいを上げるなら、先に `N/(N+1)` を出して比べること"
        "（この検査の docstring）"
    )


def test_覆る条件が撃てる形で在ること() -> None:
    """覆る条件1（比が下がらないまま `fix_gate` だけ増える）は、
    **手で数えるのではなく `fix_share()` で撃てること。**

    前の版は、この比を出す道具がどこにも無く、7日 のあいだ
    誰も判定できませんでした（比は 72.8% → 83.2% へ上がっていた）。
    """
    line = rm.fix_share_line()
    assert "`fix` 比" in line
    assert "天井" in line
