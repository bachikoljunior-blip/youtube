"""`src/topic_gaps.material_low` —— **(A) の題材が尽きる前に言う。**

一覧そのものは前からありました（「まだ表の無いテーマ N件」）。
**足りなかったのは「残りが少ない」と言う側**です ——
尽きると (A) の題材決めが **0分 → 20分** に戻り（8/17 16:2x の実測）、
補充は約2分/件（8/18 06:1x の実測）で **(A) 1本より1桁安い**のに、
**減っていることを誰も見ていませんでした。**
"""
from __future__ import annotations

from src import topic_gaps


def test_床の上では黙る():
    """**0件のときは `ring` を呼んでも記録されません**（当たり率が薄まるため）。"""
    assert topic_gaps.material_low(topic_gaps.MATERIAL_FLOOR) == []
    assert topic_gaps.material_low(topic_gaps.MATERIAL_FLOOR + 3) == []


def test_床を割ったら残りの件数ごと言う():
    out = topic_gaps.material_low(2)
    assert out, "床を割っているのに何も言っていません"
    joined = "\n".join(out)
    assert "残り 2件" in joined
    assert str(topic_gaps.MATERIAL_FLOOR) in joined


def test_潰し方と鍵が同じ行に出る():
    """**鍵が書いていないと、潰しても当たりとして数えられません**（通算3回取りこぼし）。"""
    joined = "\n".join(topic_gaps.material_low(0))
    assert "topic_material_low" in joined
    assert "--closes" in joined


def test_0件でも鳴る():
    """**尽きてからでは遅い**ので、0件は「言わない」ではなく「いちばん強く言う」。"""
    assert topic_gaps.material_low(0)


def test_一覧の末尾に付く():
    """`report_lines()` の返りに混ざること。**呼ばれていなければ意味がありません。**"""
    topics = [{"id": "aaa", "title_seed": "まだ表の無い題", "score": 1.0}]
    joined = "\n".join(topic_gaps.report_lines(topics, mods=set()))
    assert "まだ表の無いテーマ" in joined
    assert "topic_material_low" in joined, "床を割っているのに警告が出ていません"


def test_在庫の段の印を使わない():
    """**`[!]` は在庫の段（`pick` が8を割った）に予約されています。**

    `src/topic_gaps.py` の中にその注意書きが**すでに書いてあったのに**、
    この節を足した回はそれを読んだうえで `[!]` を使い、
    `tests/test_topic_stock.py` に落とされました（2026-08-18）。
    **注意書きは読まれても効きません。検査だけが効きます。**
    """
    joined = "\n".join(topic_gaps.material_low(0))
    assert "[!]" not in joined
