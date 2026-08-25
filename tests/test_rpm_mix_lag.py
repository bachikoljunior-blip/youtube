"""`src/rpm_mix.py` が **どこまでの日を含んでいるか**を言えること。

**なぜこの検査が要るか**（2026-08-21）。`fetch_mix` は窓の終わりに `date.today()`
を渡し、積んだ点にもそう書いていました。**しかし Analytics の日次はそこまで
来ていません** —— `data/analytics_lag.jsonl` の実測では、08/21 に3回測って
**最終日は 3回とも 2026-08-18**。つまり `window.end: 2026-08-21` と書かれた点の
中身は 08/18 までで、**08/19〜08/21 に公開した 65本は1本も入っていません。**

そのせいで「長尺を出して測り直す」という申し送りが **6回続けて持ち越され**、
撃った回は毎回**同じ 11再生**を読んでいました。`data/rpm_mix.jsonl` の
最後の2行が**1バイト違わず同じ**だったのが、その跡です。

**覆る条件**: Analytics が当日ぶんを返すようになったら、`--if-ready` は
毎回 True を返すので、この門は費用だけになります。**そのときは外すこと。**
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from src import rpm_mix

JST = timezone(timedelta(hours=9))


def _lag_file(tmp_path, days):
    p = tmp_path / "analytics_lag.jsonl"
    p.write_text("".join(json.dumps({"at": "x", "last_day": d}) + "\n" for d in days),
                 encoding="utf-8")
    return p


def _uploaded(tmp_path, rows):
    p = tmp_path / "uploaded.jsonl"
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                 encoding="utf-8")
    return p


def test_最終日は帳面のいちばん新しい日(tmp_path):
    p = _lag_file(tmp_path, ["2026-08-16", "2026-08-18", "2026-08-17"])
    assert rpm_mix.data_last_day(p) == "2026-08-18"


def test_帳面が無ければ今日で埋めずNoneを返す(tmp_path):
    # **今日で埋めるのが、この欠陥そのものです。**
    assert rpm_mix.data_last_day(tmp_path / "no-such-file.jsonl") is None


def test_壊れた行があっても読める(tmp_path):
    p = tmp_path / "lag.jsonl"
    p.write_text('{"last_day": "2026-08-18"}\nnot json\n\n{"at":"y"}\n', encoding="utf-8")
    assert rpm_mix.data_last_day(p) == "2026-08-18"


def test_最終日より後の公開を数え_いつ読めるかを出す(tmp_path):
    now = datetime(2026, 8, 21, 23, 0, tzinfo=JST)          # 遅れ 3日
    up = _uploaded(tmp_path, [
        {"video_id": "old", "at": "2026-08-17T00:00:00Z"},   # 入っている
        {"video_id": "a", "at": "2026-08-19T00:00:00Z"},     # 入っていない
        {"video_id": "L", "at": "2026-08-21T03:45:00Z"},     # 入っていない・長尺
        {"video_id": "future", "at": "2026-09-01T00:00:00Z"},  # まだ公開していない
    ])
    got = rpm_mix.pending_after("2026-08-18", now=now, uploaded_path=up, long_ids={"L"})
    assert got["total"] == 2
    assert got["long"] == 1
    assert got["lag_days"] == 3
    # いちばん新しい公開 08/21 ＋ 遅れ 3日 → 08/24
    assert got["readable_on"] == "2026-08-24"


def test_未公開だけなら入っていない本は0(tmp_path):
    now = datetime(2026, 8, 21, 23, 0, tzinfo=JST)
    up = _uploaded(tmp_path, [{"video_id": "f", "at": "2026-09-01T00:00:00Z"}])
    got = rpm_mix.pending_after("2026-08-18", now=now, uploaded_path=up)
    assert got["total"] == 0 and got["readable_on"] is None
    assert got["lag_days"] == 3          # 遅れは、本が無くても分かる


def test_最終日が分からなければ数えない(tmp_path):
    assert rpm_mix.pending_after(None)["total"] == 0


def test_atが無い行はuploaded_atで代える(tmp_path):
    now = datetime(2026, 8, 21, 23, 0, tzinfo=JST)
    up = _uploaded(tmp_path, [{"video_id": "u", "uploaded_at": "2026-08-20T00:00:00+00:00"}])
    assert rpm_mix.pending_after("2026-08-18", now=now, uploaded_path=up)["total"] == 1


# ---- 画面に出ること -------------------------------------------------------
def test_画面に中身は何日までといつ読めるかが出る():
    rec = {"window": {"start": "2026-05-23", "end": "2026-08-21", "days": 90,
                      "data_end": "2026-08-18"},
           "pending": {"total": 65, "long": 0, "first": "2026-08-19T09:00+09:00",
                       "last": "2026-08-21T21:00+09:00", "readable_on": "2026-08-24",
                       "lag_days": 3},
           "minutes_by_form": {"ショート": 3793.0}, "views_by_form": {"ショート": 30588.0},
           "jp_share": 0.999, "rpm_now": 20.1}
    out = rpm_mix.render(rec)
    assert "2026-08-18" in out and "3日遅れ" in out
    assert "65本" in out
    assert "2026-08-24" in out          # **いつ読めるか。「まだです」で終わらせない**


def test_最終日が無い点は分かりませんと言う():
    # **黙ると、読む側は窓の終わり＝今日を信じます。**
    out = rpm_mix.render({"window": {"start": "a", "end": "2026-08-21", "days": 90},
                          "minutes_by_form": {}, "views_by_form": {}, "jp_share": 1.0})
    assert "分かりません" in out


# ---- 撃つ前の門 -----------------------------------------------------------
def test_中身が進んでいなければ撃たない():
    prev = {"window": {"data_end": "2026-08-18"}}
    ready, why = rpm_mix.is_ready(prev, "2026-08-18")
    assert ready is False
    assert "測りません" in why
    assert "2026-08-19" in why          # 次に入る日を必ず言う


def test_中身が進んでいれば撃つ():
    prev = {"window": {"data_end": "2026-08-18"}}
    ready, why = rpm_mix.is_ready(prev, "2026-08-19")
    assert ready is True and "進みました" in why


def test_前の点に欄が無ければ撃つ():
    # 欄を足す前に積んだ点。**一度は測り直させること。**
    ready, _ = rpm_mix.is_ready({"window": {"end": "2026-08-21"}}, "2026-08-18")
    assert ready is True


def test_点が1つも無ければ撃つ():
    assert rpm_mix.is_ready(None, "2026-08-18")[0] is True


def test_最終日が分からなければ撃つ():
    # 帳面が空なのを理由に止めない（**測れない回を作らない**）。
    assert rpm_mix.is_ready({"window": {"data_end": "2026-08-18"}}, None)[0] is True


def test_門は同じ行を積むのを止める(tmp_path, monkeypatch):
    """**実測の再現。**08/21 の `data/rpm_mix.jsonl` は最後の2行が同じでした。"""
    prev = {"window": {"data_end": "2026-08-18"}}
    monkeypatch.setattr(rpm_mix, "UPLOADED", tmp_path / "none.jsonl")
    assert rpm_mix.is_ready(prev, "2026-08-18")[0] is False


@pytest.mark.parametrize("bad", ["", "  ", "not-a-time"])
def test_公開時刻が読めない行は落とすが例外にしない(tmp_path, bad):
    now = datetime(2026, 8, 21, 23, 0, tzinfo=JST)
    up = _uploaded(tmp_path, [{"video_id": "x", "at": bad}])
    assert rpm_mix.pending_after("2026-08-18", now=now, uploaded_path=up)["total"] == 0
