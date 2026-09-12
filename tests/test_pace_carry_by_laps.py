"""**目盛りからいままでは、時間ではなく「立った周の数」で運ぶ**（2026-09-06・optimizer）。

実測 09/05 17:37 → 09/06 16:41 JST: 目盛り 14% → 18%（23.1時間・0.173 %/時）。
そのあいだ `pace()` は 78分 の区間の速さ 1.538 %/時 を 21時間 運んで **47%** と言い、
間隔 431分 → `next_round.IDLE_WAIT_MAX_MIN` の 360分。親は 6時間 待った × 2回。
枠を食うのは周（サブ）であって時計ではない。周が 0 なら増えない。

**覆る条件**: `rounds.jsonl` に周が無い枠では、従来どおり時間で運ぶ（下の検査で固定）。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from scripts import quota

UTC = timezone.utc
RESET = datetime(2026, 9, 11, 22, 0, tzinfo=UTC)       # 09/12 07:00 JST
START = RESET - timedelta(days=7)


def _jsonl(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _setup(tmp_path, monkeypatch, *, anchors, rounds):
    usage = tmp_path / "usage.jsonl"
    _jsonl(usage, [{"fetched_at": at.isoformat(), "window_id": "seven_day",
                    "used_percent": used, "resets_at_iso": RESET.isoformat()}
                   for at, used in anchors])
    rl = tmp_path / "rounds.jsonl"
    _jsonl(rl, [{"at": at.isoformat(), "role": "hourly", "round": at.isoformat()}
                for at in rounds])
    monkeypatch.setattr(quota, "USAGE_LOG", usage)
    monkeypatch.setattr(quota, "ROUNDS_LOG", rl)
    monkeypatch.setattr(quota, "LOG", tmp_path / "quota.jsonl")
    monkeypatch.setattr(quota, "RUNS_LOG", tmp_path / "runs.jsonl")


def test_周が記録されている枠では目盛りの後の周の数で運ぶ(tmp_path, monkeypatch):
    """09/05→06 の形。短い区間の速さを 21時間 運ばない。"""
    g0 = START + timedelta(hours=33)                    # 09/05 16:19 JST 相当
    g1 = g0 + timedelta(minutes=78)                     # 17:37 JST・+2%
    rounds = [START + timedelta(hours=h) for h in (2, 8, 14, 20, 26)]   # 目盛りまでに 5周
    _setup(tmp_path, monkeypatch, anchors=[(g0, 12), (g1, 14)], rounds=rounds)

    now = g1 + timedelta(hours=21)
    p_idle = quota.pace(now)                            # 目盛りの後に周は 0
    assert p_idle["carry_mode"] == "laps"
    assert p_idle["carried_laps"] == 0
    assert p_idle["used_now"] == pytest.approx(14.0)    # **時計では増えない**
    # 時間で運ぶと 14 + 21 × 1.538 ≈ 46%。それを出さないこと
    assert p_idle["used_now"] < 14 + 21 * p_idle["carry_rate"] - 20

    # 目盛りの後に 3周 立ったら、そのぶんだけ増える
    _setup(tmp_path, monkeypatch, anchors=[(g0, 12), (g1, 14)],
           rounds=rounds + [g1 + timedelta(hours=h) for h in (1, 7, 13)])
    p = quota.pace(now)
    assert p["carried_laps"] == 3
    assert p["used_now"] == pytest.approx(14.0 + 3 * p["per_lap"])


def test_目盛りと同じ瞬間の周は数えない(tmp_path, monkeypatch):
    """その周はもう目盛りの %に入っている。二重に足さないこと。"""
    g = START + timedelta(hours=30)
    _setup(tmp_path, monkeypatch, anchors=[(g, 10)],
           rounds=[START + timedelta(hours=10), g])
    p = quota.pace(g + timedelta(minutes=1))
    assert p["carry_mode"] == "laps"
    assert p["carried_laps"] == 0
    assert p["used_now"] == pytest.approx(10.0)


def test_周が無い枠では従来どおり時間で運ぶ(tmp_path, monkeypatch):
    """覆る条件の側。`rounds.jsonl` が空なら 08/21 の形（区間の速さ × 経過時間）。"""
    g0 = START + timedelta(hours=10)
    g1 = g0 + timedelta(hours=10)
    _setup(tmp_path, monkeypatch, anchors=[(g0, 5), (g1, 10)], rounds=[])
    p = quota.pace(g1 + timedelta(hours=4))
    assert p["carry_mode"] == "hours"
    assert p["used_now"] == pytest.approx(10 + 4 * p["carry_rate"], abs=0.01)


def test_間隔は周で運んだ推定から出る(tmp_path, monkeypatch):
    """待っているあいだに間隔が伸び続けない（伸びるのは残り時間が減るぶんだけ）。"""
    g = START + timedelta(hours=30)
    rounds = [START + timedelta(hours=h) for h in (3, 9, 15, 21, 27)]
    _setup(tmp_path, monkeypatch, anchors=[(g, 15)], rounds=rounds)
    a = quota.pace(g + timedelta(hours=1))
    b = quota.pace(g + timedelta(hours=13))
    assert a["floor_min"] < quota.FLOOR_MAX_CLAMP
    # 12時間 待っても、使った%は動かず、残り時間が 12時間 減るぶんしか間隔は伸びない
    assert b["used_now"] == a["used_now"]
    assert b["floor_min"] / a["floor_min"] < 1.15


# --- **借りた床（`_per_lap_before`）でも周で運ぶこと**
#     （2026-09-12 12:3x JST・optimizer・Opus。実測の形をそのまま固定する） ---
#
# 09/06 17:xx の門は `laps_in_window and per_lap` で、**`laps_in_window == 0` ＝ 1周の重さが無い**
# が前提でした。08:2x に `_per_lap_before` が入ってからその同値は切れています
# （この枠で 1周も測れていなくても、前の枠から借りた重さが在る）。
# 実測 09/12 12:2x: laps_in_window 0・per_lap 0.546（借り）・carried_laps 5 →
# 門が偽 → 時間で運ぶ側へ落ち、`carry_rate` 0.000 %/時（同じ枠に2点目が無い）→
# **5周 立っても used_now 0.0%**（実際は 2.73%）＝ 床が短い側（速すぎてよい側）へ外れる。

PREV_RESET = RESET - timedelta(days=7)
PREV_START = PREV_RESET - timedelta(days=7)


def _setup_two_windows(tmp_path, monkeypatch, *, anchors, rounds):
    """`anchors` は (刻, %, その点が属する枠のリセット) の並び。"""
    usage = tmp_path / "usage.jsonl"
    _jsonl(usage, [{"fetched_at": at.isoformat(), "window_id": "seven_day",
                    "used_percent": used, "resets_at_iso": reset.isoformat()}
                   for at, used, reset in anchors])
    rl = tmp_path / "rounds.jsonl"
    _jsonl(rl, [{"at": at.isoformat(), "role": "hourly", "round": at.isoformat()}
                for at in rounds])
    monkeypatch.setattr(quota, "USAGE_LOG", usage)
    monkeypatch.setattr(quota, "ROUNDS_LOG", rl)
    monkeypatch.setattr(quota, "LOG", tmp_path / "quota.jsonl")
    monkeypatch.setattr(quota, "RUNS_LOG", tmp_path / "runs.jsonl")


def _just_rolled(tmp_path, monkeypatch):
    """前の枠には周も目盛りも在り、新しい枠の目盛りは**頭の 20分 後の 0%**（09/12 の実物）。"""
    prev_g = PREV_START + timedelta(hours=120)                        # 前の枠で 1周の重さが測れる点
    prev_rounds = [PREV_START + timedelta(hours=h) for h in range(2, 120, 6)]
    new_g = RESET + timedelta(minutes=20)                             # 枠の頭 20分 後 ＝ そこまで周 0
    new_rounds = [RESET + timedelta(hours=h) for h in (1, 2, 3, 4, 5)]  # 目盛りの後に 5周
    _setup_two_windows(
        tmp_path, monkeypatch,
        anchors=[(new_g, 0.0, RESET), (prev_g, 60.0, PREV_RESET)],
        rounds=prev_rounds + new_rounds,
    )


def test_枠が戻った直後は借りた床で周で運ぶ(tmp_path, monkeypatch):
    """**陽性対照**: 門を `laps_in_window and per_lap` へ戻すと、この 4件 が落ちる
    （`carry_mode` が `hours`・`used_now` が 0.0 になる）。撃って確かめてある。"""
    _just_rolled(tmp_path, monkeypatch)
    p = quota.pace(RESET + timedelta(hours=6))

    assert p["laps_in_window"] == 0           # 目盛りが枠の頭 20分 後 ＝ そのあいだに周は無い
    assert p["per_lap_floored"] is True       # 1周の重さは前の枠からの借り
    assert p["carried_laps"] == 5
    assert p["carry_mode"] == "laps"          # **門は `laps_in_window` ではなく `per_lap`**
    assert p["used_now"] == pytest.approx(5 * p["per_lap"])
    assert p["used_now"] > 0                  # 時間で運ぶ側なら 0.0% のまま（`carry_rate` 0）


def test_周で運ばないと床が短い側へ外れる(tmp_path, monkeypatch):
    """**向きを固定する** —— `used_now` が低いほど `forward_rate` は高く、床は**短く**なる。

    「速すぎてよい」側へ外れるので、黙って走り切れてしまう（＝ 色では出ない）。
    """
    _just_rolled(tmp_path, monkeypatch)
    now = RESET + timedelta(hours=6)
    p = quota.pace(now)

    hours_side_forward = (100.0 - 0.0) / p["left_hours"]   # used_now 0.0% で運んだ場合
    assert hours_side_forward > p["forward_rate"]
    assert p["floor_min"] is not None and p["floor_min"] > 0


def test_前の枠にも周が無ければ従来どおり時間で運ぶ(tmp_path, monkeypatch):
    """覆る条件 (a) は生きている —— 借りる先が無ければ `per_lap_floored` は False。"""
    new_g = RESET + timedelta(minutes=20)
    _setup_two_windows(tmp_path, monkeypatch,
                       anchors=[(new_g, 0.0, RESET),
                                (PREV_START + timedelta(hours=120), 60.0, PREV_RESET)],
                       rounds=[RESET + timedelta(hours=h) for h in (1, 2, 3)])
    p = quota.pace(RESET + timedelta(hours=6))
    assert p["per_lap_floored"] is False
    assert p["carry_mode"] == "hours"


def test_門は_per_lap_だけでは足りない(tmp_path, monkeypatch):
    """**単位が違う 2つ を掛けないこと。**

    `per_lap` の分母は `_births_between`（周が無ければ `quota.jsonl` の誕生へ落ちる）、
    `carried_laps` は `rounds.jsonl` の周だけ。**`per_lap` が在るかだけを門にすると**、
    周の台帳が空で誕生だけが在る枠（`tests/test_pace.py` の 08/21 の形）が
    周の側へ落ち、`carried_laps` が構造的に 0 のまま**推定が凍ります**。
    ＝ 門は `laps_in_window or per_lap_floored`（どちらも周の台帳から出た数）。
    """
    g = START + timedelta(hours=30)
    _setup(tmp_path, monkeypatch, anchors=[(g, 10)], rounds=[])   # 周の台帳が空
    p = quota.pace(g + timedelta(hours=10))
    assert p["laps_in_window"] == 0
    assert p["per_lap_floored"] is False
    assert p["carry_mode"] == "hours"
