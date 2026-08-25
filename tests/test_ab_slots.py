"""`scripts/ab_slots.py` の検査。

**守るのは1つ**: 「16本そろった」を**公開日だけ**で数えている所と、
**再生が付く枠（`day_cap`）**のあいだの食い違いを、黙って通さないこと。
実測（2026-08-26）で title_form の 問い は 8本/16、hook_form の 条件 は 7本/16 でした。
"""
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import ab_slots                                        # noqa: E402
from src.ab_split import EXPERIMENTS, MIN_PER_GROUP                 # noqa: E402

JST = timezone(timedelta(hours=9))


def _row(topic, vid, day, hour):
    return {"topic": topic, "video_id": vid, "publish": day,
            "at": datetime(day.year, day.month, day.day, hour, tzinfo=JST)}


def test_その日の何番目かを時刻で数える():
    d = date(2026, 9, 1)
    rows = [_row("b", "B", d, 12), _row("a", "A", d, 9), _row("c", "C", d, 15)]
    assert ab_slots.slot_rank(rows) == {"A": 1, "B": 2, "C": 3}


def test_日をまたぐと順位は1に戻る():
    rows = [_row("a", "A", date(2026, 9, 1), 20), _row("b", "B", date(2026, 9, 2), 9)]
    r = ab_slots.slot_rank(rows)
    assert r["A"] == 1 and r["B"] == 1, "**日ごとに数えること**（上限は1日あたり）"


def test_判定に入るのは公開の早い順に16本まで():
    exp = next(iter(EXPERIMENTS.values()))
    rows, builds = [], {}
    day = date(2026, 9, 1)
    n = 0
    for topic in ("t%d" % i for i in range(400)):
        if exp.split(topic) != exp.treated:
            continue
        rows.append(_row(topic, "v%d" % n, day + timedelta(days=n), 9))
        builds[topic] = exp.landed + timedelta(days=1)
        n += 1
        if n > MIN_PER_GROUP + 5:
            break
    got = ab_slots.judging_set(exp, rows, builds)[exp.treated]
    assert len(got) == MIN_PER_GROUP, "**床を超えた本は判定に入りません**"


def test_指示より前に作った本は群に入れない():
    """**母集団の直しが消えたら止める**（`ab_split` が5回踏んだ形）。"""
    exp = next(iter(EXPERIMENTS.values()))
    topic = next(t for t in ("t%d" % i for i in range(400))
                 if exp.split(t) == exp.treated)
    rows = [_row(topic, "V", date(2026, 9, 1), 9)]
    old = {topic: exp.landed - timedelta(hours=1)}
    new = {topic: exp.landed + timedelta(hours=1)}
    assert ab_slots.judging_set(exp, rows, old)[exp.treated] == []
    assert len(ab_slots.judging_set(exp, rows, new)[exp.treated]) == 1


def test_実物で落ちない():
    """**状態を見る道具が、状態のせいで死んではいけない。**"""
    out = ab_slots.report()
    assert out and any("再生が付く枠" in line for line in out)
