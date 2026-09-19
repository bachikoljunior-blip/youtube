"""`studio/budget.py` —— きょうの日枠を台帳から数える（**API 0単位**）。

**陽性対照 2つ**: 枠の頭をまたぐ行を外していること・`RESERVE` を動かすと「あと何本」が変わること。
"""
import datetime as dt

from studio import budget
from studio.common import JST


def _t(s):
    return dt.datetime.fromisoformat(s).replace(tzinfo=JST)


def test_枠の頭は直近の16時():
    assert budget.window_start(_t("2026-09-16T03:34:00")) == _t("2026-09-15T16:00:00")
    assert budget.window_start(_t("2026-09-16T16:00:00")) == _t("2026-09-16T16:00:00")
    assert budget.window_start(_t("2026-09-16T15:59:00")) == _t("2026-09-15T16:00:00")


def test_予約1本は1650単位():
    rows = [{"at": "2026-09-15T20:00:00+09:00", "event": "scheduled"}]
    assert budget.spent(rows, _t("2026-09-16T03:00:00"))["total"] == budget.UPLOAD_UNITS


def test_枠の頭より前の行は数えない():
    """**陽性対照 1**: 同じ行でも、刻が枠の外なら 0。"""
    rows = [{"at": "2026-09-15T15:59:00+09:00", "event": "scheduled"}]
    assert budget.spent(rows, _t("2026-09-16T03:00:00"))["total"] == 0
    assert budget.spent(rows, _t("2026-09-15T15:59:30"))["total"] == budget.UPLOAD_UNITS


def test_行が持つunitsのほうを先に読む():
    rows = [{"at": "2026-09-15T20:00:00+09:00", "event": "peers", "units": 28}]
    assert budget.spent(rows, _t("2026-09-16T03:00:00"))["total"] == 28


def test_知らないeventは0で数える():
    """覆る条件 (1) ＝ **この数は過小**。知らない口は 0 になる。"""
    rows = [{"at": "2026-09-15T20:00:00+09:00", "event": "まだ知らない口"}]
    assert budget.spent(rows, _t("2026-09-16T03:00:00"))["total"] == 0


def test_残り本数は測る側の取り分を引いてから割る():
    rows = [{"at": "2026-09-15T20:00:00+09:00", "event": "scheduled"} for _ in range(5)]
    s = budget.spent(rows, _t("2026-09-16T03:00:00"))
    assert s["total"] == 5 * budget.UPLOAD_UNITS          # 8,250
    assert s["left"] == budget.DAY_UNITS - s["total"]      # 1,750
    assert s["uploads_left"] == 0                          # (1,750 - 600) // 1,650 == 0


def test_取り分を0にすると1本ぶん増える(monkeypatch):
    """**陽性対照 2**: `RESERVE` を動かすと答えが変わる ＝ 取り分が効いている。"""
    rows = [{"at": "2026-09-15T20:00:00+09:00", "event": "scheduled"} for _ in range(5)]
    monkeypatch.setattr(budget, "RESERVE", 0)
    assert budget.spent(rows, _t("2026-09-16T03:00:00"))["uploads_left"] == 1


def test_取り分を割ったら印字が名指しする():
    """**【2026-09-19 12:xx】字が変わりました** —— 取り分を割っても**盲にはなりません**。

    再生・登録・出たか は `measure --public`／`pubcheck` が **0単位** で読みます
    （2026-09-19 11:xx）。Data API でしか読めないのは 写しと `refresh_stats` だけ。
    **「判定が止まります」は、もう本当ではありません。**
    """
    rows = [{"at": "2026-09-15T20:00:00+09:00", "event": "scheduled"} for _ in range(6)]
    out = "\n".join(budget.lines(rows, _t("2026-09-16T03:00:00")))
    assert "残りが測る側の取り分を割っています" in out
    assert "盲にはなりません" in out
    assert "0単位" in out


def test_印字は過小だと毎回言う():
    out = "\n".join(budget.lines([], _t("2026-09-16T03:00:00")))
    assert "0単位" in out and "過小" in out


# ---- 6本/日（2026-09-19 12:xx・optimizer・Opus 5・1周 1体）----------------
#
# **なぜ 6 になったか**: ショートは `thumbnails.set`（50単位）を撃たなくなり
# （`cli.cmd_schedule`・絵は 1コマ目 で YouTube の既定とほぼ同じ・フィードの外は配りの 3.4%）、
# 測る側の取り分は 公開ページが **0単位** で再生と登録を読むので 600 → 400 に下りました
# （`pubcheck.shorts_views` ＋ `cli measure --public`・2026-09-19 11:xx）。
#
#     6 × 1,600 ＋ 400 ＝ 10,000（ちょうど）
#
# **外した時の負けは 0単位**（`quotaExceeded` は課金されない ＝ 台帳の 403 69本 が 0単位）。

def test_ショートの値段はサムネを含まない():
    from studio import budget
    assert budget.UPLOAD_UNITS_SHORT == 1600
    assert budget.UPLOAD_UNITS - budget.UPLOAD_UNITS_SHORT == 50   # `thumbnails.set` ちょうど


def test_日枠は6本で割り切れる_余りは測る側():
    from studio import budget
    assert budget.DAY_UNITS - 6 * budget.UPLOAD_UNITS_SHORT == budget.RESERVE


def test_天井は6本_式は1か所():
    from studio import budget, cli, trend
    assert cli.day_upload_cap() == 6
    assert float(cli.day_upload_cap()) == trend.sponsor_daily_cap_videos()
    # **写しを持たないこと** —— 定数を動かせば両方が追う。
    assert cli.day_upload_cap() == max(
        (budget.DAY_UNITS - budget.RESERVE) // budget.UPLOAD_UNITS_SHORT, 0)


def test_残りは長尺とショートの両方で数える():
    from studio import budget
    s = budget.spent([], now=None)
    assert s["uploads_left_short"] >= s["uploads_left"]
    assert s["uploads_left_short"] == 6


def test_ショートの枠は6つ_長尺と重ならない():
    from studio import cli
    assert len(cli.SHORT_SLOTS) == 6
    assert len(set(cli.SHORT_SLOTS)) == 6
    assert not (set(cli.SHORT_SLOTS) & set(cli.LONG_SLOTS))


def test_サムネはショートに撃たない_長尺には撃つ():
    """**50単位 × 5本/日 ＝ 250** を 6本目（1,600）へ回す側（2026-09-19 12:xx）。

    ショートに撃っていた絵は `slide-01.png` ＝ **1コマ目**（`cli.thumbnail_for` の註）。
    長尺は一覧と検索だけが入口なので撃ち続けます。
    """
    from types import SimpleNamespace

    from studio import cli, script
    assert cli.sets_thumbnail(SimpleNamespace(form="long")) is True
    assert cli.sets_thumbnail(SimpleNamespace(form="short")) is False
    # 形の欄が空の本は既定（ショート）＝ 撃たない
    assert cli.sets_thumbnail(SimpleNamespace(form=None)) is (
        script.form_of(None) is script.LONG)
