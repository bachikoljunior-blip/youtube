"""**口に在って控えに無い予約が、控えへ入ること。**（2026-09-01・穴の後ろ半分）

## 何が起きたか（事実だけ）

2026-09-01 16:33 JST、オーナーの YouTube Studio に **09/01 の 18:00 / 19:00 /
20:00 / 21:00 の予約が4本**出ていました。**`data/uploaded.jsonl` には、
その4本が1行もありません** —— `at` に `2026-09-01` を持つ行は 22:00 の1本だけで、
過去の行を全部たどっても（738本ぶん）09/01 の予約は1件も出てきませんでした。

`scripts/pool_drain.py` は**控えだけ**を読みます（口は 400本で頭打ちになるので、
そう決めてあります）。だから **口に在って控えに無い予約は、外す一覧に永久に出ません。**
`--apply` を何度 撃っても当たらないまま、その日のうちに公開されます
（規則1・1日1本が破れます）。

## なぜ `retime()` では塞がらなかったか

`src.dupes.retime()` は**既にある行を書き換えるだけ**です。控えが名前すら
知らない動画には当たらず `False` を返して終わります —— **足す口が、
どこにも無かった**のがこの穴の正体です。

## この検査が押さえているもの

    1. 口が返した予約のうち、控えが知らない本が**足される**こと
    2. 足した本が `pool_drain.pool()` の一覧に**出る**こと
       （＝ `--apply` の前に必ず見える）
    3. 控えが知っている本は、口の時刻へ**書き換わる**こと（二重に足さない）
    4. `uploaded_at` を**でっち上げない**こと（作った日は知らない）

**戻すにはこの検査を消すしかありません。**
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

import pool_drain  # noqa: E402
from src import config, dupes  # noqa: E402

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 9, 1, 16, 33, tzinfo=JST).astimezone(timezone.utc)


@pytest.fixture()
def ledger(tmp_path, monkeypatch):
    """**本物の控えへは書きません**（`_may_write_ledger` と同じ姿勢）。"""
    monkeypatch.setattr(config, "ROOT", tmp_path)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    path = tmp_path / dupes.LEDGER
    path.write_text("", encoding="utf-8")
    return path


def _rows(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def test_控えが知らない予約は足される(ledger):
    mouth = [{"id": "TODAY18", "at": "2026-09-01T09:00:00Z",
              "title": "18時の1本", "topic": "t1"}]
    got = dupes.observe_scheduled(mouth)
    assert got["added"] == ["TODAY18"], (
        f"{got} —— **口に在って控えに無い予約が足されていません。**\n"
        "  `retime()` は既にある行しか書き換えません（足す口が無いのが穴です）。"
    )
    rec = _rows(ledger)[0]
    assert rec["video_id"] == "TODAY18" and rec["at"] == "2026-09-01T09:00:00Z"
    assert "uploaded_at" not in rec or rec["uploaded_at"] is None, (
        "作った日を知らないのに書いています。**知らないことを、"
        "知っているように書かないこと。**"
    )


def test_足した本が池の一覧に出る(ledger):
    """**`--apply` の前に必ず見えること。** ここが目的そのものです。"""
    dupes.observe_scheduled([{"id": "TODAY18", "at": "2026-09-01T09:00:00Z",
                              "title": "18時の1本", "topic": "t1"}])
    ids = [r["id"] for r in pool_drain.pool(now=NOW, rows=dupes.ledger_rows())]
    assert ids == ["TODAY18"], (
        f"池の一覧が {ids} です。**足したのに一覧へ出ていません** ——"
        " `house_rule.is_stockpile()` は「作った日が分からない未来の予約 ＝"
        " 作り置き」と読むはずです。"
    )


def test_知っている本は書き換える_二重に足さない(ledger):
    ledger.write_text(json.dumps(
        {"video_id": "KNOWN", "topic": "t", "title": "既にある本",
         "at": "2026-09-20T04:00:00Z",
         "uploaded_at": "2026-08-20T00:00:00+00:00"}, ensure_ascii=False) + "\n",
        encoding="utf-8")
    got = dupes.observe_scheduled([{"id": "KNOWN", "at": "2026-09-01T10:00:00Z",
                                    "title": "既にある本", "topic": "t"}])
    assert got["added"] == [] and got["retimed"] == ["KNOWN"]
    rows = _rows(ledger)
    assert len(rows) == 1, f"行が {len(rows)} 本に増えています（幻の埋まりが残ります）"
    assert rows[0]["at"] == "2026-09-01T10:00:00Z"


def test_同じ口を二度読んでも増えない(ledger):
    mouth = [{"id": "TODAY18", "at": "2026-09-01T09:00:00Z",
              "title": "18時の1本", "topic": "t1"}]
    dupes.observe_scheduled(mouth)
    again = dupes.observe_scheduled(mouth)
    assert again["added"] == [] and len(_rows(ledger)) == 1


def test_時刻の無い行は足さない(ledger):
    """`at` の無い本（予約ではない private）は、この口の話ではありません。"""
    dupes.observe_scheduled([{"id": "DARK", "at": None, "title": "暗い本"}])
    assert _rows(ledger) == []
