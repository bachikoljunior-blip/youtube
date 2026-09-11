"""**「床がいつ歯止めに当たるか」も印字すること。しかも門が読む側で数えること**
（2026-09-12 03:5x・optimizer・Opus。**API 0単位**）。

**踏んだ形**: 00:5x が `short_words` に足したのは「**当たった**回の 3行目」だけで、
**当たる手前の回は黙っていました**。その空いた所を、METHOD §7「いまの数」が
**「この枠では 05:0x ごろの見込み」という手で運んだ数**で埋めていました
（§5 教訓の形 7つ目 ＝ 覆る条件を註に書いたら、それを読む印字も一緒に作ること）。

**その数は、門が読まない側の数でした。** 出どころ（JOURNAL 00:5x）は
`pace()` を**先の刻で撃った**もので、`now` だけが進み `used_now` は進みません
（`carry_mode` が `laps` の枠では、未来に立つ周を知りようがない）＝
`--pace` が同じ画面で書いている「**時間では運びません**・枠を食うのは周」の当のもの。
**向きも逆**で、00:5x の「周が積まれればもっと早い」に対し、
`floor_raw = per_lap * left * 60 / (100 - used)` は **`used` について増加**します。

**この検査が固定するのは 4つ**:
  (a) `raw_now` は `pace()` と同じ式（**歯止めを掛ける前**）で出ていること
  (b) **向き** —— `used` を上げると床は上がる（＝「周が積まれれば早い」は偽）
  (c) 床に従う輪では当たらない盤と、当たる盤の**両方**で `clamp_eta` が正しく答えること
  (d) 当たった回（`floor_clipped == "min"`）は `clamp_words` が**黙る**
      （そこは `short_words` の 3行目 の持ち場 ＝ 同じ門を 2か所 に置かない）

**きょうの状態は当てません**（§5 教訓の形 6つ目）—— 盤はその場で作り、実物の `pace()` は見ません。

**陽性対照**（`.pyc` を消してから撃った・落ちる件数）:
    `clamp_eta` を「周を積まない側」（`frozen_hours`）で答える形にする        **2件**
    `clamp_words` が `floor_clipped == "min"` でも喋る形にする                **1件**
    `clamp_eta` の輪から `used += per_lap` を外す（時間だけ進める）            **2件**
    `raw_now` を歯止め後（`max(FLOOR_MIN_CLAMP, ...)`）にする                 **1件**
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import quota  # noqa: E402


# 盤（**実物の枠を見ない** ＝ 日が経っても腐らない）。
_LAG = 1.66
_PER_LAP = 0.546
# 当たらない盤: 2026-09-12 03:5x の実物と同じ形（床に従うと 7周 でリセットが先）。
_USED_OPEN, _LEFT_OPEN = 95.64, 3.42
# 当たる盤: 残りが短く、1周も回らないうちに生の床が歯止めを割る。
_USED_TIGHT, _LEFT_TIGHT = 95.64, 1.00


def _raw_floor(used: float, left: float, per_lap: float) -> float:
    """`pace()` と同じ式の、**歯止めを掛ける前**の床（分）。"""
    return per_lap / ((100.0 - used) / left) * 60.0


def test_いまの生の床は_pace_と同じ式で_歯止めを掛ける前の数() -> None:
    """**(a)** —— 返すのは `floor_raw` の側（`floor_min` ではない）。"""
    v = quota.clamp_eta(_USED_TIGHT, _LEFT_TIGHT, _PER_LAP, lag_min=_LAG)
    assert v is not None
    want = _raw_floor(_USED_TIGHT, _LEFT_TIGHT, _PER_LAP)
    assert abs(v["raw_now"] - want) < 1e-9
    # 歯止めの**下**の盤なので、掛けた後の数とは必ず割れる。
    assert v["raw_now"] < quota.FLOOR_MIN_CLAMP


def test_向き_周を積むと床は上がる_ゆえに当たるのは遅くなる() -> None:
    """**(b)** —— JOURNAL 00:5x の「周が積まれればもっと早い」は逆。"""
    base = _raw_floor(_USED_OPEN, _LEFT_OPEN, _PER_LAP)
    for du in (0.5, 1.0, 2.0):
        assert _raw_floor(_USED_OPEN + du, _LEFT_OPEN, _PER_LAP) > base
    # 残りを食う側だけが下げる（1周は両方を同時に動かす）。
    for dl in (0.5, 1.0):
        assert _raw_floor(_USED_OPEN, _LEFT_OPEN - dl, _PER_LAP) < base


def test_床に従う輪では当たらない盤を_当たらないと言うこと() -> None:
    """**(c)** —— 門が読む側（`reach_at_reset` と同じ輪）で数える。"""
    v = quota.clamp_eta(_USED_OPEN, _LEFT_OPEN, _PER_LAP, lag_min=_LAG)
    assert v is not None
    assert v["never"] is True
    assert v["laps"] is None
    # 輪の終わりでも歯止めの上に居る。
    assert v["raw_end"] >= quota.FLOOR_MIN_CLAMP
    # **同じ盤で、周を積まない側は「当たる」と言う** ＝ 側が答えを分けている。
    assert v["frozen_hours"] is not None and v["frozen_hours"] > 0


def test_当たる盤は_周の数と時間を返すこと() -> None:
    """**(c)** —— 当たる側も答えられること（片側しか通らない門にしない）。"""
    v = quota.clamp_eta(_USED_TIGHT, _LEFT_TIGHT, _PER_LAP, lag_min=_LAG)
    assert v is not None
    assert v["never"] is False
    assert v["laps"] == 0                     # いま既に歯止めの下
    assert v["hours"] == 0.0


def test_当たった回は_clamp_words_が黙ること() -> None:
    """**(d)** —— そこは `short_words` の 3行目 の持ち場（同じ門を 2か所 に置かない）。"""
    assert quota.clamp_words(_USED_OPEN, _LEFT_OPEN, _PER_LAP, _LAG,
                             floor_clipped="min") is None
    # 当たっていない回は喋る。
    line = quota.clamp_words(_USED_OPEN, _LEFT_OPEN, _PER_LAP, _LAG, floor_clipped="")
    assert line and "clamp_eta" in line
    assert "当たりません" in line
    # **周を積まない側は、註として並べるだけ**（判定の字には出さない）。
    head = line.splitlines()[0]
    assert "時間だけ進める" not in head
    assert "時間では運びません" in line


def test_数の無い枠では_None_を返すこと() -> None:
    """**空欄を「当たらない」と読ませない**（`short_words` の `miss` と同じ向き）。"""
    assert quota.clamp_eta(None, 3.0, 0.5) is None
    assert quota.clamp_eta(95.0, None, 0.5) is None
    assert quota.clamp_eta(95.0, 3.0, None) is None
    assert quota.clamp_eta(95.0, 3.0, 0.0) is None
    assert quota.clamp_eta(100.0, 3.0, 0.5) is None
    assert quota.clamp_words(None, 3.0, 0.5) is None
