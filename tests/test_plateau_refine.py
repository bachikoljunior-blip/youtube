"""**「◯◯から上は同じ」の◯◯は、掃引の格子の点でした。**（2026-08-27）

## なぜ

`_classify` の頭打ちは「後ろの3分の1が動かない」で判定し、返す `止まる x` は
**その3分の1の先頭にある格子の点**でした。**そこは「平らが始まった点」ではなく、
「平らを判定するのに使った窓の左端」**です。平らが窓より左から始まっていれば、
`止まる x` はそのぶん右へずれます。

実物（2026-08-27）: `jutaku.relief_room（住民税から引ける上限）` は
「`taxable` が **7,135,242** から上は 97,500 で止まる」と出ていました。
**本当の境目は 1,950,000円**（住民税からの控除上限 97,500 ÷ 課税総所得の5%）で、
**3.7倍 のずれ**です。しかも **7,135,242 は `keihi` の掃引にも同じ数で出ます**
（`keihi.aoiro_vs_keihi（事業税の差）… profit 7,135,242 から上は 22,500`）——
**同じ数が別々の表に出るなら、それは制度の境目ではなく格子の点**という合図でした。

**同じ形は 2回 直っています**（`崖` → `_refine_cliff`・2026-08-27／
`帯` → 08/26 の「帯 age 46〜62」の名指し）。**`頭打ち` にだけ、
その刻み直しがありませんでした。3周 続けて同じ所を踏んでいます。**

## 覆る条件

`_classify` の頭打ちの窓（後ろの3分の1）を、平らの始まりから直接 求める形に
書き換えたら、この検査の前半（左へ伸ばす）は要りません。
後半（格子の間を刻み直す）は、格子が有限であるかぎり要ります。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import section_sweep as ss  # noqa: E402


def test_平らの始まりまで左へ伸ばす() -> None:
    """窓の左端ではなく、**実際に平らが始まった格子の点**を返すこと。"""
    xs = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]
    ys = [1.0, 2.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0]
    hit = ss._classify(xs, ys)
    assert hit is not None
    shape, detail = hit
    assert shape == "頭打ち", shape
    # 後ろ3分の1の先頭は xs[6]=7.0。**平らは xs[2]=3.0 から始まっている。**
    assert detail["止まる x"] == 3.0, detail
    assert detail["止まる x の手前"] == 2.0, detail


def test_格子の間を刻み直して止まり際を狭める() -> None:
    """`(手前, 止まる x]` を刻み直し、**節に書ける幅**まで詰めること。"""
    def f(x: float) -> float:
        return min(x, 10.0)      # 本当の止まり際は 10.0

    # 格子は 0, 8, 16, 24 …… ＝ 止まり際は「16 から上」と粗く出る側
    xs = [0.0, 8.0, 16.0, 24.0, 32.0, 40.0]
    ys = [f(x) for x in xs]
    hit = ss._classify(xs, ys)
    assert hit is not None
    shape, detail = hit
    assert shape == "頭打ち", shape
    assert detail["止まる x"] == 16.0, detail

    out = ss._refine_plateau(f, {}, "x", 0.0, "", detail)
    # 8等分（刻み 1.0）なので、10.0 と 9.0 で挟めるところまで詰まる
    assert out["細かくした止まる x"] == 10.0, out
    assert out["細かくした止まる x の手前"] == 9.0, out


def test_刻めなかった回は黙って通さない() -> None:
    """刻めなかったことと、格子が正しかったことは別です。"""
    def boom(x: float) -> float:
        raise ValueError("だめ")

    out = ss._refine_plateau(boom, {}, "x", 0.0, "",
                             {"止まる x": 16.0, "止まる x の手前": 8.0,
                              "止まった値": 10.0})
    assert "止まり際を刻めなかった" in out, out


def test_手前の点が無ければ刻まない() -> None:
    out = ss._refine_plateau(lambda x: x, {}, "x", 0.0, "",
                             {"止まる x": 1.0, "止まった値": 1.0})
    assert "止まり際を刻めなかった" in out, out


def test_刻み直した欄は_xかyのどちらかとして宣言されている() -> None:
    """宣言しない欄が出ると、行番号のまま印字されます（`X_KEYS` / `Y_KEYS`）。"""
    for k in ("止まる x の手前", "細かくした止まる x", "細かくした止まる x の手前"):
        assert k in ss.X_KEYS, k
    assert "止まり際を刻めなかった" in ss.Y_KEYS


def test_刻み直したxは既出の判定に使わない() -> None:
    """元の `止まる x` を**狭めたもの**で、別の主張ではありません。"""
    for k in ("細かくした止まる x", "細かくした止まる x の手前", "止まる x の手前"):
        assert k not in ss.NAMING_X_KEYS, k
    assert "止まる x" in ss.NAMING_X_KEYS
