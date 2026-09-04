"""**転がった免除では、名指しの腕を外せない。**（2026-09-05・最適化の回）

実測（`data/runs.jsonl`）: `gate_arm_pick()` が入った 09-04 12:5x 以降の
ship 81件 は全部 `lever_hint = sub_rate`、引いたのは 5件（6%）、
外した 76件 は 76件とも `lever_hint_covered` を持ち、その日付は
09-03 → 09-04 → 09-05 → 09-06 と毎日 00:2x に**前の日が来る前に**
転がっていました ＝ **1日1本の規則の下で恒真の免除**。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import run_marker as rm  # noqa: E402


def _log(tmp_path, covers):
    p = tmp_path / "runs.jsonl"
    with p.open("w", encoding="utf-8") as fh:
        for at, cov in covers:
            fh.write(json.dumps({"kind": "ship", "at": at, "lever": "per_video",
                                 "lever_hint": "sub_rate",
                                 "lever_hint_covered": cov}) + "\n")
    return p


def test_roll_before_the_old_cover_landed_is_a_roll(tmp_path):
    p = _log(tmp_path, [("2026-09-04T10:00", "2026-09-05")])
    got = rm.hint_cover_rolled(p, hint="sub_rate", covered="2026-09-06",
                               today="2026-09-05")
    assert got is not None
    assert got["prev"] == "2026-09-05" and got["now"] == "2026-09-06"
    assert got["streak"] == 1


def test_moving_on_after_the_old_cover_landed_is_not_a_roll(tmp_path):
    """前の免除の日付が過ぎてから次の本へ移るのは、正しい運用。門は黙ること。"""
    p = _log(tmp_path, [("2026-09-04T10:00", "2026-09-05")])
    assert rm.hint_cover_rolled(p, hint="sub_rate", covered="2026-09-06",
                                today="2026-09-06") is None


def test_same_cover_is_not_a_roll(tmp_path):
    p = _log(tmp_path, [("2026-09-04T10:00", "2026-09-06")])
    assert rm.hint_cover_rolled(p, hint="sub_rate", covered="2026-09-06",
                                today="2026-09-05") is None


def test_earlier_cover_is_not_a_roll(tmp_path):
    """後ろへ動いたときだけ数えます（前へ動くのは免除の縮小）。"""
    p = _log(tmp_path, [("2026-09-04T10:00", "2026-09-07")])
    assert rm.hint_cover_rolled(p, hint="sub_rate", covered="2026-09-06",
                                today="2026-09-05") is None


def test_streak_counts_only_the_unbroken_covered_run(tmp_path):
    p = tmp_path / "runs.jsonl"
    rows = [
        {"kind": "ship", "at": "2026-09-03T01:00", "lever_hint": "sub_rate",
         "lever_hint_covered": "2026-09-04"},
        # **免除なしで名指しの腕を引いた回**（ここで連は切れます）
        {"kind": "ship", "at": "2026-09-04T01:00", "lever_hint": "sub_rate",
         "lever": "sub_rate"},
        {"kind": "ship", "at": "2026-09-04T02:00", "lever_hint": "sub_rate",
         "lever_hint_covered": "2026-09-05"},
        {"kind": "ship", "at": "2026-09-04T03:00", "lever_hint": "sub_rate",
         "lever_hint_covered": "2026-09-05"},
    ]
    with p.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    got = rm.hint_cover_rolled(p, hint="sub_rate", covered="2026-09-06",
                               today="2026-09-05")
    assert got is not None and got["streak"] == 2


def test_other_arm_does_not_count(tmp_path):
    """名前を定数で持たないこと ＝ 別の腕の免除は混ざらない。"""
    p = _log(tmp_path, [("2026-09-04T10:00", "2026-09-05")])
    assert rm.hint_cover_rolled(p, hint="per_video", covered="2026-09-06",
                                today="2026-09-05") is None


def test_missing_pieces_are_silent(tmp_path):
    p = _log(tmp_path, [("2026-09-04T10:00", "2026-09-05")])
    assert rm.hint_cover_rolled(p, hint=None, covered="2026-09-06") is None
    assert rm.hint_cover_rolled(p, hint="sub_rate", covered=None) is None
    assert rm.hint_cover_rolled(tmp_path / "nope.jsonl", hint="sub_rate",
                                covered="2026-09-06", today="2026-09-05") is None


def test_the_escape_mark_exists_and_is_greppable():
    """外すなら理由を残せること。**門は仕事を捨てません。**"""
    assert rm.HINT_MISS_MARK and len(rm.HINT_MISS_MARK) >= 2
