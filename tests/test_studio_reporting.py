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
    assert reporting.seen_ids(p) == {"42"}
    assert reporting.unseen([rep], reporting.seen_ids(p)) == []
    # 壊れた行が混ざっても落ちない（追記しかしない store なので、途中で切れることが在る）
    with p.open("a", encoding="utf-8") as fh:
        fh.write("{壊れ\n")
    assert reporting.seen_ids(p) == {"42"}
    assert len(reporting.load_rows(p)) == 1


def test_storeが無ければ空で読める(tmp_path):
    assert reporting.seen_ids(tmp_path / "no.jsonl") == set()
    assert reporting.load_rows(tmp_path / "no.jsonl") == []


def test_取り込みの型は台帳の行にできる(tmp_path):
    """`cmd_reporting` が台帳へ書く欄が、そのまま JSON にできること（`ledger()` を通す族）。"""
    rep = _rep("42", "2026-09-09T07:00:00Z", "2026-09-10T08:50:00Z")
    fr = reporting.freshness([rep], dt.datetime(2026, 9, 10, 9, 0, tzinfo=UTC))
    row = {"reports": 1, "rows": 1, "last_day": "20260909",
           "lag_h": fr["lag_h"], "made_h": fr["made_h"]}
    assert json.loads(json.dumps(row))["lag_h"] == 26.0
