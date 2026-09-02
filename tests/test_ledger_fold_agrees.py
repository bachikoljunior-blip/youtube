"""**控えのたたみ方を、道具ごとに変えないこと。**

## 実物（2026-09-02・最適化の回。**画面を2つ並べて踏んだ**）

同じ控え（`data/uploaded.jsonl`）を読んでいる2つの道具が、別のことを言いました:

    python -m src.next_slot       [次の枠] **09/04 13:00 JST（あと 45時間）に出る1本**
    python scripts/ahead_gate.py  先の日付の予約 **2026-09-24 〜 2026-10-10**（09/04 は無い）

原因は**たたみ方**でした。`DyEcaMK5ZU8` の行は2つ在ります:

    508行目  at = 2026-10-10T00:00:00Z   retimed_at = 2026-08-26T07:**10**:57  ← 本物
    511行目  at = 2026-09-04T04:00:00Z   retimed_at = 2026-08-26T07:**08**:07

**後ろの行のほうが、2分 古い。** `src/next_slot._rows()` は
`latest[video_id] = r` の素通し ＝ **ファイルの最後の行が勝つ**ので、
**在りもしない 09/04 の枠**を拾っていました。

`src/dupes._collapse()` は 2026-08-25 からこれを正しく解いています ——
**「勝つ行は `retimed_at` がいちばん新しい行、無ければ最後の行」**。
`retimed_at` は **`videos.update` を通った側を言う唯一の手がかり**だからです。
`status.py` / `slot_gate.py` / `ahead_gate.py` / `pool_drain.py` は
全部そちらを読んでいて、**`src/next_slot.py` だけが別でした。**

## 何が壊れていたか

`[次の枠]` は **`improve` の当てどころ**です（`lines()` の最後の行が
「規則3 が言っているのはこの1本のことです」と書いています）。
**主実行は、在りもしない枠に向かって規則3 を回していました** ——
「あと 45時間」も `swap_cost_lines()` の見積りも、その幻の上に乗ります。

## 発火を確かめてあること（**発火したことのない検査は検査ではない**）

`test_older_row_placed_last_does_not_win` は、**実物と同じ並び**
（新しい `retimed_at` の行を先に、古い行を後ろに）を注入します。
素通しの実装だと **09/04 を拾って落ちます。**

## 覆る条件

`retime()` が印を押さなくなったら `_retime_key` は両方 `(0, "")` を返し、
たたみ方は「最後の行」へ落ちます ＝ **素通しと同じ**。
そのときは**印のほうを直すこと**（この検査もそこで意味を失います）。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import dupes, next_slot  # noqa: E402

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 9, 2, 5, 0, tzinfo=timezone.utc)      # 09/02 14:00 JST

VID = "DyEcaMK5ZU8"
#: **実物の並び**（新しい `retimed_at` が先・古いほうが後ろ）。
_REAL_ORDER = [
    {"video_id": VID, "topic": "s-keihi", "title": "経費1万円の節税額",
     "at": "2026-10-10T00:00:00Z", "uploaded_at": "2026-08-24T03:34:52+00:00",
     "retimed_at": "2026-08-26T07:10:57+00:00"},
    {"video_id": VID, "topic": "s-keihi", "title": "経費1万円の節税額",
     "at": "2026-09-04T04:00:00Z", "uploaded_at": "2026-08-24T03:34:52+00:00",
     "retimed_at": "2026-08-26T07:08:07+00:00"},
]


def _ledger(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "uploaded.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows),
                 encoding="utf-8")
    return p


def test_older_row_placed_last_does_not_win(tmp_path):
    """**発火。** 後ろの行のほうが古いとき、それを拾わないこと。"""
    p = _ledger(tmp_path, _REAL_ORDER)
    got = next_slot.latest_rows(p)[VID]
    assert got["at"] == "2026-10-10T00:00:00Z", (
        "ファイルの最後の行を採っています（`retimed_at` は 2分 古い）。"
        "在りもしない 09/04 の枠を拾います")


def test_next_video_uses_the_folded_row(tmp_path):
    """`[次の枠]`（＝ `improve` の当てどころ）が、幻の枠を指さないこと。"""
    p = _ledger(tmp_path, _REAL_ORDER)
    v = next_slot.next_video(now=NOW, path=p)
    assert v is not None
    assert v["_at"].astimezone(JST).date().isoformat() == "2026-10-10"


def test_newest_retime_wins_regardless_of_order(tmp_path):
    """**並べ替えても答えが変わらないこと**（順番に依らないのが「たたむ」の意味）。"""
    for rows in (_REAL_ORDER, list(reversed(_REAL_ORDER))):
        p = _ledger(tmp_path, rows)
        assert next_slot.latest_rows(p)[VID]["at"] == "2026-10-10T00:00:00Z"


def test_falls_back_to_last_row_without_a_stamp(tmp_path):
    """**印が無い回は「最後の行」**（`_collapse` の註と同じ規則）。"""
    rows = [{**r, "retimed_at": None} for r in _REAL_ORDER]
    p = _ledger(tmp_path, rows)
    assert next_slot.latest_rows(p)[VID]["at"] == "2026-09-04T04:00:00Z"


def test_the_rule_comes_from_one_place():
    """**目盛りの出どころは `src/dupes` の1か所**（写しを作らないこと）。"""
    assert hasattr(dupes, "_retime_key")
    hi = dupes._retime_key(_REAL_ORDER[0])
    lo = dupes._retime_key(_REAL_ORDER[1])
    assert hi > lo, "`retimed_at` の新しいほうが勝つ、が崩れています"


def test_both_tools_agree_on_the_real_ledger():
    """**実物で、2つの道具の `at` が1本も食い違わないこと。**

    これがこの回に踏んだ形そのものです（`next_slot` 09/04 対 `ahead_gate` 09/24）。
    """
    theirs = {r["id"]: r.get("at") for r in dupes.ledger_rows() if r.get("id")}
    mine = next_slot.latest_rows()
    bad = [(v, mine[v].get("at"), theirs[v]) for v in mine
           if v in theirs and mine[v].get("at") != theirs[v]]
    assert not bad, f"同じ控えで `at` が食い違っています: {bad[:5]}"
