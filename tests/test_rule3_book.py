"""**規則3 の主語は「次の投稿予定に出る本」です。**（2026-09-05 01:4x に実物で踏んだ）

オーナーの固定（原文・`CLAUDE.md` 冒頭）:
**「次の投稿予定までにそこで投稿する動画を改善し続ける」**

`untreated_slot()` は `daily_pick.current(daily_pick.for_day())` で引いていました。
`for_day()` が返すのは「**まだ決めていない次の日**」で、**別のもの**です。実測::

    next_slot.next_video()  → `GFvAcxvDmYM`（09/05 09:00 JST・あと 7.5時間）
    daily_pick.for_day()    → 2026-09-06 → `DtpnSVFDtAE`（あと 31時間）

`dry_ledger_gate()` は、その名前を `--ship` に書いた回しか通しません（台帳が空の日）——
**きょう出る本を直した回が止められ、あしたの本を名乗った回が通っていました。**
"""
from __future__ import annotations

import scripts.run_marker as rm


def test_予約に立っている次の本を採る():
    got = rm.rule3_book(
        next_call=lambda: {"video_id": "NEXT", "topic": "t-next"},
        pick_call=lambda: {"video_id": "PICK", "topic": "t-pick"})
    assert got["video_id"] == "NEXT"
    assert got["src"] == "next_slot.next_video"


def test_予約が無ければ決めへ落ちる():
    """**1本も予約が無い日は、決めが唯一の名指しできる本です。**"""
    got = rm.rule3_book(next_call=lambda: None,
                        pick_call=lambda: {"video_id": "PICK", "topic": "t-pick"})
    assert got["video_id"] == "PICK"
    assert got["src"] == "daily_pick.current(for_day)"


def test_どちらも無ければ名乗らない():
    # 名指しできる本が無い日は `dry_ledger_gate` の `can_name` が偽 ＝ 免除はそのまま。
    assert rm.rule3_book(next_call=lambda: None, pick_call=lambda: None) is None


def test_次の本が題材だけでも採る():
    got = rm.rule3_book(next_call=lambda: {"topic": "t-only"},
                        pick_call=lambda: {"video_id": "PICK"})
    assert got["topic"] == "t-only"
    assert got["video_id"] == ""


def test_次の本が空の行なら決めへ落ちる():
    """`video_id` も `topic` も無い行を「名乗れた」に数えないこと。"""
    got = rm.rule3_book(next_call=lambda: {"at": "2026-09-05T00:00:00Z"},
                        pick_call=lambda: {"video_id": "PICK", "topic": "t"})
    assert got["video_id"] == "PICK"


def test_次の本が読めなくても止まらない():
    def boom():
        raise RuntimeError("控えが読めません")

    got = rm.rule3_book(next_call=boom,
                        pick_call=lambda: {"video_id": "PICK", "topic": "t"})
    assert got["video_id"] == "PICK"


def test_門は名乗った回だけ通す():
    """`dry_ledger_gate` の向き —— 名乗れば通り、名乗らなければ止まる。"""
    slot = {"video_id": "GFvAcxvDmYM", "topic": "nenkin"}
    named = rm.dry_ledger_gate("fix: GFvAcxvDmYM の題を直した", [], slot, True)
    assert named["slot_fix"] is True
    assert named["trip"] is False

    other = rm.dry_ledger_gate("fix: 計器を直した", [], slot, True)
    assert other["slot_fix"] is False
    assert other["trip"] is True


def test_実物_規則3の本は次に出る本():
    """**この回が踏んだ形。** 予約が在るあいだ、規則3 の本は `next_video()` の側です。

    覆る条件: 予約が1本も無い日は `src` が `daily_pick.current(for_day)` になります
    （どちらでも名乗れる本は1つ）。
    """
    got = rm.rule3_book()
    if got is None:          # 予約も決めも無い日（この検査は何も言いません）
        return
    assert got["src"] in ("next_slot.next_video", "daily_pick.current(for_day)")
    assert got["video_id"] or got["topic"]
