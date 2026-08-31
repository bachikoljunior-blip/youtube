"""**面が割れて外した `density` を、`reaches` の輪が入れ直さないこと。**

## なぜ要るか（2026-08-27・最適化の回）

`tests/test_levers_density_surface.py`（08/26）は
「長尺の面が開いていれば `density` は死んだ腕から外れる」を通していました。
**通っていたのは、その作り物が `arm_reaches["density"] = True` だったから**です。
**実データは False** で、`arm_state` の最後の輪が `density` をそのまま戻します:

    arm_caps    {'density': 1.0}     ← ショートの面の数
    arm_reaches {'density': False}   ← **同じ 1.0 から出た数**（`at_ceiling` の枝）
    → dead_why  {'density': '天井まで引いても届かない'}

`eta.lever_days()` は `cap <= 1.0` の腕を**解き直さず** `NEVER` を返すので、
`reaches["density"] is False` は「天井が ×1.00 だ」の**言い直し**です。
別の証拠ではありません。**同じ数を2回 数えて、2回目で殺していました。**

実測の効き（2026-08-27・`scripts/drift.py`）: `density` **64回**（ship の 23%）が
「引き代が無かった回」に数えられていました。長尺の再生は、台帳でいちばん大きい
前提（「長尺の登録率はショートより1桁以上高い」・期限 11/22・**すでに3回 延長**）の
待ち時間そのものなので、**唯一の桁ちがいの前提を早める作業が、毎回
「無駄だった」と記録されていた**ことになります。

## 覆る条件

`arm_caps` に `density_long` が入るようになったら（＝天井が面ごとに立つ）、
`reaches["density"]` は独立した証拠になります。**そのときこの除外を外すこと。**
"""
from __future__ import annotations

from src import levers

OPEN = {"short": {"at_ceiling": True, "measured": True},
        "long": {"at_ceiling": False, "measured": False}}
CLOSED = {"short": {"at_ceiling": True, "measured": True},
          "long": {"at_ceiling": True, "measured": True}}


def _row(*, reaches_density: bool, surfaces: dict | None) -> dict:
    """**実データと同じ形**（`arm_reaches["density"]` が False の行）。"""
    row = {"arm_caps": {"per_video": 3.06, "sub_rate": 3233.3, "rpm": 64.5, "density": 1.0},
           "arm_reaches": {"per_video": True, "rpm": True,
                           "sub_rate": False, "density": reaches_density},
           "lever_hint": "per_video"}
    if surfaces is not None:
        row["density_surfaces"] = surfaces
    return row


def test_reaches_が_False_でも長尺の面が開いていれば生きている():
    st = levers.arm_state(_row(reaches_density=False, surfaces=OPEN))
    assert "density" not in st["dead_why"], (
        "面で外した density を `reaches` の輪が入れ直しています"
        f"（dead_why={st['dead_why']}）")
    assert "density" not in st["dead"]
    assert "長尺の面は開いています" in st["open_why"]["density"]


def test_両方の面が閉じていれば_reaches_の理由で死ぬ():
    """**外すのは面が割れているときだけ。** 全部を生かす変更ではありません。"""
    st = levers.arm_state(_row(reaches_density=False, surfaces=CLOSED))
    assert st["dead_why"].get("density"), "両方の面が天井なのに density が生きています"
    assert "density" in st["dead"]


def test_面の欄が無い古い行は前のまま死ぬ():
    """済んだ回の判定を、あとから足した欄で塗り替えないこと。"""
    st = levers.arm_state(_row(reaches_density=False, surfaces=None))
    assert st["dead_why"].get("density")


def test_ほかの腕は救わない():
    """`sub_rate` は面が割れていません。**この除外に巻き込まないこと。**"""
    st = levers.arm_state(_row(reaches_density=False, surfaces=OPEN))
    assert st["dead_why"].get("sub_rate") == "天井まで引いても届かない"


def test_lever_notes_が同じ回に両方を言わない():
    """`--lever density` の回に「引いてよい」と「引いても届かない」を並べないこと。"""
    st = levers.arm_state(_row(reaches_density=False, surfaces=OPEN))
    notes = "\n".join(levers.lever_notes("density", st))
    assert "面が割れています" in notes
    assert "天井まで引いても届きません" not in notes
