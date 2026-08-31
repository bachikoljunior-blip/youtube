"""`day_cap.past_split_days()` の検査（2026-09-01）。

## なぜ要るか

`scripts/deadline_check.py` の「**規則（1日1本）の下では、期日までに満ちない要件**」は
直し方を2つ挙げます —— **(2) すでに公開ずみの日で判定できるなら、いま閉じる**。
**その日を探す手が、どこにもありませんでした。**
2026-09-01 の回は使い捨ての script を書いて手で探し、1件を survived で閉じています。

`booked_split_day()` は **`if day < today: continue`** で過ぎた日を飛ばします
（註「過ぎた日は、もう読みのほうで数えています」——**それは上限の話**で、
「どのモデルが当たったか」ではありません）。そして**規則1 の下では、
切り分けの日は二度と予約できません**（1日に十数本 要る）。

## ここで固定している「既知の当たり」

1. **実物の 2026-08-27 が切り分けの日として出る**（出した19本・同分の組0）
2. **比べるのは本数ではなく集合**（対称差）。生きた本数が合っていても、
   生きた本が入れ替わっていることがある（`window()` が 08-27 に直した所）
3. **同分の組がある日・生きた本が3本 未満の日は `separates` を立てない**
   （`config/hypotheses.yaml` の「判定しない条件」(1)(2) と同じ門）
4. **`deadline_check.py` がそれを印字する**（配線が外れたら赤）
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import day_cap as dc  # noqa: E402


def _t(day: str, hhmm: str) -> dt.datetime:
    h, m = hhmm.split(":")
    return dt.datetime.fromisoformat(f"{day}T{h}:{m}:00").replace(tzinfo=dc.JST)


def _fake_qual_days(rows_by_day: dict[str, list[tuple[str, int]]], line: float = 20.0):
    """`_qual_days()` の返りを差し替える（(日, [(時刻, id, 再生)], 死線)）。"""
    def gen(path=None):
        for day, rows in sorted(rows_by_day.items()):
            out = [(_t(day, hhmm), f"v{i}", n) for i, (hhmm, n) in enumerate(rows)]
            yield dt.date.fromisoformat(day), sorted(out), line
    return gen


def test_同分の組がある日は切り分けの日にしない(monkeypatch):
    """`config/hypotheses.yaml` の「判定しない条件」(1) と同じ門。"""
    rows = {"2026-01-01": [("05:00", 0), ("09:00", 300), ("09:00", 0),
                           ("10:00", 200), ("11:00", 100), ("14:00", 0)]}
    monkeypatch.setattr(dc, "_qual_days", _fake_qual_days(rows))
    got = dc.past_split_days(c=3, t_min=13 * 60 + 30, after_min=8 * 60 + 30)
    assert len(got) == 1
    assert got[0]["ties"] >= 1
    assert got[0]["separates"] is False


def test_生きた本が3本未満の日は切り分けの日にしない(monkeypatch):
    """「判定しない条件」(2) —— 縛っているのが上限ではない日。"""
    rows = {"2026-01-02": [("05:00", 0), ("06:00", 0), ("09:00", 300),
                           ("10:00", 200), ("14:00", 0)]}
    monkeypatch.setattr(dc, "_qual_days", _fake_qual_days(rows))
    got = dc.past_split_days(c=3, t_min=13 * 60 + 30, after_min=8 * 60 + 30)
    assert got[0]["alive"] == 2
    assert got[0]["separates"] is False


def test_本数が合っていても本が入れ替わっていれば取り違える(monkeypatch):
    """**比べるのは集合です。** `window()` が 2026-08-27 に直した所と同じ向き。

    生きた本は3本・本数モデルの予測も3本 —— **数は合っています。**
    しかし本数モデルは「先頭3本 ＝ 05:00 / 06:00 / 09:00」と言い、
    実際に生きたのは **09:00 / 10:00 / 11:00**。**取り違えは 4本**です。
    """
    rows = {"2026-01-03": [("05:00", 0), ("06:00", 0),
                           ("09:00", 300), ("10:00", 200), ("11:00", 100)]}
    monkeypatch.setattr(dc, "_qual_days", _fake_qual_days(rows))
    got = dc.past_split_days(c=3, t_min=13 * 60 + 30, after_min=8 * 60 + 30)[0]
    assert got["alive"] == 3
    assert got["pred"]["count"] == 3            # **数は合っている**
    assert got["diff"]["count"] == 4            # **本は入れ替わっている**
    assert got["diff"]["band"] == 0


def test_実物の08_27が切り分けの日として出る():
    """**既知の当たり。** 実データで 2026-08-27 が出ること（API 0単位）。

    2026-09-01 に手で数えた実測: 出した 19本・同分の組 0・生きた 10本、
    取り違えは **帯0 / 窓8 / 本数16**。**3つとも別の集合になる唯一の日**でした。
    """
    days = dc.past_split_days()
    if not days:
        import pytest
        pytest.skip("`data/views.jsonl` に上限の証拠になる日がありません")
    sep = [d for d in days if d["separates"]]
    assert sep, f"切り分けの日が0日です: {[d['day'] for d in days]}"
    assert any(d["day"] == "2026-08-27" for d in sep), [d["day"] for d in sep]
    d27 = next(d for d in sep if d["day"] == "2026-08-27")
    # **帯がいちばん当たっていること。** 逆転したら、前提を開き直すこと
    # （`config/hypotheses.yaml`「1日に再生が付く本の集合は、左端つきの帯…」の覆る条件）。
    assert d27["diff"]["band"] < d27["diff"]["window"] < d27["diff"]["count"], d27


def test_deadline_check_が_公開ずみの日を印字する():
    """**配線の検査。** 外れたら、次の回はまた使い捨ての script を書きます。"""
    src = (ROOT / "scripts" / "deadline_check.py").read_text(encoding="utf-8")
    assert "past_split_lines" in src, \
        "`deadline_check.py` が `day_cap.past_split_lines()` を呼んでいません"
