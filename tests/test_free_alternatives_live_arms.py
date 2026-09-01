"""**死んだ燃料の注ぎ口は、`free_alternatives()` の腕の一覧でした。**

（2026-09-01 夕・最適化の回）

`run_marker.free_alternatives()` は、日枠が尽きた回に「まだ 0単位で撃てる手」を
並べます。その先頭は `premise`（`config/hypotheses.yaml` に前提を1件 立てる）で、
**腕の候補として `levers.LEVERS` をそのまま並べていました。**

その4つには、こういう腕が入っています:

    `sub_rate`  その回の `arm_dead_at_inf` ＝ **`×10^9` でも到達日は出ない**
    `density`   天井 ×1.00 ＝ **オーナーが固定した 1日1本**（覆る条件なし）

**つまり「前提を立てろ」と言う唯一の入口が、閉じても日付が動かない腕を
候補として渡していました。** 実測 2026-09-01 12:4x（`dead_ledger()` を書いた回）:
開いている 23件 のうち **10件（43%）**がその側。

`levers.lever_notes()` は**出す瞬間**の1件を叱ります。**足りなかったのは選ぶ前**です。

**この検査が守るのは規則です**（数は写しません） ——
引き代の無い腕を候補から落とすこと・**読めない回は1本も落とさないこと。**
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _load():
    spec = importlib.util.spec_from_file_location(
        "run_marker_live_arms", ROOT / "scripts" / "run_marker.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rm = _load()

STATE = {
    "caps": {"per_video": 4.16, "sub_rate": 6.64, "rpm": 36.7, "density": 1.0},
    "dead_at_inf": ("sub_rate",),
    "dead_why": {"density": "規則", "sub_rate": "天井まで引いても届かない"},
    "hint": "per_video",
}


def _premise_line(monkeypatch, state):
    from src import levers
    monkeypatch.setattr(levers, "latest_arm_state", lambda _p: state)
    lines = [x for x in rm.free_alternatives() if x.startswith("`premise`")]
    assert len(lines) == 1, lines
    return lines[0]


def test_引き代の無い腕は候補から落ちる(monkeypatch):
    line = _premise_line(monkeypatch, STATE)
    assert "腕は per_video／rpm のどれか" in line
    assert "density／sub_rate には立てないこと" in line


def test_読めない回は1本も落とさない(monkeypatch):
    """**「死んだ腕は無い」ではなく「読めない」。**"""
    line = _premise_line(monkeypatch, {})
    assert "per_video" in line and "sub_rate" in line and "density" in line
    assert "には立てないこと" not in line


def test_生きた腕が0本なら立てる先を名指しする(monkeypatch):
    dead_all = {**STATE,
                "caps": {k: 1.0 for k in STATE["caps"]},
                "dead_at_inf": tuple(STATE["caps"])}
    line = _premise_line(monkeypatch, dead_all)
    assert "引き代のある腕が 1本もありません" in line
    assert "その天井は天井ではない" in line


def test_premise_の手そのものは消えない(monkeypatch):
    """**腕が全部 死んでも、`premise` は 0単位で撃てる手として残ること。**

    ここが消えると `fix` の連の門（`FIX_RUN_CAP`）の免除が開き、
    **`fix` だけで回る回が通り直します**（`free_alternatives()` は
    その門の唯一の入力です）。
    """
    dead_all = {**STATE, "caps": {k: 1.0 for k in STATE["caps"]},
                "dead_at_inf": tuple(STATE["caps"])}
    from src import levers
    monkeypatch.setattr(levers, "latest_arm_state", lambda _p: dead_all)
    assert any(x.startswith("`premise`") for x in rm.free_alternatives())


def test_故障を注入すると落ちる(monkeypatch):
    """**発火したことのない検査は検査ではない。**

    `density` の天井を ×1.00 から上げる（＝規則が外れた版）と、
    **`density` は候補に戻ってこなければなりません。**
    """
    lifted = {**STATE, "caps": {**STATE["caps"], "density": 3.0}}
    line = _premise_line(monkeypatch, lifted)
    assert "腕は per_video／rpm／density のどれか" in line
    assert "sub_rate には立てないこと" in line
    assert "density／" not in line
