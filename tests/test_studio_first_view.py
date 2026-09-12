"""`trend.first_view` —— 1回目の再生が付いた齢を、早い点を持つ本だけで挟む。

**陽性対照つき**（§5 の教訓の形 3つ目「陽性対照は落ちるまで撃つ」）:
`returned_private` の落としを外すと `test_privateへ戻した本は数えない` が落ち、
`FIRST_VIEW_EARLY_H` の門を外すと `test_初点が門より遅い本は答えられないので外す` が落ちる。
どちらも 2026-09-10 14:1x に動かして確かめた。
"""
import datetime as dt

from studio import trend

JST = dt.timezone(dt.timedelta(hours=9))
T0 = dt.datetime(2026, 9, 10, 10, 0, tzinfo=JST)


def _m(vid: str, age_h: float, views: int) -> dict:
    return {"event": "measured", "id": vid, "age_h": age_h, "views": views,
            "at": (T0 + dt.timedelta(hours=age_h)).isoformat()}


def test_挟みは最後の0と最初の正のあいだ():
    rows = [_m("a", 0.5, 0), _m("a", 1.4, 0), _m("a", 2.2, 7), _m("a", 3.0, 20)]
    b = trend.first_view(rows)["books"][0]
    assert (b["lo"], b["hi"]) == (1.4, 2.2)
    assert b["zero_through_h"] is None
    assert b["views"] == 20


def test_初点が既に正なら下端は無い():
    rows = [_m("a", 4.3, 85), _m("a", 6.0, 120)]
    b = trend.first_view(rows)["books"][0]
    assert b["lo"] is None and b["hi"] == 4.3
    assert "**1回目はそれより前**" in "\n".join(trend.first_view_lines(rows))


def test_0のままなら上端が無く何時間まで0かを持つ():
    # **齢は門（`FIRST_VIEW_EARLY_H`）から引く** —— 定数を動かした回に、この検査が
    # 「きょうの状態」を不変条件として持たないため（§5 教訓の形 6つ目）。
    last = trend.FIRST_VIEW_EARLY_H + 1.0
    rows = [_m("a", 0.3, 0), _m("a", 2.5, 0), _m("a", last, 0)]
    f = trend.first_view(rows)
    b = f["books"][0]
    assert b["hi"] is None and b["zero_through_h"] == last
    assert [x["id"] for x in f["zero"]] == ["a"]
    assert f["zero_early"] == []
    assert f["latest_first"] is None


def test_門の手前で0回の本はzeroにもzero_shortにも入らない(monkeypatch):
    """**陽性対照**: `through_gate` の絞り（`zero` / `zero_early` の分け）を外すと、
    `young` が `zero_short` に入って 2本 になり、この検査が落ちます
    （2026-09-12 11:1x に撃って確かめた ＝ §7「形」の 決め (5-2) の分子）。
    """
    monkeypatch.setattr(trend, "durations",
                        lambda r, uploaded=None: {"old": (90.0, "台帳 built"),
                                                  "young": (90.0, "台帳 built")})
    gate = trend.FIRST_VIEW_EARLY_H
    rows = [_m("old", 1.0, 0), _m("old", gate + 43.0, 0),          # 門を越えて 0回
            _m("young", 0.1, 0), _m("young", gate - 5.0, 0)]       # まだ門の手前
    f = trend.first_view(rows)
    assert [b["id"] for b in f["zero"]] == ["old"]
    assert [b["id"] for b in f["zero_short"]] == ["old"]
    assert [b["id"] for b in f["zero_early"]] == ["young"]
    out = "\n".join(trend.first_view_lines(rows))
    assert "**0回 のまま門を越えたのは 1本**" in out
    assert "まだ門の手前" in out and "young" in out


def test_privateへ戻した本は数えない():
    """陽性対照: `returned_private` の落としを外すと、この本が `zero` に混ざる。"""
    rows = [_m("gone", 0.1, 0),
            {"event": "unscheduled", "id": "gone",
             "at": (T0 + dt.timedelta(hours=0.2)).isoformat()},
            _m("live", 0.5, 0), _m("live", 1.5, 9)]
    f = trend.first_view(rows)
    assert [b["id"] for b in f["books"]] == ["live"]
    assert f["zero"] == []


def test_初点が門より遅い本は答えられないので外す():
    """陽性対照: 門を外すと、この本が `books` に入り `latest_first` を 30.0h へ動かす。"""
    rows = [_m("late", 30.0, 5), _m("late", 31.0, 9),
            _m("early", 0.5, 0), _m("early", 1.5, 9)]
    f = trend.first_view(rows)
    assert [b["id"] for b in f["books"]] == ["early"]
    assert f["late"] == 1
    assert f["latest_first"] == 1.5


def test_上端は挟みの上端の最大():
    rows = [_m("a", 0.5, 0), _m("a", 1.5, 3),
            _m("b", 0.4, 0), _m("b", 4.8, 30)]
    assert trend.first_view(rows)["latest_first"] == 4.8


def test_新と旧を分ける():
    rows = [{"event": "scheduled", "video_id": "a", "at": T0.isoformat()},
            _m("a", 0.5, 0), _m("a", 1.5, 3), _m("b", 0.4, 0), _m("b", 1.0, 2)]
    got = {b["id"]: b["new"] for b in trend.first_view(rows)["books"]}
    assert got == {"a": True, "b": False}
    line = "\n".join(trend.first_view_lines(rows))
    assert "新 a" in line and "旧 b" in line


def test_印字は本ごとに1行と見出しと締め():
    rows = [_m("a", 0.5, 0), _m("a", 1.5, 3), _m("b", 0.4, 0), _m("b", 1.0, 2)]
    out = trend.first_view_lines(rows)
    assert len(out) == 1 + 2 + 1
    assert out[0].startswith("**1回目の再生が付いた齢**")
    assert "判定は `hourly`" in out[-1]


def test_本が無ければ何も印字しない():
    assert trend.first_view_lines([]) == []


def test_trendの並びに入っている():
    """毎周 印字されること（**次の回は覚えていなくてよい**の当のもの）。"""
    rows = [_m("a", 0.5, 0), _m("a", 1.5, 3)]
    out = "\n".join(trend.lines(rows, now=T0 + dt.timedelta(hours=2)))
    assert "**1回目の再生が付いた齢**" in out


def test_いまN回は数え直しを落とした水準で読む():
    """`recounts()` が落とした峰を、この行も落とすこと（2026-09-10 20:5x）。

    陽性対照: `first_view` の `views` を `ceiling(good)` から点の生の `max` へ戻すと落ちる。
    実物で踏んだ形（`nQbVxuWpWw8` 68 → 66）と同じ並び —— 峰が
    `ENVELOPE_LAG_H` より長く下回ったまま戻らない。
    """
    rows = [_m("a", 0.5, 0), _m("a", 1.5, 40), _m("a", 3.0, 68)]
    rows += [_m("a", 3.0 + h, 66) for h in (1.0, 3.0, 6.5, 9.0, 12.0)]
    b = trend.first_view(rows)["books"][0]
    assert b["views"] == 66, "生の max（68）ではなく、数え直しを落とした水準"
    assert [r["id"] for r in trend.recounts(rows)] == ["a"]
    assert "いま 66回" in "\n".join(trend.first_view_lines(rows))


def test_views欄の無い点が混ざっても落ちない():
    """`series()` は `views` が None の `measured` も返す（§7 (j)）—— `ceiling` に渡さないこと。"""
    rows = [_m("a", 0.5, 0), {"event": "measured", "id": "a", "age_h": 1.0,
                              "views": None, "at": T0.isoformat()},
            _m("a", 2.0, 9)]
    b = trend.first_view(rows)["books"][0]
    assert b["views"] == 9 and (b["lo"], b["hi"]) == (0.5, 2.0)
