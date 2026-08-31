"""**検査は、本物の `data/uploaded.jsonl` に書かないこと**（2026-08-28 に踏んで足した）。

## 何が起きたか（**統計の汚れでは済みません**）

`pytest tests/ -q -k "day_cap or day_total or eta or density or supply or batch or status"`
（**637件・8分42秒・全部 緑**）を背景で走らせている最中に、
手元の `data/uploaded.jsonl` が書き換わりました。実測（`git diff` の3行）:

    WcTl11_5Khw  2026-09-30T00:30Z → **2026-08-28T12:00Z**（＝ 21:00 JST）
    cJw79xThyTY  2026-10-04T00:00Z → **2026-08-28T11:00Z**（＝ 20:00 JST）
    NEOkkCKHhSY  2026-09-29T22:30Z → **2026-08-28T13:00Z**（＝ 22:00 JST）

3本とも `#Shorts` で、移った先は **14:00〜21:00 JST の帯** ——
`docs/JOURNAL.md`（08/28 16:3x）の実測で **31本中 5本しか生存しない**帯です。
`data/queue_lag.jsonl` にも「moves: 30 / moves: 20」の約束が2行 入りました。

**そして `data/day_quota.jsonl` に `videos.update` の行は1つも増えていません** ——
**YouTube 側は動いておらず、控えだけが嘘になりました。**
push していれば、次の回は「9/30 の予約が今夜 21:00 に出る」と読み、
`--compact` も `live_slots` もその幻の埋まりの上で置き場所を決めます。

## なぜ「呼ぶ側で気をつける」ではないのか

`tests/conftest.py` の冒頭（2026-08-17）と
`tests/test_quota_ledger_not_written_by_tests.py`（2026-08-27）が、
**通算7回 踏んだ形**として同じことを書いています ——
「関係のない検査に『その帳面に気をつけろ』と約束させるのは無理なので、
書く側を機械で閉じる」。**`data/uploaded.jsonl` は、その掛かりに
入っていませんでした**（8件目）。

## 覆る条件

本物の控えへ**わざと**書く検査が要るようになったら `YT_LEDGER_WRITE=1`
（そのときは理由を `docs/JOURNAL.md` に）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config, dupes  # noqa: E402


def _real_ledger_bytes() -> bytes:
    p = ROOT / dupes.LEDGER
    return p.read_bytes() if p.exists() else b""


def _first_real_video_id() -> str | None:
    """本物の控えの、いちばん最初の `video_id`。**書けてしまうなら、この行が動きます。**"""
    import json
    p = ROOT / dupes.LEDGER
    if not p.exists():
        return None
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("video_id") and rec.get("at"):
            return rec["video_id"]
    return None


def test_retime_は本物の控えに書かない():
    vid = _first_real_video_id()
    if vid is None:
        return                            # 控えが空な環境では、この検査は何も言わない
    before = _real_ledger_bytes()
    got = dupes.retime(vid, "2030-01-01T00:00:00Z")
    after = _real_ledger_bytes()
    assert after == before, (
        "**検査が本物の `data/uploaded.jsonl` を書き換えています。**"
        " YouTube 側は動かないので、控えだけが嘘になります（このファイルの冒頭）")
    assert got is False, "書かなかったのに True を返しています（呼ぶ側が誤解します）"


def test_compact_ledger_も本物の控えに書かない():
    before = _real_ledger_bytes()
    dupes.compact_ledger()
    assert _real_ledger_bytes() == before, (
        "**`compact_ledger()` が本物の控えを書き換えています。**"
        " 重複の落とし方は正しくても、検査の走りで消えてよい行ではありません")


def test_queue_lagの約束も本物の帳面に書かない():
    """**この1行が入ると、本物の手が「もう撃った」に化けます**（`stuck_lines`）。"""
    sys.path.insert(0, str(ROOT / "scripts"))
    import queue_lag                                            # noqa: PLC0415

    p = ROOT / "data" / "queue_lag.jsonl"
    before = p.read_bytes() if p.exists() else b""
    queue_lag._note_apply({}, {}, 3)
    after = p.read_bytes() if p.exists() else b""
    assert after == before, (
        "**検査が本物の `data/queue_lag.jsonl` に約束を書いています。**"
        " `stuck_lines()` はそれを読んで「前の --apply が動いていない」と答えます")


def test_差し替えた控えには今までどおり書ける(tmp_path, monkeypatch):
    """**塞いだのは本物だけ。** `config.ROOT` を差し替えた検査は通ること。"""
    import json

    (tmp_path / "data").mkdir()
    led = tmp_path / dupes.LEDGER
    led.write_text(json.dumps(
        {"video_id": "aaa", "topic": "t", "title": "x",
         "at": "2026-09-30T00:30:00Z"}, ensure_ascii=False) + "\n",
        encoding="utf-8")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    assert dupes.retime("aaa", "2026-10-01T00:30:00Z") is True
    assert "2026-10-01T00:30:00Z" in led.read_text(encoding="utf-8")


def test_旗を立てれば本物にも書ける(tmp_path, monkeypatch):
    """**覆る条件が、実際に効くこと**（`YT_LEDGER_WRITE=1`）。"""
    monkeypatch.setenv("YT_LEDGER_WRITE", "1")
    assert dupes._may_write_ledger(ROOT) is True
