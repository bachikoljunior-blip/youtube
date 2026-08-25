"""`src/script_writer.title_form` の検査 —— **題の形の振り分け**。

## なぜ先にここを固定するのか

この振り分けは、**測定そのもの**です（`config/hypotheses.yaml` 2026-09-12）。
壊れ方が2つあり、**どちらも出力を見ても分かりません**:

- **群が偏る** … 片側が8本に届かず、期限が来ても判定できない
- **群が動く** … 同じテーマを作り直すたびに形が変われば、
  落ちて撃ち直した本が別の群に移り、**比較が静かに壊れます**

件数も見た目も変わらないので、**検査でしか見えません。**
"""

from __future__ import annotations

import yaml

from src import script_writer as sw
from src.config import ROOT


def test_form_is_stable_for_the_same_topic():
    """**同じテーマIDは、何度呼んでも同じ群。**（作り直しで群が移らない）"""
    a = [sw.title_form("s-iryohi-5nen-20man") for _ in range(5)]
    assert len(set(a)) == 1
    assert sw.title_form("s-iryohi-5nen-20man") == a[0]


def test_split_is_close_to_half_on_the_real_topic_list():
    """**実物のテーマ一覧で半々に割れること。**

    偏ると、期限が来ても「どちらの群も8本に満たない」で判定できません。
    """
    data = yaml.safe_load((ROOT / "config" / "topics.yaml").read_text(encoding="utf-8"))
    topics = data["topics"] if isinstance(data, dict) else data
    ask = [t for t in topics if sw.title_form(t["id"]) == "問い"]
    share = len(ask) / len(topics)
    assert len(topics) >= 100, "テーマが少なすぎて割合を測れません"
    assert 0.40 <= share <= 0.60, f"問いの群が {share:.1%}。半々から外れています"


def test_share_zero_and_one_are_switches():
    """**0 で止まり、1 で全部。**（外れたときに `TITLE_ASK_SHARE = 0` で畳むため）"""
    assert sw.title_form("x", share=0) == "断定"
    assert sw.title_form("x", share=1) == "問い"
    assert all(sw.title_form(f"t{i}", share=0) == "断定" for i in range(20))


def test_control_group_gets_no_extra_instruction():
    """**断定の側には1文字も足さないこと。**

    足すと対照群でなくなり、**題の形以外の差**が混ざります。
    ここは「問いの側にだけ足す」という書き方そのものを見ています。
    """
    src = (ROOT / "src" / "script_writer.py").read_text(encoding="utf-8")
    assert 'if form == "問い":\n        prompt += ASK_TITLE_RULE' in src, (
        "問いの側にだけ足す形が崩れています"
    )
    assert "ASK_TITLE_RULE" in src


def test_ask_rule_keeps_the_existing_title_limits():
    """**問いの指示が、既にある題の規則を上書きしないこと。**

    32文字と #Shorts は投稿前の検査が見ています。ここを緩めると
    **落ちるのは20分後の生成の先**です。
    """
    assert "32文字" in sw.ASK_TITLE_RULE
    assert "#Shorts" in sw.ASK_TITLE_RULE
    # **答えの数字を題に書かせない**（`verify._check_title_from_calc` が見る側と衝突しない）
    assert "答えの数字" in sw.ASK_TITLE_RULE


def test_build_perf_can_see_the_split():
    """**振り分けたものが測れること。**（測れない振り分けは、ただの変更です）"""
    from src import build_perf

    assert build_perf.features("t", "医療費20万円で戻るのは何円か #Shorts", {})["題が問いか"] == 1.0
    assert build_perf.features("t", "医療費20万円で戻るのは2万209円 #Shorts", {})["題が問いか"] == 0.0
