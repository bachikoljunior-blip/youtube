"""**同じ分に2本入っている予約を、道具が見つけるか。**

2026-08-25。前の回は控えを**手で並べて**見つけました。
`reschedule.py --list` の「二重予約」は同じテーマの重なりを見ており、
`status.py` は日ごとの本数しか見ていません ——
**手で並べる回が来なければ、そのまま公開されます。**
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import collisions  # noqa: E402

TODAY = "2026-08-25"


def row(vid: str, at: str) -> dict:
    return {"id": vid, "at": at, "topic": vid}


def test_finds_two_videos_in_one_minute() -> None:
    rows = [row("a", "2026-08-27T00:00:00Z"), row("b", "2026-08-27T00:00:00Z")]
    hits = collisions.upcoming(rows, today=TODAY)
    assert len(hits) == 1
    assert hits[0]["at"] == "09:00"          # 00:00Z ＝ 09:00 JST
    assert hits[0]["video_ids"] == ["a", "b"]


def test_the_key_is_id_not_video_id() -> None:
    """`dupes.ledger_rows()` は `video_id` を `id` に畳みます。

    **生の名前で読むと全部 None になり、衝突が1件も見えません**
    （2026-08-25 にそのまま踏んで、8本が 0件 に見えました）。
    """
    rows = [{"video_id": "a", "at": "2026-08-27T00:00:00Z"},
            {"video_id": "b", "at": "2026-08-27T00:00:00Z"}]
    assert collisions.upcoming(rows, today=TODAY)[0]["video_ids"] == ["?", "?"]


def test_different_minutes_are_not_a_hit() -> None:
    rows = [row("a", "2026-08-27T00:00:00Z"), row("b", "2026-08-27T00:30:00Z")]
    assert collisions.upcoming(rows, today=TODAY) == []


def test_the_past_is_not_reported() -> None:
    """過ぎた日は鳴らさない（**もう動かせないので、鳴らしても手がありません**）。"""
    rows = [row("a", "2026-08-20T00:00:00Z"), row("b", "2026-08-20T00:00:00Z")]
    assert collisions.upcoming(rows, today=TODAY) == []


def test_excess_counts_what_a_repair_removes() -> None:
    rows = [row("a", "2026-08-28T00:00:00Z"), row("b", "2026-08-28T00:00:00Z"),
            row("c", "2026-08-28T00:00:00Z")]
    assert collisions.excess(collisions.upcoming(rows, today=TODAY)) == 2


def test_plan_moves_within_the_day_when_it_can() -> None:
    """窓でない日は**同じ日の空き分**へ寄せる（本数が変わらないので、いちばん安い）。"""
    rows = [row("a", "2026-08-28T00:00:00Z"), row("b", "2026-08-28T00:00:00Z")]
    moves = collisions.plan(rows, today=TODAY)
    assert len(moves) == 1
    assert moves[0]["id"] == "b"
    assert moves[0]["to"].startswith("2026-08-28T")
    assert moves[0]["to"] != "2026-08-28T09:00"


def test_plan_fills_the_holes_on_the_measure_window_day() -> None:
    """**測定の窓の日は、まずその日の空き分へ寄せる**（2026-08-25 に逆へ直した）。

    前の版は「同じ日へ逃がすと 13:30 より後ろへ出る」を理由に別の日へ出していました。
    **逃がす先は `grid`（05:00〜13:30）からしか採らないので、後ろへは出ません。**
    そして寄せたぶんだけ「窓の説」の予測が上がり、**切り分けの分解能が上がります。**
    """
    rows = [row("a", "2026-08-27T00:00:00Z"),   # 09:00 JST
            row("b", "2026-08-27T00:00:00Z"),   # 09:00 JST（衝突）
            row("z", "2026-08-26T20:00:00Z"),   # 08/27 05:00 JST ＝ 早い側の枠が埋まる
            row("c", "2026-08-29T00:00:00Z")]
    moves = collisions.plan(rows, today=TODAY)
    assert len(moves) == 1
    assert moves[0]["id"] == "b"
    assert moves[0]["to"].startswith("2026-08-27T")     # **同じ日に残る**
    assert moves[0]["force_window"] is True             # 窓の日なので force が要る


def test_plan_does_not_push_past_the_days_last_slot_on_a_window_day() -> None:
    """**穴を埋めるだけ。** いちばん遅い分より後ろへ出すと T を自分で動かします。"""
    rows = [row("a", "2026-08-27T00:00:00Z"), row("b", "2026-08-27T00:00:00Z"),
            row("c", "2026-08-29T00:00:00Z")]
    moves = collisions.plan(rows, today=TODAY)
    assert len(moves) == 1
    # 08/27 に入っているのは 09:00 の2本だけ ＝ いちばん遅い分も 09:00。
    # 09:00 より前の空きはあるが `grid` の先頭から採るので 05:00 が返る。
    assert moves[0]["to"] == "2026-08-27T05:00"


def test_plan_does_not_reuse_one_slot_twice() -> None:
    rows = [row("a", "2026-08-28T00:00:00Z"), row("b", "2026-08-28T00:00:00Z"),
            row("c", "2026-08-28T01:00:00Z"), row("d", "2026-08-28T01:00:00Z")]
    moves = collisions.plan(rows, today=TODAY)
    assert len({m["to"] for m in moves}) == len(moves) == 2


def test_say_is_empty_when_clean() -> None:
    """**鳴らないことが既定**（鳴りっぱなしの計器は読まれなくなります）。"""
    assert collisions.say([row("a", "2026-08-28T00:00:00Z")], today=TODAY) == ""


def test_say_gives_a_command_you_can_paste() -> None:
    """「HH:MM」を人に埋めさせないこと —— **この輪では埋める回が来ません。**"""
    rows = [row("a", "2026-08-28T00:00:00Z"), row("b", "2026-08-28T00:00:00Z")]
    text = collisions.say(rows, today=TODAY)
    assert "reschedule.py --move b 2026-08-28T" in text
    assert "HH:MM" not in text
