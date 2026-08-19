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
    monkeypatch.setattr(ab_balance, "_pool", lambda count=60: pool)
    monkeypatch.setattr(ab_balance.config, "load_topics",
                        lambda: {"topics": pool})
    _, moves, _ = ab_balance.plan(target=4, split_name="hook_form")
    ids = {r["id"] for r in pool}
    for old, _new in moves:
        assert old in ids, f"{old} は pick の外から来ています"


def test_短いほうを目標まで埋め_長いほうを目標より下にしない(monkeypatch):
    pool = _rows(FORGED_2026_08_20 + ["s-x-a", "s-x-b"])
    monkeypatch.setattr(ab_balance, "_pool", lambda count=60: pool)
    monkeypatch.setattr(ab_balance.config, "load_topics", lambda: {"topics": pool})
    counts, moves, _ = ab_balance.plan(target=5, split_name="hook_form")
    short = min(counts, key=lambda a: len(counts[a]))
    long_ = max(counts, key=lambda a: len(counts[a]))
    assert len(counts[short]) + len(moves) <= 5 + 1
    assert len(counts[long_]) - len(moves) >= 5, "長いほうを目標より下に削っています"


def test_足りないときは動かさずに理由を出す(monkeypatch):
    """**在庫そのものが足りない回に、腕を削って取り繕わないこと。**"""
    pool = _rows(FORGED_2026_08_20[:3])
    monkeypatch.setattr(ab_balance, "_pool", lambda count=60: pool)
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
