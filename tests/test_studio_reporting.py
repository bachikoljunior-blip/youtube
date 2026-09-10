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
