"""**決めた本の台本が良くなっていれば、回が何もしなくても焼き直されること。**
（`scripts/ahead_sweep.rebake_today` の決める側 ＋ `src/daily_pick.replace_video`）

## なぜ要るか（2026-09-03 05:xx・最適化の回）

規則3 の「物が変わる1手」（焼き直し）は `[きょうの1本]` が印字するだけで、撃つかは回の裁量だった。
しかも撃っても、決め（`daily_pick.jsonl`）は旧 ID を名指ししたままなので、
`place_today` が枠へ置くのは**焼き直す前の本**だった（09/04 の試験の本 `6PKux5HNnUE` がその形）。

この検査が見るのは**決める側（純関数）**と**決めの写し**。撃つ側は `rebake_run` が背景で持つ。

## 覆る条件

- `_today_candidate` が ID ではなく題材で本を引くようになったら `replace_video` は要らない
- `REBAKE_LEAD` / `REBAKE_MAX_PER_DAY` は `scripts/ahead_sweep.py` の定数（ここに数は写さない）
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

_gspec = importlib.util.spec_from_file_location(
    "ahead_gate_for_rebake", ROOT / "scripts" / "ahead_gate.py")
ahead_gate = importlib.util.module_from_spec(_gspec)
sys.modules.setdefault("ahead_gate", ahead_gate)
_gspec.loader.exec_module(ahead_gate)

_sspec = importlib.util.spec_from_file_location(
    "ahead_sweep_rebake", ROOT / "scripts" / "ahead_sweep.py")
sweep = importlib.util.module_from_spec(_sspec)
_sspec.loader.exec_module(sweep)

from src import daily_pick  # noqa: E402

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 9, 3, 6, 0, tzinfo=JST).astimezone(timezone.utc)
SLOT = datetime(2026, 9, 4, 17, 0, tzinfo=JST)
CUR = {"video_id": "OLD00000001", "topic": "zaishoku-2026-62man", "form": "長尺",
       "why": "外の p90 624,772回"}
A = json.dumps({"title": "a", "segments": [{"narration": "旧"}]}, ensure_ascii=False)
B = json.dumps({"title": "a", "segments": [{"narration": "新・冒頭を型に"}]}, ensure_ascii=False)


def _plan(**kw):
    base = dict(cur=CUR, stash_text=A, draft_text=B, draft_newer=True, attempted=False,
                scheduled=False, slot_at=SLOT, now=NOW, baked_today=0)
    base.update(kw)
    return sweep.rebake_plan(**base)


# ---------------------------------------------------------------- 決める側
def test_台本が控えと違い_新しく_枠に間に合えば焼く():
    p = _plan()
    assert p["do"] is True
    assert p["video_id"] == "OLD00000001" and p["topic"] == "zaishoku-2026-62man"
    assert p["sha"] == sweep.script_sha(B)


def test_中身が同じなら焼かない_空白や鍵の順は見ない():
    same = json.dumps(json.loads(A), indent=2, sort_keys=True)
    p = _plan(draft_text=same)
    assert p["do"] is False and "同じ中身" in p["why"]


def test_決めが無ければ焼かない():
    assert _plan(cur=None)["do"] is False
    assert _plan(cur={"video_id": "", "topic": "x"})["do"] is False


def test_控えか台本が無ければ焼かない():
    assert _plan(stash_text=None)["do"] is False
    assert _plan(draft_text=None)["do"] is False


def test_台本が新しいと言えなければ焼かない():
    """古い台本で、新しく上げた本を上書きしない。"""
    assert _plan(draft_newer=False)["do"] is False
    assert _plan(draft_newer=None)["do"] is False


def test_同じ台本は二度焼かない():
    p = _plan(attempted=True)
    assert p["do"] is False and "一度 焼いた" in p["why"]


def test_予約が付いていれば焼かない():
    assert _plan(scheduled=True)["do"] is False


def test_枠が近すぎれば焼かない():
    close = NOW + sweep.REBAKE_LEAD - timedelta(minutes=1)
    p = _plan(slot_at=close)
    assert p["do"] is False and "焼き上がる前" in p["why"]
    assert _plan(slot_at=None)["do"] is False


def test_きょうの上限():
    assert _plan(baked_today=sweep.REBAKE_MAX_PER_DAY)["do"] is False
    assert _plan(baked_today=sweep.REBAKE_MAX_PER_DAY - 1)["do"] is True


# ---------------------------------------------------------------- 決めの写し
def test_差し替えたら決めが新IDへ写る(tmp_path):
    p = tmp_path / "daily_pick.jsonl"
    from datetime import date
    daily_pick.record("長尺", "zaishoku-2026-62man", "外の p90 624,772回", day=date(2026, 9, 4),
                      now=NOW, path=p, video_id="OLD00000001")
    daily_pick.record("長尺", "nenkin-uketorikata", "2本目", day=date(2026, 9, 5),
                      now=NOW, path=p, video_id="OTHER000001")
    days = daily_pick.replace_video(["OLD00000001"], "NEW00000001", why_note="検査", now=NOW, path=p)
    assert days == ["2026-09-04"]
    cur = daily_pick.current(date(2026, 9, 4), p)
    assert cur["video_id"] == "NEW00000001"
    assert cur["form"] == "長尺" and cur["topic"] == "zaishoku-2026-62man"
    assert "OLD00000001" in cur["why"] and "NEW00000001" in cur["why"]
    # 別の日の決めは触らない
    assert daily_pick.current(date(2026, 9, 5), p)["video_id"] == "OTHER000001"


def test_名指ししていなければ何も写さない(tmp_path):
    p = tmp_path / "daily_pick.jsonl"
    from datetime import date
    daily_pick.record("ショート", "s-x", "1本", day=date(2026, 9, 4), now=NOW, path=p, video_id="AAA")
    assert daily_pick.replace_video(["ZZZ"], "NEW", now=NOW, path=p) == []
    assert daily_pick.replace_video(["AAA"], "AAA", now=NOW, path=p) == []
    assert daily_pick.current(date(2026, 9, 4), p)["video_id"] == "AAA"


# ---------------------------------------------------------------- 掃きの口に配線されていること
def test_mainの置く手の並びにrebake_todayが在る():
    src = (ROOT / "scripts" / "ahead_sweep.py").read_text(encoding="utf-8")
    body = src.split("def main(")[1]
    assert "rebake_today(now, dry_run=args.dry_run)" in body
    assert "--rebake-run" in src.split('if __name__ == "__main__"')[1]


def test_upload_onlyが差し替えたら決めを写す():
    src = (ROOT / "scripts" / "upload_only.py").read_text(encoding="utf-8")
    assert "replace_video(replaced_ids, video_id" in src
