"""**長尺の詰め直しが「前倒し 0日」の手を出さないこと**（2026-08-27 に測って足した）。

## なぜ要るか

`reschedule.long_pack_plan` の 08-26 版は「動かす長尺の枠は空いている」として
**全部を並べ替え**ていました。本物の控えで撃った実測（2026-08-27）:

    14手 ／ **前倒しの合計 0日**
      08/28 21:00 → 08/28 **19:00**
      08/28 22:00 → 08/28 **18:00**
      08/29 21:00 → 08/29 **19:00** …

**同じ日の中で時刻をずらしているだけ**です。`batch_build._pack_long_form()` は
これを毎周 撃つので、**1周あたり 14手 × 50単位 ＝ 700単位**が
「前倒し 0日」に消えます。日枠は 10,000単位・`videos.insert` は 1本 1,600単位
なので、**上げられたはずの本に換算して 1周 0.4本**。

**長尺の時刻に意味はありません**（`LONG_HOURS_JST` の註 —— 長尺は
`SHORTS_FEED` の枠を1つも使わないので、夜に置いても生死に掛からない）。
**意味があるのは日付だけ**なので、日が縮まない手は値打ちが 0 です。

## ここが壊れたと分かる形

同じ日の中の入れ替えが1つでも計画に出たら、その回から
**日枠が「前倒し 0日」に食われはじめます。**
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import reschedule  # noqa: E402

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 8, 27, 10, 0, tzinfo=JST)


def _row(vid: str, at: datetime, topic: str = "t") -> dict:
    return {"id": vid, "topic": topic,
            "at": at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


def _packed_days(days: int, per_day: int = 5) -> tuple[list[dict], dict[str, float]]:
    """**すでに 1日 `per_day` 本で詰まっている**長尺の並び（**`NOW` の日から**）。

    **【2026-08-29 に、起点を 08/28 から `NOW` の日へ直しました】**

    ここは `head = datetime(2026, 8, 28)` で、`NOW` は **08/27 10:00 JST** ——
    **今日の夕方（18〜22時）が丸ごと空いたまま「詰まりきっている」と
    名乗っていました。** `long_pack_plan` が今日の空き枠を使えるようになった時点で、
    09/03 の本を **08/27 18:00** へ（＝ **7日 手前**へ）出す手が出て、
    この盤を使う2件が赤くなりました。

    **出ていた手は正しい**（日が7日 縮んでいる）。**偽だったのは盤のほう**です ——
    「詰まりきっている」と言いながら、いちばん手前の日を空けていました。
    `LONG_HOURS_JST[:5]` は 18〜22時 なので、`NOW`（10:00）より後ろ ＝
    **今日も本当に埋められます。**

    **この検査が守っているのは「日が縮まない手を出さないこと」**で、
    それは `test_同じ日の中の入れ替えは出さない` が別に見ています（そちらは緑のまま）。
    """
    rows, dur = [], {}
    hours = sorted(reschedule.LONG_HOURS_JST[:per_day])
    head = NOW.replace(hour=0, minute=0, second=0, microsecond=0)
    for d in range(days):
        day = head + timedelta(days=d)
        for h in hours:
            vid = f"L{d}{h}"
            rows.append(_row(vid, day.replace(hour=h)))
            dur[vid] = 300.0
    return rows, dur


def test_詰まりきっているなら1手も出さない():
    """**ここが 08-26 版の 14手 です。**"""
    rows, dur = _packed_days(7)
    plan = reschedule.long_pack_plan(rows, dur, now=NOW, per_day=5)
    assert plan == [], (
        f"詰まりきっているのに {len(plan)}手 出ています: "
        + ", ".join(f"{p['old']:%m/%d %H:%M}→{p['new']:%m/%d %H:%M}" for p in plan[:4]))


def test_同じ日の中の入れ替えは出さない():
    rows, dur = _packed_days(7)
    plan = reschedule.long_pack_plan(rows, dur, now=NOW, per_day=5)
    for p in plan:
        assert p["new"].date() < p["old"].date(), (
            f"{p['id']} は日が縮んでいません（{p['old']} → {p['new']}）")


def test_穴の後ろに取り残された本を前へ出す():
    """**08-26 版が届かなかった形**（早い本から早い枠へ、だと順番が回らない）。

    手前の日は詰まっていて、**ずっと後ろに1本だけ**居る。
    その1本は、詰まりの先にある空き日へ出せます。
    """
    rows, dur = _packed_days(3)              # 08/27・08/28・08/29 が 5本ずつ
    rows.append(_row("FAR", datetime(2026, 10, 3, 11, 30, tzinfo=JST), "far"))
    dur["FAR"] = 320.0
    plan = reschedule.long_pack_plan(rows, dur, now=NOW, per_day=5)
    assert [p["id"] for p in plan] == ["FAR"], f"取り残しを出せていません: {plan}"
    # **いちばん早い空き日は 08/30**（08/27〜08/29 が満杯・`_packed_days` の註）
    assert plan[0]["new"].date() == datetime(2026, 8, 30).date(), (
        f"いちばん早い空き日へ出していません: {plan[0]['new']}")


def test_後ろの本ほど先に前へ出す():
    """**遅い本から順に、いちばん早い空き枠へ。** 前倒しの合計を最大にします。"""
    rows, dur = _packed_days(2)              # 08/28・08/29 が満杯
    for i, day in enumerate((20, 25, 30)):
        vid = f"F{i}"
        rows.append(_row(vid, datetime(2026, 9, day, 11, 0, tzinfo=JST)))
        dur[vid] = 320.0
    plan = reschedule.long_pack_plan(rows, dur, now=NOW, per_day=5)
    first = min(plan, key=lambda p: p["new"])
    assert first["id"] == "F2", (
        f"いちばん後ろの本（09/30）ではなく {first['id']} を先頭へ出しています")
    gain = sum((p["old"] - p["new"]).days for p in plan)
    assert gain > 0, "前倒しが 0日 です"


def test_公開済みと今より手前は動かさない():
    rows, dur = _packed_days(2)
    past = _row("OLD", datetime(2026, 8, 20, 20, 0, tzinfo=JST))
    rows.append(past)
    dur["OLD"] = 300.0
    plan = reschedule.long_pack_plan(rows, dur, now=NOW, per_day=5)
    assert all(p["id"] != "OLD" for p in plan)
    assert all(p["new"] > NOW for p in plan)
