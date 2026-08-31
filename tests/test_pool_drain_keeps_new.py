"""**池化は、きょう作った1本を外さないこと。**（2026-08-31・実物で踏んだ）

`scripts/pool_drain.py` は「未来の予約」を全部 池に入れていました。
**その日に作って予約したばかりの1本も、同じ扱いで外れます。**

実測（2026-08-31 08:41 UTC）: その回の1本 `J67vEIw_VRE`（09/05 20:00 JST に予約）は、
前の回が 09/01〜09/11 を先に外し終えていたせいで **公開の早い順で3番目**に並び、
**14本のうちの1本として外れました。** 同じ回が「きょうの1本を予約まで入れた」と
commit した 90秒後です。日枠はその時点で尽きており、入れ直しは次の窓まで待ちに
なりました。

**「公開が近い順」は正しい。** 間違っていたのは池の中身のほうで、
池に入れてよいのは **作り置き**（`src.house_rule.is_stockpile()`）だけです。

**戻すにはこの検査を消すしかありません。**
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import pool_drain  # noqa: E402
from src import house_rule  # noqa: E402

NOW = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)


def _row(vid: str, at: str, made: str) -> dict:
    return {"id": vid, "video_id": vid, "at": at,
            "uploaded_at": made, "title": vid, "topic": vid}


def test_規則の下で作った1本は池に入らない():
    new = _row("today", "2026-09-05T11:00:00Z",
               house_rule.STOCKPILE_SINCE + "T08:40:00+00:00")
    old = _row("piled", "2026-09-04T04:00:00Z", "2026-08-25T00:00:00+00:00")
    got = pool_drain.pool(now=NOW, rows=[new, old])
    ids = [r["id"] for r in got]
    assert ids == ["piled"], (
        f"池に {ids} が入っています。**きょう作った1本が外れます** ——\n"
        "  `pool()` は `src.house_rule.is_stockpile()` を通すこと"
        "（規則より前に作った本だけが作り置きです）。"
    )


def test_公開が近い順に並ぶこと():
    """外す順は変えません（**放っておくと出てしまう順**）。"""
    a = _row("a", "2026-09-20T00:00:00Z", "2026-08-20T00:00:00+00:00")
    b = _row("b", "2026-09-03T00:00:00Z", "2026-08-20T00:00:00+00:00")
    got = pool_drain.pool(now=NOW, rows=[a, b])
    assert [r["id"] for r in got] == ["b", "a"]


def test_公開済みは池に入らない():
    past = _row("gone", "2026-08-20T00:00:00Z", "2026-08-19T00:00:00+00:00")
    assert pool_drain.pool(now=NOW, rows=[past]) == []


def test_余白の内側の予約は触らない():
    """`LEDGER_MARGIN` の内側（1時間以内）は「もう先ではない」扱い。"""
    soon = (NOW + timedelta(minutes=30)).isoformat().replace("+00:00", "Z")
    assert pool_drain.pool(now=NOW,
                           rows=[_row("soon", soon,
                                      "2026-08-20T00:00:00+00:00")]) == []
