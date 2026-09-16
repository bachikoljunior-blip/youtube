"""**実測（403）は推計（台帳）に勝つ** —— `budget.dry_observed` と、上げ直しの値段 `cli.reupload_cost`。

**踏んだ当のもの**（2026-09-16 21:2x・optimizer・Fable 5.1・ultracode）:
`budget.lines` が「使った **0** / 10,000・**あと 5本 出せる**」と印字した数十秒後に、
`watermark`（50単位）も `channels.list`（**1単位**）も **403 quotaExceeded** で落ちました。

**陽性対照**: 403 の後に「通った」行を 1つ 足すと、`dry_observed` は **None に戻ります**
（戻らないなら、枠が戻っても「尽きている」と言い続ける ＝ 覆る条件 (1)）。
"""
from studio import budget
from studio.cli import reupload_cost
from studio.common import JST

import datetime as dt


def _t(s):
    return dt.datetime.fromisoformat(s).replace(tzinfo=JST)


NOW = _t("2026-09-16T21:30:00")
QX = {"at": "2026-09-16T19:01:08+09:00", "event": "quota_exceeded"}
OK_BEFORE = {"at": "2026-09-16T16:49:51+09:00", "event": "channel"}
OK_AFTER = {"at": "2026-09-16T21:14:44+09:00", "event": "channel"}


def test_最後に通った刻より後の403は尽きている():
    assert budget.dry_observed([OK_BEFORE, QX], NOW) == QX["at"]


def test_403の後に通った行が在れば戻る():
    """**陽性対照**: 枠が戻れば ひとりでに消えること（覆る条件 (1)）。"""
    assert budget.dry_observed([OK_BEFORE, QX, OK_AFTER], NOW) is None


def test_前の枠の403は数えない():
    old = {"at": "2026-09-16T14:36:34+09:00", "event": "quota_exceeded"}
    assert budget.dry_observed([old], NOW) is None


def test_analyticsは通った証拠にならない():
    """`analytics_*` は**別の枠**（Data API 0単位）＝ 通っても日枠の証拠にはならない。"""
    an = {"at": "2026-09-16T21:20:00+09:00", "event": "analytics_day"}
    assert budget.dry_observed([OK_BEFORE, QX, an], NOW) == QX["at"]


def test_尽きている周はあと何本出せるを印字しない():
    out = "\n".join(budget.lines([OK_BEFORE, QX], NOW))
    assert "実測で尽きています" in out and "出せる本は 0本" in out
    assert "あと **5本**" not in out and "＝ あと" not in out


def test_尽きていない周はいつもの行():
    out = "\n".join(budget.lines([OK_BEFORE, QX, OK_AFTER], NOW))
    assert "＝ あと" in out and "実測で尽きています" not in out


# ---- 上げ直しの値段（`cli.reupload_cost`）----

def _sch(sid, vid, at="2026-09-15T01:00:00+09:00"):
    return {"at": at, "event": "scheduled", "id": sid, "video_id": vid}


def test_1本目は0単位():
    assert reupload_cost([_sch("a", "v1")], "a") == (1, 0)


def test_上げ直した分だけ1650ずつ():
    rows = [_sch("a", "v1"), _sch("a", "v2"), _sch("a", "v3")]
    assert reupload_cost(rows, "a") == (3, 2 * budget.UPLOAD_UNITS)


def test_同じvideo_idの2行目はreschedule_で数えない():
    """**陽性対照**: 刻を動かしただけの行（同じ `video_id`）は 50単位 で、上げ直しではない。"""
    rows = [_sch("a", "v1"), _sch("a", "v1", "2026-09-15T14:27:00+09:00")]
    assert reupload_cost(rows, "a") == (1, 0)


def test_ほかの台本は混ぜない():
    rows = [_sch("a", "v1"), _sch("b", "v2"), _sch("b", "v3")]
    assert reupload_cost(rows, "a") == (1, 0)
    assert reupload_cost(rows, "b") == (2, budget.UPLOAD_UNITS)
