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
