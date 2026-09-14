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
    """(m) を外から当てるには、報告の日を**台帳の `channel` の行が丸ごと覆う**必要がある。

    **2026-09-13 01:0x に、覆うだけでは足りないことが分かりました**（optimizer・Opus）——
    **最初の刻みを含む窓は読めない**ので（`censored`）、ここが指す「次の日」も
    その刻みより**後ろから始まる窓**でなければなりません。
    09/10 16:00〜09/11 16:00 は +1,625（censored）を含むので **20260911** が最初。
    """
    rows = _ch(_led([(6.0, 100)]), _CH)
    rep = [_rep("20260908", 694)]
    g = tr.report_vs_ledger(rows, rep)
    assert g["channel"]["overlap"] == []          # 20260908 は台帳の行より前 ＝ 重ならない
    assert g["channel"]["next_day"] == "20260911"  # 09/11 16:00〜09/12 16:00 JST（+44 +948）
    assert g["channel"]["predict"] == 992
    assert "いちばん早く当てられるのは報告の日 20260911" in tr.report_vs_ledger_line(rows, rep)


def test_重なる日が在れば報告と台帳の差をそのまま並べる():
    rows = _led([(6.0, 100)])
    for t, v in (("2026-09-10T15:24:00+09:00", 84781), ("2026-09-10T17:00:00+09:00", 84800),
                 ("2026-09-11T15:50:00+09:00", 86446), ("2026-09-11T17:00:00+09:00", 86446)):
        rows.append({"event": "channel", "id": "C", "at": t, "views": v, "subs": 28})
    rep = [_rep("20260910", 1700)]
    g = tr.report_vs_ledger(rows, rep)
    assert [(o["date"], o["rep"], o["led"]) for o in g["channel"]["overlap"]] \
        == [("20260910", 1700, 1665)]


def _ch(rows, points):
    """(刻, 総再生) の並びから `channel` の行を足す。"""
    for t, v in points:
        rows.append({"event": "channel", "id": "C", "at": t, "views": v, "subs": 28})
    return rows


#: 実物（2026-09-13 01:0x）の刻み: 先頭 → +1,625（censored）→ +40 → +44 → +948。
_CH = (("2026-09-10T15:24:00+09:00", 84781),
       ("2026-09-11T02:12:00+09:00", 86406),
       ("2026-09-11T15:50:00+09:00", 86446),
       ("2026-09-12T02:04:00+09:00", 86490),
       ("2026-09-12T11:52:00+09:00", 87438),
       ("2026-09-13T00:54:00+09:00", 87438))


def test_最初の刻みを含む窓は読めない側に落ちる():
    """2026-09-13 01:0x・optimizer・Opus。**実物 20260910（報告 797 対 台帳 1665）で踏んだ。**

    左端が台帳の先頭の平らに掛かる窓は **24時間 ぶんより多く抱えます**
    （`channel_steps` の `censored` と同じ理由）。**陽性対照**: `censored` の門を外すと
    `read` に落ち、下の 3つ の assert が落ちる。
    """
    rows = _ch(_led([(6.0, 100)]), _CH)
    rep = [_rep("20260910", 797)]
    g = tr.report_vs_ledger(rows, rep)
    ch = g["channel"]
    assert [(o["date"], o["led"], o["censored"]) for o in ch["overlap"]] \
        == [("20260910", 1665, True)]
    assert ch["read"] == [] and ch["drawn"] is False and ch["ratio"] is None
    # **次に読めるのは、最初の刻みより後ろから始まる窓**（09/11 16:00〜09/12 16:00 ＝ +44 +948）
    assert ch["next_day"] == "20260911" and ch["predict"] == 992
    line = tr.report_vs_ledger_line(rows, rep)
    assert "この日は読めません" in line and "次に読めるのは報告の日 20260911" in line


def test_刻みより後ろの窓は累計で読み許容は端の刻み1つぶん():
    """**許容の単位は再生**（`_overlap_edge_views`）—— 時間ではありません。

    2026-09-14 16:0x に直した所（覆る条件 (4) が **単位のせいで** 1度 引かれた）。
    窓の端で取り違えられるのは **刻み 1つ ぶん**で、その 1つ は 20〜1,625回 と 2桁 開きます。
    ここは 端 44回（09/11 16:00 の前後）＋ 948回（09/12 16:00 の手前）＝ **992回**。
    """
    rows = _ch(_led([(6.0, 100)]), _CH)
    rep = [_rep("20260910", 797), _rep("20260911", 900)]
    g = tr.report_vs_ledger(rows, rep)
    ch = g["channel"]
    assert [(o["date"], o["censored"]) for o in ch["overlap"]] \
        == [("20260910", True), ("20260911", False)]
    assert ch["rep_sum"] == 900 and ch["led_sum"] == 992
    assert round(ch["ratio"], 4) == round(992 / 900 - 1.0, 4)      # +10.2%
    assert ch["edge_views"] == 992 and ch["drawn"] is False
    assert round(ch["tol"], 4) == round(992 / 900, 4)
    assert "同じ物を数えています" in tr.report_vs_ledger_line(rows, rep)


def test_端の刻みが大きい回は門が引かれない():
    """**戻り止め（2026-09-14 16:0x）**: 実物 09/14 15:4x の数で、**引かれてはいけません**。

    読める日 2日・報告 1,291回 対 台帳 1,808回（**+40.0%**）。終わりの端の刻みが **796回**
    （09/13 11:58）なので、端の取り違えだけで **840回 ＝ 65%** 動きます。
    **許容を `刻みの周期（時間） ÷ 日数`（= 29%）へ戻すと、この検査が落ちます。**
    """
    rows = _ch(_led([(6.0, 100)]), (
        ("2026-09-10T15:24:00+09:00", 84781),
        ("2026-09-11T02:12:00+09:00", 86406),   # censored の刻み +1,625
        ("2026-09-11T14:55:00+09:00", 86446),   # +40
        ("2026-09-12T02:04:00+09:00", 86490),   # +44
        ("2026-09-12T11:52:00+09:00", 87438),   # +948
        ("2026-09-13T01:48:00+09:00", 87458),   # +20
        ("2026-09-13T11:57:00+09:00", 88254),   # +796
        ("2026-09-14T00:49:00+09:00", 88344),   # +90
    ))
    rep = [_rep("20260910", 797), _rep("20260911", 1051), _rep("20260912", 240)]
    ch = tr.report_vs_ledger(rows, rep)["channel"]
    assert ch["rep_sum"] == 1291 and ch["led_sum"] == 1808
    assert round(ch["ratio"] * 100, 1) == 40.0
    assert ch["edge_views"] == 44 + 796                 # 09/11 16:00 の前後・09/12 16:00 の後ろ
    assert ch["drawn"] is False


def test_許容を越えたら門が引かれる():
    """**陽性対照**: 端の刻みが小さいのに合計が食い違う回は、いまも引かれます。

    刻みが 10回 ずつの窓（端の取り違えは 20回 まで）で、報告 100回 対 台帳 20回 ＝ **-80%**。
    """
    rows = _ch(_led([(6.0, 100)]), (
        ("2026-09-10T15:24:00+09:00", 84781),
        ("2026-09-11T02:12:00+09:00", 86406),   # censored
        ("2026-09-11T15:50:00+09:00", 86416),   # +10
        ("2026-09-12T02:04:00+09:00", 86426),   # +10
        ("2026-09-12T11:52:00+09:00", 86436),   # +10
        ("2026-09-13T00:54:00+09:00", 86436),
    ))
    rep = [_rep("20260911", 100)]                       # 台帳 20 対 報告 100
    g = tr.report_vs_ledger(rows, rep)
    ch = g["channel"]
    assert ch["led_sum"] == 20 and ch["edge_views"] == 20
    assert ch["drawn"] is True
    assert "引かれました" in tr.report_vs_ledger_line(rows, rep)
