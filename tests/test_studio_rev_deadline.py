"""`trend.rev_deadline` —— オーナーが置いた期限と、いまの数の距離（台帳だけ・API 0単位）。

**なぜ要るか**（2026-09-13 20:3x・optimizer・Opus）: オーナーが 20:0x に
「YouTube月収20万の達成期限3ヶ月にして」と置きました（受け取り帳 `6a67e8e7`）。
`rev7_line` は距離（倍率）を毎周 印字しますが、**その倍率は「いつまでに」を持ちません** ——
基準2 の窓は 90日 なので、**期限が付くと窓はもう開いています**（期限の 90日前 ＝ いま）。

**陽性対照**（撃って落とした）:
窓の始まりを「きょう」にすると `test_窓は期限の90日前から開く` が落ち、
窓の中の実測を数えないと `test_窓に入った実測は要る数から引く` が落ち、
残り日数を窓の始まりから数えると `test_残り日数はきょうから数える` が落ちる。
"""
import datetime as dt

import pytest

from studio import trend

JST = trend.JST
END = dt.date.fromisoformat(trend.REV_DEADLINE)


@pytest.fixture
def 刻(monkeypatch):
    def _set(d: str):
        now = dt.datetime.fromisoformat(d).replace(tzinfo=JST)
        monkeypatch.setattr(trend, "now_jst", lambda: now)
    return _set


def _day(day: str, views: int, at: str = "2026-09-13T04:38:20+09:00") -> dict:
    return {"event": "analytics_day", "id": day, "views": views, "at": at}


def _chan(at: str, subs: int, views: int) -> dict:
    return {"event": "channel", "id": "c", "subs": subs, "views": views, "at": at}


def _rows() -> list[dict]:
    return [_chan("2026-09-10T20:00:00+09:00", 27, 80_000),
            _chan("2026-09-13T20:00:00+09:00", 28, 88_000),
            _day("2026-09-09", 500), _day("2026-09-10", 700)]


def test_窓は期限の90日前から開く(刻):
    """陽性対照: 窓を「きょう」から取ると `start` が 2026-09-13 になる。"""
    刻("2026-09-13T20:36:00")
    r = trend.rev_deadline(_rows())
    assert r["start"] == END - dt.timedelta(days=trend.REV_GOAL_DAYS - 1)
    assert r["start"] == dt.date(2026, 9, 15), "期限の 90日前（両端を含む）"
    assert r["ahead_days"] == trend.REV_GOAL_DAYS and r["past_days"] == 0


def test_残り日数はきょうから数える(刻):
    """陽性対照: 窓の始まりから数えると 90日 になる。"""
    刻("2026-09-13T20:36:00")
    assert trend.rev_deadline(_rows())["days_left"] == 91


def test_窓に入った実測は要る数から引く(刻):
    """陽性対照: 窓の中の実測を数えないと `got` が 0 のまま・`ahead_days` が 90 のまま。"""
    刻("2026-09-16T09:00:00")
    rows = _rows() + [_day("2026-09-15", 1_000, at="2026-09-16T04:00:00+09:00")]
    r = trend.rev_deadline(rows)
    assert r["past_days"] == 1 and r["got"] == 1_000
    assert r["ahead_days"] == trend.REV_GOAL_DAYS - 1
    assert r["need_per_day"] == pytest.approx(
        (trend.REV_GOAL_VIEWS - 1_000) / (trend.REV_GOAL_DAYS - 1))


def test_窓の外の日は数えない(刻):
    """2026-09-10 は窓（09-15〜12-13）の外 ＝ `got` に入れない。"""
    刻("2026-09-13T20:36:00")
    r = trend.rev_deadline(_rows())
    assert r["got"] == 0, "窓の外の実測を足すと、要る数が甘くなる"


def test_登録は期限までに要る人日といまの人日を並べる(刻):
    刻("2026-09-13T20:36:00")
    r = trend.rev_deadline(_rows())
    assert r["subs"] == 28 and r["subs_need"] == trend.REV_GOAL_SUBS - 28
    assert r["subs_per_day"] == pytest.approx(1 / 3, rel=0.02), "3日 で +1人"
    assert r["subs_times"] and r["subs_times"] > 1


def test_下端だと毎周言う(刻):
    """門を通ったあとの収益なので、窓は手前で閉じる ＝ この倍率は下端。"""
    刻("2026-09-13T20:36:00")
    line = trend.rev_deadline_line(_rows())
    assert trend.rev_deadline(_rows())["floor"] is True
    assert "下端" in line and "判定は `hourly` とオーナー" in line
    assert "倍**" in line


def test_期限を過ぎたら短く言う(刻):
    刻("2026-12-20T09:00:00")
    r = trend.rev_deadline(_rows())
    assert r["days_left"] < 0
    assert "過ぎました" in trend.rev_deadline_line(_rows())


def test_期限の門は1か所(刻):
    """オーナーが日を言い直したときに直す所が 1つ であること（覆る条件 (1)）。"""
    刻("2026-09-13T20:36:00")
    assert trend.rev_deadline(_rows())["deadline"] == END


def test_チャンネルの行が無い台帳でも落ちない(刻):
    """`channel_growth` は `subs` / `d_subs` を **None** で返します（見ていない ＝ 0人 ではない）。

    **踏んだ形**（2026-09-13 20:4x）: 最初の版は `REV_GOAL_SUBS - g["subs"]` を直に引き、
    `channel` の行が 1つも無い合成の台帳で `TypeError` ＝ **`trend.report` を通る検査が
    43件 まとめて赤**になりました（`tests/test_studio_zero_probe_line.py` ほか）。
    **「見ていない」を 0 と読まない**のは `yt.views_of` と同じ族です。
    """
    刻("2026-09-13T20:36:00")
    rows = [_day("2026-09-09", 500)]
    r = trend.rev_deadline(rows)
    assert r["subs"] is None and r["subs_need"] is None
    assert r["subs_per_day"] is None and r["subs_days"] is None
    line = trend.rev_deadline_line(rows)
    assert "登録は" not in line, "見ていない数を印字しないこと"
    assert "下端" in line
