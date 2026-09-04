"""`--day` を省いた決めが、別の日の決めを黙って上書きするのを止める門。

2026-09-05 00:38 に実際に踏んだ形をそのまま置いてあります ——
「09/05 を据え置くつもりで `--day` を省いたら、`for_day()` が 09-06 を返し、
27分前に別の回が決めた 09/06 の1本を潰した」。
"""
from __future__ import annotations

import json
from datetime import date, timedelta, timezone

import pytest

from src import daily_pick as dp

JST = timezone(timedelta(hours=9))


def _write(path, rows):
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                    encoding="utf-8")


def _row(day, vid, at, form="長尺", topic="t"):
    return {"at": at, "for_day": day, "form": form, "topic": topic,
            "video_id": vid, "why": "1", "expected_48h": 1.0, "kind": "decide"}


def test_standing_days_reads_the_last_row_per_day(tmp_path):
    p = tmp_path / "picks.jsonl"
    _write(p, [
        _row("2026-09-05", "AAA", "2026-09-04T22:00:00+09:00"),
        _row("2026-09-06", "BBB", "2026-09-05T00:27:00+09:00"),
        # 09/05 は途中で差し替えられている → 立っているのは新しい方だけ
        _row("2026-09-05", "CCC", "2026-09-04T23:00:00+09:00"),
    ])
    assert dp.standing_days("CCC", path=p) == ["2026-09-05"]
    assert dp.standing_days("BBB", path=p) == ["2026-09-06"]
    assert dp.standing_days("AAA", path=p) == []      # 差し替えられた側は立っていない
    assert dp.standing_days("", path=p) == []


def test_day_guard_stops_the_silent_overwrite(tmp_path, monkeypatch):
    p = tmp_path / "picks.jsonl"
    _write(p, [
        _row("2026-09-05", "GFvAcxvDmYM", "2026-09-04T23:24:00+09:00"),
        _row("2026-09-06", "DtpnSVFDtAE", "2026-09-05T00:27:00+09:00", form="ショート"),
    ])
    # きょうの枠が埋まっているので for_day() は「あす」＝ 09-06 を返す
    monkeypatch.setattr(dp, "for_day", lambda now=None: date(2026, 9, 6))
    why = dp.day_guard("GFvAcxvDmYM", None, path=p)
    assert why, "別の日に立っている本を --day 無しで決めたら止めること"
    assert "2026-09-05" in why and "2026-09-06" in why
    assert "--day" in why


def test_day_guard_passes_when_day_is_written(tmp_path, monkeypatch):
    p = tmp_path / "picks.jsonl"
    _write(p, [_row("2026-09-05", "GFvAcxvDmYM", "2026-09-04T23:24:00+09:00")])
    monkeypatch.setattr(dp, "for_day", lambda now=None: date(2026, 9, 6))
    # `--day` を書いた回は素通し（本当に移したい回は、そう書ける）
    assert dp.day_guard("GFvAcxvDmYM", date(2026, 9, 6), path=p) == ""
    assert dp.day_guard("GFvAcxvDmYM", date(2026, 9, 5), path=p) == ""


def test_day_guard_passes_for_a_new_video_and_for_the_same_day(tmp_path, monkeypatch):
    p = tmp_path / "picks.jsonl"
    _write(p, [_row("2026-09-06", "DtpnSVFDtAE", "2026-09-05T00:27:00+09:00", form="ショート")])
    monkeypatch.setattr(dp, "for_day", lambda now=None: date(2026, 9, 6))
    # まだ どの日にも立っていない本は通す
    assert dp.day_guard("ZZZ", None, path=p) == ""
    # 書き先と同じ日に立っている本（＝据え置き）は通す
    assert dp.day_guard("DtpnSVFDtAE", None, path=p) == ""
    # `--video` を付けない決めも通す
    assert dp.day_guard(None, None, path=p) == ""


def test_record_raises_on_the_overwrite(tmp_path, monkeypatch):
    p = tmp_path / "picks.jsonl"
    _write(p, [
        _row("2026-09-05", "GFvAcxvDmYM", "2026-09-04T23:24:00+09:00"),
        _row("2026-09-06", "DtpnSVFDtAE", "2026-09-05T00:27:00+09:00", form="ショート"),
    ])
    monkeypatch.setattr(dp, "for_day", lambda now=None: date(2026, 9, 6))
    monkeypatch.setattr(dp, "probe_hold", lambda *a, **k: "")
    with pytest.raises(ValueError) as e:
        dp.record("長尺", "t", "数 1", path=p, video_id="GFvAcxvDmYM", expected=8.0)
    assert "--day" in str(e.value)
    # 行は 1本も増えていない
    assert len([l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]) == 2


def test_record_still_writes_when_day_is_explicit(tmp_path, monkeypatch):
    p = tmp_path / "picks.jsonl"
    _write(p, [_row("2026-09-05", "GFvAcxvDmYM", "2026-09-04T23:24:00+09:00")])
    monkeypatch.setattr(dp, "for_day", lambda now=None: date(2026, 9, 6))
    monkeypatch.setattr(dp, "probe_hold", lambda *a, **k: "")
    row = dp.record("長尺", "t", "数 1", day=date(2026, 9, 5), path=p,
                    video_id="GFvAcxvDmYM", expected=8.0)
    assert row["for_day"] == "2026-09-05"
