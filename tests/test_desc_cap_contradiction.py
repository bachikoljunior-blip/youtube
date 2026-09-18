"""**説明欄が、自分の書いた条件と矛盾していないか**の検査（2026-09-18 23:5x・optimizer・Opus 5）。

**なぜこの検査が在るか**（この回に踏んだ実測）: 09/17 の年金の連作は、説明欄 **12か所**に
「基礎控除104万円（令和8年分・**合計所得132万円以下**の人。国税庁 タックスアンサー No.1199）」と
書いていました。ところが **毎月25万円 の本人は 合計所得190万円** ＝ **その1行が自分自身と矛盾**しています。

**数（104万円）のほうは正しい** —— 国税庁 No.1199 の表で 令和8年分の 104万円 のセルは
`rowspan=3` で 3段（132万以下／132万超336万以下／336万超489万以下）をまたぐので、
正しい境目は **489万円** です。**1段目だけを読んで条件を書いた**のが誤りでした。

**＝ どの門にも映らない穴でした**: `critique` は `say`／`show`／`sub` しか読まず、
`lint` の数の門は説明欄を見ず、数そのものは合っているので `crosscheck` も鳴りません。

守るのは 2つ:
  (1) **同じ行の中で** 条件（合計所得N万円以下）と 所得M万円 が矛盾したら鳴ること（M > N）
  (2) **「合計所得」そのものを 所得M万円 として数えないこと**（さもないと全行が鳴る）
"""
from __future__ import annotations

from studio import script

CAP = "・所得{inc}万円 − 社会保険料控除315,199円 − 基礎控除104万円（令和8年分・合計所得{cap}万円以下の人。国税庁 タックスアンサー No.1199）"
MARK = "説明欄の 1行 が自分と矛盾"


def _warn(desc: str) -> list[str]:
    s = script.load("2026-09-20-nenkin-tedori-hayamihyou")
    s.description = desc
    return [w for w in s.warnings() if MARK in w]


def test_条件より大きい所得が同じ行に在れば鳴る():
    """09/17 の連作が実際に書いていた行そのもの（190万 > 132万）。"""
    assert len(_warn(CAP.format(inc=190, cap=132))) == 1


def test_直した行では黙る():
    """正しい境目 489万円 に直した行（190万 ≦ 489万）。"""
    assert _warn(CAP.format(inc=190, cap=489)) == []


def test_条件の中に収まっていれば黙る():
    """同じ連作の 20万円 の本（130万 ≦ 132万）＝ 元から矛盾していない側。"""
    assert _warn(CAP.format(inc=130, cap=132)) == []


def test_合計所得そのものを所得として数えない():
    """`合計所得132万円以下` の 132 を「所得」側に数えると、全行が自分で鳴ってしまう。"""
    assert _warn("・合計所得132万円以下の人の基礎控除は104万円") == []


def test_行をまたいだ組み合わせでは鳴らない():
    """空振りを安くするため、見るのは **同じ行の中だけ**（覆る条件 (1)）。"""
    assert _warn("・合計所得132万円以下の人\n・所得190万円の人の計算") == []


def test_いまの台本は1本も鳴らない():
    """この回に 12か所 を直したので、`data/studio/scripts/` は 0件 のはず（回帰）。"""
    import glob
    import os

    bad = []
    for f in sorted(glob.glob("data/studio/scripts/*.json")):
        s = script.load(os.path.basename(f)[:-5])
        bad += [(f, w) for w in s.warnings() if MARK in w]
    assert bad == [], bad
