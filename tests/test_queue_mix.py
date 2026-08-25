"""待ち行列の長尺／ショートの報告（`src/queue_mix.py`）。

**なぜ要るか**は `src/queue_mix.py` の冒頭に書いてあります ——
`rpm` の天井が長尺の面から出ているのに、**待ち行列の長尺の本数を出す計器が
1つも無く**、名指しが `rpm` のまま 40本が全部ショートで進んでいました。
"""
from src import queue_mix


def test_empty_queue_prints_nothing():
    """**予約が0本の回では黙る。** 毎回鳴る警告は読まれなくなる。"""
    assert queue_mix.lines(0, 0) == []


def test_zero_long_form_is_flagged():
    """長尺が0本なら、**腕を引かずに進んだ回**になると言う。"""
    out = queue_mix.lines(0, 300)
    assert out, "ショートが300本あるのに何も出ないのは、この節の目的に反する"
    assert any("長尺が1本もありません" in line for line in out)
    assert any("--long" in line for line in out)


def test_low_share_points_at_the_default():
    """2%（この回の実測）は、**既定がショートである**ことを指す。"""
    out = queue_mix.lines(6, 294)
    assert any("既定はショート" in line for line in out)
    # 「1本もありません」のほうは出さない（実体はある）
    assert not any("1本もありません" in line for line in out)


def test_healthy_share_has_no_bang():
    """割合が足りていれば `[!]` を出さない。**鳴りっぱなしにしないため。**"""
    out = queue_mix.lines(60, 240)
    assert out
    assert not any(line.lstrip().startswith("[!]") for line in out)


def test_counts_and_share_are_printed():
    """本数と割合が、**数字のまま**出ていること。"""
    out = "\n".join(queue_mix.lines(9, 291))
    assert "長尺 **9本**" in out
    assert "ショート 291本" in out
    assert "3.0%" in out


def test_share_uses_the_whole_queue_not_just_shorts():
    """割合の分母は待ち行列の全部。**ショートだけで割らない。**"""
    out = "\n".join(queue_mix.lines(1, 1))
    assert "50.0%" in out
