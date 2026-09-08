"""**周から周の間隔を、1周 2行 の台帳から正しく数えるか**
（2026-09-09 00:2x JST・optimizer・Opus）。

§7 21:4x の覆る条件 (1) は「**周から周の中央値が `floor` の 1.25倍 を越えていたら**、
上限は丸めではない」と書いている。ところがその数の出どころ `data/rounds.jsonl` は
**1周につき役の数だけ行**を書く（`hourly` と `optimizer` で 2行・同じ時刻）。
素朴に「行から行」を数えると 0分 が交互に挟まり、中央値が半分になる:

    素朴に行から行   39.6分   ← floor(76分) の 0.52倍 ＝ **条件は永久に引かれない**
    `round` で畳む   80.4分   ← 本当の周から周（floor の 1.06倍）

＝ 鳴らない見張り。ここで止めるのはその形。
"""
import json

import pytest

import scripts.next_round as nr


def _write(tmp_path, rows):
    p = tmp_path / "rounds.jsonl"
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return p


@pytest.fixture()
def rounds(tmp_path, monkeypatch):
    def _set(rows):
        monkeypatch.setattr(nr, "ROUNDS", _write(tmp_path, rows))
    return _set


def _round(at, rid=None):
    return [{"at": at, "role": r, "round": rid or at} for r in ("hourly", "optimizer")]


def test_同じ周の2行は畳まれる(rounds):
    rounds(_round("2026-09-08T12:40:00+00:00")
           + _round("2026-09-08T14:00:00+00:00")
           + _round("2026-09-08T15:20:00+00:00"))
    assert nr.round_gaps() == [80.0, 80.0]
    assert nr.gap_median() == 80.0


def test_素朴に行から行を数えると半分になる_これが踏んだ形(rounds):
    """**陽性対照**: 畳まないとどうなるかを、同じ台帳で見せる。"""
    got = (_round("2026-09-08T12:40:00+00:00")
           + _round("2026-09-08T14:00:00+00:00")
           + _round("2026-09-08T15:20:00+00:00"))
    rounds(got)
    naive = []
    ts = sorted(nr._at(r) for r in got)
    for a, b in zip(ts, ts[1:]):
        naive.append((b - a).total_seconds() / 60.0)
    assert naive == [0.0, 80.0, 0.0, 80.0, 0.0]     # 0 が交互に挟まる
    from statistics import median
    assert median(naive) == 0.0                     # 素朴な中央値は 0分
    assert nr.gap_median() == 80.0                  # 畳めば 80分


def test_roundが無い古い行は時刻で畳む(rounds):
    rounds([{"at": "2026-09-08T12:40:00+00:00", "role": "hourly"},
            {"at": "2026-09-08T12:40:00+00:00", "role": "optimizer"},
            {"at": "2026-09-08T14:00:00+00:00", "role": "hourly"}])
    assert nr.round_gaps() == [80.0]


def test_役が1つしか立たなかった周も1周として数える(rounds):
    """穴埋めの回（片方だけ立てた周）を、間隔から落とさない。"""
    rounds(_round("2026-09-08T12:40:00+00:00")
           + [{"at": "2026-09-08T14:00:00+00:00", "role": "hourly",
               "round": "2026-09-08T14:00:00+00:00"}])
    assert nr.round_gaps() == [80.0]


def test_周が1つなら間隔は空(rounds):
    rounds(_round("2026-09-08T12:40:00+00:00"))
    assert nr.round_gaps() == []
    assert nr.gap_median() is None


def test_decideの台帳に中央値と_floorとの比が載る(rounds, monkeypatch):
    """§7 の覆る条件が、手で数えずに読めること。"""
    rounds(_round("2026-09-08T12:40:00+00:00")
           + _round("2026-09-08T14:00:00+00:00")
           + _round("2026-09-08T15:20:00+00:00"))
    monkeypatch.setattr(nr, "floor_minutes", lambda: (80.0, "検査"))
    got = nr.decide(live=0)
    assert got["gap_median_min"] == 80.0, got
    assert got["gap_over_floor"] == 1.0, got
