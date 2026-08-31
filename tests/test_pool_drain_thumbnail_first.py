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
    monkeypatch.setattr(pool_drain, "pool",
                        lambda now=None, rows=None: [
                            {"id": "keep",
                             "at": pool_drain.datetime(2026, 9, 2, 4, 0, tzinfo=utc),
                             "title": "keep", "topic": "t"},
                            {"id": "drop",
                             "at": pool_drain.datetime(2026, 9, 3, 4, 0, tzinfo=utc),
                             "title": "drop", "topic": "t"},
                        ])
    monkeypatch.setattr(pool_drain, "thumbnail_first", lambda now=None: "NEXT1")

    def _thumb(video_id: str) -> int:
        order.append(f"thumb:{video_id}")
        if thumb_raises:
            raise RuntimeError("控えが無い")
        return thumb_rc

    monkeypatch.setattr(pool_drain, "_push_thumbnail_first", _thumb)
    monkeypatch.setattr(pool_drain.uploader, "_service", lambda: object())
    monkeypatch.setattr(pool_drain.uploader, "base_status", lambda: {})
    monkeypatch.setattr(pool_drain.reschedule, "_update",
                        lambda svc, vid, at, fallback_status=None:
                        order.append(f"update:{vid}"))
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
