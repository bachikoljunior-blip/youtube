"""`--write` の画面に「**機械はこの本を焼き直すつもりか**」を出すこと。

実測 2026-09-03: 画面は「焼いたのは 04:37 JST。そのあと 6件 入っています」と
正しく言い、手で撃つ1行まで出していたのに、**機械が朝から止まっている**ことは
どこにも出ていなかった（掃きの `[rebake]` は `data/ahead_sweep.log` にしか出ない）。
註は `next_slot.machine_rebake_lines()`。
"""
from __future__ import annotations

import pathlib
from datetime import datetime, timedelta, timezone

import pytest

from src import next_slot

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 9, 3, 13, 20, tzinfo=JST)


def _patch(monkeypatch: pytest.MonkeyPatch, plan: dict, rows: list[dict]) -> None:
    from scripts import ahead_sweep

    monkeypatch.setattr(ahead_sweep, "rebake_plan_for",
                        lambda day, now, **kw: dict(plan))
    monkeypatch.setattr(ahead_sweep, "_rebake_rows", lambda root=None: list(rows))


def test_機械も焼くなら手で撃つなと言う(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, {"do": True, "video_id": "V", "sha": "s", "why": ""}, [])
    out = "\n".join(next_slot.machine_rebake_lines("V", NOW))
    assert "機械も焼き直します" in out
    assert "2本" in out


def test_止まっているなら理由をそのまま出す(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch,
           {"do": False, "video_id": "V", "sha": "s", "why": "きょう既に 2回 焼いた（上限 2）"},
           [])
    out = "\n".join(next_slot.machine_rebake_lines("V", NOW))
    assert "機械は焼き直しません" in out
    assert "きょう既に 2回 焼いた" in out
    assert "見送らないこと" in out


def test_焼いている最中を_もう焼いたと混ぜない(monkeypatch: pytest.MonkeyPatch) -> None:
    """`rebake_attempted()` は「いま焼いている」も「もう焼いた」も True にする。"""
    _patch(monkeypatch,
           {"do": False, "video_id": "V", "sha": "s", "why": "同じ台本（sha s）は一度 焼いた"},
           [{"at": "2026-09-03T13:12:00+09:00", "kind": "start", "video_id": "V", "sha": "s"}])
    out = "\n".join(next_slot.machine_rebake_lines("V", NOW))
    assert "いま焼いています" in out
    assert "13:12" in out


def test_弾かれた回は_いま焼いている扱いにしない(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch,
           {"do": False, "video_id": "V", "sha": "s", "why": "同じ台本（sha s）は一度 焼いた"},
           [{"at": "2026-09-03T11:41:52+09:00", "kind": "start", "video_id": "V", "sha": "s"},
            {"at": "2026-09-03T11:41:53+09:00", "kind": "skip", "video_id": "V", "sha": "s"}])
    out = "\n".join(next_slot.machine_rebake_lines("V", NOW))
    assert "いま焼いています" not in out
    assert "機械は焼き直しません" in out


def test_本が無ければ何も言わない() -> None:
    assert next_slot.machine_rebake_lines("", NOW) == []


def test_焼いている印は_手の1行を落とす目印になる(monkeypatch: pytest.MonkeyPatch) -> None:
    """**同じ画面が、同じ本について逆のことを2行 並べていた**（2026-09-03 13:2x の実物）:

        いま焼いています —— **手で撃たないこと。同じ本が2本 上がります**
        → **焼き直すのが `improve` の1手です**（`python -m src.pipeline` …）   ← 次の行

    05:1x の回は、これで手と機械が同じ sha を焼き、片方を止めている。
    `lines()` は、この2つの語のどちらかが出ていたら手の1行を出さない。
    """
    _patch(monkeypatch,
           {"do": False, "video_id": "V", "sha": "s", "why": "同じ台本（sha s）は一度 焼いた"},
           [{"at": "2026-09-03T13:12:00+09:00", "kind": "start", "video_id": "V", "sha": "s"}])
    body = next_slot.machine_rebake_lines("V", NOW)
    assert any(("いま焼いています" in ln) or ("機械も焼き直します" in ln) for ln in body)

    src = (pathlib.Path(next_slot.__file__)).read_text(encoding="utf-8")
    assert "machine_has_it" in src
    assert "if not machine_has_it:" in src

