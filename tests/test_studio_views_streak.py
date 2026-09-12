"""`trend.views_streak` / `views_streak_line`
—— **§7 末尾「1日1本」の覆る条件（500回 が 7本 続いたら 2本/日 を試す）を、本で数える口**。

2026-09-12 20:3x JST・optimizer・Opus。

**族の 5例目**（`late_run` 04:3x／`blind_run` 16:0x／`reporting_empty_run` 18:4x／
`outside_runs` 20:0x）—— 「N本 続いたら」と覆る条件に書きながら、**N を数える物が無い**。
この条件だけは、引かれたら動くのが**1日の本数そのもの**（§5 の回り方・親の周・枠の配り）です。

**この口の肝は「越えた側は言い切れ、越えていない側は言い切れない」**（並びは包絡 ＝
再生は下からしか動かない）。だから連は 2つ 返します:
``run``（いま越えている本だけ）と ``run_if_growing``（**まだ伸びている本は続きうる**として数えた側）。
`run_if_growing` が門に届かなければ、**その周に門が引かれる目は在りません**。

**陽性対照つき**（§5 の教訓の形 3つ目 ＝ **落ちるまで撃つ**・`.pyc` を毎回 消してから・11つ目）。
この回に動かして確かめた数は JOURNAL 20:3x。
"""
import datetime as dt

from studio import trend
from studio.common import JST

NOW = dt.datetime(2026, 9, 12, 21, 0, tzinfo=JST)


def _book(vid: str, pub: str, points: list[tuple[float, int]]) -> list[dict]:
    """`scheduled` 1行 ＋ `measured` の点。`pub` は "09-12" の形（すべて 10:00 JST 公開）。"""
    base = dt.datetime.fromisoformat(f"2026-{pub}T10:00:00+09:00")
    out = [{"event": "scheduled", "id": f"2026-{pub}-x", "at": base.isoformat(),
            "video_id": vid}]
    for age, views in points:
        at = base + dt.timedelta(hours=age)
        out.append({"event": "measured", "id": vid, "at": at.isoformat(),
                    "age_h": age, "views": views, "likes": 0, "title": vid})
    return out


def _settled(vid: str, pub: str, views: int, age: float = 100.0) -> list[dict]:
    """**確定した本**（齢 48h 超・最後の伸びから `flats` の境目 24時間 より長い）。"""
    return _book(vid, pub, [(1.0, views), (age, views)])


def _growing(vid: str, pub: str, views: int, age: float = 100.0) -> list[dict]:
    """**まだ伸びている本**（齢は古くても、最後の点で伸びている ＝ 平らが短い）。"""
    return _book(vid, pub, [(1.0, 1), (age - 1.0, 1), (age, views)])


def test_越えた本を新しいほうから数える():
    rows = (_settled("A", "09-08", 900) + _settled("B", "09-09", 100)
            + _settled("C", "09-10", 900) + _settled("D", "09-11", 900)
            + _settled("E", "09-12", 900))
    s = trend.views_streak(rows)
    # **新しいほうから** C・D・E の 3本。
    # **古いほうから数えると 1本**（A だけ）・**全部の「越えた本」を数えると 4本** ＝
    # この 3 は、向きを間違えた側とも、連ではない側とも別の数です（陽性対照 JOURNAL 20:3x）。
    assert s["run"] == 3
    assert s["n"] == 5
    assert s["broke"]["id"] == "B"


def test_500回ちょうどは越えていない():
    rows = _settled("A", "09-11", 500) + _settled("B", "09-12", 501)
    s = trend.views_streak(rows)
    assert s["run"] == 1
    assert s["broke"]["id"] == "A"


def test_0回の本も1本として数える():
    rows = _settled("A", "09-11", 0) + _settled("B", "09-12", 900)
    s = trend.views_streak(rows)
    # `hold` は分母が作れず落とすが、ここは「越えたか」しか訊かないので落とさない。
    assert s["n"] == 2
    assert s["run"] == 1
    assert s["broke"]["id"] == "A"


def test_伸びている本はrunを切るがrun_if_growingは切らない():
    rows = (_settled("A", "09-09", 900) + _growing("B", "09-10", 100)
            + _settled("C", "09-11", 900) + _settled("D", "09-12", 900))
    s = trend.views_streak(rows)
    assert s["run"] == 2
    assert s["run_if_growing"] == 4
    assert s["broke"]["growing"] is True


def test_確定した本はrun_if_growingも切る():
    rows = (_settled("A", "09-09", 900) + _settled("B", "09-10", 100)
            + _settled("C", "09-11", 900) + _settled("D", "09-12", 900))
    s = trend.views_streak(rows)
    assert s["run"] == 2
    assert s["run_if_growing"] == 2
    assert s["broke"]["growing"] is False
    # 門 7本 に対し、いま在る本では 2本 まで ＝ 足りない 5本 は新しい本でしか埋まらない。
    assert s["short"] == 5


def test_旧作りの本は数えない():
    rows = _settled("A", "09-12", 900)
    rows += [{"event": "measured", "id": "OLD", "at": NOW.isoformat(),
              "age_h": 100.0, "views": 9000, "likes": 0, "title": "OLD"}]
    s = trend.views_streak(rows)
    assert s["n"] == 1
    assert [b["id"] for b in s["books"]] == ["A"]


def test_門に届いたら判定はhourlyとオーナーと言う():
    days = ["09-06", "09-07", "09-08", "09-09", "09-10", "09-11", "09-12"]
    rows = []
    for i, d in enumerate(days):
        rows += _settled(f"V{i}", d, 900)
    s = trend.views_streak(rows)
    assert s["run"] == 7
    assert s["drawn"] is True
    assert s["short"] == 0
    line = trend.views_streak_line(rows)
    assert "門に届きました" in line
    assert "`hourly` とオーナー" in line


def test_門に届かない回は判定の句を出さない():
    rows = _settled("A", "09-11", 900) + _settled("B", "09-12", 900)
    line = trend.views_streak_line(rows)
    assert "門に届きました" not in line
    assert "2本" in line


def test_trendの並びに出る():
    rows = _settled("A", "09-11", 900) + _settled("B", "09-12", 900)
    out = "\n".join(trend.lines(rows, now=NOW))
    assert "500回 を越えた連" in out
    assert "`trend.views_streak`" in out
