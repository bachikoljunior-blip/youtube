# -*- coding: utf-8 -*-
"""`gap_ratios` の分母は「親が実際に狙った先」（`aim_min`）であること。

**なぜ**（2026-09-09 22:4x・optimizer・Opus）: `pace()` が目盛りを読み直すのは GO の中なので、
床が動いた回は「古い床の下で待った区間 ÷ その場で生まれた新しい床」になり、
親が 3分 しか外していないのに **1.37倍** と鳴る。§7 の覆る条件 (1) は 1.25倍 が門なので、
そのまま読んだ回は在りもしない上限を探しにいく。註は `next_round.gap_ratios` の docstring。

**陽性対照**: 分母を GO の `floor_min` に戻すと 1件目・2件目が落ちる（この回に撃って確かめた）。
"""
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _mod():
    spec = importlib.util.spec_from_file_location("_nr_gap_aim", ROOT / "scripts" / "next_round.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


T0 = datetime(2026, 9, 9, 11, 49, 17, tzinfo=timezone.utc)


def _wakes(aim):
    """床が **GO の中で** 52.89 → 41.21 へ動いた回を、そのまま組む。"""
    rows = [
        {"at": T0.isoformat(), "who": "owner", "go": True, "floor_min": 52.89},
    ]
    if aim is not None:
        rows.append(
            {
                "at": (T0 + timedelta(minutes=17)).isoformat(),
                "who": "owner",
                "go": False,
                "idle": True,
                "floor_min": 53.44,
                "aim_min": aim,
            }
        )
    rows.append(
        {
            "at": (T0 + timedelta(minutes=56, seconds=28)).isoformat(),
            "who": "owner",
            "go": True,
            "floor_min": 41.21,          # ← pace() が この GO の中で読み直した床
        }
    )
    return rows


def _starts(mod, monkeypatch):
    got = [T0, T0 + timedelta(minutes=56, seconds=28)]
    monkeypatch.setattr(mod, "round_starts", lambda: got)


def test_床が_GO_の中で動いた区間は_狙った先で割る(monkeypatch):
    mod = _mod()
    _starts(mod, monkeypatch)
    got = mod.gap_ratios(got=_wakes(53.44))
    assert len(got) == 1
    # 56.47 ÷ 53.44 ＝ 1.057（親は狙いを 3.0分 外しただけ）
    assert got[0] == pytest.approx(1.057, abs=0.01)


def test_GO_の床で割ると_37パーセント_超過に見える(monkeypatch):
    """この検査が守っている当のもの —— 同じ区間を GO の床で割った値。"""
    mod = _mod()
    _starts(mod, monkeypatch)
    got = mod.gap_ratios(got=_wakes(53.44))
    naive = 56.47 / 41.21
    assert naive == pytest.approx(1.37, abs=0.01)
    assert got[0] < 1.25 < naive          # §7 の覆る条件 (1) の門をまたぐ


def test_aim_が無い古い区間は_GO_の床へ落ちる(monkeypatch):
    """**区間の中に WAIT の行が 1つ も無ければ** GO の床で割ること（`aim_min` より前の台帳）。

    2026-09-12 05:3x に言い直した —— この検査のデータには WAIT の行が 1行 も無く、
    見ているのは「欄が古い」ではなく「**区間の中に狙い先の行が無い**」側です
    （`live >= 1` の WAIT は欄が空でも `floor_min` を持つので、いまはそちらが分母になります・
    `tests/test_next_round_aim_on_live_wait.py`）。
    """
    mod = _mod()
    _starts(mod, monkeypatch)
    got = mod.gap_ratios(got=_wakes(None))
    assert got[0] == pytest.approx(56.47 / 41.21, abs=0.01)


def test_区間の外の_aim_は使わない(monkeypatch):
    """前の区間に置かれた `aim_min` を引かないこと（刻ずれを別の向きに作らないため）。"""
    mod = _mod()
    _starts(mod, monkeypatch)
    rows = [{"at": (T0 - timedelta(minutes=30)).isoformat(), "who": "owner",
             "go": False, "idle": True, "aim_min": 999.0}] + _wakes(None)
    got = mod.gap_ratios(got=rows)
    assert got[0] == pytest.approx(56.47 / 41.21, abs=0.01)


def test_実物の台帳でも門を越えないこと():
    """本物の `data/parent_wakes.jsonl` で、比の中央値が §7 の 1.25倍 の門より下に居ること。"""
    mod = _mod()
    ratio, n = mod.gap_ratio_median()
    if ratio is None:
        pytest.skip("台帳に比を数えられる区間が無い")
    assert n > 0
    assert ratio < 1.25, "比の中央値 %.3f（n=%d）が §7 の門を越えている" % (ratio, n)
