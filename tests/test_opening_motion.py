"""冒頭0.9秒の動きの**切り替え**（`YT_OPENING_MOTION`）。

**なぜ検査が要るか。** この切り替えは、対照群を作るためだけに在ります
（`config/hypotheses.yaml` 09/05「冒頭0.9秒に動きを入れると engaged が上がる」）。
既定が「入れる」から動くと、**対照群のつもりで作った本に動きが入り**、
気づかないまま比較が壊れます（8/19 の `ab_split` と同型の事故）。
"""
import os

import pytest

from src import renderer


@pytest.fixture(autouse=True)
def _clean_env():
    old = os.environ.get("YT_OPENING_MOTION")
    os.environ.pop("YT_OPENING_MOTION", None)
    yield
    if old is None:
        os.environ.pop("YT_OPENING_MOTION", None)
    else:
        os.environ["YT_OPENING_MOTION"] = old


def test_default_is_on() -> None:
    """**既定は「入れる」。** 対照群は明示したときだけ。"""
    assert renderer.opening_motion_on() is True


@pytest.mark.parametrize("val", ["0", "false", "off", " 0 "])
def test_off_values(val: str) -> None:
    os.environ["YT_OPENING_MOTION"] = val
    assert renderer.opening_motion_on() is False


@pytest.mark.parametrize("val", ["1", "true", "yes", ""])
def test_other_values_stay_on(val: str) -> None:
    """**知らない値で黙って切らない。** 切るのは明示した3語だけ。"""
    os.environ["YT_OPENING_MOTION"] = val
    assert renderer.opening_motion_on() is True
