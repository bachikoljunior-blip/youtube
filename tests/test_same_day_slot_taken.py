"""**きょうの枠が埋まっている回に、きょうへの `--move` を出さない／通さない。**

## 実物（2026-09-02・最適化の回。**印字と門の両方が素通りでした**）

オーナーが同じ日に固定その4（規則5）を足しています ——

    公開したら → **すぐ次の日の1本を作り始める** → 次の枠まで改善し続ける
               → **その日になったら、その日で予約して出す**

主実行はそのとおりに回っていました:

    09/02 13:00 JST  `a63FzIUV2wI` を公開（規則1 の枠は、これで埋まった）
    09/02 13:57 JST  次の日のぶん `MqQKSnbM0OI` を `--draft` で上げた（正しい）

そこへ `src/next_slot.draft_lines()` がこう印字していました:

    python scripts/reschedule.py --move MqQKSnbM0OI 2026-09-02T20:00

**撃つと 09/02 が 2本**（`src/house_rule.PUBLISH_PER_DAY = 1` に正面から反する）。
日付は `{t:%Y-%m-%d}` ＝ **いつ撃っても「きょう」**で、
**きょうの枠が空いているかを一度も見ていません**でした。

そして `--per-day` は `_clamp_per_day()` で締めてあるのに
（`--compact` / `--spread` / `batch_build` は全部そこを通る）、
**`--move` だけが素通り**でした。＝ `src/house_rule.py` 冒頭が名指ししている
「**言っている所と、している所が別**」の、暦の側の実例です。

## 発火を確かめてあること（**発火したことのない検査は検査ではない**）

- `test_taken_day_is_refused` … 埋まっている日への `--move` が拒まれる（発火）
- `test_empty_day_is_allowed` … 空いている日は通る（**常に拒む実装を落とす**）
- `test_printer_does_not_offer_today` … 印字が「きょう」を出さない（発火）
- `test_printer_offers_today_when_free` … 空いている回は出す（**常に黙る実装を落とす**）

**実際に踏んだ故障も1つ検査にしてあります**（`test_holders_key_is_id`）——
最初の `_day_holders()` は `r.get("video_id")` で引いており、
`dupes.ledger_rows()` が控えの `video_id` を **`id`** に写して返すので
**全行 None ＝ 門は一度も鳴らずに「空いています」と答えました。**

## 覆る条件

オーナーが規則1（1日1本）を外したら `house_rule.PUBLISH_PER_DAY` が動き、
ここの期待値も一緒に動きます（**どちらも同じ1か所を読んでいます**）。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import house_rule, next_slot  # noqa: E402
from scripts import reschedule  # noqa: E402

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 9, 2, 5, 0, tzinfo=timezone.utc)      # 09/02 14:00 JST


def _ledger(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "uploaded.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows),
                 encoding="utf-8")
    return p


def _published_today() -> dict:
    """**きょう 13:00 JST に出た1本**（`at` は既に過去）。"""
    return {"video_id": "a63FzIUV2wI", "title": "きょうの1本",
            "topic": "kouki", "at": "2026-09-02T04:00:00+00:00",
            "uploaded_at": "2026-09-01T04:00:00+00:00"}


def _draft() -> dict:
    """**予約を付けずに上げた下書き**（`at` も `retimed_at` も無い）。"""
    return {"video_id": "MqQKSnbM0OI", "title": "次の日のぶん",
            "topic": "gassan", "uploaded_at": "2026-09-02T04:57:15+00:00"}


# ---------------------------------------------------------------- 数える側

def test_today_count_includes_the_video_already_published(tmp_path):
    """**きょう既に公開した本も、きょうの枠を埋めています。**

    `calendar()` の `per_day` は `at > t` しか数えないので、
    **公開した直後の回ほど「きょうは空いている」と答えます。**
    """
    p = _ledger(tmp_path, [_published_today(), _draft()])
    assert next_slot.today_count(now=NOW, path=p) == 1
    assert next_slot.today_full(now=NOW, path=p) is True


def test_today_count_is_zero_when_nothing_is_placed(tmp_path):
    """**常に「埋まっている」と答える実装を落とすため。**"""
    p = _ledger(tmp_path, [_draft()])
    assert next_slot.today_count(now=NOW, path=p) == 0
    assert next_slot.today_full(now=NOW, path=p) is False


# ---------------------------------------------------------------- 印字の側

def test_printer_does_not_offer_today(tmp_path):
    """埋まっている回に `--move <きょう>` を印字しないこと（**発火**）。"""
    p = _ledger(tmp_path, [_published_today(), _draft()])
    out = "\n".join(next_slot.draft_lines(now=NOW, path=p))
    assert out, "下書きが在るのに1行も出ていません"
    assert "--move MqQKSnbM0OI 2026-09-02" not in out, \
        "きょうの枠は埋まっているのに、きょうへの `--move` を出しています（規則1 に反する手）"
    assert "2026-09-03T20:00" in out, "明日の日付を名指ししていません"
    assert "improve" in out, "きょうやること（規則3）を名指ししていません"


def test_printer_offers_today_when_free(tmp_path):
    """**常に黙る実装を落とすため。** 空いている回は、きょうへ入れろと言うこと。"""
    p = _ledger(tmp_path, [_draft()])
    out = "\n".join(next_slot.draft_lines(now=NOW, path=p))
    assert "--move MqQKSnbM0OI 2026-09-02" in out


# ---------------------------------------------------------------- 門の側

def _rows_for(monkeypatch, rows: list[dict]) -> None:
    """`dupes.ledger_rows()` の返りの形（`video_id` ではなく **`id`**）で差し替える。"""
    import src.dupes as dupes
    monkeypatch.setattr(
        dupes, "ledger_rows",
        lambda *a, **k: [{"id": r.get("video_id", ""), "title": r.get("title", ""),
                          "topic": r.get("topic", ""), "at": r.get("at"),
                          "uploaded_at": r.get("uploaded_at")} for r in rows])


def test_taken_day_is_refused(monkeypatch):
    """**埋まっている日への `--move` は、API を1回も呼ばずに拒むこと**（発火）。"""
    _rows_for(monkeypatch, [_published_today(), _draft()])
    got = reschedule._rule_blocks_move("MqQKSnbM0OI", "2026-09-02T20:00")
    assert got, "規則1 を破る `--move` が素通りしています"
    assert "a63FzIUV2wI" in "\n".join(got), "その日に居る本を名指ししていません"


def test_empty_day_is_allowed(monkeypatch):
    """**常に拒む実装を落とすため。** 空いている日は通すこと。"""
    _rows_for(monkeypatch, [_published_today(), _draft()])
    assert reschedule._rule_blocks_move("MqQKSnbM0OI", "2026-09-03T20:00") == []


def test_moving_a_video_within_its_own_day_is_allowed(monkeypatch):
    """**自分の枠は数えないこと**（時刻だけ動かす回を止めない）。"""
    _rows_for(monkeypatch, [_published_today()])
    assert reschedule._rule_blocks_move("a63FzIUV2wI", "2026-09-02T20:00") == []


def test_holders_key_is_id(monkeypatch):
    """**実際に踏んだ故障。** `video_id` で引くと全行 None ＝ 門が一度も鳴らない。"""
    _rows_for(monkeypatch, [_published_today()])
    assert reschedule._day_holders("2026-09-02") == ["a63FzIUV2wI"]


def test_gate_reads_the_one_source(monkeypatch):
    """**上限の出どころは `src/house_rule.py` の1か所。** 緩めたら門も緩むこと。"""
    _rows_for(monkeypatch, [_published_today(), _draft()])
    monkeypatch.setattr(house_rule, "PUBLISH_PER_DAY", 2)
    assert reschedule._rule_blocks_move("MqQKSnbM0OI", "2026-09-02T20:00") == []
