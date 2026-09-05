"""**同じ題材の本が同じ日の枠に 2本 入っていたら、門が鳴り、掃きが 2本目を外すこと。**
（`scripts/slot_gate.same_topic_twice` / `mismatch_lines` / `scripts/ahead_sweep.dedupe_plan`）

## なぜ要るか（2026-09-05 09:0x に実測で踏んだ）

09/05 は `kzefG44_APU`（09:00）と `a23e696j0f8`（10:00）が同じ台本・同じ題で両方 枠に入っていた。
07:20 の置く手は `--move` を帳面の取り置きで止められ、`place_by_insert` で新しい ID を置いたが、
旧 ID を外す `videos.update` は同じ窓で撃てない。`mismatch_lines()` の「公開ずみの題材」の枝は
その日より前に公開された題材しか見ないので、同じ日の 2本 は見えていなかった
（`python scripts/slot_gate.py` は「食い違いもありません」と言っていた）。
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"_{name}_dupe", ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    if name == "ahead_sweep":
        g = importlib.util.spec_from_file_location("ahead_gate", ROOT / "scripts" / "ahead_gate.py")
        gm = importlib.util.module_from_spec(g)
        sys.modules.setdefault("ahead_gate", gm)
        g.loader.exec_module(gm)
    spec.loader.exec_module(mod)
    return mod


TODAY = date(2026, 9, 5)


def _row(vid: str, at: str, topic: str = "s-shokibo", title: str = "題"):
    return {"id": vid, "at": at, "topic": topic, "title": title, "scheduled": True}


ROWS = [_row("kzefG44_APU", "2026-09-05T00:00:00Z"),
        _row("a23e696j0f8", "2026-09-05T01:00:00Z"),
        _row("other", "2026-09-05T02:00:00Z", topic="s-ikuji")]


def test_同じ題材が2本なら_決めの本を残して他を外す():
    sg = _load("slot_gate")
    got = sg.same_topic_twice(ROWS, today=TODAY,
                              picked={TODAY: {"video_id": "a23e696j0f8"}}, days=1)
    assert got == [{"day": TODAY, "topic": "s-shokibo", "keep": "a23e696j0f8",
                    "drop": ["kzefG44_APU"]}]


def test_決めが無ければ_早いほうを残す():
    sg = _load("slot_gate")
    got = sg.same_topic_twice(ROWS, today=TODAY, picked={}, days=1)
    assert got[0]["keep"] == "kzefG44_APU" and got[0]["drop"] == ["a23e696j0f8"]


def test_別の日の同じ題材は数えない():
    sg = _load("slot_gate")
    rows = [_row("a", "2026-09-05T00:00:00Z"), _row("b", "2026-09-06T00:00:00Z")]
    assert sg.same_topic_twice(rows, today=TODAY, picked={}, days=2) == []


def test_門が鳴って_unschedule_の行を出す():
    sg = _load("slot_gate")
    out = "\n".join(sg.mismatch_lines(rows=ROWS, today=TODAY,
                                      picked={TODAY: {"video_id": "a23e696j0f8"}},
                                      published=set(), days=1))
    assert "同じ題材 `s-shokibo`" in out
    assert "--unschedule kzefG44_APU" in out
    assert "--unschedule a23e696j0f8" not in out


def test_掃きの計画は_きょうぶんだけ():
    sweep = _load("ahead_sweep")
    now = datetime(2026, 9, 5, 9, 30, tzinfo=timezone(timedelta(hours=9))).astimezone(timezone.utc)
    rows = ROWS + [_row("c", "2026-09-06T00:00:00Z", topic="s-x"),
                   _row("d", "2026-09-06T01:00:00Z", topic="s-x")]
    got = sweep.dedupe_plan(now, rows=rows, picked={TODAY: {"video_id": "a23e696j0f8"}})
    assert [d["drop"] for d in got] == [["kzefG44_APU"]]


def test_日枠が閉じていれば_外さない(monkeypatch, capsys):
    sweep = _load("ahead_sweep")
    now = datetime(2026, 9, 5, 9, 30, tzinfo=timezone(timedelta(hours=9))).astimezone(timezone.utc)
    monkeypatch.setattr(sweep, "dedupe_plan",
                        lambda n, rows=None, picked=None: [{"day": TODAY, "topic": "s-shokibo",
                                                            "keep": "a23e696j0f8",
                                                            "drop": ["kzefG44_APU"]}])
    calls: list = []
    monkeypatch.setattr(sweep, "_run", lambda argv, label, timeout=0: calls.append(argv) or 0)
    sweep.dedupe_today(now, quota_open=False)
    assert calls == []
    assert "日枠が尽きています" in capsys.readouterr().out
    sweep.dedupe_today(now, quota_open=True)
    assert calls and calls[0][-2:] == ["--unschedule", "kzefG44_APU"]
