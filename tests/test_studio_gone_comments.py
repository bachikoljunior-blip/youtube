"""`cli.gone_comments` の検査（2026-09-10 16:0x・optimizer・Opus）。

**なぜ足したか**: `status` も `comments` も突き合わせを **1方向しか** していなかった ——
「台帳に無い新着」は数えるのに、その裏（**台帳に在ったのに消えた**）を数える口が無い。
実測: `@sakimura5257` の「コメントしたのに消えた」そのものが、台帳に 2回 記録されたあと
API の 3列 のどこからも消えた。

**陽性対照つき** —— 下の `test_positive_control_*` は、道具の門を外すと落ちる形で書いてある。
"""
from __future__ import annotations

from studio import cli


def _led(cid: str, text: str = "本文", vid: str = "vvv", author: str = "@a") -> dict:
    return {"event": "viewer_comment", "comment_id": cid, "id": vid,
            "author": author, "posted_at": "2026-09-08T03:39:30Z", "text": text}


def _live(cid: str) -> dict:
    return {"id": cid, "video_id": "vvv", "author": "@a", "text": "本文",
            "at": "2026-09-08T03:39:30Z", "likes": 0, "status": "published"}


def test_nothing_gone():
    rows = [_led("c1"), _led("c2")]
    assert cli.gone_comments(rows, [_live("c1"), _live("c2")]) == []
    assert "0件" in cli.gone_comments_line(rows, [_live("c1"), _live("c2")])


def test_one_gone():
    rows = [_led("c1", "コメントしたのに消えた"), _led("c2")]
    gone = cli.gone_comments(rows, [_live("c2")])
    assert [r["comment_id"] for r in gone] == ["c1"]
    line = cli.gone_comments_line(rows, [_live("c2")])
    assert "**消えたコメント 1件**" in line and "コメントしたのに消えた" in line


def test_same_comment_logged_twice_counts_once():
    """台帳は同じコメントを何度も書く（`measure` の周ごと）。**数は 1件**。"""
    rows = [_led("c1"), _led("c1"), _led("c1")]
    assert len(cli.gone_comments(rows, [])) == 1


def test_other_events_are_not_counted():
    rows = [{"event": "measured", "id": "v", "comment_id": "c9"}, _led("c1")]
    assert [r["comment_id"] for r in cli.gone_comments(rows, [])] == ["c1"]


def test_rows_without_comment_id_are_skipped():
    rows = [{"event": "viewer_comment", "id": "v", "text": "欄が無い"}, _led("c1")]
    assert [r["comment_id"] for r in cli.gone_comments(rows, [])] == ["c1"]


def test_held_comment_still_returned_is_not_gone():
    """保留・迷惑の列に落ちただけの行は「消えた」ではない（3列 とも引いてあるので返ってくる）。"""
    rows = [_led("c1")]
    live = [{**_live("c1"), "status": "heldForReview"}]
    assert cli.gone_comments(rows, live) == []


def test_line_says_we_cannot_tell_who_deleted_it():
    """**分けられないことを、分けられないと書く**（Data API では投稿者か YouTube かが出ない）。"""
    line = cli.gone_comments_line([_led("c1")], [])
    assert "投稿者自身か YouTube 側" in line


def test_real_shape_from_the_ledger():
    """実物の形（09/08 15:03 と 15:05 の 2行・同じ `comment_id`）で通ること。"""
    rows = [
        {"comment_id": "Ugy3gdkwxAy5P3Nw_fd4AaABAg", "author": "@sakimura5257",
         "posted_at": "2026-09-08T03:39:30Z", "text": "コメントしたのに消えた",
         "at": "2026-09-08T15:05:31+09:00", "id": "lQHX9LJ80Sg", "event": "viewer_comment"},
        {"comment_id": "Ugxalw5necUowSfrP1t4AaABAg", "author": "@sakimura5257",
         "posted_at": "2026-09-08T03:38:20Z", "text": "65歳までに死んだら丸々損したことにならないの？",
         "at": "2026-09-08T15:05:31+09:00", "id": "lQHX9LJ80Sg", "event": "viewer_comment"},
        {"comment_id": "Ugy3gdkwxAy5P3Nw_fd4AaABAg", "author": "@sakimura5257",
         "posted_at": "2026-09-08T03:39:30Z", "text": "コメントしたのに消えた",
         "at": "2026-09-08T15:03:55+09:00", "id": "lQHX9LJ80Sg", "event": "viewer_comment"},
    ]
    live = [{"id": "Ugxalw5necUowSfrP1t4AaABAg", "video_id": "lQHX9LJ80Sg",
             "author": "@sakimura5257", "text": "65歳までに死んだら丸々損したことにならないの？",
             "at": "2026-09-08T03:38:20Z", "likes": 0, "status": "published"}]
    gone = cli.gone_comments(rows, live)
    assert len(gone) == 1
    assert gone[0]["comment_id"] == "Ugy3gdkwxAy5P3Nw_fd4AaABAg"


def test_positive_control_dedupe():
    """**陽性対照**: 重なりを畳まないと、同じコメントが 2件 に数えられる。"""
    rows = [_led("c1"), _led("c1")]
    assert len(cli.gone_comments(rows, [])) == 1
    assert len([r for r in rows if r.get("event") == "viewer_comment"]) == 2


def test_positive_control_direction():
    """**陽性対照**: 「新着」の側（live に在って台帳に無い）は、この口では 1件も数えない。"""
    rows = [_led("c1")]
    assert cli.gone_comments(rows, [_live("c1"), _live("c2")]) == []


def _gone_led(cid: str) -> dict:
    return {"event": "comment_gone", "comment_id": cid, "id": "vvv",
            "author": "@a", "posted_at": "2026-09-08T03:39:30Z", "text": "本文"}


def test_記録ずみの消えたコメントは撃つ命令を出さない():
    """2026-09-10 18:3x（optimizer・Opus）。**数は残し、命令だけ引っ込める**（`gone_unlogged` の註）。"""
    rows = [_led("c1"), _gone_led("c1")]
    gone = cli.gone_comments(rows, [])
    assert len(gone) == 1                       # 数は消えない（§7 (n) は件数で数える）
    assert cli.gone_unlogged(rows, gone) == []  # 記録ずみ ＝ 未記録は 0件
    mark = cli.gone_status_mark(rows, gone)
    assert "撃つこと" not in mark and "!!" not in mark and "1件" in mark


def test_まだ記録していない消えたコメントは撃つ命令を出す():
    rows = [_led("c1")]
    gone = cli.gone_comments(rows, [])
    assert [r["comment_id"] for r in cli.gone_unlogged(rows, gone)] == ["c1"]
    assert "撃つこと" in cli.gone_status_mark(rows, gone)


def test_消えたコメントが0件なら1字も足さない():
    assert cli.gone_status_mark([_led("c1"), _gone_led("c1")], []) == ""


def test_positive_control_記録の突き合わせは種別を見る():
    """**陽性対照**: `comment_gone` ではなく `viewer_comment` の側を数えると、
    **消えたコメントは必ず「記録ずみ」に見えます**（同じ `comment_id` が両方に在るため）。
    種別で引いているので、`comment_gone` が 1行 も無いこの並びでは 1件 が未記録に立ちます。"""
    rows = [_led("c1")]
    gone = cli.gone_comments(rows, [])
    assert len(cli.gone_unlogged(rows, gone)) == 1
