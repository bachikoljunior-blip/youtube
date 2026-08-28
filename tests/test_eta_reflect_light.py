"""`--reflect` が、**印字にしか使わない軌跡を解かない**ことを固定する。

## なぜ要るか（2026-08-28。**`retro.py` の持ち越し① / (a2) 問い1 が8回中7回**）

直近8回の「設計の見直し」問い1（この回でいちばん時間を食ったのはどこか）は、
**7回が「道具が答えを返すのを待つところ」**（体感 4〜6割）でした。
穴を1つずつ塞いでも種類が同じなら、塞ぐべきは穴ではなく**穴を作っている側**です
（`docs/trigger_main.md` §2.7 の末尾）。

`solve()` の中身を1本ずつ計った実測（2026-08-28）::

    analyse + supply_state   0.3秒
    plan(sensitivity=True)   4.1秒
    軌跡 base               20.0秒
    軌跡 fast               16.1秒   ← `--reflect` は解いて、捨てていた
    軌跡 slow               30.6秒   ← 同上
    軌跡 planned            21.9秒   ← 同上
    軌跡 choice（腕4本で）   14.5秒
                           ------
    合計                   107.5秒 → **`full=False` で 38.9秒**（-68.6秒・**-64%**）

`fast` / `slow` / `planned` は **`headline()` と `_report_trajectory()` の印字専用**で、
`data/eta.jsonl` に積む行を組む `_row()` は1つも読みません。
ところが `reflect()` は 10行しか印字しないので、**3本ぶんが丸ごと捨てられていました。**

## この検査が守っているもの

1. `full=False` は `fast` / `slow` / `planned` を**解かない**（軌跡の呼び出し回数で見る）
2. `full=False` でも `base` / `choice` / `arms` / `band` は**そのまま在る**
3. **`_row()` はこの3つを読まない** —— でたらめを入れても、積む行が変わらない。
   **誰かが `_row()` にこの3つを積ませたら、ここが落ちます**
   （そのときは `reflect()` を `full=True` に戻すこと）
4. `reflect()` が `solve(..., full=False)` を呼んでいること（配線そのもの）
"""
from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("eta_reflect_light_mod",
                                               ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)


def _stub_trajectory(calls: list):
    """`trajectory()` の身代わり。**解かずに、呼ばれた形だけ数える。**"""
    def fake(m, a0, **kw):
        calls.append({"focus": kw.get("focus"), "rate_scale": kw.get("rate_scale", 1.0),
                      "arms": kw.get("arms")})
        return {"days": 100.0, "date": eta.today_jst(), "t_work": 3,
                "factors": {}, "binding": "b", "plan_days": 97.0,
                "arms": kw.get("arms") or {}, "focus": kw.get("focus"),
                "rate_scale": kw.get("rate_scale", 1.0), "blocking": {},
                "searched_days": 1}
    return fake


def _arms():
    return {k: {"rate": 0.01, "focus_rate": 0.02, "cap": 2.0, "share": 0.25}
            for k in eta.arm_speed.ARMS}


def _run(monkeypatch, *, full: bool) -> tuple[dict, list]:
    calls: list = []
    monkeypatch.setattr(eta, "trajectory", _stub_trajectory(calls))
    monkeypatch.setattr(eta, "_capped_arms", lambda *a, **k: _arms())
    monkeypatch.setattr(eta.arm_speed, "closed", lambda *a, **k: [])
    monkeypatch.setattr(eta.arm_speed, "band",
                        lambda *a, **k: {"p": 0.5, "lo": 0.25, "hi": 0.75, "k": 3, "n": 6})
    monkeypatch.setattr(eta.arm_speed, "miss_streak", lambda *a, **k: 0)
    monkeypatch.setattr(eta.arm_speed, "unreadable", lambda *a, **k: [])
    monkeypatch.setattr(eta.arm_speed, "planned",
                        lambda *a, **k: {"n": 4, "share": {k: 0.25 for k in eta.arm_speed.ARMS}})
    tr = eta.trajectory_all({}, {}, full=full)
    return tr, calls


def test_full_false_skips_the_three_printing_only_trajectories(monkeypatch):
    """1: 幅の両端と台帳の配分は、`full=False` では**解かない**。"""
    tr_full, calls_full = _run(monkeypatch, full=True)
    tr_light, calls_light = _run(monkeypatch, full=False)

    # `base` 1本 ＋ `choice`（腕の数）は、どちらでも解く。
    n_arms = len(eta.arm_speed.ARMS)
    assert len(calls_light) == 1 + n_arms, (
        f"`full=False` が {len(calls_light)}本 解いています（要るのは base 1本 ＋ 腕 {n_arms}本）")
    # `fast` / `slow` / `planned` の3本ぶん多いのが `full=True`。
    assert len(calls_full) == len(calls_light) + 3, (
        "`full=True` が幅の両端（fast/slow）と台帳の配分（planned）を解いていません。"
        "**この3本が無いなら、この節ごと畳んでよい**")
    assert tr_light["fast"] is None and tr_light["slow"] is None
    assert tr_light["planned"] is None
    assert tr_full["fast"] is not None and tr_full["slow"] is not None


def test_full_false_keeps_what_the_row_reads(monkeypatch):
    """2: `_row()` が読む4つ（base / choice / arms / band）は、そのまま在る。"""
    tr_light, _ = _run(monkeypatch, full=False)
    for key in ("base", "choice", "arms", "band"):
        assert tr_light.get(key) is not None, f"`{key}` が落ちています（`_row()` が読みます）"
    assert len(tr_light["choice"]) == len(eta.arm_speed.ARMS)


def test_row_does_not_read_fast_slow_planned(monkeypatch):
    """3: **`_row()` はこの3つを読まない。**

    でたらめを入れた軌跡と、`None` のままの軌跡で、**積む行が同一**であること。
    誰かが `_row()` に `fast` / `slow` / `planned` を積ませたら、ここが落ちます ——
    そのときは `reflect()` の `full=False` を `True` に戻すこと。
    """
    tr_light, _ = _run(monkeypatch, full=False)
    poisoned = dict(tr_light,
                    fast={"days": -1.0, "date": None},
                    slow={"days": 9e9, "date": None},
                    planned={"days": 0.0, "date": None, "planned": {"n": 99}})

    m = {"subs_net": 9, "views_7d": 100}
    a = {"per_video_now": 12.0, "rate": 0.5}
    pl = {"days_to_target": 100.0, "target_date": None, "days_revenue": 90.0,
          "binding": "b", "lever_hint": "per_video"}
    monkeypatch.setattr(eta, "physical_caps", lambda *a_, **k: {})

    assert eta._row(dict(m), dict(a), dict(pl), tr_light, None) == \
        eta._row(dict(m), dict(a), dict(pl), poisoned, None), (
        "`_row()` が fast / slow / planned のどれかを読んでいます。"
        "**`reflect()` はその3本を解いていません** —— `full=True` に戻すこと")


def test_reflect_is_wired_to_full_false():
    """4: 配線そのもの。`reflect()` が `full=False` で解いていること。"""
    src = inspect.getsource(eta.reflect)
    assert "full=False" in src, (
        "`reflect()` が `solve(..., full=False)` を呼んでいません —— "
        "**10行しか印字しない側が、印字専用の軌跡3本（実測 68.6秒）を解いています**")
