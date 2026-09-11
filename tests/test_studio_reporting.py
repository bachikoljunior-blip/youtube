"""`studio/reporting.py`（一括レポート・3つ目の枠）の検査。2026-09-10 18:0x・optimizer・Opus。

**陽性対照つき**（下の 3件）—— 道具を壊すと落ちることを、この回に撃って確かめてある。
"""
from __future__ import annotations

import datetime as dt
import json

from studio import reporting

UTC = dt.timezone.utc


def _rep(rid: str, end: str, made: str) -> dict:
    return {"id": rid, "endTime": end, "createTime": made, "downloadUrl": "http://x/" + rid}


def test_ジョブは型で選び無ければNoneを返す():
    js = [{"id": "a", "reportTypeId": "channel_reach_basic_a1"},
          {"id": "b", "reportTypeId": "channel_basic_a3"}]
    assert reporting.job_for("channel_basic_a3", js)["id"] == "b"
    # **「無い」を空の dict で返さないこと**（§4 (0-b) の族）
    assert reporting.job_for("channel_traffic_source_a3", js) is None


def test_未読は件数で切らない():
    """`scripts/reach.py` が 08/20 まで `reports[-3:]` しか落としていなかった穴の裏返し。"""
    reps = [_rep(str(i), f"2026-08-{i:02d}T07:00:00Z", f"2026-08-{i + 1:02d}T09:00:00Z")
            for i in range(1, 31)]
    assert len(reporting.unseen(reps, set())) == 30
    assert len(reporting.unseen(reps, {"1", "2", "3"})) == 27


def test_遅れは期間の終わりから数え置かれるまでも別に出す():
    reps = [_rep("1", "2026-09-08T07:00:00Z", "2026-09-09T06:00:00Z"),
            _rep("2", "2026-09-09T07:00:00Z", "2026-09-10T08:50:20.451718Z")]
    now = dt.datetime(2026, 9, 10, 9, 0, tzinfo=UTC)
    fr = reporting.freshness(reps, now)
    assert fr["end"] == dt.datetime(2026, 9, 9, 7, 0, tzinfo=UTC)
    assert fr["lag_h"] == 26.0            # いまから見た遅れ
    assert 25.0 < fr["made_h"] < 26.0     # 期間の終わりから置かれるまで（実測 25.8時間）
    assert fr["late"] is False


def test_報告が0本なら遅れはNoneで0ではない():
    """ジョブを作った直後の正しい姿。**0 と読ませないこと。**"""
    assert reporting.freshness([], dt.datetime(2026, 9, 10, tzinfo=UTC)) is None


def test_置き直された日は新しい報告のほうを採る():
    rows = [{"date": "20260909", "video_id": "v1", "views": "100",
             "_report_id": "1", "_created": "2026-09-10T08:00:00Z"},
            {"date": "20260909", "video_id": "v1", "views": "137",
             "_report_id": "2", "_created": "2026-09-11T08:00:00Z"},
            {"date": "20260908", "video_id": "v1", "views": "9",
             "_report_id": "1", "_created": "2026-09-10T08:00:00Z"}]
    got = {(r["date"], r["views"]) for r in reporting.latest_rows(rows)}
    assert got == {("20260909", "137"), ("20260908", "9")}
    assert reporting.views_by_day(rows, "v1") == [("20260908", 9), ("20260909", 137)]


def test_10時JSTの公開は前日の報告の日に入る():
    """**この口のいちばん高い罠**（期間は 07:00Z 〜 翌 07:00Z ＝ 太平洋時間の日）。"""
    jst = dt.timezone(dt.timedelta(hours=9))
    assert reporting.pt_day(dt.datetime(2026, 9, 10, 10, 0, tzinfo=jst)) == "20260909"
    # 16:00 JST を越えると、その日の行へ移る
    assert reporting.pt_day(dt.datetime(2026, 9, 10, 16, 30, tzinfo=jst)) == "20260910"


def test_CSVはどの報告から来たかを行に残す():
    rep = _rep("42", "2026-09-09T07:00:00Z", "2026-09-10T08:50:00Z")
    rows = reporting.parse("date,video_id,views\n20260909,v1,7\n", rep)
    assert rows == [{"date": "20260909", "video_id": "v1", "views": "7",
                     "_report_id": "42", "_period_end": "2026-09-09T07:00:00Z",
                     "_created": "2026-09-10T08:50:00Z"}]


def test_積んだ報告のIDは畳む口から読める(tmp_path):
    p = tmp_path / "reporting.jsonl"
    rep = _rep("42", "2026-09-09T07:00:00Z", "2026-09-10T08:50:00Z")
    reporting.append(reporting.parse("date,video_id,views\n20260909,v1,7\n", rep), p)
    assert "42" in reporting.seen_marks(p)
    assert reporting.unseen([rep], reporting.seen_marks(p)) == []
    # 壊れた行が混ざっても落ちない（追記しかしない store なので、途中で切れることが在る）
    with p.open("a", encoding="utf-8") as fh:
        fh.write("{壊れ\n")
    assert "42" in reporting.seen_marks(p)
    assert len(reporting.load_rows(p)) == 1


def test_報告IDを持たない古いstoreも畳める(tmp_path):
    """`data/reach.jsonl`（旧 `scripts/reach.py` が書いた 2,095行）は `_report_end` しか持たない。

    **ID だけで見分けると「1本も積んでいない」と読め、64本 を落とし直して同じ日を二重に積みます。**
    2026-09-10 23:5x に実際に踏みかけた形（`seen_marks` の註）。
    """
    p = tmp_path / "reach.jsonl"
    p.write_text(json.dumps({"date": "20260815", "video_id": "v1",
                             "_report_end": "2026-08-16T07:00:00Z"}) + "\n", encoding="utf-8")
    old = _rep("99", "2026-08-16T07:00:00Z", "2026-08-17T09:00:00Z")
    new = _rep("100", "2026-08-17T07:00:00Z", "2026-08-18T09:00:00Z")
    marks = reporting.seen_marks(p)
    # 期間の終わりで畳めていること（ID は store に無い）
    assert "99" not in marks
    assert [r["id"] for r in reporting.unseen([old, new], marks)] == ["100"]


def test_positive_control_期間の終わりを見なければ古いstoreは二重に積まれる(tmp_path):
    """**陽性対照** —— `seen_marks` が `_report_end` を落とすと、この検査が落ちます。"""
    p = tmp_path / "reach.jsonl"
    p.write_text(json.dumps({"date": "20260815", "video_id": "v1",
                             "_report_end": "2026-08-16T07:00:00Z"}) + "\n", encoding="utf-8")
    ids_only = {str(json.loads(li).get("_report_id"))
                for li in p.read_text(encoding="utf-8").splitlines() if li.strip()} - {"None"}
    old = _rep("99", "2026-08-16T07:00:00Z", "2026-08-17T09:00:00Z")
    # ID だけの見分けでは、すでに積んだ報告がもう一度 未読に出る（＝ 二重に積む）
    assert reporting.unseen([old], ids_only) == [old]
    assert reporting.unseen([old], reporting.seen_marks(p)) == []


def test_取り込む型は2つ以上で1つに戻らないこと():
    """**1つの型だけを見る形へ戻すと落ちる**（2026-09-10 23:5x に踏んだ穴・`reporting.JOBS` の註）。

    18:0x の `cmd_reporting` は a3 だけを見ており、同じ口に置かれていた
    `channel_reach_basic_a1` の 8日ぶん が道具から 1行 も見えませんでした。
    """
    types = [t for t, _ in reporting.JOBS]
    assert reporting.REPORT_TYPE in types
    assert reporting.REACH_TYPE in types
    # 型ごとに store が分かれていること（同じ file に混ぜると `date` が別の意味で重なる）
    assert len({str(s) for _, s in reporting.JOBS}) == len(reporting.JOBS)


def test_面の行は日ごとにインプレッションとCTRで読める():
    rows = [{"date": "20260901", "video_id": "v1",
             "video_thumbnail_impressions": "200", "video_thumbnail_impressions_ctr": "0.05",
             "_created": "2026-09-02T09:00:00Z"},
            {"date": "20260902", "video_id": "v1",
             "video_thumbnail_impressions": "0", "video_thumbnail_impressions_ctr": "0",
             "_created": "2026-09-03T09:00:00Z"},
            {"date": "20260901", "video_id": "v2",
             "video_thumbnail_impressions": "9", "video_thumbnail_impressions_ctr": "0",
             "_created": "2026-09-02T09:00:00Z"}]
    assert reporting.reach_by_day(rows, "v1") == [("20260901", 200, 5.0), ("20260902", 0, 0.0)]


def test_storeが無ければ空で読める(tmp_path):
    assert reporting.seen_marks(tmp_path / "no.jsonl") == set()
    assert reporting.load_rows(tmp_path / "no.jsonl") == []


def test_取り込みの型は台帳の行にできる(tmp_path):
    """`cmd_reporting` が台帳へ書く欄が、そのまま JSON にできること（`ledger()` を通す族）。"""
    rep = _rep("42", "2026-09-09T07:00:00Z", "2026-09-10T08:50:00Z")
    fr = reporting.freshness([rep], dt.datetime(2026, 9, 10, 9, 0, tzinfo=UTC))
    row = {"reports": 1, "rows": 1, "last_day": "20260909",
           "lag_h": fr["lag_h"], "made_h": fr["made_h"]}
    assert json.loads(json.dumps(row))["lag_h"] == 26.0


# ---- 1日は 1行 ではない（2026-09-11 17:5x・optimizer・Opus。**最初の CSV が届いた回に撃った**）
# **踏んだ形（実物）**: `channel_basic_a3` の 1行 は（日・本・**国・登録の有無・生か収録か**）で割れる。
# `latest_rows` が (日・本) で 1行 に畳んでいたので、`lQHX9LJ80Sg` の 09/08 は
# **ZZ の 0回** だけが残り、**JP の 232回** が落ちていた（台帳の側は 692回）。

def _a3(date, vid, views, country, created="2026-09-11T08:00:00Z", subscribed="not_subscribed"):
    return {"date": date, "video_id": vid, "views": str(views), "country_code": country,
            "subscribed_status": subscribed, "live_or_on_demand": "on_demand",
            "_report_id": "r" + created[-3:], "_created": created}


def _split_day():
    """実物の形（1本・1日 が 6行）。"""
    return [_a3("20260908", "v1", 0, "ZZ"), _a3("20260908", "v1", 232, "JP"),
            _a3("20260908", "v1", 1, "US"), _a3("20260908", "v1", 1, "HK"),
            _a3("20260908", "v1", 1, "BR"),
            _a3("20260908", "v1", 3, "JP", subscribed="subscribed")]


def test_同じ日の次元の行は足すこと():
    assert reporting.views_by_day(_split_day(), "v1") == [("20260908", 238)]


def test_positive_control_1行に畳むと2桁小さくなる():
    """**陽性対照**: (日・本) で 1行 に畳むと、`ZZ` の 0回 だけが残ること。

    ＝ 上の検査が通るのは足しているからで、数の書き換えではない。
    """
    rows = _split_day()
    one = {}
    for r in rows:
        one.setdefault((r["date"], r["video_id"]), r)
    assert [int(r["views"]) for r in one.values()] == [0]        # 先に来た行が残る
    assert sum(int(r["views"]) for r in rows) == 238             # 本当は 238


def test_同じ次元の行が二重に積まれても畳むこと():
    """store は追記しかしないので、同じ報告が 2度 積まれることが在る（`_dim_key`）。"""
    rows = _split_day() + _split_day()
    assert reporting.views_by_day(rows, "v1") == [("20260908", 238)]


def test_置き直された報告の行だけを足すこと():
    """古い報告と新しい報告が同じ日に在ったら、**新しいほうの行だけ**を足すこと（註の (4)）。"""
    old = [_a3("20260908", "v1", 100, "JP", created="2026-09-10T08:00:00Z")]
    new = [_a3("20260908", "v1", 232, "JP", created="2026-09-11T08:00:00Z"),
           _a3("20260908", "v1", 6, "US", created="2026-09-11T08:00:00Z")]
    assert reporting.views_by_day(old + new, "v1") == [("20260908", 238)]


def test_面のCTRはインプレッションで重みを付けること():
    """行ごとの %をそのまま平均しないこと（`reach_by_day`）。"""
    rows = [{"date": "20260909", "video_id": "v1", "country_code": "JP",
             "video_thumbnail_impressions": "100", "video_thumbnail_impressions_ctr": "0.10",
             "_created": "2026-09-10T09:00:00Z"},
            {"date": "20260909", "video_id": "v1", "country_code": "US",
             "video_thumbnail_impressions": "900", "video_thumbnail_impressions_ctr": "0",
             "_created": "2026-09-10T09:00:00Z"}]
    (day, imp, ctr), = reporting.reach_by_day(rows, "v1")
    assert (day, imp) == ("20260909", 1000)
    assert abs(ctr - 1.0) < 1e-9      # 重み付け 1.0%（そのまま平均すると 5.0%）


# --- 2026-09-11 18:4x（optimizer・Opus）: §7 (o-4)(3) の並べ直し -------------------


def test_報告の日の終わりは翌日の16時JST():
    """報告の期間は 16:00 JST 〜 翌 16:00 JST（`pt_day` の裏）。

    **10:00 JST 公開の本は、最初の境目が 齢 6.0時間 ちょうど**（`day_end_jst` の註）。
    """
    e = reporting.day_end_jst("20260908")
    assert (e.year, e.month, e.day, e.hour) == (2026, 9, 9, 16)
    # `pt_day` と往復すること（10:00 JST 公開 → その日の報告の日 → 終わりは 6時間 後）
    pub = dt.datetime(2026, 9, 9, 10, 0, tzinfo=dt.timezone(dt.timedelta(hours=9)))
    d = reporting.pt_day(pub)
    assert (reporting.day_end_jst(d) - pub).total_seconds() / 3600 == 6.0


def test_日の穴を数える():
    rows = [{"date": "20260901", "video_id": "a", "views": "1", "_created": "c"},
            {"date": "20260903", "video_id": "a", "views": "1", "_created": "c"},
            {"date": "20260906", "video_id": "a", "views": "1", "_created": "c"}]
    assert reporting.missing_days(rows) == ["20260902", "20260904", "20260905"]
    # **縁は穴ではない**（最初の日より前・最後の日より後は数えない）
    assert reporting.missing_days(rows[:1]) == []


def test_累計は次元で割れた行を足したあとで積む():
    """1日 1行 ではない（`latest_rows` の 17:5x の穴）—— 足してから累計にすること。"""
    rows = [
        {"date": "20260908", "video_id": "v", "views": "0", "country_code": "ZZ",
         "_created": "2026-09-11T08:00:00Z"},
        {"date": "20260908", "video_id": "v", "views": "232", "country_code": "JP",
         "_created": "2026-09-11T08:00:00Z"},
        {"date": "20260909", "video_id": "v", "views": "10", "country_code": "JP",
         "_created": "2026-09-11T08:00:00Z"},
    ]
    assert reporting.cum_views(rows, "v") == [("20260908", 232, 232), ("20260909", 10, 242)]
