"""**検査は、本物の `data/day_quota.jsonl` に書かないこと**（2026-08-27 に測って足した）。

## なぜ要るか

`tests/conftest.py` の冒頭（2026-08-17）は、この repo が**通算7回**踏んだ形として
**「検査は、本物の台帳に書かないこと」**と書いています。
**`data/day_quota.jsonl` は、その自動の掛かりに入っていませんでした。**

実測 2026-08-27 —— 本物の帳面 4,338行 のうち **97行が検査の書いた行**
（08/26 に 37行・08/27 に 60行）。出どころは
`tests/test_unschedule_ledger.py` が偽の service で `reschedule._update` を呼び、
その中の `upload_cap.note_quota_ok(detail="videos.update vid1")` が通る形です。

## ここが壊れると何が起きるか（**統計の汚れでは済みません**）

`note_quota_ok` が書くのは `{"ok": true}` の行で、`day_quota()` はそれを見て
**「403 のあとに通っている ＝ あの 403 は日枠ではない。押してよい」**と答えます
（`quota_ok_after_hits`）。つまり **`pytest` を1回 走らせるたびに、
本当に尽きている日枠が「開いている」に化けます。**

そこから `queue_lag`・`live_slots`・`refresh_thumbnail`・`batch_build` が
いっせいに撃ち、**全部 403 で落ちて、また閉じる。**
2026-08-27 のこの窓で 403 を **29回** 観測しているのは、その往復です
（尽きた時点で降りていれば 1回 で済みます）。

## 覆る条件

本物の帳面へ**わざと**書く検査が要るなら `YT_QUOTA_LEDGER_WRITE=1`。
そのときは理由を `docs/JOURNAL.md` に。
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config, upload_cap  # noqa: E402

NOW = datetime(2026, 8, 27, 8, 0, tzinfo=timezone.utc)


def _real_ledger_lines() -> int:
    p = ROOT / upload_cap.DAY_QUOTA_HITS
    if not p.exists():
        return 0
    return len(p.read_text(encoding="utf-8").splitlines())


def test_note_quota_ok_は本物の帳面に書かない():
    before = _real_ledger_lines()
    upload_cap.note_quota_ok(now=NOW, detail="videos.update vid1")
    assert _real_ledger_lines() == before, (
        "**検査が本物の `data/day_quota.jsonl` に書いています。**"
        " その1行が `day_quota().open` を True に化けさせます（このファイルの冒頭）")


def test_note_quota_hit_も本物の帳面に書かない():
    before = _real_ledger_lines()
    upload_cap.note_quota_hit(now=NOW, detail="videos.update vid1")
    assert _real_ledger_lines() == before


def test_差し替えた根なら今までどおり書ける(tmp_path, monkeypatch):
    """**`config.ROOT` を tmp へ向けた検査は、今までどおり通ること。**

    閉じているのは「本物の repo を指したまま書く」道だけです ——
    `tests/test_day_quota.py` の作法を壊しません。
    """
    monkeypatch.setattr(config, "ROOT", tmp_path)
    upload_cap.note_quota_ok(now=NOW, detail="videos.update v9")
    upload_cap.note_quota_hit(now=NOW, detail="videos.update v9")
    lines = (tmp_path / upload_cap.DAY_QUOTA_HITS).read_text(
        encoding="utf-8").splitlines()
    assert len(lines) == 2, "差し替えた根に書けていません"


def test_旗を立てれば本物にも書ける(tmp_path, monkeypatch):
    """**覆る条件**（`YT_QUOTA_LEDGER_WRITE`）が実際に効くこと。"""
    monkeypatch.setenv("YT_QUOTA_LEDGER_WRITE", "1")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    upload_cap.note_quota_ok(now=NOW, detail="videos.update v9")
    assert (tmp_path / upload_cap.DAY_QUOTA_HITS).exists()


def test_偽のokは日枠を開けてしまう(tmp_path, monkeypatch):
    """**この検査が、上の3件の「なぜ」です。**

    403 のあとに `ok` の行が1つ入るだけで、`day_quota().open` が
    False → **True** に反転します。
    """
    monkeypatch.setenv("YT_QUOTA_LEDGER_WRITE", "1")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    upload_cap.note_quota_hit(now=NOW, detail="videos.update 本物")
    assert upload_cap.day_quota(NOW).open is False, "403 を観測したのに開いています"
    later = datetime(2026, 8, 27, 8, 30, tzinfo=timezone.utc)
    upload_cap.note_quota_ok(now=later, detail="videos.update vid1")
    assert upload_cap.day_quota(later).open is True, (
        "この反転が起きないなら、上の3件は要りません。**その回はこの一式ごと外すこと**")
