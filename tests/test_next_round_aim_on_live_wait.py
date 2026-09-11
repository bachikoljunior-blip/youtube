# -*- coding: utf-8 -*-
"""**狙い先（`aim_min`）は、`live >= 1` の WAIT にも書くこと**（2026-09-12 05:3x・optimizer・Opus）。

**なぜ**: `decide()` は 2026-09-09 20:5x から `aim_min` を書いていますが、その1行は
**`if idle:`（＝ 0体・起こしを置く枝）の中**にありました。`live >= 1` の WAIT は
**同じ `floor` を狙っているのに欄が空**で、実測 `data/parent_wakes.jsonl` は
**38行 とも空**です。

その区間は `gap_ratios` の分母が **GO の `floor_min`** へ落ちます ＝
**分子は古い床の下で待った区間・分母はその GO の中で `pace()` が生んだ新しい床**
—— 2026-09-09 22:4x が「閉じた」と書いた **4つ目の刻ずれ**そのもの。

実物（110区間・API 0単位）: 落ちていた区間 **39**、うち **17 は `aim_min` が在る時代**
（`gap_ratios` の註が言う「`aim_min` より前の台帳」ではない）。
そして **§7 (d) の門（1.25倍）を越えた窓は 7つ とも その 17 の側**でした
＝ **門が読む窓だけが、直したはずの分母で読まれていた。**

**陽性対照**（この回に撃って落とした・`.pyc` を消してから）:
  - `decide()` の `aim_min` を `if idle:` の中へ戻すと 1件目が落ちる
  - `gap_ratios` の「WAIT の `floor_min` を拾う」枝を外すと 3件目が落ちる
  - その枝から `not row.get("go")` を外すと 4件目が落ちる
"""
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# `next_round.decide()` の中から `import quota` が走る（`scripts/` が sys.path に居ること）
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
T0 = datetime(2026, 9, 12, 0, 0, 0, tzinfo=timezone.utc)


def _mod():
    spec = importlib.util.spec_from_file_location("_nr_aim_live", ROOT / "scripts" / "next_round.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _decide(mod, monkeypatch, tmp_path, live):
    """前の周が 5分 前に立ったところへ、床 30分・心拍 60分 で親を起こす。"""
    monkeypatch.setattr(mod, "floor_minutes", lambda: (30.0, "検査で固定"))
    monkeypatch.setattr(mod, "heartbeat_minutes", lambda: (60.0, "検査で固定"))
    monkeypatch.setattr(mod, "wake_latency_minutes", lambda *a, **k: (2.0, "検査で固定"))
    monkeypatch.setattr(mod, "LIVE", tmp_path / "live_subs.json")
    monkeypatch.setattr(mod, "WAKE", tmp_path / "parent_wake.json")
    group = [{"at": (T0 - timedelta(minutes=5)).isoformat(), "role": r, "round": "R1"}
             for r in mod.ROLES]
    monkeypatch.setattr(mod, "current_round", lambda *a, **k: group)
    return mod.decide(now=T0, live=live)


def test_live_のある_WAIT_にも狙い先が書かれる(monkeypatch, tmp_path):
    mod = _mod()
    got = _decide(mod, monkeypatch, tmp_path, live=2)
    assert got["go"] is False and got["idle"] is False
    assert got.get("aim_min") == pytest.approx(30.0), (
        "`live >= 1` の WAIT に `aim_min` が無い ＝ その区間の分母が GO の床へ落ちる")


def test_0体_の_WAIT_の狙い先は変わらない(monkeypatch, tmp_path):
    """20:5x の決め（狙い先は `target` ではなく `floor`）を動かしていないこと。"""
    mod = _mod()
    got = _decide(mod, monkeypatch, tmp_path, live=0)
    assert got["go"] is False and got["idle"] is True
    assert got.get("aim_min") == pytest.approx(30.0)
    assert got.get("wake_wait_min") == pytest.approx(25.0, abs=0.2)


def _rows(mod, wait_row):
    """床が GO の中で 30.0 → 20.0 へ動いた 1区間（22:4x の形をそのまま小さくした）。"""
    rows = [{"at": T0.isoformat(), "who": "owner", "go": True, "floor_min": 30.0}]
    if wait_row:
        rows.append(wait_row)
    rows.append({"at": (T0 + timedelta(minutes=36)).isoformat(), "who": "owner",
                 "go": True, "floor_min": 20.0})
    return rows


def _starts(mod, monkeypatch):
    monkeypatch.setattr(mod, "round_starts",
                        lambda: [T0, T0 + timedelta(minutes=36)])


def test_aim_の無い_WAIT_は_その行の床を分母にする(monkeypatch):
    """`live >= 1` の WAIT（欄は空・`floor_min` は在る）を分母に拾うこと。"""
    mod = _mod()
    _starts(mod, monkeypatch)
    wait = {"at": (T0 + timedelta(minutes=10)).isoformat(), "who": "owner",
            "go": False, "idle": False, "live": 2, "floor_min": 30.0}
    got = mod.gap_ratios(got=_rows(mod, wait))
    assert len(got) == 1
    assert got[0] == pytest.approx(36.0 / 30.0, abs=0.01)     # 1.20 ＝ 門の下
    naive = 36.0 / 20.0                                       # 1.80 ＝ GO の床へ落ちた側
    assert got[0] < 1.25 < naive


def test_GO_の行の床は狙い先に使わない(monkeypatch):
    """分母の落ち先そのもの（GO の `floor_min`）を、狙い先として拾い直さないこと。"""
    mod = _mod()
    _starts(mod, monkeypatch)
    # 区間の中に GO の行を 1つ 置く（`floor_min` 5.0）。拾ってしまえば比は 7.2 になる。
    extra = {"at": (T0 + timedelta(minutes=10)).isoformat(), "who": "owner",
             "go": True, "floor_min": 5.0}
    got = mod.gap_ratios(got=_rows(mod, extra))
    assert got and got[0] == pytest.approx(36.0 / 20.0, abs=0.01)


def test_aim_min_が在れば_そちらが勝つ(monkeypatch):
    """欄が在る行では、`floor_min` ではなく `aim_min` を読むこと。"""
    mod = _mod()
    _starts(mod, monkeypatch)
    wait = {"at": (T0 + timedelta(minutes=10)).isoformat(), "who": "owner",
            "go": False, "idle": True, "floor_min": 99.0, "aim_min": 30.0}
    got = mod.gap_ratios(got=_rows(mod, wait))
    assert got[0] == pytest.approx(36.0 / 30.0, abs=0.01)


def test_実物の台帳で_WAIT_を持つ区間は_GO_の床へ落ちないこと():
    """**日付を焼き込まない形**（§5 教訓の形 6つ目）——

    「きょうは 17区間」ではなく「WAIT の行が区間の中に在れば、分母はその行から取る」
    という**構造**を見る。台帳が伸びても、この不変条件は動かない。
    """
    mod = _mod()
    got = mod.wake_rows()
    marks, aims = [], []
    for row in got:
        at = mod._at(row)
        if at is None or row.get("who") != "owner":
            continue
        if row.get("go"):
            if row.get("floor_min"):
                marks.append((at, float(row["floor_min"])))
        else:
            v = row.get("aim_min") or row.get("floor_min")
            if v:
                aims.append((at, float(v)))
    if not marks or not aims:
        pytest.skip("台帳に GO か WAIT の数が無い")
    starts = mod.round_starts()
    ratios = dict(((a, b), r) for (a, b, r) in mod.gap_windows(limit=0))
    checked = 0
    for a, b in zip(starts, starts[1:]):
        near = min(marks, key=lambda m: abs((m[0] - b).total_seconds()))
        if abs((near[0] - b).total_seconds()) / 60.0 > mod._GO_MATCH_MIN:
            continue
        inside = [v for (t, v) in aims if a < t < near[0]]
        got = ratios.get((a, b))
        if not inside or got is None:
            continue               # WAIT が 1行 も無い区間は GO の床へ落ちてよい
        span = (b - a).total_seconds() / 60.0
        checked += 1
        assert got == pytest.approx(span / inside[-1], abs=1e-6), (
            "%s の区間が、区間の中の狙い先（%.2f）ではなく GO の床（%.2f）で割られている"
            % (a.isoformat(), inside[-1], near[1]))
    assert checked > 0, "WAIT の行を持つ区間が 1つ も無い（この検査は何も守っていない）"
