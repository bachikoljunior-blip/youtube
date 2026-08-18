"""`status.py` の「予約の先」が、**日ごとの本数**を出すこと。

## なぜ要るか（2026-08-19 に踏んだ）

この節は長らく **「控えの最後 09/27（あと 39.3日 / 246本）」の1行だけ**でした。
そこから読めるのは平均 **6.4本/日** です。ところが実物はこうでした:

    08/19=1 08/20=1 08/21=1 08/22=1 08/23=1 08/24=22 08/25=23 08/26=25 08/27=22 08/28=1

**今日から5日が1本/日**で、平均はその形を完全に消しています。
見つけたのはこの回が**手で数え直したから**で、手順のどこにも
「日ごとに数えろ」とは書いてありません。**次の回は同じ穴を踏みます。**
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import status as st  # noqa: E402

JST = timezone(timedelta(hours=9))


def _ahead(spec: dict[str, int]) -> list[datetime]:
    """`{"2026-08-20": 3}` → その日に3本ある形の並び（JST の 9時から30分ずつ）。

    **1時間ずつにしないこと** —— 25本置くと 9+24 で `hour must be in 0..23` になります。
    実物の詰め方（30分きざみ・9〜21時 ＝ 1日25枠）と同じにしてあります。
    """
    out = []
    for day, n in spec.items():
        y, m, d = (int(x) for x in day.split("-"))
        for i in range(n):
            out.append((datetime(y, m, d, 9, 0, tzinfo=JST)
                        + timedelta(minutes=30 * i)).astimezone(timezone.utc))
    return sorted(out)


def test_日ごとの本数が出る(capsys):
    st._print_per_day(_ahead({"2026-08-20": 1, "2026-08-21": 3}))
    out = capsys.readouterr().out
    assert "08/20=1" in out and "08/21=3" in out


def test_薄い日を名指しする(capsys):
    """**平均では見えない形**を、名前で出すこと。"""
    st._print_per_day(_ahead({"2026-08-20": 1, "2026-08-21": 1, "2026-08-22": 25}))
    out = capsys.readouterr().out
    assert "1日2本以下の日が 2日" in out
    assert "08/20" in out and "08/21" in out
    assert "08/22" not in out.split("1日2本以下")[1]


def test_薄い日が無ければ黙る(capsys):
    st._print_per_day(_ahead({"2026-08-20": 25, "2026-08-21": 25}))
    out = capsys.readouterr().out
    assert "08/20=25" in out
    assert "1日2本以下" not in out


def test_横に長くしない(capsys):
    """**読まれない行を作らないこと。** 出すのは直近 `PER_DAY_SPAN` 日ぶんだけ。"""
    many = {f"2026-09-{d:02d}": 1 for d in range(1, 26)}
    st._print_per_day(_ahead(many))
    line = [x for x in capsys.readouterr().out.splitlines() if "日ごと" in x][0]
    assert line.count("=") == st.PER_DAY_SPAN


def test_空でも落ちない(capsys):
    st._print_per_day([])
    assert capsys.readouterr().out == ""


def test_窓を見ろと言う(capsys):
    """薄い日は「空けてある」ことがあります（M14 の測定の窓）。

    **詰めろとだけ言うと、測定を壊しにいかせます。**
    """
    st._print_per_day(_ahead({"2026-08-20": 1, "2026-08-21": 25}))
    out = capsys.readouterr().out
    assert "measure_window" in out and "reschedule" in out
