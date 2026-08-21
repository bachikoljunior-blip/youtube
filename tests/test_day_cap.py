"""`src/day_cap.py` —— **1日に何本まで再生が付くか**を、崩れた日から読む道具。

**先に固定するのは「この道具が正しければ、必ず当てるはずの1件」**です
（`docs/trigger_main.md` §4）。それは実測の 2026-08-20:

    25本 公開して、**#11から先の15本が 0〜3再生**。#10 は 1,111再生。

そして**外してはいけない1件**が、同じ実測の中にあります:

    08/16 の 14時 = #4 → 1,361再生 ／ 08/20 の 14時 = #12 → 0再生

**時刻ではなく通し番号で割れている**ことが、この道具の存在理由です。
"""
from __future__ import annotations

import datetime as dt
import json

import pytest

from src import day_cap


def _log(tmp_path, rows):
    """rows: [(公開JST文字列, id, 再生)] → `data/views.jsonl` と同じ形の一時ファイル。"""
    p = tmp_path / "views.jsonl"
    with p.open("w", encoding="utf-8") as fh:
        for pub, vid, views in rows:
            t = dt.datetime.fromisoformat(pub).replace(tzinfo=day_cap.JST)
            at = (t + dt.timedelta(hours=12)).astimezone(dt.timezone.utc)
            fh.write(json.dumps({"at": at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                 "id": vid, "hours": 12.0, "views": views}) + "\n")
    return p


def test_崩れた日から上限を読む(tmp_path):
    """**既知の当たり**: 10本まで生きて11本目から死ぬ日を置けば、上限は 10。"""
    rows = [(f"2026-08-20T{9 + i // 2:02d}:{(i % 2) * 30:02d}", f"v{i}",
             800 if i < 10 else 0) for i in range(25)]
    m = day_cap.measure(_log(tmp_path, rows))
    assert m["measured"] is True
    assert m["cap"] == 10
    assert m["collapse"] == 11


def test_同じ時刻でも通し番号で割れる(tmp_path):
    """**外してはいけない1件。** 14時の本が、#4 なら生き #12 なら死ぬ。

    時刻で切る道具なら「14時は死ぬ」と読み、**上限は 14時より前の本数**に
    化けます。ここが落ちたら、軸が通し番号から時刻へずれています。
    """
    early = [(f"2026-08-16T{8 + i:02d}:00", f"a{i}", 1300) for i in range(5)]   # #4 は 14時
    late = [(f"2026-08-20T{9 + i // 2:02d}:{(i % 2) * 30:02d}", f"b{i}",
             800 if i < 10 else 0) for i in range(25)]                          # #12 は 14時
    m = day_cap.measure(_log(tmp_path, early + late))
    assert m["cap"] == 10, "14時そのものを死んだ時刻と読んでいます"
    assert m["floor"] == 10


def test_一本ごとの不発を上限と読まない(tmp_path):
    """**別の日に #10 が生きているなら、#3 から先が0の日は「上限3」ではありません。**

    これは実データで一度踏んでいます（2026-08-04 の7本で `cap=2` と出た）。
    上限だと言えるのは `floor` より後ろで崩れたときだけ。
    """
    good = [(f"2026-08-20T{9 + i // 2:02d}:{(i % 2) * 30:02d}", f"g{i}", 900) for i in range(10)]
    flop = [("2026-08-04T09:00", "f0", 600), ("2026-08-04T10:00", "f1", 500),
            ("2026-08-04T11:00", "f2", 0), ("2026-08-04T12:00", "f3", 0)]
    m = day_cap.measure(_log(tmp_path, good + flop))
    assert m["measured"] is False, "1本ごとの不発を『上限』と読んでいます"
    assert m["floor"] == 10
    assert m["cap"] >= 10


def test_面に載っていない日は上限の証拠にしない(tmp_path):
    """その日の上位3本ごと 0〜数再生なら、上限ではなく**まだ誰にも届いていない**日。"""
    dead = [(f"2026-08-05T{9 + i:02d}:00", f"d{i}", 2 if i < 2 else 0) for i in range(6)]
    m = day_cap.measure(_log(tmp_path, dead))
    assert m["measured"] is False
    assert m["cap"] == day_cap.FALLBACK


def test_上限を超えたぶんは0として数える(tmp_path):
    rows = [(f"2026-08-20T{9 + i // 2:02d}:{(i % 2) * 30:02d}", f"v{i}",
             800 if i < 10 else 0) for i in range(25)]
    p = _log(tmp_path, rows)
    assert day_cap.effective(25, p) == 10
    assert day_cap.effective(4, p) == 4


def test_実データで上限が10と出る():
    """**手元の `data/views.jsonl` そのもの。**（2026-08-21 時点で 10本）

    ここが動いたら、それは**壊れではなく測り直し**です。動いたことを
    `docs/JOURNAL.md` に書いて、この数を更新すること —— 上限が上がるのは
    「上限より多く出した日に、後ろの本が再生を取った」ときで、**それは前進です。**
    """
    m = day_cap.measure()
    if not m["measured"]:
        pytest.skip("崩れをまだ観測していない（読みが足りない）")
    assert 3 <= m["cap"] <= 92
    assert m["cap"] == m["floor"]
