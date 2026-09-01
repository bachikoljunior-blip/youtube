"""**池化より先に残すのは、サムネイル 50単位 だけではありません。**

## なぜ要るか（2026-09-01 22:2x に踏んだ。**同じ形の2度目**）

`pool_drain.thumbnail_first()` は 2026-09-01 に足された順番の門で、
「**次に公開される本のサムネイルが載っていない**」ときだけ 50単位 を先に押します。
**サムネイルが既に載っている本には、空文字を返します。**

`improve` のもう1つの道 —— **焼き直して差し替える**
（`--unschedule` → `--move` ＝ `videos.update` ×2 ＝ **100単位**）—— は
その門の外でした。実測 2026-09-01 の窓（16:00 JST 起点）:

    16:0x  `refresh_thumbnail` 50単位（**上の門は正しく効いた**）
    16:0x  `pool_drain --apply` で 160本 ＝ 窓ぜんぶ（12,258 / 10,000単位）
    結果   次の枠 `a63FzIUV2wI`（09/02 13:00 公開）は、焼いたあとに入った
           **6件 が1つも入らないまま**出ます

**その本のサムネイルは載っていました。** だから門は何も言いませんでした。
1度目（08/31）は 50単位、2度目（09/01）は 100単位。**同じ所で2回。**

## 何を守るか

- **残す形であって、止める形ではありません**（`thumbnail_first` の註 ——
  止めると、押せない事情が1つでもあれば池化が永久に止まり、
  `first_breach()` の締切が動かない）
- **間に合わない本には残しません。** `next_slot.window_reaches()` が `False`
  なら差し替えはもう撃てないので、残すと**誰にも使われない取り置き**になります
  （`upload_cap.RESERVE_UNITS` がまさにその形 —— 取り置きを、取り置かれている
  相手自身が通れない）
- **帳面が読めない回は減らしません**（推測で締切を遅らせない）
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import pool_drain  # noqa: E402
from src import next_slot  # noqa: E402

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 9, 1, 13, 0, tzinfo=timezone.utc)      # 09/01 22:00 JST
FAR = datetime(2026, 9, 3, 13, 0, tzinfo=JST)               # 枠が戻った後に出る本
SOON = datetime(2026, 9, 2, 13, 0, tzinfo=JST)              # 枠が戻る前に出る本


def _slot(monkeypatch, *, at, commits: int) -> None:
    monkeypatch.setattr(next_slot, "next_video",
                        lambda *a, **k: {"video_id": "vid1",
                                         "uploaded_at": "2026-08-26T04:27:00+09:00",
                                         "_at": at})
    monkeypatch.setattr(next_slot, "stale_commits",
                        lambda *a, **k: ["c" + str(i) for i in range(commits)])


def test_差し替えの要る本は_名前で返る(monkeypatch) -> None:
    _slot(monkeypatch, at=FAR, commits=6)
    monkeypatch.setattr(next_slot, "window_reaches", lambda *a, **k: True)
    assert pool_drain.swap_reserve(NOW) == ("vid1", 6)


def test_焼き直しても同じ物が出る本には_残さない(monkeypatch) -> None:
    """`stale_commits()` が空 ＝ 差し替える意味がありません。"""
    _slot(monkeypatch, at=FAR, commits=0)
    monkeypatch.setattr(next_slot, "window_reaches", lambda *a, **k: True)
    assert pool_drain.swap_reserve(NOW) is None


def test_枠が間に合わない本には_残さない(monkeypatch) -> None:
    """**誰にも使われない取り置きを作らないこと**（`RESERVE_UNITS` がその形）。"""
    _slot(monkeypatch, at=SOON, commits=6)
    monkeypatch.setattr(next_slot, "window_reaches", lambda *a, **k: False)
    assert pool_drain.swap_reserve(NOW) is None


def test_分からない回は_残す側へ倒す(monkeypatch) -> None:
    """`None` ＝ 分からない。**倒す先は「残す」**（早く消える側へ倒さない）。"""
    _slot(monkeypatch, at=SOON, commits=6)
    monkeypatch.setattr(next_slot, "window_reaches", lambda *a, **k: None)
    assert pool_drain.swap_reserve(NOW) == ("vid1", 6)


def test_残りが足りない回は_外す本を減らす(monkeypatch) -> None:
    """**100単位 ＝ 2本ぶん**（`UNITS_PER_VIDEO` 51）。"""
    from src import quota_ledger

    # 残り 306単位（10,000 - 9,694）。差し替えの 100 を引くと 206 ＝ 4本ぶん。
    monkeypatch.setattr(quota_ledger, "spent", lambda *a, **k: {"data": 9_694})
    drop = [{"id": f"v{i}"} for i in range(10)]
    kept, held = pool_drain._trim_for_swap(drop, NOW)
    assert len(kept) == 4, "差し替えのぶんを残していません"
    assert held == 6


def test_枠が余っている回は_1本も減らさない(monkeypatch) -> None:
    """**止める門ではありません。** 足りているなら、池化はそのまま進む。"""
    from src import quota_ledger

    monkeypatch.setattr(quota_ledger, "spent", lambda *a, **k: {"data": 0})
    drop = [{"id": f"v{i}"} for i in range(10)]
    kept, held = pool_drain._trim_for_swap(drop, NOW)
    assert kept == drop
    assert held == 0


def test_もう残っていない回は_減らさない(monkeypatch) -> None:
    """**空にしても差し替えは撃てません。** 池化の締切だけが遅れます。"""
    from src import quota_ledger

    monkeypatch.setattr(quota_ledger, "spent",
                        lambda *a, **k: {"data": quota_ledger.DAY_UNITS + 1})
    drop = [{"id": f"v{i}"} for i in range(10)]
    kept, held = pool_drain._trim_for_swap(drop, NOW)
    assert kept == drop
    assert held == 0


def test_帳面が読めない回は_減らさない(monkeypatch) -> None:
    """**推測で締切を遅らせないこと**（`first_breach()` に締切があります）。"""
    from src import quota_ledger

    def boom(*a, **k):
        raise RuntimeError("帳面が読めない（テスト）")

    monkeypatch.setattr(quota_ledger, "spent", boom)
    drop = [{"id": f"v{i}"} for i in range(10)]
    kept, held = pool_drain._trim_for_swap(drop, NOW)
    assert kept == drop
    assert held == 0


def test_判定を書き直していない() -> None:
    """**出どころは1か所**（`src/next_slot`）。2つの答えを作らないこと。"""
    src = (ROOT / "scripts" / "pool_drain.py").read_text(encoding="utf-8")
    body = src[src.index("def swap_reserve("):src.index("def _trim_for_swap(")]
    for name in ("next_video", "stale_commits", "window_reaches"):
        assert f"next_slot.{name}" in body or f"next_slot._parse" in body, name
    assert "git log" not in body, (
        "**判定をここで書き直しています。** `src/next_slot` を呼ぶこと")


def test_外す口が在る() -> None:
    """**外した回は理由を JOURNAL に**（`--no-thumbnail-first` と同じ扱い）。"""
    src = (ROOT / "scripts" / "pool_drain.py").read_text(encoding="utf-8")
    assert "--no-swap-reserve" in src
