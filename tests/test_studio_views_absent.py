"""`yt.views_of` —— **`viewCount` の欄が無い**のと **本当に 0回** を分ける。

2026-09-10 14:2x・optimizer・Opus。5本目 `2YZ_4FXC-XI` が 齢 3.9h で 0回 だった回に足した。
**この回に実測**（`videos.list` 1単位）: 3本 とも欄は在り、5本目 の値は文字列 `"0"`
＝ **いま踏んでいない口を塞いだだけ**（`yt.views_of` の註）。

**陽性対照つき**（§5 の教訓の形 3つ目「陽性対照は落ちるまで撃つ」）:
`views_of` を `.get("viewCount", 0)` の1行に戻すと `test_欄が無い読みは0回と別の形になる` と
`test_行の印は欄が無いときだけ立つ` が落ちる。2026-09-10 14:2x に動かして確かめた。
"""
from studio import yt


def _v(vid: str, stats: dict) -> dict:
    return {"id": vid, "snippet": {"title": "題", "publishedAt": "2026-09-10T01:00:00Z"},
            "status": {"privacyStatus": "public"}, "statistics": stats}


def test_欄が無い読みは0回と別の形になる():
    assert yt.views_of({"likeCount": "0"}) == (0, True)
    assert yt.views_of({"viewCount": "0", "likeCount": "0"}) == (0, False)


def test_本当の0回は印が立たない():
    """5本目 `2YZ_4FXC-XI` の実物の形（この回に `videos.list` で見た）。"""
    st = {"viewCount": "0", "likeCount": "0", "dislikeCount": "0",
          "favoriteCount": "0", "commentCount": "0"}
    views, absent = yt.views_of(st)
    assert (views, absent) == (0, False)


def test_値が在れば読む():
    assert yt.views_of({"viewCount": "929"}) == (929, False)


def test_行の印は欄が無いときだけ立つ():
    assert yt._row(_v("a", {"likeCount": "1"}))["views_absent"] is True
    assert yt._row(_v("b", {"viewCount": "0"}))["views_absent"] is False


def test_行はほかの欄をこわさない():
    r = yt._row(_v("a", {"viewCount": "7", "likeCount": "2", "commentCount": "3"}))
    assert (r["views"], r["likes"], r["comments"]) == (7, 2, 3)
    assert r["id"] == "a" and r["privacy"] == "public"


def test_statistics_ごと無い本でも落ちない():
    v = {"id": "a", "snippet": {"title": "題", "publishedAt": "2026-09-10T01:00:00Z"},
         "status": {"privacyStatus": "private"}}
    r = yt._row(v)
    assert r["views"] == 0 and r["views_absent"] is True


def test_落とさずに印だけ立てる():
    """行を落とすと分母が黙って減る（`views_of` の註）—— 欄が無くても行は在ること。"""
    r = yt._row(_v("a", {}))
    assert r["id"] == "a" and "views" in r
