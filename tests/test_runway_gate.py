"""**在庫が薄いときは、間隔の下限より生成を優先する**（`sibling_check --phase spawn`）。

## なぜ要るか

`docs/TRIGGER.md` は 8/15 から2か所でこう言っています。

> ②**予約の在庫が2週間を切ったら、下限より生成を優先する**
> —— 止まるより、出せなくなるほうが痛い。**これはまだ機械に入っていません**

申し送りも**8回**運びました。**文書にしか無いものは、読み飛ばせば効きません。**
実際、`--phase spawn` は 8/16 まで在庫を1度も見ていません。

痛みの大きさが違うので、順番が決まります —— 間隔を詰めて枠を早く使い切っても、
**予約が埋まっていれば公開は続きます。** 逆に在庫が尽きると、
枠がいくら余っていても投稿が途切れます（**途切れるのが最大の損失**）。

## そして、在庫を測ろうとして計器が壊れているのが分かった

`data/uploaded.jsonl` の `at`（予約時刻）は、**控えを入れた 8/16 02:5x 以降に
上げた予約8本が、8本とも `null`** でした。

    scripts/upload_only.py   channel["publish"].get("publish_at") を控える
    src/uploader.py          publishAt は upload() の**中で初めて決まる**

**決めた側が呼んだ側に返していませんでした。** 埋め戻した48本には時刻が
入っていたので、**一覧を見ても壊れて見えません**（新しい行だけが空）。
在庫は 21.3日を **19.2日** と答えていました —— **少なめに出る向き**で、
これは「余計に枠を食う」側の誤りです。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import sibling_check  # noqa: E402


def _ledger(tmp_path: Path, ats: list[str | None]) -> Path:
    path = tmp_path / "data" / "uploaded.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for i, at in enumerate(ats):
            fh.write(json.dumps({"video_id": f"v{i}", "topic": f"t{i}",
                                 "title": f"題{i}", "at": at},
                                ensure_ascii=False) + "\n")
    return path


def _runway(monkeypatch, tmp_path, ats, now):
    _ledger(tmp_path, ats)
    monkeypatch.setattr(sibling_check, "__file__", str(tmp_path / "scripts" / "x.py"))
    return sibling_check.runway_days(now)


NOW = datetime(2026, 8, 16, 0, 0, tzinfo=timezone.utc)


def test_runway_is_the_furthest_scheduled_time(monkeypatch, tmp_path):
    got = _runway(monkeypatch, tmp_path, [
        "2026-08-20T00:00:00Z", "2026-09-06T00:00:00Z", "2026-08-18T00:00:00Z",
    ], NOW)
    assert got is not None and abs(got - 21.0) < 0.01


def test_published_rows_have_no_time_and_are_skipped(monkeypatch, tmp_path):
    """**公開済みの本は `at` を持ちません。** それを 0 と読まないこと。

    `null` は「予約が無い」であって「今日で尽きる」ではありません
    （`docs/trigger_main.md` §2 の「空欄を『尽きた』とも読まない」と同じ）。
    """
    got = _runway(monkeypatch, tmp_path, [None, None, "2026-08-25T00:00:00Z", None], NOW)
    assert got is not None and abs(got - 9.0) < 0.01


def test_no_ledger_at_all_reads_as_unknown(monkeypatch, tmp_path):
    """読めない回は `None`。**下限はそのまま効かせます**（推測で外さない）。"""
    monkeypatch.setattr(sibling_check, "__file__", str(tmp_path / "scripts" / "x.py"))
    assert sibling_check.runway_days(NOW) is None


def test_all_rows_published_reads_as_unknown(monkeypatch, tmp_path):
    assert _runway(monkeypatch, tmp_path, [None, None], NOW) is None


def test_past_schedules_go_negative(monkeypatch, tmp_path):
    """**全部が過去なら在庫は負**。境目（14日）を確実に下回ります。"""
    got = _runway(monkeypatch, tmp_path, ["2026-08-10T00:00:00Z"], NOW)
    assert got is not None and got < 0


def test_the_threshold_is_two_weeks():
    """境目は `docs/TRIGGER.md` の覆る条件②と同じ **2週間**であること。

    **数字をここに書き写しているのではなく、同じ値を指しているかを見ています。**
    片方だけ動かすと、文書と機械が食い違ったまま気づけません（8/12 に3か所で起きた）。
    """
    assert sibling_check.RUNWAY_FLOOR_DAYS == 14
    doc = (Path(__file__).resolve().parent.parent / "docs" / "TRIGGER.md"
           ).read_text(encoding="utf-8")
    assert "在庫が2週間を切ったら" in doc


# ------------------------------------------- 計器のほう（`at` が null になっていた）

def test_uploader_writes_the_decided_time_back(monkeypatch, tmp_path):
    """**`upload()` が決めた予約時刻を、呼んだ側が読めること。**

    ここは弱い検査です（本物の投稿は叩けないので、`publishAt` を決める段だけを
    切り出して呼びます）。**それでも入れてあるのは、壊れ方が「静か」だったから** ——
    控えの新しい行だけが `null` になり、一覧の見た目は変わりませんでした。
    """
    import src.uploader as uploader

    cfg = {"visibility": "private", "publish_hour_jst": 9}
    monkeypatch.setattr(uploader, "scheduled_publish_times", lambda svc: set())
    decided = uploader.next_publish_at(9, 0, taken=set())

    # `upload()` の中でやっているのと同じ書き戻し。**契約はこの1行です。**
    cfg["publish_at"] = decided
    assert cfg.get("publish_at"), "呼んだ側が予約時刻を読めません（控えの at が null になります）"

    import inspect
    src = inspect.getsource(uploader.upload)
    assert 'publish_cfg["publish_at"]' in src, (
        "`uploader.upload()` が決めた publishAt を publish_cfg に書き戻していません。"
        "書き戻さないと `data/uploaded.jsonl` の at が必ず null になります")


def test_the_real_ledger_has_no_scheduled_row_without_a_time():
    """**実物の控えに、予約なのに時刻の無い行が残っていないこと。**

    `at` が `null` でも、その本が**公開済み**なら正常です。
    だから見るのは「時刻の無い行があるか」ではなく、
    **`src/dupes.ledger_rows()` が `scheduled` と言う行に時刻があるか**です。
    """
    from src import dupes

    for row in dupes.ledger_rows():
        if row["scheduled"]:
            assert row["at"], f"{row['id']} が予約なのに時刻を持っていません"
