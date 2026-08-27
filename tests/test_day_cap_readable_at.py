"""**「読める時刻」に、本当に読めるか**（2026-08-27）。

`src/day_cap.booked_split_day()` の `answer` / `answer_at` は **齢だけ**で出ています
（その日の最後の本が `MIN_AGE_H` になる時刻）。ところが `data/views.jsonl` を積むのは
`scripts/snapshot.py` ＝ **Data API の `videos.list`** で、**日枠が尽きている窓では
403 しか返りません。**

実測 2026-08-27 20:5x JST —— この窓の 403 は 88回 観測ずみ・枠が戻るのは 08/28 16:00 JST。
それでも出力は「読めるのは **2026-08-27 22:00** 以降」と言い、`docs/JOURNAL.md` の
申し送りは **3周 連続**で「22:00 を過ぎていたら `snapshot.py` を撃つこと」を運んでいました。
**22:00 に撃っても 403 です。**

ここが守るのは1つ: **齢と日枠の、遅いほうを採る。**
"""
from __future__ import annotations

import datetime as dt
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import day_cap, upload_cap  # noqa: E402

JST = day_cap.JST


@dataclass
class _DQ:
    open: bool
    resets_at: dt.datetime


def _fake_day_quota(monkeypatch, *, open_: bool, resets_at: dt.datetime):
    monkeypatch.setattr(upload_cap, "day_quota",
                        lambda *a, **k: _DQ(open_, resets_at))


def _booked(answer_ts: str) -> dict:
    at = dt.datetime.fromisoformat(answer_ts)
    return {"day": at.date().isoformat(), "answer": at.date().isoformat(),
            "answer_at": at.strftime("%H:%M"), "answer_ts": answer_ts,
            "before": 8, "total": 19, "count": 10, "window": 18,
            "gap": 8, "ties": 0, "kept": 19, "running": True}


def test_日枠が閉じていたら遅いほうを採る(monkeypatch):
    """齢は 22:00 に足りるが、日枠が戻るのは翌 16:00 —— 採るのは翌 16:00。"""
    _fake_day_quota(monkeypatch, open_=False,
                    resets_at=dt.datetime(2026, 8, 28, 7, 0, tzinfo=dt.timezone.utc))
    r = day_cap.readable_at(_booked("2026-08-27T22:00:00+09:00"),
                            now=dt.datetime(2026, 8, 27, 20, 50, tzinfo=JST))
    assert r["binding"] == "quota"
    assert r["at"] == dt.datetime(2026, 8, 28, 16, 0, tzinfo=JST)


def test_日枠が開いていたら齢のほうを採る(monkeypatch):
    _fake_day_quota(monkeypatch, open_=True,
                    resets_at=dt.datetime(2026, 8, 28, 7, 0, tzinfo=dt.timezone.utc))
    r = day_cap.readable_at(_booked("2026-08-27T22:00:00+09:00"),
                            now=dt.datetime(2026, 8, 27, 20, 50, tzinfo=JST))
    assert r["binding"] == "age"
    assert r["at"] == dt.datetime(2026, 8, 27, 22, 0, tzinfo=JST)


def test_日枠が齢より先に戻るなら齢が縛る(monkeypatch):
    """閉じてはいるが、齢が来る前に戻る窓 —— 縛っているのは齢のほう。"""
    _fake_day_quota(monkeypatch, open_=False,
                    resets_at=dt.datetime(2026, 8, 27, 7, 0, tzinfo=dt.timezone.utc))
    r = day_cap.readable_at(_booked("2026-08-27T22:00:00+09:00"),
                            now=dt.datetime(2026, 8, 27, 12, 0, tzinfo=JST))
    assert r["binding"] == "age"
    assert r["at"] == dt.datetime(2026, 8, 27, 22, 0, tzinfo=JST)


def test_日枠が読めない回は縛らない側へ倒す(monkeypatch):
    """**読めないことを『閉じている』と読まないこと**（`day_quota()` と同じ考え方）。"""
    def boom(*a, **k):
        raise RuntimeError("帳面が読めません")
    monkeypatch.setattr(upload_cap, "day_quota", boom)
    r = day_cap.readable_at(_booked("2026-08-27T22:00:00+09:00"),
                            now=dt.datetime(2026, 8, 27, 20, 50, tzinfo=JST))
    assert r["binding"] == "age"


def test_answer_ts_が無い古い形でも落ちない():
    r = day_cap.readable_at({"answer": "2026-08-27", "answer_at": "22:00"})
    assert r["at"] is None


def test_booked_split_day_が_answer_ts_を返す(tmp_path):
    """印字の側が齢の時刻を**組み立て直さない**ため（写しを2つ作らない）。"""
    import json
    up = tmp_path / "uploaded.jsonl"
    # JST 05:00〜09:00（UTC では前日 20:00〜）。`tests/test_day_cap.py` と同じ形。
    times = ["2026-08-26T20:00:00Z", "2026-08-26T21:00:00Z", "2026-08-26T22:00:00Z",
             "2026-08-26T23:00:00Z", "2026-08-27T00:00:00Z"]
    up.write_text("\n".join(json.dumps({"video_id": f"v{i}", "topic": f"s-{i}", "at": t})
                            for i, t in enumerate(times)), encoding="utf-8")
    b = day_cap.booked_split_day("08:59", today=dt.date(2026, 8, 25),
                                 uploaded=up, c=2, t_min=13 * 60 + 30)
    assert b is not None
    assert "answer_ts" in b
    got = dt.datetime.fromisoformat(b["answer_ts"])
    assert got.date().isoformat() == b["answer"]
    assert got.strftime("%H:%M") == b["answer_at"]


def test_印字の行は日枠が縛るときだけ出る(monkeypatch):
    """**開いている回にまで警告を出さないこと**（読む側が慣れて素通りします）。"""
    b = _booked("2026-08-27T22:00:00+09:00")
    _fake_day_quota(monkeypatch, open_=True,
                    resets_at=dt.datetime(2026, 8, 28, 7, 0, tzinfo=dt.timezone.utc))
    assert day_cap._readable_lines(b) == []
    _fake_day_quota(monkeypatch, open_=False,
                    resets_at=dt.datetime(2026, 8, 28, 7, 0, tzinfo=dt.timezone.utc))
    got = day_cap._readable_lines(b)
    assert len(got) == 2
    assert "その時刻には読めません" in got[0]
    assert "2026-08-28 16:00 JST" in got[1]
