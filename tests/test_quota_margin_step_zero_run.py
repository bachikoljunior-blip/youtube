"""**余裕の列の「桁の下（0.000）の連」と、振れ幅の速い端の刻**（2026-09-13 22:5x・optimizer・Opus）。

**なぜこの検査が要るか**: `margin_step` の覆る条件 (1) は 09/11 08:4x から
「実測の 1周 が **3周 続けて 0.000** なら」と書いていましたが、
**その連を数える口がどこにもありませんでした** —— 印字は直近2点の 1つ だけ、
`docs/METHOD.md` §7「いまの数」は**毎周 上書き**で 1点 しか運ばない
＝ **原理的に引けない覆る条件**です（`quota.agree_run` が 09/12 01:4x に踏んだのと同じ族）。

**この検査が守るもの**:
 (1) 連は道具が数える（`step_zero_run`）。
 (2) 連の窓は**列の全部**（印字の 8周 ではない）。
 (3) 「門まで 早くて あと N周」を出す端が、**どの刻の周から出たか**を必ず言う
     —— 実測でその端は「刻が中央の 1.70倍 だった周」そのものでした。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import quota  # noqa: E402


def _series(vals: list[float], gap_min: float = 55.0,
            start: str = "2026-09-13T00:00:00+09:00") -> list[tuple[str, float]]:
    """刻が一定の列を作る（末尾へ向かって `gap_min` 分ずつ進む）。"""
    from datetime import datetime, timedelta
    t = datetime.fromisoformat(start)
    out = []
    for i, v in enumerate(vals):
        out.append(((t + timedelta(minutes=gap_min * i)).isoformat(), v))
    return out


def test_桁の下の連を道具が数える():
    # 4.000 が 4つ 並ぶ ＝ 動きは 0.000 が 3つ ＝ 門ちょうど
    st = quota.margin_step(_series([4.010, 4.000, 4.000, 4.000, 4.000]))
    assert st["zero_run"] == 3
    assert st["zero_run_max"] == 3
    assert st["zero_drawn"] is True


def test_連は切れたら0に戻る():
    st = quota.margin_step(_series([4.000, 4.000, 4.000, 4.000, 3.990]))
    assert st["zero_run"] == 0          # いま の連
    assert st["zero_run_max"] == 3      # いちばん長い連は残る
    assert st["zero_drawn"] is True


def test_門に届かない列では引かれない():
    st = quota.margin_step(_series([4.000, 4.000, 4.000, 3.990, 3.980]))
    assert st["zero_run_max"] == 2
    assert st["zero_drawn"] is False


def test_門は1か所から出る():
    """`STEP_ZERO_RUN_NEED` を動かすと、判定も一緒に動く（定数を 2か所 に置かせない）。"""
    xs = _series([4.010, 4.000, 4.000, 4.000, 4.000])          # 0.000 が 3つ
    need = quota.STEP_ZERO_RUN_NEED
    try:
        quota.STEP_ZERO_RUN_NEED = 4
        assert quota.margin_step(xs)["zero_drawn"] is False    # 陽性対照
        quota.STEP_ZERO_RUN_NEED = 3
        assert quota.margin_step(xs)["zero_drawn"] is True
    finally:
        quota.STEP_ZERO_RUN_NEED = need


def test_連の窓は印字の窓ではなく列の全部():
    """**過去に満たした窓**が、印字の 8周 から出ても消えないこと。"""
    # 頭に 0.000 の連 3つ、そのあと 12周 は動き続ける ＝ 直近 8周 には連が無い
    vals = [4.000, 4.000, 4.000, 4.000] + [4.000 - 0.005 * i for i in range(1, 13)]
    xs = _series(vals)
    assert quota.margin_step(xs[-9:])["zero_run_max"] == 0     # 窓だけ見ると 0
    assert quota.margin_step(xs)["zero_run_max"] == 3          # 列の全部なら 3


def test_速い端の刻を言う():
    """振れ幅の速い端が「刻の伸びた周」なら、印字がそう言うこと（陽性対照つき）。"""
    from datetime import datetime, timedelta
    t = datetime.fromisoformat("2026-09-13T00:00:00+09:00")
    xs, v = [], 4.700
    # 床どおりの周 5つ（0.000）＋ 刻 93分 の周 1つ（-0.023）
    for gap, d in [(0, 0.0), (55, 0.0), (55, 0.0), (55, 0.0), (55, 0.0), (93, -0.023)]:
        t = t + timedelta(minutes=gap)
        v = round(v + d, 3)
        xs.append((t.isoformat(), v))
    st = quota.margin_step(xs)
    assert st["step_lo"] == pytest.approx(-0.023, abs=1e-9)
    assert st["step_lo_gap"] == pytest.approx(93.0)
    words = quota._step_lo_words(st)
    assert "刻 93分 の周" in words
    assert "その刻がずっと続いたら" in words
    # **陽性対照**: 端が床どおりの周から出た列では、逆のことを言う
    xs2 = _series([4.700, 4.690, 4.690, 4.690, 4.690], gap_min=55.0)
    st2 = quota.margin_step(xs2)
    assert "床どおりの周" in quota._step_lo_words(st2)


def test_印字に連と端の刻が出る():
    line = quota.margin_line(8, 0.546)
    assert "桁の下（0.000）の連" in line
    assert f"門 {quota.STEP_ZERO_RUN_NEED}周" in line
    # **「止まった」と読ませない一言**（`margin_step` の註 22:5x）
    assert "親が床を守った" in line
