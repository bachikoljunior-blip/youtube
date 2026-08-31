"""**「天井」と呼ぶ数が、何本の反証に耐えたかを持っていること**（2026-08-31）。

## この検査が持っている主題

`scripts/eta.py` の `residual_gap()` は、自分でこう書いています ——
「**『届きません』を作っているのは、この2つの未実測の定数です**」。
その片方が `per_video` の天井 **1,891**、つまり **標本の最大**です。

**標本の最大を「天井」と呼ぶのは、ふつうは誤りです。**
裾の重い分布では、最大は本数と一緒に伸び続けます ——
「天井」ではなく「まだ大きいのを引いていない」だけのことがあります。

**この機械は、その反論に答える数を1つも持っていませんでした。**
`per_video_best()` は `best / n / mean / median / settled / censor` を返しますが、
**その記録がいつ立ったか**は返していませんでした。

## 実測（2026-08-31・`data/views.jsonl` だけ・API 0単位）

    ショート  n=156  記録 1,891 は **17本目**で立ち、そのあと **139本** が抜けていない
    長尺      n=22   記録   156 は **13本目**で立ち、そのあと **9本** だけ

**この差が、この検査の主題です。** ショートの天井は 139回 反証にかけられて
生き残っており、長尺の天井は 9回 しか挑まれていません。
**同じ「天井」という字で、確からしさが桁で違います。**

## 見ている3点

1. **数が返っていること**（`record_rank` / `tested_by`）
2. **記録が最後に立った本なら `tested_by` は 0**（＝ 一度も反証にかかっていない）
3. **順は公開の順**であること（views の大きい順に数えると、記録は必ず 1本目になる）

**緩めないこと。** ここが消えると、天井の確からしさを誰も見なくなります。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src import form_record


def _write(path: Path, rows: list[tuple[str, str, float, int]]) -> None:
    """`(id, at, hours, views)` を書く。"""
    path.write_text(
        "\n".join(json.dumps({"id": i, "at": a, "hours": h, "views": v})
                  for i, a, h, v in rows) + "\n", encoding="utf-8")


def _at(day: int, hours_old: float) -> str:
    """`hours_old` 前に世に出た本を、`day` 日目に観測した時刻。"""
    return (datetime(2026, 8, day) ).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_記録が何本目で立ったかを返す(tmp_path: Path):
    """**1・3 の検査。** 公開の順で数えること（views の順ではない）。

    3本の長尺を、公開の順に a → b → c で置きます。**記録は真ん中の b**。
    正しく数えれば `record_rank=2` / `tested_by=1`。
    **views の大きい順で数える実装なら `record_rank=1` / `tested_by=2`** になります。
    """
    views = tmp_path / "views.jsonl"
    forms = {"aaaaaaaaaaa": "長尺", "bbbbbbbbbbb": "長尺", "ccccccccccc": "長尺"}
    # 観測はすべて同じ時刻。年齢が大きいほど、先に世に出ている
    obs = "2026-08-20T00:00:00Z"
    _write(views, [
        ("aaaaaaaaaaa", obs, 300.0, 10),    # いちばん古い
        ("bbbbbbbbbbb", obs, 200.0, 99),    # **記録**（2本目）
        ("ccccccccccc", obs, 100.0, 20),    # いちばん新しい
    ])
    form_record.censor_memo_clear()
    r = form_record.per_video_best(views_path=views, forms=forms)["長尺"]

    assert r["best"] == 99 and r["id"] == "bbbbbbbbbbb"
    assert r["record_rank"] == 2, (
        f"記録は公開の順で **2本目**のはずですが {r['record_rank']} です。"
        " **再生の大きい順で数えていませんか** —— それだと記録は必ず 1本目になり、"
        "`tested_by` は『そのあとの全部』になります（意味が反転します）"
    )
    assert r["tested_by"] == 1, (
        f"記録のあとに出たのは 1本 のはずですが {r['tested_by']} です"
    )


def test_記録が最後の本なら_反証は0(tmp_path: Path):
    """**2 の検査。** いちばん新しい本が記録なら、**まだ一度も挑まれていない**。

    ここが 0 を返さない実装は、「天井が更新された直後」を
    「よく確かめられた天井」と同じ顔で出します。**いちばん危ない誤り**です。
    """
    views = tmp_path / "views.jsonl"
    forms = {"aaaaaaaaaaa": "長尺", "bbbbbbbbbbb": "長尺"}
    obs = "2026-08-20T00:00:00Z"
    _write(views, [
        ("aaaaaaaaaaa", obs, 300.0, 10),
        ("bbbbbbbbbbb", obs, 100.0, 99),    # **いちばん新しくて、記録**
    ])
    form_record.censor_memo_clear()
    r = form_record.per_video_best(views_path=views, forms=forms)["長尺"]
    assert r["tested_by"] == 0, (
        f"いちばん新しい本が記録なのに `tested_by={r['tested_by']}` です。"
        " **更新された直後の天井は、一度も反証にかかっていません。**"
        " そこを 0 で言わないと、読む側は確かめられた天井と区別できません"
    )


def test_実データの2つの形で_確からしさが桁で違う():
    """**この節が在る理由そのもの。** 数が出ていることと、形で違うことを見ます。

    **絶対値では縛りません**（本が増えれば動きます）。見るのは
    「**両方の形で数が出ていること**」と「**その2つが同じではないこと**」だけ。
    """
    if not form_record.VIEWS.exists():
        pytest.skip("`data/views.jsonl` がありません")
    form_record.censor_memo_clear()
    recs = form_record.per_video_best()
    got = {f: r.get("tested_by") for f, r in recs.items()}
    if len(got) < 2 or any(v is None for v in got.values()):
        pytest.skip(f"両方の形の `tested_by` がまだ出ません: {got}")
    assert len(set(got.values())) > 1, (
        f"2つの形の `tested_by` が同じです: {got}。"
        " **形ごとに数えていない可能性**があります"
    )
