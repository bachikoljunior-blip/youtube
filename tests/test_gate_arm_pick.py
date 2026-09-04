"""**到達日が出ない回の名指しは、軌跡ではなく 門1'（登録者）から取ること。**

2026-09-04 12:5x・最適化の回。オーナー「最適化されてんの？」「過去の実行に対して
聞いてんだからな」に、過去の回を数えて答えた結果 入れた検査です。

## 何を守るか（実測。`python scripts/eta.py` をこの回に撃った出力）

頭の5行目は命令形でこう出していました::

    縛っているのは **再生数が天井に当たっている** → **この回に引く腕は `per_video`**

その 14行 下は、同じ出力の中でこう出していました::

    最初に落ちる門は 門1'（登録者 500人・あと 475人）で **512日**
      `per_video` を天井 x4.54 まで引く → **113日後**
      `sub_rate`  を天井 x6.21 まで引く →  **83日後**
      直近 7日 の ship: `per_video` 134件 ／ `sub_rate` 14件

**同じ出力が逆を向いていて、引かれたのは頭が名指ししたほうでした。**
その 7日間 に 再生/日 は 6,299 → 943（-85%）。

`lever_hint` は `need_over_cap`（**軌跡の中の量**）で選ばれます。ところが
`target_date is None` の回は、どの腕を無限大にしても動いた日数が定義上 0 で、
**その中の順位に意味がありません。** 意味の無い順位が命令形で頭に出ていました。

## 覆る条件

`sub_rate` の天井が `per_video` より低くなったら、この検査の期待は**自分で入れ替わります**
（`gate_arm_pick` は定数を持たず、毎周 `lever_days` の `cap` を読むため）。
そのときは下の `test_ceiling_swap_flips_the_pick` が新しい向きを守ります。
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import eta  # noqa: E402


def _pl(**over):
    pl = {
        "target_date": None,
        "gates": {"fan_subs_remaining": 475, "subs_per_day": 0.93},
        "lever_days": [{"lever": "per_video", "cap": 4.54},
                       {"lever": "sub_rate", "cap": 6.21},
                       {"lever": "rpm", "cap": 36.57}],
    }
    pl.update(over)
    return pl


def test_picks_the_arm_that_moves_gate1_soonest():
    """**門1' を早く開けるほうを名指しすること。** 実測の天井で `sub_rate`。"""
    got = eta.gate_arm_pick(_pl())
    assert got is not None
    assert got["lever"] == "sub_rate", (
        "軌跡が出ない回の名指しが、門1' の日数で選ばれていません。"
        f" 出たのは {got['lever']}・日数 {got['days_all']}")
    assert got["days_all"]["sub_rate"] < got["days_all"]["per_video"]


def test_ceiling_swap_flips_the_pick():
    """**定数を持たないこと。** 天井が入れ替われば名指しも入れ替わる。"""
    got = eta.gate_arm_pick(_pl(lever_days=[{"lever": "per_video", "cap": 9.0},
                                            {"lever": "sub_rate", "cap": 2.0}]))
    assert got["lever"] == "per_video"


def test_both_arms_are_a_product():
    """2本とも引いた日数は、片方ずつのどちらよりも小さいこと（積）。"""
    got = eta.gate_arm_pick(_pl())
    assert got["both_days"] < min(got["days_all"].values())


def test_silent_when_the_trajectory_reaches():
    """**到達日が出た回は何もしないこと** —— そのときの軌跡の順位は本物。"""
    assert eta.gate_arm_pick(_pl(target_date=date(2027, 1, 1))) is None


def test_silent_when_gate1_is_already_open():
    assert eta.gate_arm_pick(_pl(gates={"fan_subs_remaining": 0,
                                        "subs_per_day": 0.93})) is None
    assert eta.gate_arm_pick(_pl(gates={"fan_subs_remaining": 475,
                                        "subs_per_day": 0})) is None


def test_silent_without_caps():
    assert eta.gate_arm_pick(_pl(lever_days=[])) is None
    assert eta.gate_arm_pick(_pl(lever_days=[{"lever": "rpm", "cap": 36.5}])) is None


def test_only_gate_arms_are_considered():
    """`rpm` / `density` は 門1' を動かしません（`subs/日 = views/day x sub_rate`）。"""
    got = eta.gate_arm_pick(_pl())
    assert set(got["caps"]) <= set(eta.GATE_ARMS)


def test_the_override_is_wired_into_the_head():
    """**関数が在るだけでは効きません。** 名指しを実際に倒している行が要る。"""
    src = (ROOT / "scripts" / "eta.py").read_text(encoding="utf-8")
    assert "_gap = gate_arm_pick(pl)" in src, (
        "gate_arm_pick が lever_hint を倒す位置から外れました。"
        " 関数だけ残しても、頭の名指しは軌跡のままです。")
    assert 'pl["lever_from"] = "門1\'"' in src


def test_resume_gate_still_wins():
    """審査の門が開いている回は、`gate` が後から勝つこと（順番を守る）。"""
    src = (ROOT / "scripts" / "eta.py").read_text(encoding="utf-8")
    i_gap = src.index("_gap = gate_arm_pick(pl)")
    i_gate = src.index('pl["lever_hint"] = "gate"')
    assert i_gap < i_gate, (
        "門1' の上書きが、審査の門より後ろに来ています。"
        " 止まっている回に『引けない腕』を名指しすることになります。")


@pytest.mark.parametrize("name", ["gate_arm_pick"])
def test_doctests(name):
    import doctest
    fn = getattr(eta, name)
    res = doctest.run_docstring_examples(
        fn, {"gate_arm_pick": eta.gate_arm_pick, "date": date},
        verbose=False, name=name)
    assert res is None
