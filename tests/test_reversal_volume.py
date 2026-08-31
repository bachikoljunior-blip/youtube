"""**件数で書いた「覆る条件」を、量の伸びと切り分ける**（2026-08-31）。

## なぜ要るか（実測。同じ日に、同じ形の条件が2件 発火しました）

`config/hypotheses.yaml` の「覆る条件」40件のうち、**件数の絶対値**で書かれたものは
**分母が伸びれば、効果が無くても必ず発火します。** 2026-08-31 の実測:

    endcard        「28日窓で**1件でも**」   → 1件 付いた。**覆らない**（量ぶん）
    RELATED_VIDEO  「90日窓で **10 以上**」  → 47再生。**覆る**（量の 2.18倍）

**答えが逆になったことが要点です。** 「件数の条件を全部 率に直す」と、
RELATED_VIDEO の側を取り逃がします（占有 0.06% は率だけ見れば小さい）。

この検査が固定するのは、その切り分けが**両方の実測で正しく出ること**です。

## この検査が覆る条件

`RATIO_GATE`（2.0倍）は取り決めであって実測の線ではありません。
**外れた側を2件 数えたら引き直すこと**（`src/reversal.py` の docstring）。
"""
from __future__ import annotations

from src import reversal as rev


def test_related_video_は覆る():
    """**2026-08-31 の実測。** 量の 2.18倍 なので、開け直す側に落ちること。"""
    r = rev.share_moved(before=(6, 21823), now=(47, 78505))
    assert r["moved"] is True
    assert 2.1 < r["ratio"] < 2.3
    # 直近7日はもっとはっきりしている。
    r7 = rev.share_moved(before=(6, 21823), now=(25, 11928))
    assert r7["moved"] is True
    assert r7["ratio"] > 7.0


def test_endcard_は比が出せない():
    """閉じたときが 0件 なので、予測が 0 になって比が定義できないこと。

    **そこで「覆る」に倒さないこと。** 返りは `moved=False` で、
    印字が「率で見ること」と言います（実際の率の判定は
    `src/endcard_verdict.reversal()` の側）。
    """
    r = rev.share_moved(before=(0, 20332), now=(1, 56751))
    assert r["ratio"] is None
    assert r["moved"] is False
    assert "率で見ること" in r["line"]


def test_量どおりに伸びただけなら覆らない():
    """**この検査の中心。** 占有が同じままなら、件数が何倍になっても覆らない。"""
    # 6/21,823 と同じ占有のまま、分母を 10倍 にした（件数は 60）。
    r = rev.share_moved(before=(6, 21823), now=(60, 218230))
    assert abs(r["ratio"] - 1.0) < 1e-9
    assert r["moved"] is False
    # 分母を 100倍 にしても同じ（＝「件数が増えた」だけでは覆らない）。
    assert rev.share_moved((6, 21823), (600, 2182300))["moved"] is False


def test_閉じたときの分母が小さいと比を返さない():
    """比が跳ねる領域では、黙って大きい数を出さないこと。"""
    assert rev.volume_ratio(before=(1, 10), now=(50, 100000)) is None


def test_実測の表が道具と食い違わない():
    """`MEASURED` は印字と `status.py` の両方が読みます。**1か所に持つこと。**"""
    assert set(rev.MEASURED) == {
        "endcard（末尾の問いかけ → コメント）",
        "RELATED_VIDEO（推薦面は自力で伸びるか）",
        "RELATED_VIDEO（直近7日で見ると）",
    }
    base = rev.MEASURED["RELATED_VIDEO（推薦面は自力で伸びるか）"]["before"]
    assert base == (6, 21823)          # 2026-08-20 の判定時の実測
