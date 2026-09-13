"""`trend.rev7_source` / `rev7_source_line`
—— **§7 の収益の節の 覆る条件 (4) の「分子の中身」を分ける口**。

2026-09-13 09:1x JST・`hourly`・Opus。

(4) は「直近7日の平均が 3回 続けて上がったら、**分子は『新しい本』ではなく
チャンネル全体の回復の側**」と書いてあり、`rev7_run` は**その連だけ**を数えます。
**分子が何でできているかは、どの口も見ていませんでした** —— 答えは台帳の
`analytics_video` の `studio` の札に在ります。

**陽性対照つき**（§5 の教訓の形 3つ目 ＝ **落ちるまで撃つ**）。
実測と derivation は JOURNAL 2026-09-13 09:1x。
"""
from studio import trend


def _draw(at: str, day: str, start: str, new: dict[str, int], old: dict[str, int]) -> list[dict]:
    """1回の引き（同じ `at` の `analytics_video` の塊）。"""
    rows = []
    for vid, v in new.items():
        rows.append({"event": "analytics_video", "id": vid, "views": v, "studio": True,
                     "day": day, "start": start, "at": f"2026-09-{at}+09:00"})
    for vid, v in old.items():
        rows.append({"event": "analytics_video", "id": vid, "views": v, "studio": False,
                     "day": day, "start": start, "at": f"2026-09-{at}+09:00"})
    return rows


def _real() -> list[dict]:
    """**実物と同じ形**（09/10 → 09/11 → 09/12 → 09/13 の 4引き・JOURNAL 09/13 09:1x の数）。

    新しい本 468 → 1,400 → 1,836 → 2,589 ／ 古い本 2,996 → 2,990 → 2,910 → 2,785。
    """
    return (_draw("10T16:18:00", "2026-09-07", "2026-08-31", {"n": 468}, {"o": 2996})
            + _draw("11T12:18:00", "2026-09-08", "2026-09-01", {"n": 1400}, {"o": 2990})
            + _draw("12T08:25:00", "2026-09-09", "2026-09-02", {"n": 1836}, {"o": 2910})
            + _draw("13T04:38:00", "2026-09-10", "2026-09-03", {"n": 2589}, {"o": 2785}))


def test_実物の形では古い側の連は_0で_引かれない():
    s = trend.rev7_source(_real())
    assert len(s["draws"]) == 4
    assert [d["studio"] for d in s["draws"]] == [468, 1400, 1836, 2589]
    assert [d["old"] for d in s["draws"]] == [2996, 2990, 2910, 2785]
    assert s["old_run"] == 0
    assert s["drawn"] is False
    assert abs(s["draws"][-1]["share"] - 2589 / 5374) < 1e-9


def test_同じ日までを引き直した回は_1つに畳む():
    rows = (_draw("10T16:07:00", "2026-09-07", "2026-08-31", {"n": 400}, {"o": 2996})
            + _draw("10T16:18:00", "2026-09-07", "2026-08-31", {"n": 468}, {"o": 2996})
            + _draw("11T12:18:00", "2026-09-08", "2026-09-01", {"n": 1400}, {"o": 2990}))
    s = trend.rev7_source(rows)
    assert len(s["draws"]) == 2
    assert s["draws"][0]["studio"] == 468        # あとの読みが勝つ


def test_古い側が_3引き_続けて上がったら引かれる():
    """**陽性対照** —— 覆る条件 (1) の側（ここで初めて「チャンネル全体の回復」）。"""
    rows = (_draw("10T16:18:00", "2026-09-07", "2026-08-31", {"n": 468}, {"o": 1000})
            + _draw("11T12:18:00", "2026-09-08", "2026-09-01", {"n": 468}, {"o": 1200})
            + _draw("12T08:25:00", "2026-09-09", "2026-09-02", {"n": 468}, {"o": 1400})
            + _draw("13T04:38:00", "2026-09-10", "2026-09-03", {"n": 468}, {"o": 1600}))
    s = trend.rev7_source(rows)
    assert s["old_run"] == 3
    assert s["drawn"] is True
    assert "ここで初めて" in trend.rev7_source_line(rows)


def test_行は_引かれないときに_量は毒を開けるなと言う():
    line = trend.rev7_source_line(_real())
    assert "新しい本 2,589回" in line
    assert "古い本 2,785回" in line
    assert "48.2%" in line
    assert "量は毒" in line and "開けないこと" in line
    assert "0/3引き" in line


def test_引きが_1回_しか無ければ_そう言う():
    one = _draw("10T16:18:00", "2026-09-07", "2026-08-31", {"n": 468}, {"o": 2996})
    assert "そろっていません" in trend.rev7_source_line(one)
    assert "そろっていません" in trend.rev7_source_line([])


def test_report_が毎周_この行を印字する():
    """§5 教訓の形 7つ目 —— **註だけでなく印字も置くこと**（`rev7_line` の隣）。"""
    body = "\n".join(trend.lines(_real()))
    assert "上がった分の出どころ" in body
