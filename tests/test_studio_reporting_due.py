"""`trend.reporting_due` —— **`reporting` を、この回に撃つ番か**（台帳の `reported` と時計だけ・API 0単位）。

2026-09-12 17:5x・optimizer・Opus。**§5 の「教訓の形 7つ目」の族**（覆る条件や次の手を註に書いたら、
それを読む**印字**も一緒に作ること）—— `report_vs_ledger_line` は「次の報告の日」と
「置かれる見込みの刻」を毎周 印字しながら、**その刻を過ぎたかも、最後に撃ったのがいつかも
言っていませんでした**。実測: 最後に撃ったのは 09/11 18:46 で、この回まで **23.1時間・9周**。

**陽性対照つき**（下の 4件 は、門を 1つ ずつ外すと落ちる）。
"""
import datetime as dt

import studio.reporting as rp
import studio.trend as tr

JST = dt.timezone(dt.timedelta(hours=9))


def _fired(when: str, made_h: float = 25.8) -> dict:
    return {"event": "reported", "id": rp.REPORT_TYPE, "at": when,
            "reports": 31, "rows": 0, "last_day": "20260909", "made_h": made_h}


def _now(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s)


def test_見込みの前は撃たない():
    """報告の日 20260910 の期間の終わりは 09/11 16:00 JST ＝ 見込みは その 25.8時間 後。"""
    d = tr.reporting_due([_fired("2026-09-11T18:46:00+09:00")], "20260909",
                         now=_now("2026-09-12T17:33:00+09:00"))
    assert d["due"] is False and d["why"] == "early"
    assert d["next_day"] == "20260910"
    assert d["eta"].astimezone(JST).strftime("%m/%d %H:%M") == "09/12 17:48"
    assert d["age_h"] == 22.8


def test_見込みを過ぎたら撃つ番になる():
    d = tr.reporting_due([_fired("2026-09-11T18:46:00+09:00")], "20260909",
                         now=_now("2026-09-12T18:33:00+09:00"))
    assert d["due"] is True and d["why"] == "due"


def test_見込みの後に撃って空だった回は少し待つ():
    """**毎周 撃たない** —— 報告が遅れている側なので、`REPORT_RETRY_H` のあいだは撃ち直さない。"""
    rows = [_fired("2026-09-11T18:46:00+09:00"), _fired("2026-09-12T18:33:00+09:00")]
    d = tr.reporting_due(rows, "20260909", now=_now("2026-09-12T19:33:00+09:00"))
    assert d["due"] is False and d["why"] == "waited"


def test_待ちを過ぎたら撃ち直す():
    rows = [_fired("2026-09-11T18:46:00+09:00"), _fired("2026-09-12T18:33:00+09:00")]
    later = _now("2026-09-12T18:33:00+09:00") + dt.timedelta(hours=tr.REPORT_RETRY_H + 0.1)
    d = tr.reporting_due(rows, "20260909", now=later)
    assert d["due"] is True and d["why"] == "due"


def test_1度も積んでいなければ撃つ():
    d = tr.reporting_due([], None, now=_now("2026-09-12T17:33:00+09:00"))
    assert d["due"] is True and d["why"] == "never"
    assert d["last_at"] is None and d["age_h"] is None


def test_置かれるまでの時間は台帳のmade_hから取る():
    """**手で書いた 25.8 ではありません** —— 枠が変われば台帳の側が動きます。"""
    d = tr.reporting_due([_fired("2026-09-11T18:46:00+09:00", made_h=30.0)], "20260909",
                         now=_now("2026-09-12T17:33:00+09:00"))
    assert d["made_h"] == 30.0
    assert d["eta"].astimezone(JST).strftime("%m/%d %H:%M") == "09/12 22:00"
    # 台帳に 1行 も無ければ既定
    assert tr.reporting_due([], "20260909",
                            now=_now("2026-09-12T17:33:00+09:00"))["made_h"] == tr.REPORT_MADE_H


def test_他のジョブの行を最後の撃ちと読まない():
    """`reported` は a3 と reach の 2行 出ます。**刻は同じでも、読むのは a3 の側だけ**。"""
    rows = [_fired("2026-09-11T18:46:00+09:00"),
            {"event": "reported", "id": rp.REACH_TYPE, "at": "2026-09-12T17:00:00+09:00",
             "made_h": 22.5}]
    d = tr.reporting_due(rows, "20260909", now=_now("2026-09-12T17:33:00+09:00"))
    assert d["last_at"].astimezone(JST).strftime("%m/%d %H:%M") == "09/11 18:46"
    assert d["made_h"] == 25.8


def test_印字は撃つ番かを言う():
    w = tr.reporting_due_words([_fired("2026-09-11T18:46:00+09:00")], "20260909",
                               now=_now("2026-09-12T18:33:00+09:00"))
    assert "この回に `python -m studio.cli reporting` を撃つこと" in w
    assert "0.8時間 過ぎています" in w
    early = tr.reporting_due_words([_fired("2026-09-11T18:46:00+09:00")], "20260909",
                                   now=_now("2026-09-12T17:33:00+09:00"))
    assert "撃たなくてよい回です" in early and "あと 0.2時間" in early
    # **同じ1行に時計が 2つ 並びます** —— `made_h` は残り時間ではなく「窓が閉じてから置かれるまで」。
    # 2026-09-13 01:5x に印字を直した（実測 09/13 00:5x の行: 「あと 21.3時間（…置かれるまで 31.1時間）」
    # ＝ 読む側は 2つ目も残り時間に読めた・§5 教訓の形 7つ目「読まれるのは印字のほう」）。
    assert "窓が閉じてから置かれるまでの" in early and "残り時間ではありません" in early


# ---- `trend.reporting_empty_run` —— 覆る条件 (1) の「3回 続いたら」を数える口 ----
# 2026-09-12 18:4x・optimizer・Opus。**§7 (m) の `blind_run`（16:0x）と同じ族**:
# 「N回 続いたら」と註に書きながら、N を数える物が無かった側。
# **陽性対照つき**（下の 5件 は、述語か門を 1つ ずつ外すと落ちる）。

def _fired_day(when: str, last_day: str, rows_n: int = 0) -> dict:
    return {"event": "reported", "id": rp.REPORT_TYPE, "at": when,
            "reports": 31, "rows": rows_n, "last_day": last_day, "made_h": 25.8}


def test_空振りは見込みの後に撃った回だけ数える():
    """実測の並び: 09/11 18:46（見込み 09/12 17:48 の前）・09/12 17:36（同じく前）・09/12 18:29（後）。"""
    rows = [_fired_day("2026-09-11T17:52:02+09:00", "20260909"),
            _fired_day("2026-09-11T18:46:58+09:00", "20260909"),
            _fired_day("2026-09-12T17:36:14+09:00", "20260909"),
            _fired_day("2026-09-12T18:29:20+09:00", "20260909")]
    e = tr.reporting_empty_run(rows)
    assert e["run"] == 1 and e["drawn"] is False and e["day"] == "20260910"
    assert e["since"].astimezone(JST).strftime("%m/%d %H:%M") == "09/12 18:29"


def test_報告の日が進んだら連なりは切れる():
    rows = [_fired_day("2026-09-11T17:52:02+09:00", "20260909"),
            _fired_day("2026-09-12T18:29:20+09:00", "20260909"),
            _fired_day("2026-09-12T21:40:00+09:00", "20260910", rows_n=592)]
    assert tr.reporting_empty_run(rows)["run"] == 0


def test_0行でも報告の日が進んでいれば空振りではない():
    """**述語は `rows == 0` ではありません** —— 同じ日を撃ち直した回も 0行 になる（註の「述語は 1つ」）。"""
    rows = [_fired_day("2026-09-11T17:52:02+09:00", "20260909"),
            _fired_day("2026-09-12T18:29:20+09:00", "20260910", rows_n=0)]
    assert tr.reporting_empty_run(rows)["run"] == 0


def test_門に届いたら引かれ句が見積りの側を名指しする():
    rows = [_fired_day("2026-09-11T17:52:02+09:00", "20260909"),
            _fired_day("2026-09-12T18:29:20+09:00", "20260909"),
            _fired_day("2026-09-12T21:40:00+09:00", "20260909"),
            _fired_day("2026-09-13T01:00:00+09:00", "20260909")]
    e = tr.reporting_empty_run(rows)
    assert e["run"] == 3 and e["drawn"] is True
    w = tr.reporting_due_words(rows, "20260909", now=_now("2026-09-13T01:10:00+09:00"))
    assert "空振り 3/3回" in w and "made_h" in w and "最大" in w


def test_報告の日がまだ無い回は数えない():
    """1度も置かれていない枠（`last_day` が None）は「空振り」と読めない ＝ 連なりを切る。"""
    rows = [{"event": "reported", "id": rp.REPORT_TYPE, "at": "2026-09-10T18:11:31+09:00",
             "reports": 0, "rows": 0, "last_day": None},
            _fired_day("2026-09-12T18:29:20+09:00", "20260909")]
    assert tr.reporting_empty_run(rows)["run"] == 0
