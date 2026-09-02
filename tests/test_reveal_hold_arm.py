"""**門は「行」ではなく「比べられる本」を数えること。**（2026-08-31 に踏んだ）

`config/hypotheses.yaml` の「完成した図を説明のあいだ画面に残すと engaged が
上がる」の `count_expr` は `rows('uploaded.jsonl')` を数えていました。
**`data/uploaded.jsonl` は1本につき1行ではありません**（実測 850行 / 735本 ——
予約を動かすたびに行が増える。`KfQeYEJwL7Q` だけで4行）。

    式の答え          **17** → `deadline_check` は「要 16 ／ いま 17 → 足りています」
    本で畳むと        **11**
    うちショート       **8**（長尺は `pipeline.reveal_variants` を通らない）
    齢48時間 を超えた  **1** ← `falsified_if` が比べられるのはこれだけ

そこから `ready_by_claim()` → `arm_speed.next_close()` → `scripts/eta.py` の
頭3行「**この回は `verdict` で日付が動かせます**」まで通ります。
**頭3行しか読まない回は、処置1本で前提を閉じ、到達日が在りもしないデータで動きます。**

同じ形の穴は 2026-08-29 に `deadline_check.deep_short_arm()` で1度 塞がれています。
**これが2件目なので、ここでは前提1件ではなく「台帳ぜんぶ」に門を置きます。**
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from src import reveal_hold

ROOT = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)


def _row(vid: str, built: str, at: str, dur: float | None) -> dict:
    r = {"video_id": vid, "uploaded_at": built, "at": at}
    if dur is not None:
        r["duration_s"] = dur
    return r


# ---------------------------------------------------------------- 数え方の側

def test_同じ本の行を何度も数えないこと() -> None:
    """予約を動かした本は控えに何行も残ります。**畳んで1本。**"""
    rows = [
        _row("a", "2026-08-28T00:00:00+00:00", "2026-08-28T00:00:00Z", 30.0),
        _row("a", "2026-08-28T00:00:00+00:00", "2026-08-28T00:00:00Z", 30.0),
        _row("a", "2026-08-28T00:00:00+00:00", "2026-08-28T00:00:00Z", 30.0),
    ]
    got = reveal_hold.comparable(NOW, rows)
    assert got["処置"] == ["a"], f"行で数えています: {got}"


def test_長尺は処置群に入れないこと() -> None:
    """長尺は `reveal_variants` を1度も通りません（対照と中身が同じ）。"""
    rows = [
        _row("short", "2026-08-28T00:00:00+00:00", "2026-08-28T00:00:00Z", 30.0),
        _row("long", "2026-08-28T00:00:00+00:00", "2026-08-28T01:00:00Z", 300.0),
    ]
    got = reveal_hold.comparable(NOW, rows)
    assert got["処置"] == ["short"], f"長尺が混ざっています: {got}"


def test_齢48時間に届かない本は比べないこと() -> None:
    """`falsified_if` は「**齢48時間でそろえた**」と書いています。"""
    young = (NOW - timedelta(hours=5)).isoformat().replace("+00:00", "Z")
    rows = [_row("y", "2026-08-28T00:00:00+00:00", young, 30.0)]
    assert reveal_hold.comparable(NOW, rows)["処置"] == []


def test_尺の分からない本は数えないこと() -> None:
    """満ちていないものを満ちたと言うより、**遅れて満ちるほうが安全**。"""
    rows = [_row("u", "2026-08-28T00:00:00+00:00", "2026-08-28T00:00:00Z", None)]
    assert reveal_hold.comparable(NOW, rows)["処置"] == []


def test_群は作った時刻で割ること_公開時刻ではない() -> None:
    """処置かどうかを決めるのは `uploaded_at`。**同じ日に公開された対照が居ます。**"""
    rows = [
        _row("new", "2026-08-28T00:00:00+00:00", "2026-08-28T02:00:00Z", 30.0),
        _row("old", "2026-08-20T00:00:00+00:00", "2026-08-28T03:00:00Z", 30.0),
    ]
    got = reveal_hold.comparable(NOW, rows)
    assert got["処置"] == ["new"] and got["対照"] == ["old"]
    days = reveal_hold.paired_days(NOW, rows)
    assert len(days) == 1, f"同じ日の対が作れていません: {days}"


def test_同じ日の中で対にすること() -> None:
    """日で割らないと「新しい日は本数が少なかっただけ」が差として残ります。"""
    rows = [
        _row("n1", "2026-08-28T00:00:00+00:00", "2026-08-28T02:00:00Z", 30.0),
        _row("o1", "2026-08-20T00:00:00+00:00", "2026-08-28T03:00:00Z", 30.0),
        _row("o2", "2026-08-20T00:00:00+00:00", "2026-08-27T03:00:00Z", 30.0),
    ]
    pairs = reveal_hold.ratios_by_day({"n1": 0.5, "o1": 0.2, "o2": 0.9}, NOW, rows)
    assert [d.isoformat() for d, _o, _n in pairs] == ["2026-08-28"], (
        "対照だけの日が混ざっています（08/27 は処置が居ません）")


def test_日が足りなければ判定しないこと() -> None:
    """1日ぶんでは、その日の題材の当たり外れと区別が付きません。"""
    got = reveal_hold.verdict([(NOW.date(), 0.2, 0.5)])
    assert got["decided"] is False, got


def test_同点は外れの側に置くこと() -> None:
    """`falsified_if` は「**上回らない**なら外れ」（同点も外れ）。"""
    same = [(NOW.date(), 0.4, 0.4)] * 3
    assert reveal_hold.verdict(same)["verdict"] == "falsified"


# ---------------------------------------------------------------- 台帳の側の門

def _accruals() -> list[tuple[str, str]]:
    doc = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
    out: list[tuple[str, str]] = []
    for item in doc.get("hypotheses") or doc.get("items") or []:
        if not isinstance(item, dict):
            continue
        for need in item.get("needs") or []:
            if isinstance(need, dict) and need.get("count_expr"):
                out.append((str(item.get("claim", ""))[:60], str(need["count_expr"])))
    return out


def test_控えを行で数える門を置かないこと() -> None:
    """**`data/uploaded.jsonl` を `rows()` で数える `count_expr` を置かないこと。**

    あの控えは1本につき1行ではありません。数えたいのは**本**なので、
    `video_id` の集合にするか、`*_arm()` のような道具を通すこと。
    """
    bad = [(c, e) for c, e in _accruals() if "uploaded.jsonl" in e and "rows(" in e]
    assert not bad, (
        "`rows('uploaded.jsonl')` は**行**を数えます（実測 850行 / 735本）。"
        f"本で数えること: {bad}")


def test_控えを読む門は本で畳んでいること() -> None:
    """`uploaded()` を直に舐める式は、`video_id` の集合に畳んでいること。"""
    bad = []
    for claim, expr in _accruals():
        if "uploaded()" not in expr:
            continue
        if "_arm(" in expr:
            continue
        if "{" in expr and "video_id" in expr:
            continue
        bad.append((claim, expr))
    assert not bad, f"本で畳んでいない `count_expr` があります: {bad}"


def test_完成形の保持の門は比べられる本を数えていること() -> None:
    """この前提の `count_expr` が、また行を数える式に戻っていないこと。

    ## **2026-09-02 に、門が2つになりました**

    ここは長らく「**全部の `count_expr` に `reveal_hold_arm(` が入っていること**」
    でした。**`needs` が1つしか無かったから**です。

    同じ日に2つ目を足しました —— `reveal_hold_days()`（`need: 3`）。
    理由は、`reveal_hold_arm()` が数える**本の数**と、`reveal_hold.verdict()` が
    見る**比の取れた日**が別だったからです（実測 2026-09-02: 本 16/21 で
    `need: 16` を満たすのに、撃つと **対にできた日 2日（要 3日）**で
    `decided: False`。`paired_days()` は控えだけ、`ratios_by_day()` は
    そこへ Analytics の engaged 比を join するので **4日 → 2日**）。

    **`all(... reveal_hold_arm ...)` のままだと、この2つ目を足した瞬間に赤くなります**
    —— **正しい足しなのに落ちる**ので、見ているものを本来の不変条件へ直しました:

        (1) どの `count_expr` も `reveal_hold_*()` を通っている（＝行を数えない）
        (2) **本の門と、日の門が、両方 在る**

    (2) を足したのは、片方だけに戻す直しを止めるためです。
    """
    exprs = [e for c, e in _accruals() if "完成した図" in c]
    assert exprs, "前提が見つかりません（`claim` が変わったなら、この検査も直すこと）"
    assert all("reveal_hold_" in e for e in exprs), \
        f"行を数える式に戻っています（`reveal_hold_*()` を通すこと）: {exprs}"
    assert any("reveal_hold_arm(" in e for e in exprs), \
        f"**本の門**（両群 16本）がありません: {exprs}"
    assert any("reveal_hold_days(" in e for e in exprs), \
        ("**日の門**（`verdict()` が見る「比の取れた日」）がありません。"
         "本の数だけを門にすると、`eta.py` が「いま判定できる」と名指しして、"
         f"撃つと判定できない回が毎周 出ます: {exprs}")
