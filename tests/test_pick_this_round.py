"""**決めた回に「前の回の散文だ、決め直せ」と言わないこと** —— 2026-09-04 18:4x に踏んだ検査。

`standing_form_conflict()` は、立っている決めの理由をいつでも
「**前の回の散文です —— 根拠にしないこと**」と呼び、`lines()` の見出しも同じ字でした。
**決めた回にも同じ字で出ます。** 実測: 18:20 に数で決め直した回が、19分後に同じ画面を読んで
**もう一度 同じ議論をやり直しかけました**。

「前の回のものか」は数えられます —— `data/runs.jsonl` の最後の `start` より後に
書かれた決めは、この回のものです。
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from src import daily_pick as dp

JST = timezone(timedelta(hours=9))


def _runs(tmp_path, at: str):
    p = tmp_path / "runs.jsonl"
    p.write_text(json.dumps({"at": at, "kind": "start", "session": "s"},
                            ensure_ascii=False) + "\n", encoding="utf-8")
    return p


def test_回が立ったあとの決めは_この回のもの(tmp_path):
    runs = _runs(tmp_path, "2026-09-04T18:16:49+09:00")
    row = {"at": "2026-09-04T18:20:18+09:00"}
    assert dp.decided_this_round(row, runs_path=runs) is True


def test_回が立つ前の決めは_この回のものではない(tmp_path):
    runs = _runs(tmp_path, "2026-09-04T18:16:49+09:00")
    row = {"at": "2026-09-04T16:55:51+09:00"}
    assert dp.decided_this_round(row, runs_path=runs) is False


def test_印が読めなければ_この回のものと言わない(tmp_path):
    empty = tmp_path / "none.jsonl"
    assert dp.decided_this_round({"at": "2026-09-04T18:20:18+09:00"}, runs_path=empty) is False
    runs = _runs(tmp_path, "2026-09-04T18:16:49+09:00")
    assert dp.decided_this_round({}, runs_path=runs) is False
    assert dp.decided_this_round({"at": "こわれた日付"}, runs_path=runs) is False


def test_round_started_at_は最後のstartを返す(tmp_path):
    p = tmp_path / "runs.jsonl"
    p.write_text("\n".join(json.dumps(x) for x in [
        {"at": "2026-09-04T17:00:00+09:00", "kind": "start"},
        {"at": "2026-09-04T17:30:00+09:00", "kind": "ship"},
        {"at": "2026-09-04T18:16:49+09:00", "kind": "start"},
    ]) + "\n", encoding="utf-8")
    got = dp.round_started_at(p)
    assert got == datetime(2026, 9, 4, 18, 16, 49, tzinfo=JST)


def test_食い違いの行は_決めた回には_やり直せと言わない(tmp_path, monkeypatch):
    picks = tmp_path / "picks.jsonl"
    runs = _runs(tmp_path, "2026-09-04T18:16:49+09:00")
    dp.record("長尺", "t", "数 314 で決めた", day=date(2026, 9, 5), path=picks, video_id="A",
              now=datetime(2026, 9, 4, 18, 20, tzinfo=JST))
    cur = list(dp._jsonl(picks))[-1]
    monkeypatch.setattr(dp, "RUNS", runs)
    out = dp.standing_form_conflict(
        cur, picks_path=picks,
        form_call=lambda **k: ("ショート", "AND の遠い脚: ショート ×106 対 長尺 ×314"),
        treated_call=lambda *a, **k: (0, 36))
    body = "\n".join(out)
    assert "この回が書いたものです" in body
    assert "決め直すなら" not in body            # ← やり直させない
    assert "python -m src.daily_pick --pick" not in body


def test_前の回の決めなら_やり直す口を出す(tmp_path, monkeypatch):
    picks = tmp_path / "picks.jsonl"
    runs = _runs(tmp_path, "2026-09-04T18:16:49+09:00")
    dp.record("長尺", "t", "数 314 で決めた", day=date(2026, 9, 5), path=picks, video_id="A",
              now=datetime(2026, 9, 4, 16, 55, tzinfo=JST))
    cur = list(dp._jsonl(picks))[-1]
    monkeypatch.setattr(dp, "RUNS", runs)
    out = dp.standing_form_conflict(
        cur, picks_path=picks,
        form_call=lambda **k: ("ショート", "AND の遠い脚"),
        treated_call=lambda *a, **k: (0, 36))
    body = "\n".join(out)
    assert "前の回の散文" in body and "決め直すなら" in body
