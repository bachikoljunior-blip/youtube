"""**作り置きを「そろう日」の材料にしないこと**（規則2・2026-09-01・最適化の回）。

## なぜ要るか（実物で踏んだ）

`src/reveal_hold.next_ready()` は「予約表から」その群が `need` 本 そろう日を
出します。**その予約表は、規則2 が外す本でできていました。**

実測 2026-09-01: 控えの未来の予約 **293本 は 293本 とも作り置き**
（`house_rule.is_stockpile`・作り置きでない未来の予約は **0本**）。
それでも `scripts/status.py` はこう印字していました:

    あと **10本**  完成形の保持-16本（いま 6 / 要る 16）
        … ／ **予約表では 2026-09-02 にそろう**

**規則2 の下では、その本は `pool_drain --apply` が外します**（1本も公開されない）。
**「明日そろう」と読んだ回は、何もしないのが正解だと読みます。**

`src/judgeable.members()` は 2026-08-31 に同じ絞りを入れています
（「作り置きの予約は、床に数えません」）。**同じ台帳を読む2つ目の入口だけが、
その絞りを持っていませんでした。**

**この回の実測では、答えの日付は動きません**（処置は 08/30〜08/31 に公開ずみの
10本 でちょうど 16本 に届き、落ちたのは 09/24 以降の作り置き 6本）。
**動かないうちに塞ぐのが安いので、ここに検査を置きます。**

**覆る条件**: オーナーが規則2 を外したら（`house_rule.STOCKPILE_IS_SUPPLY`）、
`is_stockpile()` が全部 `False` を返すので、この検査は自然に緩みます ——
そのときはこのファイルごと落とすこと。
"""
from __future__ import annotations

from datetime import datetime, timezone

from src import reveal_hold


def _row(vid: str, at: str, made: str) -> dict:
    return {"video_id": vid, "at": at, "uploaded_at": made, "duration_s": 40.0}


NOW = datetime(2026, 9, 1, 3, 0, tzinfo=timezone.utc)


def test_作り置きだけではそろう日が出ない():
    """規則より前に作った未来の予約は、**1本も公開されません**。"""
    rows = [_row(f"S{i}", f"2026-09-2{i}T04:00:00Z", "2026-08-25T04:00:00Z")
            for i in range(1, 7)]
    side = reveal_hold.side_of(rows[0])
    assert reveal_hold.next_ready(4, now=NOW, rows=rows, side=side) is None


def test_規則の下で作った予約は材料にする():
    """**落とすのは作り置きだけ。** 規則の下で作った本まで落とすと供給が消えます
    （`house_rule.is_stockpile` の docstring と同じ理由）。"""
    rows = [_row(f"N{i}", f"2026-09-0{i + 1}T04:00:00Z", "2026-09-01T04:00:00Z")
            for i in range(1, 5)]
    side = reveal_hold.side_of(rows[0])
    assert reveal_hold.next_ready(4, now=NOW, rows=rows, side=side) is not None


def test_絞りの出どころは規則の1か所():
    """同じ絞りを2か所に書かないこと（`src/judgeable._live_ids()` と同じ姿勢）。"""
    src = (reveal_hold.__file__)
    text = open(src, encoding="utf-8").read()
    assert "house_rule.is_stockpile" in text or "house_rule" in text
    assert "STOCKPILE_SINCE" not in text, (
        "規則の日付を写しています。`house_rule.is_stockpile()` を呼ぶこと")
