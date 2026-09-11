"""`trend.late_gain` —— **齢 48h より後に付いた割合**（2026-09-12 04:3x・optimizer・Opus）。

§1 の表の行は **覆る条件 (2)「48h の後の伸びが 3本 続けて 5% 未満なら、後半を戻す」**を
持ちながら、**その割合を印字する口が 1つも無かった**（`HOLD_AGES` は 24h で止まっていた）。
＝ サブが毎周 やる仕事 (b)（覆る条件を数字で見る）が、この 1つ だけ構造的にできなかった。
その行は代わりに**手で数えた 2つ の割合を本文へ写して**おり、1日 で古くなっている。
この検査は、その口を機械に留める。
"""
import datetime as dt

import studio.trend as tr


def _rows(points, vid="AAA", start="2026-09-08T10:00:00+09:00"):
    """(齢h, 生の再生) の並びから measured 行を作る（`test_studio_trend_hold` と同じ形）。"""
    pub = dt.datetime.fromisoformat(start)
    out = [{"event": "scheduled", "video_id": vid, "at": start}]
    for age, views in points:
        out.append({
            "event": "measured", "id": vid, "age_h": age, "views": views,
            "at": (pub + dt.timedelta(hours=age)).isoformat(),
        })
    return out


def test_48hの列が並びに出る():
    """**陽性対照つき**: 直す前の `HOLD_AGES`（6/12/24）では、この列は作れない。"""
    assert tr.HOLD_LATE_H in tr.HOLD_AGES
    rows = _rows([(1.0, 10), (6.0, 40), (30.0, 90), (47.0, 95), (60.0, 100), (130.0, 100)])
    got = tr.hold(rows)[0]
    assert got["at"][48.0] is not None
    assert "48h" in "\n".join(tr.hold_lines(rows))
    # 陽性対照: 齢が 48h に届かない本は、この列を持たない（None ＝ 数えない）
    young = tr.hold(_rows([(1.0, 10), (20.0, 100)], vid="YOUNG"))[0]
    assert young["at"][48.0] is None
    assert tr.late_gain([young]) == []


def test_確定した本は_5パーセント未満を言い切る():
    rows = _rows([(1.0, 10), (30.0, 98), (47.5, 100), (48.4, 100), (130.0, 100)])
    got = tr.hold(rows)
    assert got[0]["growing"] is False
    one = tr.late_gain(got)[0]
    assert one["verdict"] == "under" and one["hi"] < tr.HOLD_LATE_GATE_PCT
    assert tr.late_run(tr.late_gain(got)) == 1


def test_伸びている本には_5パーセント未満を返さない():
    """分母（いまの再生）がこれから増える ＝ **後の伸びは上がるだけ** ＝ 下端しか決まらない。"""
    rows = _rows([(1.0, 10), (30.0, 98), (47.5, 100), (48.4, 100), (60.0, 100), (60.5, 101)])
    got = tr.hold(rows)
    assert got[0]["growing"] is True
    one = tr.late_gain(got)[0]
    assert one["lo"] < tr.HOLD_LATE_GATE_PCT and one["verdict"] == "unknown"
    # 陽性対照: 同じ数でも、平らが門を越えて確定すれば `under` になる
    settled = tr.hold(_rows([(1.0, 10), (30.0, 98), (47.5, 100), (48.4, 100),
                             (60.0, 101), (170.0, 101)]))
    assert settled[0]["growing"] is False
    assert tr.late_gain(settled)[0]["verdict"] == "under"


def test_下端が門の上なら_伸びていても言い切れる():
    """``over`` は片側だけで決まる —— 分母が増えても、後の伸びは下がらない。"""
    rows = _rows([(1.0, 10), (30.0, 50), (47.5, 60), (48.4, 60), (130.0, 100)])
    got = tr.hold(rows)
    assert got[0]["growing"] is True
    one = tr.late_gain(got)[0]
    assert one["verdict"] == "over" and one["lo"] >= tr.HOLD_LATE_GATE_PCT
    assert tr.late_run(tr.late_gain(got)) == 0


def test_48hちょうどの点が無い本は挟みで開く():
    """`hold_verdict` と同じ規則 —— 下は「48h 以前の最後の点」、上は「越えた最初の点」。"""
    rows = _rows([(1.0, 10), (44.8, 70), (53.0, 90), (130.0, 100)])
    one = tr.late_gain(tr.hold(rows))[0]
    assert round(one["lo"]) == 10 and round(one["hi"]) == 30
    assert one["verdict"] == "over"      # 下端 10% ＝ 門の上
    # 陽性対照: 48h ちょうど（±HOLD_EXACT_H）の点が在れば挟みは潰れる
    exact = tr.late_gain(tr.hold(_rows([(1.0, 10), (48.0, 90), (130.0, 100)], vid="EXACT")))[0]
    assert abs(exact["hi"] - exact["lo"]) < 1e-9


def test_鎖は新しいほうから数え_言えない本で切れる():
    """§1 の「**3本 続けて** 5% 未満」は、公開の順の**末**から数える。"""
    under = {"verdict": "under"}
    unknown = {"verdict": "unknown"}
    over = {"verdict": "over"}
    assert tr.late_run([under, under, under]) == 3
    assert tr.late_run([under, under, unknown]) == 0      # 末が言えない ＝ 続いていない
    assert tr.late_run([over, under, under]) == 2
    assert tr.late_run([]) == 0


def test_門の判定が印字される():
    rows = _rows([(1.0, 10), (30.0, 98), (47.5, 100), (48.4, 100), (130.0, 100)])
    line = tr.late_gain_line(tr.hold(rows))
    assert "5% 未満が新しいほうから続いているのは 1本" in line
    assert "門 3本 ＝ **引かれません**" in line
    assert "判定は `hourly`" in line


def test_本物の台帳で行が出る():
    got = tr.hold(tr.ledger_rows())
    rows = tr.late_gain(got)
    assert rows, "齢 48h を越えたこちらの本が 1本 も無い ＝ この口は早すぎる"
    assert all(r["lo"] <= r["hi"] for r in rows)
    line = "\n".join(tr.hold_lines(tr.ledger_rows()))
    assert "48h より後に付いた割合" in line
