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


def test_plan_never_places_before_the_live_edge() -> None:
    """**置き先が `LIVE_FROM_MIN` より前に出ないこと**（2026-08-27 に書き換えた）。

    ここは「測定の窓の日は、まずその日の**早い側の空き**へ寄せる」を確かめる
    試験でした（05:00 / 05:30 / …）。**その測定は 2026-08-27 に終わり、
    答えは「朝は生きない」**です —— 05:00〜08:30 に置いた 8本 は全部 0再生
    （8本とも `public`/`processed`）。`LIVE_FROM_MIN` は 05:00 → 09:00 へ戻して
    あるので、**早い側の空きはもう候補ではありません。**

    確かめるのは、その日に残るかどうかではなく（それは帯の埋まり方で変わる）、
    **どの手も生きる帯の中にしか置かないこと**のほうです。
    """
    rows = [row("a", "2026-08-27T00:00:00Z"),   # 09:00 JST
            row("b", "2026-08-27T00:00:00Z"),   # 09:00 JST（衝突）
            row("z", "2026-08-26T20:00:00Z"),   # 08/27 05:00 JST ＝ 帯の外
            row("c", "2026-08-29T00:00:00Z")]
    moves = collisions.plan(rows, today=TODAY)
    assert len(moves) == 1
    assert moves[0]["id"] == "b"
    hh, mm = moves[0]["to"].split("T")[1].split(":")
    m = int(hh) * 60 + int(mm)
    assert collisions.LIVE_FROM_MIN <= m <= collisions.LIVE_TO_MIN, (
        f"{moves[0]['to']} は生きる帯の外です（0再生が確定する時刻へ逃がしています）")
    assert m % collisions.STEP_MIN == 0


def test_plan_does_not_push_past_the_days_last_slot_on_a_window_day(
        monkeypatch) -> None:
    """**穴を埋めるだけ。** いちばん遅い分より後ろへ出すと T を自分で動かします。

    08/27 に入っているのは 09:00 の2本だけ ＝ いちばん遅い分も 09:00 で、
    **帯の下端（09:00）と同じ**です。つまりその日には空き分が1つも無いので、
    **別の日へ出ます**（前は 05:00 が空いていたので同じ日に残っていました）。

    ## **窓は、この検査が自分で立てます**（2026-08-29 に直した）

    ここは `src/measure_window.WINDOWS` に 08/27 の窓が**在ること**に
    寄りかかっていました。**あれは動く台帳です** —— 支えている前提が閉じれば
    窓は外れます。実際 2026-08-28 23:3x に別の回が
    「閉じた前提の窓を外した」で 08/27 の窓を消し、**この検査が赤になりました**
    （`collisions.plan` は1行も変わっていません）。

    **`today` の注入だけでは足りません。** 08-28 に同じ検査が赤になったとき
    （`collisions.window()` の註）、直したのは「壁の時計を読んでいた」ほうで、
    **窓そのものが台帳から消える道**は残っていました。**2回目です。**

    だから窓は `monkeypatch` で立てます。この検査が見たいのは
    **「窓の日には、いちばん遅い分より後ろへ出さない」という `plan()` の振る舞い**
    であって、**いまその窓が台帳に在るかどうか**ではありません。

    **覆る条件**: `plan()` が `measure_window` を直に呼ばなくなったら、
    ここの差し替え先も一緒に動かすこと。
    """
    from src import measure_window

    monkeypatch.setattr(
        measure_window, "inside",
        lambda day, window=None, today=None: day == "2026-08-27")

    rows = [row("a", "2026-08-27T00:00:00Z"), row("b", "2026-08-27T00:00:00Z"),
            row("c", "2026-08-29T00:00:00Z")]
    moves = collisions.plan(rows, today=TODAY)
    assert len(moves) == 1
    day, hhmm = moves[0]["to"].split("T")
    hh, mm = hhmm.split(":")
    assert day != "2026-08-27" or int(hh) * 60 + int(mm) <= 9 * 60, (
        "窓の日で、いちばん遅い分より後ろへ出しています（T を自分で動かします）")


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
