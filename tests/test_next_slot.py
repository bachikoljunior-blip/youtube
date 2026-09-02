"""**`src/next_slot.py` の一覧が、実物と外れたら赤くする。**

## なぜ要るか（2026-09-01。**書いた同じ回に、この検査が2件 見つけました**）

`next_slot._MAKERS` は「その本を焼くコード」の**手で並べた一覧**です。
`git log -- <一覧>` に渡すので、**綴りが違っても、存在しなくても、git は
黙って 0件 を返します** —— 画面には
「そのあと生成側のコードは変わっていません」と出ます。
**間違いが「大丈夫です」の顔で出る形**なので、機械の側で押さえます。

実際に見つかったもの（この検査を書いた回）:

    `src/titles.py`  **存在しません**（題は `script_writer.title_form()`）
    `src/config.py` / `src/util.py`  `pipeline` が import しているのに、
                                     どちらの箱にも入っていなかった

## 覆る条件

- `src/pipeline.py` が import を動的にしはじめたら、下の読み取りは空になります
  （`_pipeline_imports()` が 0件 を返したら、この検査自身が落ちます）。
- 「出来上がりを変える／変えない」の仕分けは判断です。**入れ替えてよい** ——
  ただし `_NOT_MAKERS` に移すなら、`src/next_slot.py` の註に理由を書くこと。
"""
from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src import next_slot

ROOT = Path(__file__).resolve().parent.parent
PIPELINE = ROOT / "src" / "pipeline.py"


def _pipeline_imports() -> set[str]:
    """`src/pipeline.py` が `src/` の中から import している module 名。"""
    tree = ast.parse(PIPELINE.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 1:
            if node.module:                       # from .renderer import ...
                out.add(node.module.split(".")[0])
            else:                                 # from . import a, b, c
                out.update(a.name for a in node.names)
    return out


def test_pipeline_imports_are_classified() -> None:
    """**pipeline の import は、必ずどちらかの箱に入っていること。**

    片方にも入っていない module は「変わったのに鳴らない」側に落ちます。
    """
    mods = _pipeline_imports()
    assert mods, "pipeline の import を1件も読めていません（動的 import？）"
    known = set(next_slot._MAKERS) | set(next_slot._NOT_MAKERS)
    missing = sorted(m for m in mods if f"src/{m}.py" not in known)
    assert not missing, (
        "`src/pipeline.py` が import しているのに、`next_slot._MAKERS` にも "
        f"`_NOT_MAKERS` にも入っていません: {missing}。"
        "**入れないと、そこが変わっても『変わっていません』と出ます。**")


def test_listed_paths_exist() -> None:
    """**一覧の綴りが実物と合っていること**（`git log` は黙って 0件 を返します）。"""
    bad = [p for p in (*next_slot._MAKERS, *next_slot._NOT_MAKERS)
           if not (ROOT / p).exists()]
    assert not bad, (
        f"`next_slot` の一覧に、実在しない道があります: {bad}。"
        "**`git log -- <無い道>` は 0件 を返すので、画面には"
        "『変わっていません』と出ます。**")


def test_boxes_do_not_overlap() -> None:
    both = set(next_slot._MAKERS) & set(next_slot._NOT_MAKERS)
    assert not both, f"両方の箱に入っています: {sorted(both)}"


def test_next_video_takes_the_last_row_of_a_video(tmp_path: Path) -> None:
    """**同じ `video_id` は、控えのいちばん後ろの行を採ること。**

    予約を外すと `at` が `null` になった行が**後ろに**足されます。
    前の行を採ると、**もう予約されていない本を「次の1本」に出します。**
    """
    p = tmp_path / "uploaded.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in [
        {"video_id": "A", "topic": "t-a", "at": "2026-09-05T00:00:00Z"},
        {"video_id": "A", "topic": "t-a", "at": None},      # 予約を外した
        {"video_id": "B", "topic": "t-b", "at": "2026-09-09T00:00:00Z"},
    ]) + "\n", encoding="utf-8")
    now = datetime(2026, 9, 1, tzinfo=timezone.utc)
    got = next_slot.next_video(now=now, path=p)
    assert got is not None and got["video_id"] == "B"


def test_next_video_is_none_when_nothing_is_scheduled(tmp_path: Path) -> None:
    p = tmp_path / "uploaded.jsonl"
    p.write_text(json.dumps({"video_id": "A", "at": None}) + "\n",
                 encoding="utf-8")
    now = datetime(2026, 9, 1, tzinfo=timezone.utc)
    assert next_slot.next_video(now=now, path=p) is None
    # **その回でも1行は出ること**（黙ると `improve` の当てどころが消えます）。
    assert next_slot.lines(now=now)


def test_stale_commits_needs_a_time() -> None:
    assert next_slot.stale_commits(None) == []


@pytest.mark.parametrize("bad", ["", "not-a-time", "2026-13-40"])
def test_parse_survives_junk(bad: str) -> None:
    assert next_slot._parse(bad) is None


class _Out:
    returncode = 0

    def __init__(self, text: str) -> None:
        self.stdout = text


def test_stale_commits_drops_what_was_applied_to_this_book(monkeypatch) -> None:
    """**その本へ当て直したコミットは引くこと**（`_applied_to()` の註）。

    引かないと、`improve` の1手（生成側を直して、**その場で焼き直す**）が
    次の回から「入っていません」と鳴り続け、**同じ手が2度 撃たれます。**
    実測 2026-09-01: この道具の1発目が `e598caea` でそうなりました。
    """
    calls = {"n": 0}

    def fake_run(cmd, **kw):
        calls["n"] += 1
        if "critique_queue" in " ".join(cmd):
            return _Out("bbbbbbb\n")            # この本へ当て直したほう
        return _Out("aaaaaaa 09/01 01:00 fix: zukai\n"
                    "bbbbbbb 09/01 02:00 improve: thumb\n")

    monkeypatch.setattr(next_slot.subprocess, "run", fake_run)
    since = datetime(2026, 9, 1, tzinfo=timezone.utc)
    got = next_slot.stale_commits(since, video_id="VID")
    assert [ln.split(" ", 1)[0] for ln in got] == ["aaaaaaa"]
    assert calls["n"] == 2, "2回とも撃つこと（生成側 → その本）"


def test_stale_commits_without_video_id_keeps_everything(monkeypatch) -> None:
    monkeypatch.setattr(next_slot.subprocess, "run",
                        lambda *a, **k: _Out("aaaaaaa 09/01 01:00 fix: zukai\n"))
    since = datetime(2026, 9, 1, tzinfo=timezone.utc)
    assert len(next_slot.stale_commits(since)) == 1


def test_pending_thumbnail_is_false_without_an_id() -> None:
    assert next_slot.pending_thumbnail(None) is False
    assert next_slot.pending_thumbnail("") is False


def test_pending_thumbnail_asks_the_one_place_that_knows(monkeypatch) -> None:
    """**判定は `scripts/critique_queue.missing_thumbnail()` の1か所だけ。**

    ここで条件（`thumbnail_set is False` かつ bytes が在る）を書き直すと、
    **2か所に増えた瞬間から片方だけが直ります**（この repo の通算8件の形）。
    """
    from scripts import critique_queue

    monkeypatch.setattr(critique_queue, "missing_thumbnail",
                        lambda: [{"video_id": "AAA"}, {"video_id": "BBB"}])
    assert next_slot.pending_thumbnail("AAA") is True
    assert next_slot.pending_thumbnail("ZZZ") is False


def test_pending_thumbnail_survives_a_broken_store(monkeypatch) -> None:
    """**読めない回でも黙って False**（`improve` の行ごと消さないため）。"""
    from scripts import critique_queue

    def boom():
        raise OSError("store is gone")

    monkeypatch.setattr(critique_queue, "missing_thumbnail", boom)
    assert next_slot.pending_thumbnail("AAA") is False


def _stub_quota(monkeypatch, used: int, back_hour_utc: int):
    from src import quota_ledger, upload_cap

    monkeypatch.setattr(quota_ledger, "spent", lambda *a, **k: {"data": used})
    monkeypatch.setattr(
        upload_cap, "window_end",
        lambda *a, **k: datetime(2026, 9, 1, back_hour_utc, tzinfo=timezone.utc))


PUB = datetime(2026, 9, 1, 13, tzinfo=timezone.utc)          # 09/01 22:00 JST
NOW = datetime(2026, 8, 31, 20, tzinfo=timezone.utc)


def test_quota_note_says_it_can_be_pushed_now(monkeypatch) -> None:
    _stub_quota(monkeypatch, used=1_000, back_hour_utc=7)
    note = next_slot.quota_note(PUB, NOW)
    assert note and "この回で押せます" in note


def test_quota_note_counts_the_hours_left_before_publication(monkeypatch) -> None:
    """**「いつか押す」と「この6時間で押す」は別の手です。**"""
    _stub_quota(monkeypatch, used=13_365, back_hour_utc=7)     # 16:00 JST
    note = next_slot.quota_note(PUB, NOW)
    assert note and "残り 6時間" in note and "13,365" in note


def test_quota_note_says_when_it_is_already_too_late(monkeypatch) -> None:
    _stub_quota(monkeypatch, used=13_365, back_hour_utc=20)    # 公開のあと
    note = next_slot.quota_note(PUB, NOW)
    assert note and "間に合いません" in note


def test_quota_note_is_silent_when_the_ledger_is_unreadable(monkeypatch) -> None:
    """**読めない回は黙ること**（`improve` の行ごと消さないため）。"""
    from src import quota_ledger

    def boom(*a, **k):
        raise OSError("ledger is gone")

    monkeypatch.setattr(quota_ledger, "spent", boom)
    assert next_slot.quota_note(PUB, NOW) is None


def test_next_slot_follows_the_daily_pick_when_nothing_is_scheduled(monkeypatch) -> None:
    """予約が無く、`[きょうの1本]` が下書きと別の本を決めていたら、`[次の枠]` はその本
    （2026-09-02 20:xx に踏んだ —— 同じ画面が 6GtzWaguZhg と DtpnSVFDtAE の2本を名指しし、
    `stale_commits()` は出ない側の本で数えていた）。"""
    from datetime import timedelta
    from src import daily_pick
    t = datetime.now(timezone.utc)
    old = {"video_id": "OLD", "topic": "gassan-1", "title": "長尺", "duration_s": 300,
           "uploaded_at": t.isoformat(), "at": None}
    pick = {"video_id": "PICK", "topic": "s-shokibo-1", "title": "短い #Shorts",
            "uploaded_at": (t - timedelta(days=15)).isoformat(), "at": None,
            "retimed_at": t.isoformat()}
    monkeypatch.setattr(next_slot, "calendar_lines", lambda **kw: [])
    monkeypatch.setattr(next_slot, "draft_lines", lambda **kw: [])
    monkeypatch.setattr(next_slot, "next_video", lambda **kw: None)
    monkeypatch.setattr(next_slot, "drafts", lambda **kw: [dict(old)])
    monkeypatch.setattr(next_slot, "latest_rows", lambda *a, **kw: {"OLD": old, "PICK": pick})
    monkeypatch.setattr(daily_pick, "current", lambda day, path=None: {
        "for_day": day.isoformat(), "form": "ショート", "topic": "s-shokibo-1",
        "video_id": "PICK", "why": "173 対 1"})
    seen: list[str | None] = []

    def fake_stale(built, video_id=None, **kw):
        seen.append(video_id)
        return []

    monkeypatch.setattr(next_slot, "stale_commits", fake_stale)
    monkeypatch.setattr(next_slot, "pending_thumbnail", lambda *a, **kw: False)
    out = next_slot.lines()
    nxt = next(ln for ln in out if ln.startswith("[次の枠]"))
    assert "`PICK`" in nxt and "`OLD`" not in nxt.split("——")[0]
    assert "[きょうの1本]" in nxt and "OLD" in nxt          # 下書きは池に残すと書く
    assert seen == ["PICK"]                                  # 古さも、出る側の本で数える


def test_next_slot_keeps_a_real_reservation_over_the_pick(monkeypatch) -> None:
    """予約が実際に在る回は、予約が正（決めのほうが古い）。"""
    from datetime import timedelta
    from src import daily_pick
    t = datetime.now(timezone.utc)
    fake = {"video_id": "RES", "topic": "kaigo-9", "title": "t", "duration_s": 300,
            "uploaded_at": t.isoformat(), "_at": t + timedelta(hours=5)}
    monkeypatch.setattr(next_slot, "calendar_lines", lambda **kw: [])
    monkeypatch.setattr(next_slot, "draft_lines", lambda **kw: [])
    monkeypatch.setattr(next_slot, "next_video", lambda **kw: dict(fake))
    monkeypatch.setattr(daily_pick, "current", lambda day, path=None: {
        "for_day": day.isoformat(), "form": "ショート", "topic": "s-x-1",
        "video_id": "PICK", "why": "1 対 2"})
    monkeypatch.setattr(next_slot, "stale_commits", lambda *a, **kw: [])
    monkeypatch.setattr(next_slot, "pending_thumbnail", lambda *a, **kw: False)
    out = next_slot.lines()
    nxt = next(ln for ln in out if ln.startswith("[次の枠]"))
    assert "`RES`" in nxt and "PICK" not in nxt
