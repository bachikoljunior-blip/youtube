"""**すでに立っている決めの再掲を止める門**（`src/daily_pick.restated_pick_block`）。

なぜ要るか: 2026-09-05 の最適化の回が実物で数えた —— `data/daily_pick.jsonl` の
09/05 の枠だけで決めが 24回、うち 14回 は直前と 形・題材・動画ID が完全に同じ。
最後の 8回 は全部 同じ動画で、変わったのは `why` の長さだけ。
中身の門（`untreated_slot_block` / `probe_hold` / `slot_cost`）は再掲を止めません。
"""
import json
from datetime import date

import pytest

from src import daily_pick as d


def _write(tmp_path, rows):
    p = tmp_path / "daily_pick.jsonl"
    with p.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return p


def _row(at, day, form, topic, vid, exp, kind="decide"):
    return {"at": at, "for_day": day, "form": form, "topic": topic,
            "video_id": vid, "why": "数 1", "expected_48h": exp, "kind": kind}


DAY = date(2026, 9, 5)
STANDING = _row("2026-09-05T01:00:00+09:00", "2026-09-05", "ショート", "t1", "V1", 1049.0)


def test_same_pick_is_blocked(tmp_path):
    """同じ決めの再掲は止まる。"""
    p = _write(tmp_path, [STANDING])
    msg = d.restated_pick_block("ショート", "t1", "V1", DAY, expected=1049.0, path=p)
    assert msg
    assert "もう立っています" in msg


@pytest.mark.parametrize("form,topic,vid", [
    ("長尺", "t1", "V1"),      # 形が変わった
    ("ショート", "t2", "V1"),   # 題材が変わった
    ("ショート", "t1", "V2"),   # 動画IDが変わった
])
def test_real_change_passes(tmp_path, form, topic, vid):
    """本物の決め直し（決定そのものが変わる）は通る。"""
    p = _write(tmp_path, [STANDING])
    assert d.restated_pick_block(form, topic, vid, DAY, expected=1049.0, path=p) == ""


def test_expected_correction_passes(tmp_path):
    """実測 09-05T01:17 の 8.0 → 1.0 は、次の回が実物と並べる数が変わっている。"""
    p = _write(tmp_path, [STANDING])
    assert d.restated_pick_block("ショート", "t1", "V1", DAY, expected=1.0, path=p) == ""


def test_undecided_day_passes(tmp_path):
    """決めが立っていない日は通る。"""
    p = _write(tmp_path, [STANDING])
    assert d.restated_pick_block("ショート", "t1", "V1", date(2026, 9, 9),
                                 expected=1049.0, path=p) == ""


def test_carry_row_is_not_a_decision(tmp_path):
    """`kind="carry"` は焼き直しが ID を写しただけ。回は触っていない。"""
    p = _write(tmp_path, [_row("2026-09-05T01:00:00+09:00", "2026-09-05",
                               "ショート", "t1", "V1", 1049.0, kind="carry")])
    assert d.restated_pick_block("ショート", "t1", "V1", DAY, expected=1049.0, path=p) == ""


def test_message_counts_the_repeats(tmp_path):
    """何回 続いているかを数で言う。"""
    rows = [_row(f"2026-09-05T0{i}:00:00+09:00", "2026-09-05",
                 "ショート", "t1", "V1", 1049.0) for i in range(1, 4)]
    p = _write(tmp_path, rows)
    msg = d.restated_pick_block("ショート", "t1", "V1", DAY, expected=1049.0, path=p)
    assert "3回" in msg


def test_record_refuses_and_anyway_cannot_pass(tmp_path):
    """`--anyway` は `probe_hold` の口。再掲が買うものは 0 なので越える数が存在しない。"""
    p = _write(tmp_path, [STANDING])
    with pytest.raises(ValueError, match="もう立っています"):
        d.record("ショート", "t1", "数 1 の理由", day=DAY, path=p, video_id="V1",
                 expected=1049.0, anyway="機会費用の門を越える 1回")


def test_rebake_carry_path_stays_open(tmp_path):
    """`replace_video()` の `kind="carry"` は門を通ること（止まると枠に古い本が入る）。"""
    p = _write(tmp_path, [STANDING])
    got = d.replace_video(["V1"], "V9", path=p)
    assert got == ["2026-09-05"]
    last = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()][-1]
    assert last["video_id"] == "V9" and d.pick_kind(last) == "carry"
