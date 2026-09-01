"""**0単位で印字した案が、枠の戻った回にそのまま撃てること。**

## なぜ要るか（2026-09-02 01:0x に測って足した。**15時間後に効く欠陥でした**）

`--compact`（API 0単位）を印字する回と、`--compact --apply`（1本50単位）を
撃つ回は**別の回**です。日枠は 1日1回・JST 16:00 に戻るので、
**尽きている窓の回が案を作り、次の窓の回が撃つ**のが既定の形になります。

そのとき `compact_plan` が見ていたのは `now + lead_min` だけでした。結果:

    いま 01:07 JST の案の1行目
        09/02 13:00 → 09/02 09:00  a63FzIUV2wI
    枠が戻るのは 09/02 16:00 JST

**置き先の 09:00 も、動かす本の公開 13:00 も、枠が戻る 3時間 前**
＝ その行は撃てる時刻に1つも残っていません。さらに悪いことに、
その1本が 13:00 に公開されると錨（＝いちばん早い予約の日）が **09/24 へ 22日 跳び**、
**穴の 09/03〜09/23（20日）が目盛りから丸ごと消えて**、
`max_days` を 26〜40 のどれにしても `SystemExit`（後ろへ動かす割り当て）でした。

ここで固定するのは2つ:

    1. `writable_from` を渡したら、**それより前の置き先は案に入らない**
    2. `writable_from` を渡した案は、**その時刻に解き直しても同じ**
       （＝ 印字した回と撃つ回が別でも、同じものが撃てる）
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

reschedule = pytest.importorskip("reschedule")

JST = timezone(timedelta(hours=9))
EMPTY = ("", "")
#: 2026-09-02 01:00 JST。実際にこの欠陥を踏んだ時刻。
NOW = datetime(2026, 9, 1, 16, 0, tzinfo=timezone.utc)
#: 枠が戻るのは 09/02 16:00 JST。
BACK = datetime(2026, 9, 2, 7, 0, tzinfo=timezone.utc)


def _row(vid: str, at_jst: str) -> dict:
    at = datetime.fromisoformat(at_jst).replace(tzinfo=JST).astimezone(timezone.utc)
    return {"id": vid, "topic": "s-x", "title": vid,
            "at": at.strftime("%Y-%m-%dT%H:%M:%SZ")}


def _ids(plan) -> list[str]:
    return [p["id"] for p in plan]


def _pairs(plan) -> list[tuple[str, str]]:
    return [(p["id"], p["new"]) for p in plan]


#: 実際の控えの形 —— 手前に1本、22日 空けて山（1日3本）。
ROWS = ([_row("head", "2026-09-02T13:00")]
        + [_row(f"v{i}", f"2026-09-2{4 + i // 3}T{10 + i % 3:02d}:00") for i in range(9)])


def test_枠が戻る前の置き先は案に入らない():
    plan = reschedule.compact_plan(ROWS, now=NOW, max_days=30, lead_min=60,
                                   window=EMPTY, live_edge_min=9 * 60,
                                   writable_from=BACK)
    assert plan, "動かす本が1本も出ないのは、この欠陥の再発です"
    for p in plan:
        new = datetime.fromisoformat(p["new"].replace("Z", "+00:00"))
        assert new > BACK, f"{p['id']} の置き先が枠の戻る前: {p}"
    # 枠が戻る前に出る本（09/02 13:00）は、動かしようがないので対象外
    assert "head" not in _ids(plan)


def test_印字した案が枠の戻った回にそのまま撃てる():
    """**前は、同じ引数が 16:05 に `SystemExit` になっていました。**"""
    before = reschedule.compact_plan(ROWS, now=NOW, max_days=30, lead_min=60,
                                     window=EMPTY, live_edge_min=9 * 60,
                                     writable_from=BACK)
    # 枠が戻った回: `head` は公開ずみ、`writable_from` は要らない（撃てる）
    after = reschedule.compact_plan(ROWS, now=BACK + timedelta(minutes=5),
                                    max_days=30, lead_min=60, window=EMPTY,
                                    live_edge_min=9 * 60)
    assert _pairs(before) == _pairs(after)


def test_穴の手前の1本が出ても穴は目盛りに残る():
    """**錨が「いちばん早い予約の日」だと、ここで 22日 跳びました。**"""
    after = reschedule.compact_plan(ROWS, now=BACK + timedelta(minutes=5),
                                    max_days=30, lead_min=60, window=EMPTY,
                                    live_edge_min=9 * 60)
    days = sorted({p["new"][:10] for p in after})
    assert days[0] == "2026-09-03", days      # 穴の先頭から埋まる
    assert len(days) == len(after) == 9       # 1日1本
    for p in after:
        assert p["new"] <= p["old"], p


def test_writable_from_を渡さなければ今までどおり():
    """**既定は据え置き**（渡さない呼び側を壊さない）。"""
    plan = reschedule.compact_plan(ROWS, now=NOW, max_days=30, lead_min=60,
                                   window=EMPTY, live_edge_min=9 * 60)
    assert [p["new"] for p in plan][0] < BACK.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_writable_from_は日枠が尽きているときだけ返る(monkeypatch):
    from src import next_slot, quota_ledger
    monkeypatch.setattr(quota_ledger, "spent",
                        lambda now=None: {"data": quota_ledger.DAY_UNITS + 1})
    assert next_slot.writable_from(NOW) is not None
    monkeypatch.setattr(quota_ledger, "spent", lambda now=None: {"data": 0})
    assert next_slot.writable_from(NOW) is None
