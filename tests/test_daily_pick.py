"""**`src/daily_pick.py` —— その日の1本の「形」を、数で決める口が生きているか。**

## なぜ要るか（2026-09-02 夜・最適化の回）

規則（1日1本）の下で、毎日の1本は目標に触れる唯一の出力です。その1本がどの形かを
数字で決める口が無く、48時間 中央値 1回 の形の本が 5回 磨かれて 1再生 でした。
この検査が守るのは3つ:

    1. 形ごとの 48時間 再生が、控えから正しく数えられること（同じ齢・その日の本数）
    2. 画面（`lines()`）に**両方の形の数と比**が出て、決めていない日はそう出ること
    3. `run_marker.py --write` の `[次の枠]` の直後に、この塊が必ず出ること

## 覆る条件

- オーナーが 1日1本 を外したら、「その日の1本」の主語が変わる（`for_day()`）。
  そのとき 2 の文面は変わってよいが、**両方の形の数が並ぶこと**は残すこと。
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from src import daily_pick, next_slot

UTC = timezone.utc


def _jsonl(path: Path, rows: list[dict]) -> Path:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                    encoding="utf-8")
    return path


def _fixture(tmp_path: Path, same_day: bool = True) -> tuple[Path, Path]:
    """ショート2本（200回・100回）と長尺1本（2回）。齢 50時間 の観測つき。"""
    t0 = datetime(2026, 8, 1, 0, 0, tzinfo=UTC)
    t1 = t0 if same_day else t0 + timedelta(days=1)
    up = [
        {"video_id": "S1", "topic": "s-nenkin-1", "title": "a #Shorts", "duration_s": 30,
         "at": t0.isoformat(), "uploaded_at": t0.isoformat()},
        {"video_id": "S2", "topic": "s-nenkin-2", "title": "b #Shorts", "duration_s": 31,
         "at": t1.isoformat(), "uploaded_at": t1.isoformat()},
        {"video_id": "L1", "topic": "nenkin-3", "title": "c", "duration_s": 300,
         "at": t0.isoformat(), "uploaded_at": t0.isoformat()},
    ]
    views = []
    for vid, base, v48 in (("S1", t0, 200), ("S2", t1, 100), ("L1", t0, 2)):
        views.append({"at": (base + timedelta(hours=1)).isoformat(), "id": vid,
                      "hours": 1.0, "views": 1, "likes": 0})
        views.append({"at": (base + timedelta(hours=50)).isoformat(), "id": vid,
                      "hours": 50.0, "views": v48, "likes": 0})
        views.append({"at": (base + timedelta(hours=200)).isoformat(), "id": vid,
                      "hours": 200.0, "views": v48 + 5, "likes": 0})
    return (_jsonl(tmp_path / "views.jsonl", views),
            _jsonl(tmp_path / "uploaded.jsonl", up))


def test_aged_views_counts_each_form_at_the_same_age(tmp_path: Path) -> None:
    views, up = _fixture(tmp_path)
    rows = daily_pick.aged_views(48, views_path=views, uploaded_path=up,
                                 measured={}, by_id={}, known={"nenkin"})
    by = {r["video_id"]: r for r in rows}
    assert by["S1"]["form"] == "ショート" and by["L1"]["form"] == "長尺"
    assert by["S1"]["views"] == 200 and by["S2"]["views"] == 100 and by["L1"]["views"] == 2
    assert by["S1"]["life"] == 205                       # 生涯は観測した最大
    assert by["S1"]["family"] == "nenkin"                # `s-` を外した先頭の語
    assert by["S1"]["day_count"] == 3                    # 同じ日に3本
    bf = daily_pick.by_form(rows)
    assert bf["ショート"] == {"n": 2, "median": 150, "p90": 200, "max": 200}
    assert bf["長尺"]["median"] == 2
    # 規則の密度（≤2本/日）の日は無い
    assert daily_pick.by_form(rows, max_per_day=2)["ショート"]["n"] == 0


def test_rule_band_uses_the_days_own_count(tmp_path: Path) -> None:
    views, up = _fixture(tmp_path, same_day=False)
    rows = daily_pick.aged_views(48, views_path=views, uploaded_path=up,
                                 measured={}, by_id={}, known=set())
    band = daily_pick.by_form(rows, max_per_day=2)
    assert band["ショート"]["n"] == 2 and band["長尺"]["n"] == 1


def test_by_family_ranks_by_median() -> None:
    rows = [
        {"form": "ショート", "family": "a", "views": 10},
        {"form": "ショート", "family": "a", "views": 30},
        {"form": "ショート", "family": "b", "views": 100},
        {"form": "長尺", "family": "b", "views": 999},
    ]
    fams = daily_pick.by_family(rows, min_n=2)
    assert [f["family"] for f in fams] == ["b", "a"]
    assert fams[1]["enough"] and not fams[0]["enough"]
    assert daily_pick.family_rank(fams, "a") == (2, fams[1])
    assert daily_pick.family_rank(fams, "zzz") == (None, None)


def _cmp(tmp_path: Path) -> dict:
    views, up = _fixture(tmp_path)
    rows = daily_pick.aged_views(48, views_path=views, uploaded_path=up,
                                 measured={}, by_id={}, known={"nenkin"})
    return daily_pick.compare(rows=rows)


def test_lines_show_both_forms_the_ratio_and_the_undecided_day(tmp_path: Path) -> None:
    picks = tmp_path / "picks.jsonl"
    nxt = {"video_id": "L9", "topic": "kaigo-9", "duration_s": 300, "title": "x"}
    text = "\n".join(daily_pick.lines(nxt, cmp=_cmp(tmp_path), picks_path=picks,
                                      topics={"kaigo-9", "s-kaigo-9"}, cands=[], untried=[]))
    assert "[きょうの1本]" in text
    assert "ショート" in text and "長尺" in text
    assert "1/75" in text                                # 150 ÷ 2
    assert "まだ決めていません" in text
    assert "`s-kaigo-9`" in text                         # 同じ題材のもう一方の形


def test_lines_show_the_decision_and_the_move_for_a_pool_video(tmp_path: Path) -> None:
    picks = tmp_path / "picks.jsonl"
    day = daily_pick.for_day()
    daily_pick.record("ショート", "s-shokibo-1", "ショート 150回 対 長尺 2回", day=day,
                      video_id="P1", path=picks)
    nxt = {"video_id": "L9", "topic": "kaigo-9", "duration_s": 300, "title": "x"}
    text = "\n".join(daily_pick.lines(nxt, cmp=_cmp(tmp_path), picks_path=picks,
                                      topics=set(), cands=[], untried=[]))
    assert "の1本: ショート `s-shokibo-1` ＝ `P1`" in text
    assert f"reschedule.py --move P1 {day:%Y-%m-%d}T" in text
    assert "まだ決めていません" not in text
    assert "`L9` は**消さない**" in text


def test_record_requires_a_number_and_current_reads_the_last(tmp_path: Path) -> None:
    picks = tmp_path / "picks.jsonl"
    d = date(2026, 9, 3)
    with pytest.raises(ValueError):
        daily_pick.record("ショート", "s-x", "なんとなく", day=d, path=picks)
    with pytest.raises(ValueError):
        daily_pick.record("縦", "s-x", "1回", day=d, path=picks)
    daily_pick.record("長尺", "x", "1回", day=d, path=picks)
    daily_pick.record("ショート", "s-x", "150回", day=d, path=picks)
    cur = daily_pick.current(d, picks)
    assert cur and cur["form"] == "ショート" and cur["topic"] == "s-x"
    assert daily_pick.current(date(2026, 9, 4), picks) is None


def test_other_form_topic_skips_what_is_already_made() -> None:
    assert daily_pick.other_form_topic("x", topics={"x", "s-x"}, posted=set()) == "s-x"
    assert daily_pick.other_form_topic("s-x", topics={"x", "s-x"}, posted=set()) == "x"
    assert daily_pick.other_form_topic("x", topics={"x", "s-x"}, posted={"s-x"}) is None
    assert daily_pick.other_form_topic("x", topics={"x"}, posted=set()) is None
    assert daily_pick.other_form_topic(None, topics={"x"}, posted=set()) is None


def test_pool_candidates_exclude_published_and_the_draft(tmp_path: Path) -> None:
    up = _jsonl(tmp_path / "uploaded.jsonl", [
        {"video_id": "P1", "topic": "s-a-1", "title": "p #Shorts", "duration_s": 30,
         "at": None, "uploaded_at": "2026-08-20T00:00:00+00:00", "retimed_at": "2026-09-02T00:00:00+00:00"},
        {"video_id": "P2", "topic": "s-b-1", "title": "q #Shorts", "duration_s": 30,
         "at": None, "uploaded_at": "2026-08-20T00:00:00+00:00"},
        {"video_id": "P3", "topic": "b-1", "title": "long", "duration_s": 300,
         "at": None, "uploaded_at": "2026-08-20T00:00:00+00:00"},
        {"video_id": "X1", "topic": "s-a-2", "title": "x #Shorts", "duration_s": 30,
         "at": None, "uploaded_at": "2026-08-20T00:00:00+00:00"},
    ])
    fams = [{"family": "a", "n": 3, "median": 500, "p90": 600, "max": 700, "enough": True},
            {"family": "b", "n": 2, "median": 50, "p90": 60, "max": 70, "enough": True}]
    rows = [{"video_id": "X1", "form": "ショート", "family": "a", "views": 5}]
    got = daily_pick.pool_candidates(fams=fams, uploaded_path=up, rows=rows, exclude="P2",
                                     by_id={}, known={"a", "b"},
                                     views_path=tmp_path / "no_views.jsonl")
    assert [g["video_id"] for g in got] == ["P1"]          # 公開ずみ X1・下書き P2・長尺 P3 は外れる
    assert got[0]["fam_median"] == 500 and not got[0]["draft"]


def test_next_slot_prints_the_block_right_after_the_next_video(monkeypatch) -> None:
    """`run_marker.py --write` が読む `next_slot.lines()` に、この塊が必ず出ること。"""
    fake = {"video_id": "ZZ", "topic": "kaigo-9", "title": "t", "duration_s": 300,
            "uploaded_at": datetime.now(UTC).isoformat(),
            "_at": datetime.now(UTC) + timedelta(hours=5)}
    monkeypatch.setattr(next_slot, "calendar_lines", lambda **kw: [])
    monkeypatch.setattr(next_slot, "draft_lines", lambda **kw: [])
    monkeypatch.setattr(next_slot, "next_video", lambda **kw: dict(fake))
    monkeypatch.setattr(next_slot, "stale_commits", lambda *a, **kw: [])
    monkeypatch.setattr(next_slot, "pending_thumbnail", lambda *a, **kw: False)
    out = next_slot.lines()
    idx_next = next(i for i, ln in enumerate(out) if ln.startswith("[次の枠]"))
    idx_pick = next(i for i, ln in enumerate(out) if ln.startswith("[きょうの1本]"))
    assert idx_pick == idx_next + 1
    assert any("ショート" in ln and "長尺" in ln for ln in out[idx_pick:idx_pick + 3])
