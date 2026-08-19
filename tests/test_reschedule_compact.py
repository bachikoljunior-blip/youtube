"""`scripts/reschedule.py --compact` の割り当てと、控えの書き換え。

**この道具は251本の予約を動かします。**間違えると、投稿が途切れるか、
測定中の窓を踏むか、同じ割り当てを2回目に出せなくなります。
守っている条件は3つで、ここで固定します:

    1. **新しい時刻は必ず今より前か同じ**（途中で止まっても、やり直せる）
    2. 測定の窓（`src.measure_window`）の日は、置き先からも対象からも外す
    3. 控え（`data/uploaded.jsonl`）は**足さずに書き換える**（幻の埋まりを残さない）
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src import dupes  # noqa: E402

reschedule = pytest.importorskip("reschedule")

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 8, 18, 2, 0, tzinfo=timezone.utc)      # 08/18 11:00 JST
EMPTY = ("", "")


def _row(vid: str, at_jst: str, topic: str = "s-x") -> dict:
    at = datetime.fromisoformat(at_jst).replace(tzinfo=JST).astimezone(timezone.utc)
    return {"id": vid, "topic": topic, "title": vid,
            "at": at.strftime("%Y-%m-%dT%H:%M:%SZ")}


def _jst(stamp: str) -> str:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(
        JST).strftime("%Y-%m-%dT%H:%M")


def test_1時間きざみの3日ぶんが30分きざみの1日に詰まる():
    rows = [_row(f"v{i}", f"2026-08-2{4 + i // 6}T{9 + i % 6:02d}:00") for i in range(18)]
    plan = reschedule.compact_plan(rows, now=NOW, max_days=1, window=EMPTY)
    # 25枠（9:00〜21:00・30分）に18本なので、全部 08/24 に入る
    assert {p["id"] for p in plan} == {f"v{i}" for i in range(1, 18)}   # v0 は動かない
    assert _jst(plan[0]["new"]) == "2026-08-24T09:30"
    assert _jst(plan[-1]["new"]) == "2026-08-24T17:30"


def test_動かす先はいつも今より前か同じ():
    rows = [_row(f"v{i}", f"2026-08-2{4 + i // 6}T{9 + i % 6:02d}:00") for i in range(18)]
    plan = reschedule.compact_plan(rows, now=NOW, max_days=2, window=EMPTY)
    for p in plan:
        assert p["new"] <= p["old"], p


def test_途中で止めても2回目が同じ割り当てを出す():
    """**`videos.update` は日枠で 190本ぶんしか撃てません。**途中で止まります。"""
    rows = [_row(f"v{i}", f"2026-08-2{4 + i // 6}T{9 + i % 6:02d}:00") for i in range(18)]
    first = reschedule.compact_plan(rows, now=NOW, max_days=1, window=EMPTY)
    half = first[:5]
    moved = {p["id"]: p["new"] for p in half}
    after = [dict(r, at=moved.get(r["id"], r["at"])) for r in rows]
    second = reschedule.compact_plan(after, now=NOW, max_days=1, window=EMPTY)
    assert {(p["id"], p["new"]) for p in second} == {
        (p["id"], p["new"]) for p in first[5:]}


def test_測定の窓は置き先からも対象からも外れる():
    """窓の中の本は動かさず、**窓の日には1本も置きません**（M14）。"""
    win = ("2026-08-26", "2026-08-27")
    rows = [_row("in", "2026-08-26T09:00")] + [
        _row(f"v{i}", f"2026-08-2{5 + i // 6}T{9 + i % 6:02d}:00") for i in range(12)]
    plan = reschedule.compact_plan(rows, now=NOW, max_days=2, window=win)
    assert "in" not in {p["id"] for p in plan}
    days = {_jst(p["new"])[:10] for p in plan}
    assert days & {"2026-08-26", "2026-08-27"} == set()
    assert days <= {"2026-08-25", "2026-08-28"}


def test_いちばん早い予約より前へは出さない():
    """置き先は**いちばん早い予約の日から**。それより前は、窓か、目前の日です。"""
    rows = [_row("a", "2026-09-01T09:00"), _row("b", "2026-09-02T09:00")]
    plan = reschedule.compact_plan(rows, now=NOW, max_days=1, window=EMPTY)
    assert [p["id"] for p in plan] == ["b"]
    assert _jst(plan[0]["new"]) == "2026-09-01T09:30"


def test_いまより前の本と公開済みは触らない():
    rows = [_row("past", "2026-08-17T09:00"), _row("soon", "2026-08-18T11:30"),
            {"id": "none", "topic": "s-x", "title": "none", "at": None},
            _row("ok", "2026-09-01T09:00")]
    rows.append(_row("ok2", "2026-09-02T09:00"))
    plan = reschedule.compact_plan(rows, now=NOW, max_days=1, lead_min=60,
                                   window=EMPTY)
    # past（過ぎた）・soon（lead の中）・at が無い行は、**枠を1つも食わない**
    assert [p["id"] for p in plan] == ["ok2"]
    assert _jst(plan[0]["new"]) == "2026-09-01T09:30"


def test_後ろへ動かす割り当てになったら止まる():
    """`--hour` が遅すぎると、前に詰めるつもりで後ろへ送ります。"""
    rows = [_row("v0", "2026-08-24T09:00")]
    with pytest.raises(SystemExit, match="後ろへ動かす"):
        reschedule.compact_plan(rows, now=NOW, hour=20, until_hour=21,
                                max_days=1, window=EMPTY)


def test_目盛りが60の約数でないと止まる():
    with pytest.raises(SystemExit, match="60 の約数"):
        reschedule.compact_plan([_row("v0", "2026-09-01T09:00")], now=NOW,
                                step_min=7, window=EMPTY)


def test_控えは足さずに書き換える(tmp_path, monkeypatch):
    """**足すと `ledger_minutes` が古い時刻も「埋まっている」と読みます。**"""
    from src import config
    path = tmp_path / "data" / "uploaded.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"video_id": "a", "topic": "s-a", "title": "A",
                    "at": "2026-09-01T00:00:00Z", "uploaded_at": "2026-08-17T00:00:00Z"},
                   ensure_ascii=False) + "\n"
        + json.dumps({"video_id": "b", "topic": "s-b", "title": "B",
                      "at": "2026-09-02T00:00:00Z"}, ensure_ascii=False) + "\n",
        encoding="utf-8")
    monkeypatch.setattr(config, "ROOT", tmp_path)

    assert dupes.retime("a", "2026-08-24T00:30:00Z") is True
    lines = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert len(lines) == 2                      # **増えていない**
    got = {r["video_id"]: r for r in lines}
    assert got["a"]["at"] == "2026-08-24T00:30:00Z"
    assert got["a"]["uploaded_at"] == "2026-08-17T00:00:00Z"   # 投稿時刻は動かさない
    assert got["b"]["at"] == "2026-09-02T00:00:00Z"
    assert dupes.retime("a", "2026-08-24T00:30:00Z") is False  # 同じなら書かない
    assert dupes.retime("zz", "2026-08-24T00:30:00Z") is False


def test_同じ動画IDが2行あれば両方書き換える(tmp_path, monkeypatch):
    from src import config
    path = tmp_path / "data" / "uploaded.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text("\n".join(
        json.dumps({"video_id": "a", "topic": "s-a", "title": "A", "at": at})
        for at in ("2026-09-01T00:00:00Z", "2026-09-05T00:00:00Z")) + "\n",
        encoding="utf-8")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    assert dupes.retime("a", "2026-08-24T00:30:00Z") is True
    ats = {json.loads(x)["at"] for x in path.read_text(encoding="utf-8").splitlines() if x.strip()}
    assert ats == {"2026-08-24T00:30:00Z"}


# ---------------------------------------------------------------------------
# **真ん中に空く穴**（2026-08-19 12:5x に足した）
#
# `--min-days` は「予約の最後」しか見ません。**全部を詰め切らない**割り当てでは、
# 後ろの何本かが元の時刻に残るので**最後は動かず**、その手前だけが空になります。
# 実物（317本・`--max-days 10`）で **08/30〜09/11 の13日**がこの形でした。
# ---------------------------------------------------------------------------


def _hole_setup(days: int):
    """1日1本 × 12日ぶん。`max_days` を小さくすると詰め切れずに穴が空く。"""
    rows = [_row(f"v{i}", f"2026-08-{19 + i:02d}T09:00") for i in range(12)]
    plan = reschedule.compact_plan(rows, now=NOW, step_min=60, hour=9, until_hour=11,
                                   max_days=days, window=EMPTY)
    return rows, plan


def test_詰め切らないと真ん中に穴が空くのを数える():
    rows, plan = _hole_setup(2)          # 置き先は 08/19〜08/20 の 3枠 × 2日
    holes = reschedule.hole_days(rows, plan, NOW)
    assert holes, "穴が空いているのに0件を返した"
    # 最後の本（08/30）は動かないので、その手前が空になる
    assert "08/30" not in holes, "**予約の最後そのもの**を穴に数えている"
    assert "08/22" in holes


def test_全部を詰め切ったときは穴と数えない():
    """後ろがからになるのは**地平線が縮んだ**だけ。`--min-days` が見る側です。"""
    rows, plan = _hole_setup(12)
    assert reschedule.hole_days(rows, plan, NOW) == []


def test_動かすものが無ければ穴も無い():
    rows = [_row("v0", "2026-08-19T09:00")]
    assert reschedule.hole_days(rows, [], NOW) == []


def test_予約の最後より後ろの0本の日は穴ではない():
    """12本を1日ぶんに詰めると 08/19 以外は全部 0本。**穴は0件**であること。"""
    rows = [_row(f"v{i}", f"2026-08-{19 + i:02d}T09:00") for i in range(12)]
    plan = reschedule.compact_plan(rows, now=NOW, step_min=5, hour=9, until_hour=11,
                                   max_days=1, window=EMPTY)
    assert len(plan) == 11               # 08/19 09:00 の1本だけ動かない
    assert reschedule.hole_days(rows, plan, NOW) == []


class _Args:
    """`suggest_max_days` が読む欄だけ。"""
    step_min = 60
    hour = 9
    until_hour = 11
    lead_min = 60
    min_days = 0.0

    def __init__(self, max_days: int):
        self.max_days = max_days


def test_穴の空かない詰め方を道具の側が名指しする():
    """**増やすと消える**ので、人の直感（減らす）と逆向きです。"""
    rows = [_row(f"v{i}", f"2026-08-{19 + i:02d}T09:00") for i in range(12)]
    hint = reschedule.suggest_max_days(rows, NOW, _Args(2), ceiling=20)
    assert hint is not None
    plan = reschedule.compact_plan(rows, now=NOW, step_min=60, hour=9, until_hour=11,
                                   max_days=hint, window=EMPTY)
    assert reschedule.hole_days(rows, plan, NOW) == []


def test_撃ち切れない回は途中の姿の穴も数えられる():
    """`--max` で切ると、前に詰めた本が抜けた跡が**翌日の窓まで空いたまま**残る。

    穴が0件の割り当てでも、**途中の姿は別に数える**こと。
    """
    rows = [_row(f"v{i}", f"2026-08-{19 + i:02d}T09:00") for i in range(12)]
    plan = reschedule.compact_plan(rows, now=NOW, step_min=60, hour=9, until_hour=11,
                                   max_days=12, window=EMPTY)
    assert reschedule.hole_days(rows, plan, NOW) == []      # 撃ち切れば穴は無い
    assert reschedule.hole_days(rows, plan[:3], NOW), "途中で止めた姿の穴を数えていない"
