"""`scripts/ab_balance.py` —— A/B の腕を在庫の側で埋める道具。

**既知の当たりを先に固定しています**（手順 §4「道具を新しく足す回は」）。
当たりは、2026-08-20 00:2x の実測そのものです ——
`topic_forge` で足した11本が**11本とも `条件` に入り**、
`hook_form` の律速の腕（`問い` 7本・判定の床は8本）が**1本も増えませんでした。**
この道具が正しければ、**その11本を1本ずつ `問い` 側へ振り直せる**はずです。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import ab_balance                       # noqa: E402
from src.script_writer import hook_form              # noqa: E402

#: 2026-08-20 00:2x に `topic_forge --count 14` が足した本のうち、`pick` が返した11本。
#: **この11本は、実測で11本とも `条件` でした。**
FORGED_2026_08_20 = [
    "s-kogaku-gassan-70000",
    "s-nenkin-119-120",
    "s-saishushoku-100nichi-wakare",
    "s-serufu-choten-100000",
    "s-zoyo-hito-toshi-kake",
    "s-kogaku-tasukai-teigaku",
    "s-nenkinmenjo-zero-wakare",
    "s-saishushoku-330-oikoshi",
    "s-serufu-shinikane-212000",
    "s-zoyo-3nin-4nen",
    "s-zangyo-61jikanme-2480",
]


def test_既知の当たり_足した11本は全部おなじ腕に入っていた():
    """**この検査が緑でなくなったら、道具の理由そのものが消えています。**

    偏った実装ではなく引きです（全434件では 210/224）。
    だから**直す先は `hook_form` ではなく、在庫の側**です。
    """
    arms = {hook_form(i) for i in FORGED_2026_08_20}
    assert len(arms) == 1, f"11本が2つの腕に割れています: {arms}。**この道具の前提が変わりました**"


def test_既知の当たり_その11本を1本ずつ反対の腕へ振り直せる():
    long_arm = hook_form(FORGED_2026_08_20[0])
    short = "問い" if long_arm == "条件" else "条件"
    taken: set[str] = set(FORGED_2026_08_20)
    for tid in FORGED_2026_08_20:
        new = ab_balance.rename_for(tid, short, hook_form, taken)
        assert new is not None, f"{tid} を {short} 側へ振り直せません"
        assert hook_form(new) == short
        taken.add(new)


def test_振り直しても題材はそのまま():
    """IDの頭は変えません。**calc も題材も変わらない**ことの担保です。"""
    for tid in FORGED_2026_08_20:
        new = ab_balance.rename_for(tid, "問い", hook_form, set())
        if new is None:
            continue
        assert new.startswith(tid), f"{tid} → {new} で頭が変わっています"


def test_既に使われているIDは返さない():
    tid = FORGED_2026_08_20[0]
    want = "問い" if hook_form(tid) == "条件" else "条件"
    first = ab_balance.rename_for(tid, want, hook_form, set())
    assert first is not None
    second = ab_balance.rename_for(tid, want, hook_form, {first})
    assert second is not None and second != first


def test_接尾を足し直しても増え続けない():
    """一度振り直したIDをもう一度渡しても、`-r2-r3` のようには伸びません。"""
    tid = FORGED_2026_08_20[0] + "-r5"
    new = ab_balance.rename_for(tid, hook_form(tid), hook_form, set())
    assert new is None or new.count("-r") <= 1, f"接尾が重なりました: {new}"


def _rows(ids: list[str]) -> list[dict]:
    return [{"id": i, "calc": i.split("-")[1]} for i in ids]


def test_動かすのはpickが返した本だけ(monkeypatch):
    """**投稿済みの本には触りません。**`pick` が既に外しているので、そこから出ません。"""
    pool = _rows(FORGED_2026_08_20 + ["s-x-a", "s-x-b"])
    monkeypatch.setattr(ab_balance, "_pool", lambda count=60, days=1: pool)
    monkeypatch.setattr(ab_balance.config, "load_topics",
                        lambda: {"topics": pool})
    _, moves, _ = ab_balance.plan(target=4, split_name="hook_form")
    ids = {r["id"] for r in pool}
    for old, _new in moves:
        assert old in ids, f"{old} は pick の外から来ています"


def test_短いほうを目標まで埋め_長いほうを目標より下にしない(monkeypatch):
    pool = _rows(FORGED_2026_08_20 + ["s-x-a", "s-x-b"])
    monkeypatch.setattr(ab_balance, "_pool", lambda count=60, days=1: pool)
    monkeypatch.setattr(ab_balance.config, "load_topics", lambda: {"topics": pool})
    counts, moves, _ = ab_balance.plan(target=5, split_name="hook_form")
    short = min(counts, key=lambda a: len(counts[a]))
    long_ = max(counts, key=lambda a: len(counts[a]))
    assert len(counts[short]) + len(moves) <= 5 + 1
    assert len(counts[long_]) - len(moves) >= 5, "長いほうを目標より下に削っています"


def test_足りないときは動かさずに理由を出す(monkeypatch):
    """**在庫そのものが足りない回に、腕を削って取り繕わないこと。**"""
    pool = _rows(FORGED_2026_08_20[:3])
    monkeypatch.setattr(ab_balance, "_pool", lambda count=60, days=1: pool)
    monkeypatch.setattr(ab_balance.config, "load_topics", lambda: {"topics": pool})
    _, moves, note = ab_balance.plan(target=12, split_name="hook_form")
    assert moves == []
    assert "在庫" in note or "動かしません" in note


def test_書き換えはidの行だけ(tmp_path, monkeypatch):
    y = tmp_path / "topics.yaml"
    y.write_text(
        "topics:\n"
        "  - id: s-a-1\n"
        "    title_seed: \"s-a-1 のことを書いた題\"\n"
        "  - id: s-a-2\n", encoding="utf-8")
    monkeypatch.setattr(ab_balance, "TOPICS", y)
    ab_balance.apply([("s-a-1", "s-a-1-r2")])
    got = y.read_text(encoding="utf-8")
    assert "id: s-a-1-r2" in got
    assert "s-a-1 のことを書いた題" in got, "題の中の字まで書き換えています"
    assert "id: s-a-2" in got


def test_当たらないidでは書かない(tmp_path, monkeypatch):
    y = tmp_path / "topics.yaml"
    y.write_text("topics:\n  - id: s-a-1\n", encoding="utf-8")
    monkeypatch.setattr(ab_balance, "TOPICS", y)
    with pytest.raises(SystemExit):
        ab_balance.apply([("s-nothing", "s-nothing-r2")])
    assert y.read_text(encoding="utf-8") == "topics:\n  - id: s-a-1\n"


# ===================================================================
# **在庫を「1日ぶんの上限」で数えていた**（2026-08-20 19:2x に測って直した）
#
# `pick` の `per_calc=2` は「**同じ制度の本が1日に何本も並ぶと繰り返しに見える**」
# ための門です（`batch_build.pick` の docstring）。ところが `_pool` はそれを
# **締切までに作れる上限**として使っていました。
#
# 実測（2026-08-20 19:2x・`config/topics.yaml`）:
#     未投稿・calc あり            33本
#     pick(60)（＝1日ぶん）        26本   ← aoiro 5→2 / zoyo 4→2 / kogaku 3→2 / nenkinmenjo 3→2
#
# `hook_form` の床は両群16本＝**32本**。26本と読むと `**動かせません。**` で降り、
# 33本と読むと 問い15→16 / 条件18→17 で**両腕とも床に届きます。**
# ===================================================================


def test_締切までの日数だけper_calcが緩む(monkeypatch):
    """`_pool(days=d)` が `pick` に渡す `per_calc` は **1日ぶん × d** です。"""
    seen: dict = {}

    def fake_pick(count, explicit, per_calc=2):
        seen["count"], seen["per_calc"] = count, per_calc
        return []

    monkeypatch.setattr(ab_balance.batch_build, "pick", fake_pick)
    ab_balance._pool(60, days=1)
    assert seen["per_calc"] == ab_balance.batch_build.DEFAULT_PER_CALC
    ab_balance._pool(60, days=21)
    assert seen["per_calc"] == ab_balance.batch_build.DEFAULT_PER_CALC * 21, (
        "**締切が21日先でも1日ぶんの門で数えています。**在庫が実際より少なく見えます"
    )


def test_日数は今日をふくむ():
    from datetime import date
    assert ab_balance.days_until(date(2026, 9, 9), date(2026, 8, 20)) == 21
    assert ab_balance.days_until(date(2026, 8, 20), date(2026, 8, 20)) == 1
    assert ab_balance.days_until(date(2026, 8, 1), date(2026, 8, 20)) == 1, (
        "過ぎた締切でも 1 未満にはしない（0本と読むと在庫が丸ごと消えます）"
    )


def test_既知の当たり_33本の在庫なら両腕とも16本に届く(monkeypatch):
    """**2026-08-20 19:2x の実測そのもの。** 26本と読むと降り、33本と読むと動きます。

    腕の内訳（実測）: 問い 15 / 条件 18 → 1本の付け替えで 16 / 17。
    """
    from src.script_writer import hook_form as hf

    pool = []
    i, arms = 0, {"問い": 0, "条件": 0}
    while arms["問い"] < 15 or arms["条件"] < 18:
        tid = f"s-stock-{i}"
        i += 1
        a = hf(tid)
        if arms[a] >= (15 if a == "問い" else 18):
            continue
        arms[a] += 1
        pool.append({"id": tid, "calc": "aoiro", "title_seed": "", "score": 1.0})
    assert len(pool) == 33

    monkeypatch.setattr(ab_balance, "_pool", lambda count=60, days=1: pool)
    monkeypatch.setattr(ab_balance.config, "load_topics", lambda: {"topics": pool})
    counts, moves, note = ab_balance.plan(target=16, split_name="hook_form", days=21)
    assert len(moves) == 1, f"1本の付け替えで届くはずです: {note}"
    after = {a: len(v) for a, v in counts.items()}
    assert after["問い"] == 15 and after["条件"] == 18
    assert "動かせません" not in note
