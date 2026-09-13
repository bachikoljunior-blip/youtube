"""`scripts/turf_run.py` の見張り（§5 の file ごとの取り分の連）。

**陽性対照で測ってあります** —— どの検査も、門か当たりを 1つ 外すと落ちます
（§5 教訓の形 3つ目: 「在るか」で見る形は、畳んでも通ってしまう）。
"""

from __future__ import annotations

import datetime as dt
import importlib

turf = importlib.import_module("scripts.turf_run")

JST = dt.timezone(dt.timedelta(hours=9))


def _at(h: int, m: int = 0, d: int = 13) -> dt.datetime:
    return dt.datetime(2026, 9, d, h, m, tzinfo=JST)


def test_判定はhourlyの塊が名指ししたstudioのfileだけ拾う() -> None:
    text = (
        "**判定は `hourly`**（§5）。数える口は `trend.shape_run`。\n"
        "\n"
        "ここは別の塊で、`hear.near_spans` を名指しするが 判定の字が無い。\n"
        "\n"
        "**判定は `optimizer`** の塊で `yt.views_of` を名指しする。\n"
    )
    assert turf.judged_files(text) == {"studio/trend.py"}


def test_判定の字が無ければ拾わない_陽性対照() -> None:
    """塊から「判定は `hourly`」を抜くと、当たりが 0 になること。"""
    ok = "**判定は `hourly`**。`trend.shape_run`。\n"
    assert turf.judged_files(ok) == {"studio/trend.py"}
    assert turf.judged_files(ok.replace("判定は `hourly`", "数は")) == set()


def test_連の起点はNがいちばん大きい二重の刻() -> None:
    text = (
        "（2026-09-12 10:2x・optimizer。**5回目の二重**）\n"
        "（2026-09-13 02:5x・optimizer。**6回目の二重**）\n"
        "（2026-09-11 01:0x・optimizer。**4回目の二重**）\n"
    )
    assert turf.last_double(text) == _at(2, 50)


def test_二重の記録が無ければ起点は無い() -> None:
    assert turf.last_double("二重の字がどこにも無い本文\n") is None


def test_親のcommitは_役の字を含んでいても数えない_陽性対照() -> None:
    """`_PARENT_SUBJECTS` が実際に効いていること。

    いまの親の題（「周の台帳: …（hourly, optimizer）」）は役の正規表現に
    そもそも当たらないので、**当たる形の題**で測る。この検査は
    `_PARENT_SUBJECTS` から「周の台帳」を外すと落ちる。
    """
    raw = (
        "\x002026-09-13T00:23:00+00:00\x0109/13 09:1x optimizer: 直した\nstudio/trend.py\n"
        "\x002026-09-13T00:24:00+00:00\x01周の台帳: optimizer: 09/13 09:0x JST の周を記録\n"
        "studio/trend.py\n"
        "\x002026-09-13T00:25:00+00:00\x01周の畳み（09/13 09:09 JST の周・optimizer 終い）\n"
        "data/parent_wakes.jsonl\n"
    )
    got = turf.touches(_at(0), raw=raw)
    assert [(r, sorted(f)) for _, r, f in got] == [("optimizer", ["studio/trend.py"])]
    # 陽性対照: 除外を外すと、親の commit が役として数えられる
    saved = turf._PARENT_SUBJECTS
    try:
        turf._PARENT_SUBJECTS = tuple(p for p in saved if p != "周の台帳")
        assert len(turf.touches(_at(0), raw=raw)) == 2
    finally:
        turf._PARENT_SUBJECTS = saved


def test_役の字が無い題は数えない() -> None:
    raw = ("\x002026-09-13T00:24:00+00:00\x01周の台帳: 09/13 09:0x JST の周を記録"
           "（hourly, optimizer）\ndata/rounds.jsonl\n")
    assert turf.touches(_at(0), raw=raw) == []


def test_触れていない周は連を伸ばしも切りもしない() -> None:
    rs = [_at(3), _at(4), _at(5)]
    tt = [
        (_at(3, 10), "optimizer", {"studio/trend.py"}),
        (_at(4, 10), "hourly", {"studio/trend.py"}),      # 判定を持つ側だけの周
        (_at(5, 10), "optimizer", {"studio/trend.py"}),
    ]
    marks = turf.marks_from(rs, tt, {"studio/trend.py"})
    assert [m["round"] for m in marks] == [_at(3), _at(5)]
    assert all(m["both"] == [] for m in marks)


def test_同じ周に両方が触れた周には印が付く() -> None:
    rs = [_at(9)]
    tt = [
        (_at(9, 20), "optimizer", {"studio/trend.py"}),
        (_at(9, 25), "hourly", {"studio/trend.py"}),
    ]
    marks = turf.marks_from(rs, tt, {"studio/trend.py"})
    assert marks[0]["both"] == ["studio/trend.py"]


def test_判定を持つ側のfileでなければ数えない_陽性対照() -> None:
    rs = [_at(3)]
    tt = [(_at(3, 10), "optimizer", {"scripts/quota.py"})]
    assert turf.marks_from(rs, tt, {"studio/trend.py"}) == []
    assert turf.marks_from(rs, tt, {"scripts/quota.py"}) != []


def test_門は3回で_連が届かなければ引かれない() -> None:
    assert turf.GATE == 3
    rs = [_at(3), _at(4)]
    tt = [(_at(3, 10), "optimizer", {"studio/trend.py"}),
          (_at(4, 10), "optimizer", {"studio/trend.py"})]
    assert len(turf.marks_from(rs, tt, {"studio/trend.py"})) < turf.GATE


def test_いまのrepoで撃てて_行に連と門と起点が出る() -> None:
    res = turf.run(laps=40)
    assert res["gate"] == 3
    assert res["run"] == len(res["marks"])
    out = turf.line(res)
    assert "連:" in out and "門 3回" in out
    assert ("引かれました" in out) == res["drawn"]
