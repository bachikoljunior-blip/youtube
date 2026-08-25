"""`--date` は、**撃つ前に**形を見る（2026-08-19 08:1x に9本ぶん捨てて足した）。

`batch_build.py --date 08/23` は、この道具の中では最後まで通ります ——
`slots()` は文字を組み立てるだけで、印字も `08/23 の1日に入れます` と出る。
形を見るのは `uploader.next_publish_at`（`videos.insert` の直前）だけで、
そこは **9本の生成が全部終わったあと**でした（実測 約20分 → `0 / 9 本`）。

**落ちること自体は正しい。落ちる場所が20分先だったのが欠陥です。**
"""
import pytest

from src.uploader import normalize_date_jst


@pytest.mark.parametrize("given", ["2026-08-23", "2026/08/23", "08/23", "8/23", "08-23"])
def test_受ける形(given):
    assert normalize_date_jst(given).endswith("-08-23")


def test_空文字はそのまま():
    """`--date` を渡さない道（1日1本ずつ後ろへ積む）を壊さない。"""
    assert normalize_date_jst("") == ""


@pytest.mark.parametrize("bad", ["nope", "23/08/2026", "2026-13-01", "08//23"])
def test_読めない形は例外(bad):
    with pytest.raises(ValueError):
        normalize_date_jst(bad)


def test_batch_buildは生成の前に落ちる():
    """**入口で見ていること**を固定する。ここが本体です。

    形を増やしただけでは、次に別の形を渡した回がまた20分を捨てます。
    """
    import scripts.batch_build as bb

    assert bb.main(["--date", "nope", "--count", "1"]) == 2
