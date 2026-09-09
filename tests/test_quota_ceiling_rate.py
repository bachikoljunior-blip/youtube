"""`ceiling_rate()` —— 閉じた輪が出せる最速と、床に従う見込みを疑う条件。

2026-09-09 23:5x・optimizer・Opus。

**この検査が守っているのは着地の数ではありません。**
`reach_at_reset()` の「床に従えば 99.8%」は **`per_lap` にも遅れにも動かない**ので、
その数を見張っても見込みが壊れる瞬間は見えません。壊れるのは
**1周が最短（`FLOOR_MIN_CLAMP` ＋ 遅れ）になっても要る速さに追いつかなくなったとき**で、
`ceiling_rate()` がその最速を返します。門は **余裕 3.0倍**（144点 を掃いて引いた・関数の註）。

**陽性対照**（壊したら落ちるところまで撃った・METHOD §5「教訓の形 3つ目」）:
天井の式から**遅れの項を落とす**／`FLOOR_MIN_CLAMP` を見なくする／`per_lap` に比例しなくする、
のどれでも赤になります。**最初に書いた検査は 1つ目を素通りしました**（底だけで数えた式でも通った）
＝ 検査のデータのほうを直してから通しています（遅れが効く点を帯に入れた）。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import quota  # noqa: E402

# 掃いたときの点（`ceiling_rate()` の註）。used・left はその回の実測。
USED, LEFT = 52.4, 55.0
REQ = (100.0 - USED) / LEFT
LAG = 2.878


def test_ceiling_counts_the_lag_not_only_the_floor():
    """**天井は「1周の最短 ＝ 底 ＋ 遅れ」で割る。** 遅れを落とすと過大に出る。

    ここが陽性対照の 1つ目（最初の検査はこれを素通りした）。
    """
    got = quota.ceiling_rate(0.6, lag_min=LAG)
    assert got == pytest.approx(0.6 * 60.0 / (quota.FLOOR_MIN_CLAMP + LAG))
    # 底だけで数えた式（＝ 落とした形）とは、はっきり違う値であること。
    floor_only = 0.6 * 60.0 / quota.FLOOR_MIN_CLAMP
    assert got < floor_only * 0.85, (got, floor_only)
    # 遅れが増えるほど天井は下がる（単調）。
    seq = [quota.ceiling_rate(0.6, lag_min=g) for g in (0.0, 5.0, 10.0, 20.0)]
    assert seq == sorted(seq, reverse=True), seq


def test_ceiling_is_proportional_to_per_lap():
    for per_lap in (0.2, 0.6, 1.2):
        assert quota.ceiling_rate(per_lap, lag_min=LAG) == pytest.approx(
            per_lap * 60.0 / (quota.FLOOR_MIN_CLAMP + LAG))
    assert quota.ceiling_rate(1.2, lag_min=LAG) == pytest.approx(
        2.0 * quota.ceiling_rate(0.6, lag_min=LAG))
    assert quota.ceiling_rate(0.0) is None
    assert quota.ceiling_rate(0.6, lag_min=0.0, floor_min=0.0) is None


def test_margin_gate_3x_separates_truncation_from_a_real_shortfall():
    """**門 3.0倍**: 越えている点では、不足は最後の1周の切り捨てだけ（144点 で 0件 の反例）。"""
    checked = 0
    for per_lap in (0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0):
        for lag in (0.0, 1.0, 2.0, LAG, 4.0, 5.0, 7.0, 10.0, 15.0, 20.0, 30.0, 40.0):
            margin = quota.ceiling_rate(per_lap, lag_min=lag) / REQ
            reach = quota.reach_at_reset(USED, LEFT, per_lap, lag_min=lag)
            if margin >= 3.0:
                checked += 1
                assert (100.0 - reach) <= per_lap + 1e-9, (per_lap, lag, margin, reach)
            if margin < 1.0:
                assert reach < 99.0, (per_lap, lag, margin, reach)
    assert checked >= 50, checked


def test_landing_is_flat_so_the_staged_per_lap_is_not_worth_building():
    """**`reach_at_reset()` の覆る条件 (1) を閉じた当のもの。**

    Fable が尽きて `hourly` も opus になると `per_lap` は 0.600 → 約 0.540（軽くなる）。
    段で分けて回しても、分けない答えとの差は最後の1周ぶんに収まる（門は 5 ポイント）。
    """
    flat = quota.reach_at_reset(USED, LEFT, 0.600, lag_min=LAG)

    # 段で分けて回す: 残り 27時間（Fable が尽きる見込み）までは 0.600、その先は 0.540。
    used, left = USED, LEFT
    for _ in range(10000):
        if used >= 100.0 or left <= 27.0:
            break
        fwd = (100.0 - used) / left
        step = (max(quota.FLOOR_MIN_CLAMP, 0.600 / fwd * 60.0) + LAG) / 60.0
        if step > left - 27.0:
            break
        left -= step
        used += 0.600
    staged = quota.reach_at_reset(used, left, 0.540, lag_min=LAG)

    assert abs(staged - flat) < 5.0, (staged, flat)
    assert abs(staged - flat) <= 0.6, (staged, flat)
    # **向きは「届きやすい」ではない**（`landing()` が書いていた向きの陽性対照）。
    assert staged <= flat, (staged, flat)


def test_pace_exposes_the_margin():
    """`pace()` が余裕を出していること（出さなくなったら、この註ごと読めなくなる）。"""
    p = quota.pace()
    if p is None or not p.get("per_lap"):
        pytest.skip("目盛りが無い")
    assert p["reach_ceiling_rate"] == pytest.approx(
        quota.ceiling_rate(p["per_lap"], p["reach_lag_min"]))
    assert p["reach_ceiling_margin"] == pytest.approx(
        p["reach_ceiling_rate"] / p["forward_rate"])
