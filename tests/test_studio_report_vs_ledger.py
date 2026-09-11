"""`trend.report_vs_ledger` —— 一括レポート（a3）の日ごとの再生を、台帳の包絡と並べる。

2026-09-11 18:4x・optimizer・Opus。**§7 (o-4)(3) が名指ししていた並べ直し**
（「複製から返らない唯一の口で、(m) を外から当てられるのはここだけ」）。

**陽性対照つき**（下の 3件）—— 道具を壊すと落ちることを、この回に撃って確かめてある。
"""
import datetime as dt

import studio.trend as tr

JST = dt.timezone(dt.timedelta(hours=9))


def _led(points, vid="AAA", start="2026-09-09T10:00:00+09:00"):
    """(齢h, 生の再生) の並びから、台帳の `scheduled` ＋ `measured` の行を作る。"""
    pub = dt.datetime.fromisoformat(start)
    out = [{"event": "scheduled", "video_id": vid, "at": start}]
    for age, views in points:
        out.append({"event": "measured", "id": vid, "age_h": age, "views": views,
                    "at": (pub + dt.timedelta(hours=age)).isoformat()})
    return out


def _rep(date, views, vid="AAA", country="JP", created="2026-09-11T08:00:00Z"):
    return {"date": date, "video_id": vid, "views": str(views),
            "country_code": country, "_created": created}


def test_齢6時間ちょうどの境目で報告と台帳を並べる():
    """10:00 JST 公開 ＋ 16:00 JST の区切り ＝ **最初の境目は 齢 6.0h ちょうど**。"""
    rows = _led([(1.0, 100), (6.0, 458), (30.0, 930)])
    rep = [_rep("20260908", 694), _rep("20260909", 236)]
    g = tr.report_vs_ledger(rows, rep)
    pts = g["books"][0]["points"]
    assert [p["age_h"] for p in pts] == [6.0, 30.0]
    # 齢 6.0h: 報告 694 に対し、台帳の包絡は 458 ＝ **-34%**（複製がそろって遅れている帯）
    assert pts[0]["cum"] == 694 and pts[0]["led"] == 458
    assert round(pts[0]["ratio"] * 100, 1) == -34.0
    # 次の境目で閉じる
    assert pts[1]["cum"] == 930 and pts[1]["led"] == 930 and pts[1]["diff"] == 0


def test_同じ日の次元で割れた行を足してから累計にする():
    """**陽性対照 1**: 1行 だけ採る形へ戻すと、この検査が落ちる（17:5x に踏んだ穴）。"""
    rows = _led([(6.0, 100)])
    rep = [_rep("20260908", 0, country="ZZ"), _rep("20260908", 232, country="JP")]
    g = tr.report_vs_ledger(rows, rep)
    assert g["books"][0]["points"][0]["cum"] == 232


def test_台帳の側は包絡で読む():
    """**陽性対照 2**: 生の点で読むと、遅れた複製に落ちて差が水増しされる。"""
    rows = _led([(5.0, 458), (6.0, 120)])   # 6.0h は遅れた複製
    rep = [_rep("20260908", 694)]
    g = tr.report_vs_ledger(rows, rep)
    assert g["books"][0]["points"][0]["led"] == 458


def test_日に穴が在る回は名指しする():
    """**陽性対照 3**: 穴を数えない形へ戻すと、印字は穴の在る累計を黙って出す。"""
    rows = _led([(6.0, 100), (30.0, 200)])
    rep = [_rep("20260907", 50), _rep("20260909", 60)]
    g = tr.report_vs_ledger(rows, rep)
    assert g["holes"] == ["20260908"]
    assert "日に穴 1日" in tr.report_vs_ledger_line(rows, rep)


def test_チャンネルの側は重なりが無ければ次に当てられる日と予測を出す():
    """(m) を外から当てるには、報告の日を**台帳の `channel` の行が丸ごと覆う**必要がある。"""
    rows = _led([(6.0, 100)])
    for t, v in (("2026-09-10T15:24:00+09:00", 84781), ("2026-09-11T15:50:00+09:00", 86446),
                 ("2026-09-11T18:42:00+09:00", 86446)):
        rows.append({"event": "channel", "id": "C", "at": t, "views": v, "subs": 28})
    rep = [_rep("20260908", 694)]
    g = tr.report_vs_ledger(rows, rep)
    assert g["channel"]["overlap"] == []          # 20260908 は台帳の行より前 ＝ 重ならない
    assert g["channel"]["next_day"] == "20260910"  # 09/10 16:00〜09/11 16:00 JST を覆う
    assert g["channel"]["predict"] == 1665
    assert "いちばん早く当てられるのは報告の日 20260910" in tr.report_vs_ledger_line(rows, rep)


def test_重なる日が在れば報告と台帳の差をそのまま並べる():
    rows = _led([(6.0, 100)])
    for t, v in (("2026-09-10T15:24:00+09:00", 84781), ("2026-09-10T17:00:00+09:00", 84800),
                 ("2026-09-11T15:50:00+09:00", 86446), ("2026-09-11T17:00:00+09:00", 86446)):
        rows.append({"event": "channel", "id": "C", "at": t, "views": v, "subs": 28})
    rep = [_rep("20260910", 1700)]
    g = tr.report_vs_ledger(rows, rep)
    assert [(o["date"], o["rep"], o["led"]) for o in g["channel"]["overlap"]] \
        == [("20260910", 1700, 1665)]
