"""**作り置きを供給として数える式が、もう無いこと。**（2026-08-31）

オーナー原文（**一字も変えないこと**）:

    「使わなければ良いだけ前提にも再利用もしない」

3つのうちの **2つ目（前提にしない）** を、機械の側で押さえます。

## 何が起きていたか（事実だけ）

`data/uploaded.jsonl` には、**予約済みで未公開の本が 400本超**あります。
規則2（1日1本・作り置きなし）の下では、**あれは1本も公開しません** ——
予約を外して非公開のまま置くからです（削除はしません）。

ところが `src/reach_split.publishes_per_day()` は、控えの未来の `at` を
そのまま数えていました。そして `surface_forecast()` が

    これから先の面（回/日） ＝ 公開1本あたり × これからの公開 本/日

で**掛けます**。つまり **公開しない本で面が立ち、到達日が早く出ていました。**

## この検査が押さえているもの

    1. `STOCKPILE_IS_SUPPLY` が False のままであること
    2. 未来の予約を控えに何本 足しても、**これからの公開本数が増えないこと**
    3. **規則の下で作った本は落ちないこと**（落とすと、これから出す1本が
       供給から消え、「1日1本 作っても面は0」という嘘になります）
    4. 公開済み（過去）の実績は落ちないこと

**戻すにはこの検査を消すしかありません**（diff に出ます）。
"""
from __future__ import annotations

import json

import pytest

from src import house_rule, reach_split


TODAY = "2026-09-10"


def _row(vid: str, at: str, made: str) -> dict:
    return {"video_id": vid, "at": at + "T20:00:00+09:00",
            "uploaded_at": made + "T00:00:00", "duration_s": 300.0}


def test_作り置きは供給ではない旗が立っていること():
    assert house_rule.STOCKPILE_IS_SUPPLY is False, (
        "`STOCKPILE_IS_SUPPLY` が True に戻っています。**戻さないこと** ——\n"
        "  予約に在る本は規則2で予約を外すので、1本も公開されません。\n"
        "  供給に数えると、**公開しない本で到達日が早く出ます**。"
    )


def test_規則より前に作った未来の予約は作り置き():
    # 未来の予約 かつ 規則より前に作った → 作り置き
    assert house_rule.is_stockpile(
        _row("a", "2026-09-20", "2026-08-25"), today=TODAY)


def test_規則の下で作った本は作り置きではない():
    # 未来の予約でも、`STOCKPILE_SINCE` 以降に作った本は**これからの供給**
    assert not house_rule.is_stockpile(
        _row("b", "2026-09-20", house_rule.STOCKPILE_SINCE), today=TODAY)


def test_公開済みは作り置きではない():
    # 過去は実績。**供給の話ではない**ので落とさない
    assert not house_rule.is_stockpile(
        _row("c", "2026-09-01", "2026-08-01"), today=TODAY)


def test_at_が読めない行は落とさない():
    # **測っていないことを、落とす側に倒さないこと**
    assert not house_rule.is_stockpile({"video_id": "d"}, today=TODAY)


def _ledger(tmp_path, rows: list[dict]):
    p = tmp_path / "uploaded.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows),
                 encoding="utf-8")
    return p


@pytest.fixture()
def _today(monkeypatch):
    monkeypatch.setattr(house_rule, "_jst_today", lambda: TODAY)


def test_未来の予約を何本足しても_これからの公開本数が増えない(tmp_path, _today):
    """**この検査がいちばんの中身です。**

    控えに作り置きを 200本 足しても、`publishes_per_day()` の
    **今日より後**の合計は 1本も増えないこと。
    """
    base = [_row("keep", "2026-09-01", "2026-08-01")]        # 公開済み
    piled = base + [_row(f"s{i}", "2026-09-20", "2026-08-25")
                    for i in range(200)]

    ids = {"keep"} | {f"s{i}" for i in range(200)}
    a = reach_split.publishes_per_day(longs=ids,
                                      ledger_path=_ledger(tmp_path, base))
    p2 = tmp_path / "two"
    p2.mkdir()
    b = reach_split.publishes_per_day(longs=ids,
                                      ledger_path=_ledger(p2, piled))

    def future(d: dict) -> int:
        key = TODAY.replace("-", "")
        return sum(n for day, n in d.items() if day > key)

    assert future(a) == 0
    assert future(b) == 0, (
        "作り置き 200本 が「これから公開する本」として数えられています。\n"
        "  落とす所は `src.house_rule.is_stockpile()` の1か所です"
        "（`src/reach_split.publishes_per_day()` が呼びます）。"
    )
    # 公開済みの実績は落ちていないこと
    assert sum(a.values()) == 1
    assert sum(b.values()) == 1


def test_規則の下で作った1本は_これからの供給に入る(tmp_path, _today):
    rows = [_row("today", "2026-09-20", house_rule.STOCKPILE_SINCE)]
    got = reach_split.publishes_per_day(longs={"today"},
                                        ledger_path=_ledger(tmp_path, rows))
    assert sum(got.values()) == 1, (
        "**規則の下で作った本まで落としています。**\n"
        "  そうすると『1日1本 作っても面は 0回/日』と印字することになり、"
        "実物と食い違います。"
    )


def test_これから公開する本数は規則から出ること():
    assert house_rule.planned_publishes_per_day() == house_rule.cap()
