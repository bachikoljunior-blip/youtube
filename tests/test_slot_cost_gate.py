"""**枠の機会費用を、印字ではなく門にした**（2026-09-05・最適化の回）。

`src/daily_pick.record()` は 09-04 22:5x から `--expected` を**必須**にしていましたが、
門が見ていたのは「数が置かれているか」だけで、**その数が枠の機会費用に足りているか**は
どこも見ていませんでした。実測（`data/daily_pick.jsonl` 09-05T00:38 の決め）::

    形 長尺 ／ `expected_48h` **8.0** ／ `anyway` 空   ← 通っていました
    同じ時刻の `slot_cost.slot_value()` ＝ **1枠 1,049回**（ショート・規則の密度・齢48h）
    ＝ 置かれた数は 機会費用の **1/131**

`src/slot_cost.py` は 09-05 00:20 から この比を**印字**していました。
印字は決めを1度も変えていません（`daily_pick.jsonl` は 11回 連続で長尺）。
**この検査は「通さないこと」のほうを固定します。**

**覆る条件**: どの形でも規則の密度の中央値が入れ替われば `slot_value()` の勝者は
自分で入れ替わり、門はその形を通します（形の禁止ではありません）。
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import daily_pick as dp  # noqa: E402


def _cost():
    from src import slot_cost
    return slot_cost.slot_value()


def test_見込みが機会費用に足りない決めは通らない():
    """**本番の控え（`path=None`）で、負けている形の小さい見込みは止まる。**"""
    sv = _cost()
    if sv.get("cost") in (None, 0) or not sv.get("best"):
        pytest.skip("枠の機会費用が測れません（標本 0本）")
    loser = next((f for f in dp.FORMS if f != sv["best"]), None)
    assert loser, "形が1つしかありません"
    with pytest.raises(ValueError) as e:
        dp.record(loser, "t", "数 8 の見込みで決めた", expected=8.0,
                  day=date(2026, 9, 20), video_id="Z")
    msg = str(e.value)
    assert "枠のぶんを払えません" in msg
    assert f"{sv['cost']:,.0f}" in msg          # 機会費用を数で出すこと
    assert sv["best"] in msg                    # 通る形を名指しすること


def test_anyway_なら数字つきで越えられる(tmp_path):
    """**禁止ではありません** —— `probe_hold` と同じ口で越えられ、控えに残ります。"""
    p = tmp_path / "picks.jsonl"
    row = dp.record("長尺", "t", "数 8 の見込み", expected=8.0, path=p,
                    day=date(2026, 9, 20),
                    anyway="09/07 の判定に要る最後の 48h・1件")
    assert row["anyway"]


def test_素振り_path_を渡した回では門は立たない(tmp_path):
    """本番の控えを守る門なので、`uploaded_path` の註と同じ切り分けにしています。"""
    p = tmp_path / "picks.jsonl"
    row = dp.record("長尺", "t", "数 8", expected=8.0, path=p,
                    day=date(2026, 9, 20), video_id="Z")
    assert row["expected_48h"] == 8.0
