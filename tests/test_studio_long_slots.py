"""長尺の枠は 1日に複数（`cli.LONG_SLOTS`）・予約の刻だけ動かす口（`cli.cmd_reschedule`）。

2026-09-15 14:xx・optimizer・Fable 5.1（ultracode）。固定 2（期限内にできるか → できる以外なら やり方を疑え）で
疑った先: 閉じた長尺が 09/18・09/19 の枠で 3〜4日 座っていた（1周 1本 焼けるのに、出す枠が 1日 1本 だった）。
理由と覆る条件は `cli.LONG_SLOTS` の註・JOURNAL 2026-09-15 14:xx。

**陽性対照**（撃って落とした）: `LONG_SLOT_LEAD_H` を 0 にすると `test_2時間より先` が落ち、
`cmd_reschedule` の public の門を外すと `test_公開ずみは動かさない` が落ちる。
"""
import datetime as dt

import pytest

from studio import cli, yt

JST = cli.JST
NOW = dt.datetime(2026, 9, 15, 14, 30, tzinfo=JST)


def _t(m, d, hh, mm=0):
    return dt.datetime(2026, m, d, hh, mm, tzinfo=JST)


# **【2026-09-17 19:xx】下の 4件 は `LONG_SLOTS == ("12:00","19:00","21:00")` を直に書いていました。**
# `LONG_SLOTS` を **1枠（19:00）**に戻し `SHORT_SLOTS` を足したので、**刻を引数で渡す形**に置き換えます
# （元の期待値は各 test の docstring に残す。理由は `cli.LONG_SLOTS` の註・METHOD §5「形の配り」・JOURNAL 09/17 19:xx）。
# **挟んでいる性質は 1つ も減らしていません** —— 早い順・2時間の先・±60分・門は 1か所。
_SLOTS3 = ("12:00", "19:00", "21:00")      # 09/15〜09/17 の `LONG_SLOTS`（この検査の中だけで使う）


def test_2時間より先の空いている枠を早い順に():
    """元の字: `next_long_slots(taken, NOW) == [09/15 21:00, 09/16 12:00, 09/16 21:00]`（枠 3つ の頃）。"""
    taken = [_t(9, 15, 10), _t(9, 15, 19), _t(9, 16, 10), _t(9, 16, 19)]
    got = cli.next_slots(taken, NOW, slots=_SLOTS3)
    assert got == [_t(9, 15, 21), _t(9, 16, 12), _t(9, 16, 21)]


def test_2時間より先():
    """いま 14:30 → 16:30 より前の刻は出ない（処理と差し替えの余地）。"""
    assert cli.next_slots([], _t(9, 15, 17, 30), slots=_SLOTS3)[0] == _t(9, 15, 21)
    assert cli.next_slots([], _t(9, 15, 9, 30), slots=_SLOTS3)[0] == _t(9, 15, 12)
    # いまの `LONG_SLOTS`（1枠）でも同じ性質が立つこと。
    assert cli.next_long_slots([], _t(9, 15, 9, 30))[0] == _t(9, 15, 19)
    assert cli.next_long_slots([], _t(9, 15, 16, 30))[0] == _t(9, 15, 19)   # 16:30 + 2h = 18:30 ≦ 19:00
    assert cli.next_long_slots([], _t(9, 15, 17, 30))[0] == _t(9, 16, 19)   # 17:30 + 2h = 19:30 → 次の日


def test_近い刻に本が在れば埋まっている():
    """19:30 に本が在れば 19:00 の枠は取らない（±60分）。"""
    got = cli.next_slots([_t(9, 16, 19, 30)], _t(9, 16, 8), slots=_SLOTS3)
    assert _t(9, 16, 19) not in got
    assert got[0] == _t(9, 16, 12)
    # いまの `LONG_SLOTS`（1枠）では、その日は飛んで次の日へ。
    assert cli.next_long_slots([_t(9, 16, 19, 30)], _t(9, 16, 8))[0] == _t(9, 17, 19)


def test_門の数は1か所():
    """元の字: `cli.LONG_SLOTS == ("12:00", "19:00", "21:00")`。

    **2026-09-17 19:xx に 1枠 へ戻しました**（`form_yield` の実測: ショート 中央 719回/本 対 長尺 1回/本）。
    ここで挟むのは「刻の綴りが 1か所 から来ること」と「2つ の枠が重ならないこと」。
    """
    assert cli.LONG_SLOTS == ("19:00",)
    assert cli.SHORT_SLOTS == ("07:00", "10:00", "12:00", "15:00", "18:00")
    assert not set(cli.LONG_SLOTS) & set(cli.SHORT_SLOTS)    # 同じ刻に 2つ の形を置かない
    assert cli.LONG_SLOT_LEAD_H >= 1.0
    # **`day_cap` の実測（再生が付く上限 10本/日）を越えないこと**（`SHORT_SLOTS` の覆る条件 (2)）。
    assert len(cli.LONG_SLOTS) + len(cli.SHORT_SLOTS) <= 10


def test_ショートの枠も同じ口から出る():
    """`next_short_slots` は `SHORT_SLOTS` を読む（`SLOT_AT` の 1刻 だけではない）。"""
    got = cli.next_short_slots([], _t(9, 15, 5, 0), n=3)
    assert got == [_t(9, 15, 7), _t(9, 15, 10), _t(9, 15, 12)]
    assert cli.next_short_slots([_t(9, 15, 10, 20)], _t(9, 15, 5, 0), n=2) == [_t(9, 15, 7), _t(9, 15, 12)]


def _stage(monkeypatch, tmp_path, privacy="private", publish_at="2026-09-18T10:00:00Z"):
    sid = "2026-09-18-x"
    (tmp_path / f"{sid}.json").write_text(
        '{"id": "%s", "date": "2026-09-18", "title": "t", "takeaway": "k", "description": "d", "tags": [],'
        ' "form": "long", "segments": []}' % sid,
        encoding="utf-8")
    monkeypatch.setattr(cli.script, "SCRIPTS", tmp_path)
    rows = [{"event": "scheduled", "id": sid, "video_id": "VID", "publish_at": "2026-09-18T19:00+09:00",
             "at": "2026-09-15T11:00:00+09:00"}]
    monkeypatch.setattr(cli, "ledger_rows", lambda: rows)
    written = []
    monkeypatch.setattr(cli, "ledger", lambda ev, vid, **kw: written.append({"event": ev, "id": vid, **kw}))
    monkeypatch.setattr(cli, "now_jst", lambda: NOW)
    live = [{"id": "VID", "privacy": privacy, "publish_at": publish_at, "published_at": "2026-09-15T02:00:00Z",
             "title": "t", "views": 0, "likes": 0}]
    monkeypatch.setattr(yt, "all_videos", lambda refresh=False: live)
    monkeypatch.setattr(yt, "scheduled_all", lambda: [v for v in live if v["publish_at"] and v["privacy"] != "public"])
    monkeypatch.setattr(yt, "now_jst", lambda: NOW)
    moved = []

    # **`reschedule` は打った刻を読み返して返す**（2026-09-16 23:3x・`yt.reschedule` の註）。
    # 09/15 に 2本 を落としたのは、返りを見ずに「動かした」と台帳へ書いていたため。
    def _resched(vid, at, stuck=True):
        moved.append((vid, at))
        return {"want": at.isoformat(), "got": at.isoformat() if stuck else None, "stuck": stuck}

    monkeypatch.setattr(yt, "reschedule", _resched)
    return sid, written, moved


class _A:
    def __init__(self, id, at, force=False, dry_run=False):
        self.id, self.at, self.force, self.dry_run = id, at, force, dry_run


def test_刻だけ動かして台帳に行を足す(monkeypatch, tmp_path):
    sid, written, moved = _stage(monkeypatch, tmp_path)
    assert cli.cmd_reschedule(_A(sid, "2026-09-15 21:00", force=True)) == 0
    assert moved == [("VID", _t(9, 15, 21))]
    assert written[-1]["event"] == "scheduled"
    assert written[-1]["video_id"] == "VID"
    assert written[-1]["publish_at"] == "2026-09-15T21:00+09:00"
    assert written[-1]["moved_from"] == "2026-09-18T19:00+09:00"


def test_公開ずみは動かさない(monkeypatch, tmp_path):
    sid, written, moved = _stage(monkeypatch, tmp_path, privacy="public", publish_at=None)
    assert cli.cmd_reschedule(_A(sid, "2026-09-15 21:00", force=True)) == 1
    assert moved == [] and written == []


def test_同じ日に本が在れば_force_が要る(monkeypatch, tmp_path, capsys):
    sid, written, moved = _stage(monkeypatch, tmp_path)
    other = {"id": "OTHER", "privacy": "public", "publish_at": None, "published_at": "2026-09-15T01:00:00Z",
             "title": "o", "views": 1, "likes": 0}
    live = yt.all_videos() + [other]
    monkeypatch.setattr(yt, "all_videos", lambda refresh=False: live)
    assert cli.cmd_reschedule(_A(sid, "2026-09-15 21:00")) == 1
    assert "もう本がある" in capsys.readouterr().out
    assert moved == []


def test_過ぎた刻は拒む(monkeypatch, tmp_path):
    sid, written, moved = _stage(monkeypatch, tmp_path)
    assert cli.cmd_reschedule(_A(sid, "2026-09-15 14:00", force=True)) == 1
    assert moved == []


def test_刻が入らなかったら台帳に書かない(monkeypatch, tmp_path, capsys):
    """**2026-09-16 23:3x に足した門**（`yt.reschedule` の註）。

    09/15 14:27 の 2本 は、刻が入らないまま台帳に `scheduled` が書かれ、
    `pubcheck`（当時まだ無い）も `trend` も「予約が在る」と読んだ ＝
    **枠が過ぎるまで、誰も気づかなかった。** 書かなければ、次の周が同じ本を見つけられる。
    """
    sid, written, moved = _stage(monkeypatch, tmp_path)
    monkeypatch.setattr(yt, "reschedule",
                        lambda vid, at: {"want": at.isoformat(), "got": None, "stuck": False})
    assert cli.cmd_reschedule(_A(sid, "2026-09-15 21:00", force=True)) == 1
    out = capsys.readouterr().out
    assert "刻が入りませんでした" in out
    assert [w["event"] for w in written] == ["reschedule_failed"]   # `scheduled` は 1行も足さない


def test_statusの1行は空いている枠を3つ言う():
    """元の字: 長尺の 1行 だけを見て `09/15 21:00` と `09/16 12:00` を挟んでいた（枠 3つ の頃）。

    **2026-09-17 19:xx**: `long_slot_line` は**長尺の行 ＋ ショートの行**の 2行 を返します。
    挟むのは (a) 埋まっている刻（09/15 19:00 ＝ B の 10:00Z）が出ないこと、
    (b) **ショートの枠が印字されること**（この行が無かったあいだ、ショートを置く先が 1刻 しか無かった）。
    """
    vids = [{"id": "A", "privacy": "public", "publish_at": None, "published_at": "2026-09-15T01:00:00Z"},
            {"id": "B", "privacy": "private", "publish_at": "2026-09-15T10:00:00Z", "published_at": "2026-09-15T02:00:00Z"}]
    line = cli.long_slot_line(vids, NOW)
    assert "次の長尺の枠" in line and "次のショートの枠" in line
    assert "09/16 19:00" in line          # B が 09/15 19:00 を埋めている ＝ 次の日へ
    assert "09/15 19:00" not in line
    assert "09/15 18:00" in line          # ショート側の、いちばん早い空き
