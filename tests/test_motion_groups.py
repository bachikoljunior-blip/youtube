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
    assert motion_by_topic(tmp_path / "nope.jsonl", tmp_path / "nf.jsonl") == {}
    assert topic_by_video(tmp_path / "nope.jsonl") == {}


def test_per_video_flags_are_read(tmp_path: Path, monkeypatch) -> None:
    """**1本ごとのラベルも群になる。**

    回のおしまいの記録（`batch_runs.jsonl`）だけだと、**途中で落ちた回のぶんが消える**。
    2026-08-23 に実測: 8本頼んで6本できた回が落ち、記録が1行も残らず、
    **6本が「どちらの群か分からない本」**になった。
    """
    import src.motion_groups as mg
    flags = tmp_path / "build_flags.jsonl"
    _write(flags, [{"at": "1", "topic": "a", "opening_motion": False}])
    monkeypatch.setattr(mg, "FLAGS", flags)
    got = mg.motion_by_topic(tmp_path / "no_runs.jsonl")
    assert got == {"a": False}


# --- 2026-08-25 に足した3件 ----------------------------------------------
# **生の本数は標本ではありません。** 09/05 の前提の条件は「動きありと同じ日に
# 交互で予約する」なので、片方しか居ない日の本は使えません。ここで固定するのは:
#
#   4. 予約の時刻は **後の行**を採る（`reschedule.py` が動かすたびに1行足すため）
#   5. 群を割る日は **JST**（UTC の日で割ると JST の朝が前日に落ちる）
#   6. 共有日だけの標本が門に足りないとき、**動かす割り当て**が出る

from src.motion_groups import by_day, free_slot, jst_day, paired, retime_plan, scheduled_at


def test_予約の時刻は後の行を採る(tmp_path: Path) -> None:
    """**実測: 491本のうち 14本が2つの `at` を持っていた**（2026-08-25）。

    最初の行は「投稿したときの予約」で、後の行が `--compact` で動かした後の姿。
    先の行を採ると、その本が1日ずれた群に落ちます。
    """
    up = tmp_path / "up.jsonl"
    _write(up, [
        {"video_id": "V1", "topic": "a", "at": "2026-09-23T03:00:00Z"},
        {"video_id": "V1", "topic": "a", "at": "2026-09-22T00:30:00Z"},   # 後で動かした
    ])
    assert scheduled_at(up) == {"V1": "2026-09-22T00:30:00Z"}


def test_群を割る日はJST(tmp_path: Path) -> None:
    """UTC の 20〜23時台は、**JST では翌日の朝**です。ここで割り方が変わります。"""
    assert jst_day("2026-08-26T23:00:00Z") == "2026-08-27"     # JST 08:00
    assert jst_day("2026-08-27T02:00:00Z") == "2026-08-27"     # JST 11:00
    assert jst_day(None) is None
    assert jst_day("こわれた") is None


def test_片方しか居ない日は標本に入れない() -> None:
    at = {
        "OFF1": "2026-09-06T00:00:00Z", "ON1": "2026-09-06T01:00:00Z",   # 共有日
        "OFF2": "2026-09-24T00:30:00Z",                                   # 対照だけ
        "ON2": "2026-09-23T03:00:00Z",                                    # 動きありだけ
    }
    off, on = ["OFF1", "OFF2"], ["ON1", "ON2"]
    days = by_day(off, on, at)
    assert [d for d, (a, b) in days.items() if a and b] == ["2026-09-06"]
    assert paired(off, on, at) == (["OFF1"], ["ON1"])


def test_足りない側だけを動かす割り当てが出る() -> None:
    """**足りているほうを動かさないこと** —— 共有になっている日を壊します。"""
    at = {
        "OFF1": "2026-09-06T00:00:00Z", "OFF2": "2026-09-24T00:30:00Z",
        "ON1": "2026-09-06T01:00:00Z", "ON2": "2026-09-23T03:00:00Z",
    }
    plan = retime_plan(["OFF1", "OFF2"], ["ON1", "ON2"], at, bar=2)
    # 対照が共有日に1本しか居ないので、**孤立している OFF2 のほうが動く**
    assert plan == [("OFF2", "2026-09-24", "2026-09-23")]
    assert paired(["OFF1", "OFF2"], ["ON1", "ON2"], at) == (["OFF1"], ["ON1"])


def test_門に足りていれば割り当ては空() -> None:
    at = {"OFF1": "2026-09-06T00:00:00Z", "ON1": "2026-09-06T01:00:00Z"}
    assert retime_plan(["OFF1"], ["ON1"], at, bar=1) == []


def test_空き時刻を選ぶ() -> None:
    """`--move` は時刻の取り合いを見ないので、**こちらで空きを選ぶ**。"""
    at = {"A": "2026-09-23T00:00:00Z", "B": "2026-09-23T00:30:00Z"}   # JST 09:00 / 09:30
    assert free_slot("2026-09-23", at) == "10:00"
    assert free_slot("2026-09-25", at) == "09:00"                     # 誰も居ない日
