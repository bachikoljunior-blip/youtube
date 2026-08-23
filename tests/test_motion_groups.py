"""`src/motion_groups.py`。**群は「作ったときの値」で割る。**

8/19 と 8/23 に同型の事故を2回起こしている（日付で割ると両群の中身が同じになる）。
ここで固定するのは3つ:

1. 記録された `opening_motion` で割れる
2. **記録の無い本はどちらにも入れない**（「無い＝動きあり」と推定しない）
3. 同じテーマが複数回に出てきたら、**最初の記録**を採る（作り直しで群が動かない）
"""
import json
from pathlib import Path

from src.motion_groups import groups, motion_by_topic, topic_by_video


def _write(p: Path, rows: list[dict]) -> None:
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


def test_split_by_recorded_flag(tmp_path: Path) -> None:
    runs = tmp_path / "runs.jsonl"
    _write(runs, [
        {"at": "1", "opening_motion": True, "results": [{"topic": "a"}]},
        {"at": "2", "opening_motion": False, "results": [{"topic": "b"}]},
    ])
    up = tmp_path / "up.jsonl"
    _write(up, [{"video_id": "VA", "topic": "a"}, {"video_id": "VB", "topic": "b"}])
    off, on = groups(motion=motion_by_topic(runs), topics=topic_by_video(up))
    assert (off, on) == (["VB"], ["VA"])


def test_unrecorded_is_dropped(tmp_path: Path) -> None:
    """**記録の無い回は数えない。** 実装前の本が混ざる可能性を残さない。"""
    runs = tmp_path / "runs.jsonl"
    _write(runs, [{"at": "1", "results": [{"topic": "old"}]}])       # opening_motion なし
    up = tmp_path / "up.jsonl"
    _write(up, [{"video_id": "VOLD", "topic": "old"}])
    assert groups(motion=motion_by_topic(runs), topics=topic_by_video(up)) == ([], [])


def test_conflicting_records_are_dropped(tmp_path: Path) -> None:
    """**食い違ったテーマは両方から落とす。**（2026-08-23 に実際に踏んだ）

    `--skip-upload` で作った本は「使った」にならないので、次の `pick()` が
    **同じテーマを選び直し**、`build/` を上書きする。ディスクは動きあり・
    記録の1件目は動きなし、という食い違いが起きた。
    最初の記録を採ると、**中身が動きありの本を対照群として数える**ことになる。
    """
    runs = tmp_path / "runs.jsonl"
    _write(runs, [
        {"at": "1", "opening_motion": False, "results": [{"topic": "a"}]},
        {"at": "2", "opening_motion": True, "results": [{"topic": "a"}]},
        {"at": "3", "opening_motion": True, "results": [{"topic": "b"}]},
    ])
    got = motion_by_topic(runs)
    assert "a" not in got          # 食い違い → 落とす
    assert got["b"] is True        # 食い違わないものは残る


def test_missing_files_are_empty(tmp_path: Path) -> None:
    assert motion_by_topic(tmp_path / "nope.jsonl") == {}
    assert topic_by_video(tmp_path / "nope.jsonl") == {}
