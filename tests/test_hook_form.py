"""`src/script_writer.hook_form` の検査 —— **冒頭1枚目の形の振り分け**。

## なぜ先にここを固定するのか

`tests/test_title_form.py` と同じ理由です。この振り分けは**測定そのもの**で
（`config/hypotheses.yaml` 2026-09-16）、壊れ方が3つあり、**どれも出力を見ても
分かりません**:

- **群が偏る** … 片側が8本に届かず、期限が来ても判定できない
- **群が動く** … 同じテーマを作り直すたびに形が変われば、
  落ちて撃ち直した本が別の群に移り、**比較が静かに壊れます**
- **題の形（`title_form`）と重なる** … 塩が同じだと2つの実験が完全に一致し、
  **どちらが効いたのか永久に分かりません。** 件数も見た目も正常なままです

**この3つ目は、この道具にしか無い穴です**（`title_form` のときは実験が1本しか
無かった）。`docs/trigger_main.md` §4 の「**既知の当たりを1件、検査に先に固定する**」
に当たるのがここで、**先に置いたのはこの独立性のほう**です。
"""

from __future__ import annotations

import yaml

from src import script_writer as sw
from src.config import ROOT


def _topics() -> list[dict]:
    data = yaml.safe_load((ROOT / "config" / "topics.yaml").read_text(encoding="utf-8"))
    return data["topics"] if isinstance(data, dict) else data


def test_form_is_stable_for_the_same_topic():
    """**同じテーマIDは、何度呼んでも同じ群。**（作り直しで群が移らない）"""
    a = [sw.hook_form("s-iryohi-5nen-20man") for _ in range(5)]
    assert len(set(a)) == 1
    assert sw.hook_form("s-iryohi-5nen-20man") == a[0]


def test_split_is_close_to_half_on_the_real_topic_list():
    """**実物のテーマ一覧で半々に割れること。**

    偏ると、期限が来ても「どちらの群も8本に満たない」で判定できません。
    """
    topics = _topics()
    ask = [t for t in topics if sw.hook_form(t["id"]) == "問い"]
    share = len(ask) / len(topics)
    assert len(topics) >= 100, "テーマが少なすぎて割合を測れません"
    assert 0.40 <= share <= 0.60, f"問いの群が {share:.1%}。半々から外れています"


def test_it_does_not_ride_on_the_title_experiment():
    """**題の形と冒頭の形が、同じ本に揃わないこと。**

    塩を写し忘れると `title_form` と1本ずつ完全に一致します。そのとき
    件数は正常（半々）で、**壊れているのは「どちらが効いたか」だけ**です。
    2つの実験が同時に走っている以上、ここが実験の前提そのものになります。

    見ているのは4つの組（問い×問い／問い×条件／断定×問い／断定×条件）で、
    **どれも全体の 15% を下回らないこと**。完全一致だと2つの組が 0% になります。
    """
    topics = _topics()
    cells: dict[tuple[str, str], int] = {}
    for t in topics:
        key = (sw.title_form(t["id"]), sw.hook_form(t["id"]))
        cells[key] = cells.get(key, 0) + 1
    n = len(topics)
    assert len(cells) == 4, f"4つの組が揃っていません: {sorted(cells)}"
    for key, count in cells.items():
        assert count / n >= 0.15, (
            f"{key} が {count / n:.1%} しかありません。"
            "題の形と冒頭の形が重なっていて、どちらが効いたか分けられません"
        )


def test_share_zero_and_one_are_switches():
    """**0 で止まり、1 で全部。**（外れたときに `HOOK_ASK_SHARE = 0` で畳むため）"""
    assert sw.hook_form("x", share=0) == "条件"
    assert sw.hook_form("x", share=1) == "問い"
    assert all(sw.hook_form(f"t{i}", share=0) == "条件" for i in range(20))


def test_control_group_gets_no_extra_instruction():
    """**条件の側には1文字も足さないこと。**

    足すと対照群でなくなり、**冒頭の形以外の差**が混ざります。
    """
    src = (ROOT / "src" / "script_writer.py").read_text(encoding="utf-8")
    assert 'if hook == "問い":\n        prompt += ASK_HOOK_RULE' in src, (
        "問いの側にだけ足す形が崩れています"
    )
    assert "ASK_HOOK_RULE" in src


def test_the_rule_keeps_the_premise_numbers_on_screen():
    """**前提の数字を消させないこと。**

    冒頭1枚目は `stat` も `formula` も空なので（`reveal_variants`）、
    `note` から数字が消えると **画面に数字が1つも無い1枚目**になります。
    在庫341本ではそれが 13本（4%）しかなく、**そこへ寄せる変更ではありません。**
    """
    assert "前提の数字は消さないこと" in sw.ASK_HOOK_RULE
    assert "答えの数字は書かない" in sw.ASK_HOOK_RULE
