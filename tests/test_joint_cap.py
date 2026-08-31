"""**腕を1本ずつしか動かさない数を、「残りの距離」として出さないこと。**

`src/joint_cap.py` の docstring に、なぜ要るかと「覆る条件」があります。
ここが固定するのは3つ:

    1. 天井の束の作り方（`cap <= 1.0` は入れない ＝ 引き代なし）
    2. 割り算の向き（`ratio` と `gap` が逆にならないこと）
    3. **`headline()` に配線されていること** —— 撃たれない道具の効果はゼロ

**3が本体です。** この repo でいちばん多い壊れ方は
「言っている所と、している所が別」なので、印字まで見ます。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import joint_cap                                     # noqa: E402


# --- 1. 天井の束 -------------------------------------------------------------

def test_引き代のない腕は束に入らない():
    rows = [
        {"lever": "per_video", "cap": 2.0},
        {"lever": "density", "cap": 1.0},      # 引き代なし
        {"lever": "sub_rate", "cap": None},    # 測れていない
        {"lever": "rpm", "cap": 28.05},
    ]
    assert joint_cap.joint_scale(rows) == {"per_video": 2.0, "rpm": 28.05}


def test_行が無ければ束も空():
    assert joint_cap.joint_scale(None) == {}
    assert joint_cap.joint_scale([]) == {}


# --- 2. 割り算の向き ---------------------------------------------------------

def test_ratio_は届いた割合_gap_は残りの倍率():
    assert joint_cap.ratio(500_000, 56_730) == 56_730 / 500_000
    g = joint_cap.gap(500_000, 56_730)
    assert g is not None and abs(g - 500_000 / 56_730) < 1e-9
    # **届いていれば gap は 1.0 以下**
    assert joint_cap.gap(100.0, 200.0) < 1.0


def test_分母が無い回は言わない():
    assert joint_cap.ratio(None, 100) is None
    assert joint_cap.ratio(0, 100) is None
    assert joint_cap.gap(500_000, None) is None


# --- 3. solve と印字 ---------------------------------------------------------

def _rows():
    return [{"lever": "per_video", "cap": 2.007}, {"lever": "rpm", "cap": 28.05}]


def test_solve_は解き直した1点を返す():
    seen = {}

    def resolve(scale):
        seen["scale"] = scale
        return 159_710.0, 1891.0            # (need_month, ceiling_day)

    res = joint_cap.solve(_rows(), resolve)
    assert seen["scale"] == {"per_video": 2.007, "rpm": 28.05}
    assert res["ceiling_month"] == 1891.0 * 30
    assert abs(res["ratio"] - (1891.0 * 30) / 159_710.0) < 1e-9
    assert res["reaches"] is False
    assert 2.7 < res["gap"] < 3.0           # **実測 ×2.82 の帯**


def test_solve_が落ちても回を止めない():
    def boom(_scale):
        raise RuntimeError("模型が落ちた")

    assert joint_cap.solve(_rows(), boom) is None
    assert joint_cap.solve([{"lever": "density", "cap": 1.0}],
                           lambda _s: (1.0, 1.0)) is None


def test_1本ずつの倍率のほうが大きい回は_そう書く():
    res = joint_cap.solve(_rows(), lambda _s: (159_710.0, 1891.0))
    lines = joint_cap.lines(res, 8.819)
    assert len(lines) == 2
    joined = "".join(lines)
    assert "2.82" in joined                  # 残りの距離
    assert "8.82" in joined                  # 画面が出していた数
    assert "残りの距離ではありません" in joined


def test_残りのほうが大きい回は_余計な行を出さない():
    res = joint_cap.solve(_rows(), lambda _s: (159_710.0, 1891.0))
    assert len(joint_cap.lines(res, None)) == 1
    assert len(joint_cap.lines(res, 1.5)) == 1     # 1本ずつのほうが小さい
    assert joint_cap.lines(None, 8.8) == []        # **無い回は1行も出さない**


# --- 4. **配線**（本体） -----------------------------------------------------

def _eta():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_eta_joint", ROOT / "scripts" / "eta.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_headline_が_joint_cap_の行を出す():
    """**`plan()` が積んだ `joint_cap` が、頭の3行の下に出ること。**

    ここが切れると、この道具は `data/eta.jsonl` に数を積むだけで、
    **腕を選ぶ側には1文字も届きません**（2026-08-31 に同じ形を2件 踏んだ）。
    """
    eta = _eta()
    pl = {
        "target_date": None, "days_to_target": eta.NEVER,
        "binding": "再生数が天井に当たっている", "lever_hint": "per_video",
        "lever_chosen_by": "need_over_cap",
        "lever_need": 17.702, "lever_need_over_cap": 8.819,
        "joint_cap": joint_cap.solve(_rows(), lambda _s: (159_710.0, 1891.0)),
    }
    out = "".join(eta.headline(pl))
    assert "2.82" in out, "残りの距離が頭の3行に出ていません"
    assert "同時に天井" in out


def test_joint_cap_が無い回は_headline_が黙る():
    eta = _eta()
    pl = {
        "target_date": None, "days_to_target": eta.NEVER,
        "binding": "再生数が天井に当たっている", "lever_hint": "per_video",
        "lever_chosen_by": "need_over_cap",
        "lever_need": 17.702, "lever_need_over_cap": 8.819,
    }
    out = "".join(eta.headline(pl))
    assert "同時に天井" not in out


def test_plan_が_joint_cap_を積む配線が残っていること():
    """**`plan()` の中で `joint_cap.solve()` が呼ばれていること。**

    実物を解くと数分 かかるので、ここは配線だけを見ます
    （数のほうは上の `solve` の検査が固定しています）。
    """
    src = (ROOT / "scripts" / "eta.py").read_text(encoding="utf-8")
    assert "joint_cap.solve(" in src, "plan() の配線が外れています"
    assert "joint_cap.lines(" in src, "headline() の配線が外れています"
    assert "joint_cap_ratio" in src, "eta.jsonl への積みが外れています"
