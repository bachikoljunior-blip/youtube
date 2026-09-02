"""**池化より先に、次に公開される本のサムネイルを押すこと。**（2026-09-01 に踏んだ）

## 実測（2026-08-31 の窓・`python -m src.quota_ledger`）

    reschedule.py:_update          **9,668単位**  ← `pool_drain --apply`
    history.py:channel_video_ids    3,409単位
    thumbnails.set                     50単位（**1回だけ**・別の本）

同じ窓で、**09/01 22:00 JST に公開される `UIWHsypOPPg` は
`thumbnail_set: false` のまま**でした。要ったのは **50単位**、
その窓で焼けたのは **13,388単位**。**0.4% が取れませんでした。**

## この順番は、3か所に書いてありました

    docs/trigger_main.md §2.6
    retro.py の申し送り「16:00 JST 以降の窓の回は、
      `refresh_thumbnail --video <次の1本>` を **`reschedule` より先に**」
    scripts/refresh_thumbnail.py の `only_video` の註

**3つとも「次に来た側が覚えていること」に頼っています。**
`batch_build.slots()`:「**人の記憶と手写しに依存する門は、この輪では
毎回落ちる側**」。だから門を、単位を焼く側（`pool_drain`）へ移しました。

## この検査が押さえていること

1. 次に公開される本のサムネイルが載っていなければ、`thumbnail_first()` が
   **その本を名指しする**（**API 0単位**。控えと `git log` しか読みません）
2. 載っていれば **空文字**（余計な 50単位 を使わない）
3. `--apply` の道で、**サムネイルの押し込みが `reschedule._update` より前**に来る
4. **押せなくても池化は止まらない**（池化には締切がある ——
   `first_breach()`: 規則1 が最初に破れるのは 2026-09-12）

**戻すにはこの検査を消すしかありません。**
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import pool_drain  # noqa: E402
from src import next_slot  # noqa: E402


def test_次に公開される本のサムネが無ければ名指しする(monkeypatch):
    monkeypatch.setattr(next_slot, "next_video", lambda now=None: {"video_id": "AAA"})
    monkeypatch.setattr(next_slot, "pending_thumbnail", lambda vid: vid == "AAA")
    assert pool_drain.thumbnail_first() == "AAA"


def test_サムネが載っていれば名指ししない(monkeypatch):
    monkeypatch.setattr(next_slot, "next_video", lambda now=None: {"video_id": "AAA"})
    monkeypatch.setattr(next_slot, "pending_thumbnail", lambda vid: False)
    assert pool_drain.thumbnail_first() == ""


def test_次の1本が無ければ名指ししない(monkeypatch):
    monkeypatch.setattr(next_slot, "next_video", lambda now=None: None)
    assert pool_drain.thumbnail_first() == ""


def _stub_apply(monkeypatch, order: list, *, thumb_rc: int = 0,
                thumb_raises: bool = False):
    """`--apply` の道を、API を1単位も使わずに通す。**順番だけを見ます。**"""
    utc = pool_drain.timezone.utc
    # **日付は `now` からの相対**（2026-09-03 に直した）—— 固定の 09/02・09/03 04:00Z で
    # 書かれていて、09/03 JST になった日に `plan()` の「きょう以前は外さない」
    # （規則5）に両方とも入り、`order == []` で赤になった。**この検査が見るのは
    # 順番だけ**なので、外される側（明日以降）に2本 置ければ足りる。
    base = pool_drain.datetime.now(utc).replace(hour=4, minute=0, second=0, microsecond=0)
    d1 = base + pool_drain.timedelta(days=1)
    d2 = base + pool_drain.timedelta(days=2)
    monkeypatch.setattr(pool_drain, "pool",
                        lambda now=None, rows=None: [
                            {"id": "keep", "at": d1, "title": "keep", "topic": "t"},
                            {"id": "drop", "at": d2, "title": "drop", "topic": "t"},
                        ])
    monkeypatch.setattr(pool_drain, "thumbnail_first", lambda now=None: "NEXT1")
    # **この作り物の予約に穴はありません**（09/02・09/03 の2本 ＝ 1日1本）。
    # `_calendar_hold()` は `pool` ではなく `data/uploaded.jsonl` を読むので、
    # 揃えないと**実物の暦（この日は 19日 連続の空白）で止まります**
    # —— 門そのものは `tests/test_pool_drain_calendar_hold.py` が見ます。
    monkeypatch.setattr(pool_drain, "_calendar_hold", lambda: [])

    def _thumb(video_id: str) -> int:
        order.append(f"thumb:{video_id}")
        if thumb_raises:
            raise RuntimeError("控えが無い")
        return thumb_rc

    monkeypatch.setattr(pool_drain, "_push_thumbnail_first", _thumb)
    monkeypatch.setattr(pool_drain.uploader, "_service", lambda: object())
    monkeypatch.setattr(pool_drain.uploader, "base_status", lambda: {})
    # **`report=` を受けること**（2026-09-02）—— `_update` は `False` の
    #   2つの意味（"same" ＝ 実物はもうその値／"move_hold" ＝ 撃っていない）を
    #   そこへ入れて返し、掃きは**前者のときだけ控えを直します**。
    def _stub_update(svc, vid, at, fallback_status=None, report=None):
        order.append(f"update:{vid}")
        if report is not None:
            report.update({"wrote": True, "reason": "wrote"})
        return True

    monkeypatch.setattr(pool_drain.reschedule, "_update", _stub_update)
    monkeypatch.setattr(pool_drain.dupes, "retime", lambda vid, at: None)


def test_サムネイルは_reschedule_の書き込みより先(monkeypatch):
    order: list[str] = []
    _stub_apply(monkeypatch, order)
    pool_drain.main(["--apply", "--no-inbox"])
    assert order and order[0] == "thumb:NEXT1", order
    assert "update:drop" in order
    assert order.index("thumb:NEXT1") < order.index("update:drop")


@pytest.mark.parametrize("kwargs", [{"thumb_rc": 1}, {"thumb_raises": True}])
def test_サムネイルが押せなくても池化は進む(monkeypatch, kwargs):
    """**止める形にしないこと。** 池化には締切があります（09/12・238本 多い）。"""
    order: list[str] = []
    _stub_apply(monkeypatch, order, **kwargs)
    pool_drain.main(["--apply", "--no-inbox"])
    assert "update:drop" in order, order


def test_外す口がある(monkeypatch):
    """`--no-thumbnail-first` で外せること（外した回は理由を JOURNAL に）。"""
    order: list[str] = []
    _stub_apply(monkeypatch, order)
    pool_drain.main(["--apply", "--no-inbox", "--no-thumbnail-first"])
    assert not any(o.startswith("thumb:") for o in order), order
    assert "update:drop" in order
