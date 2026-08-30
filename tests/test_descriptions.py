"""`src/descriptions.py` —— **説明欄**を停止の理由で測る道具。

**この検査が守っているのは2つです。**

1. **定型文を数えないこと。** `▼ 目次` から先（目次・footer・`[t:` の印）は
   `pipeline.build_description()` が全本に同じものを足します。そこを数えると
   694本 が「1つの型」に見え、**解除条件3の判断が反転します**。
2. **少ないほうで上書きしないこと。** 正本は Data API 側で、日枠が尽きた回は
   `videos.list` が 403 を返して **0本** を持ち帰ります。それを書くと、
   **測れていた 735本 が 0本 に化けます**（2026-08-30 に実際に踏んだ）。
"""
from __future__ import annotations

import json

import pytest

from src import descriptions as D

FOOTER = """

─────────────
※ この動画は一般的な情報提供を目的としたもので、個別の助言ではありません。
"""


def _desc(body: str) -> str:
    return f"{body}\n\n{D.TOC_MARK}\n0:00 はじめに\n1:20 計算{FOOTER}\n[t:s-kojo-2]\n"


# --------------------------------------------------------------------------
# 1) 定型文を落とす
# --------------------------------------------------------------------------

def test_body_drops_toc_footer_and_marker():
    assert D.body(_desc("手取りを計算します。\n前提はこの3つです。")) == (
        "手取りを計算します。\n前提はこの3つです。")


def test_body_drops_marker_even_without_toc():
    """目次の無い古い形でも、`[t:` の印より手前だけを本文と見ること。"""
    assert D.body("本文です。\n[t:s-a-1]\n") == "本文です。"


def test_body_of_empty_is_empty():
    assert D.body("") == ""
    assert D.body(None) == ""


def test_frame_does_not_count_the_boilerplate():
    """**同じ footer を持つ 3本が「1つの型」に化けないこと。**

    本文が全部ちがえば、実効の型数は本数（3.0）に近くなる。
    定型文を数えていると 1.0 に潰れる。
    """
    recs = [{"description": _desc(f"{w}を計算します。\n{w}の前提です。")}
            for w in ("残業代", "iDeCo", "扶養")]
    f = D.frame(recs)
    assert f["n"] == 3
    assert f["opening"]["effective"] > 2.5
    assert f["opening"]["distinct"] == 3


def test_frame_catches_a_real_template():
    """逆に、**本当に同じ入り方**なら 1.0 に落ちること（数字だけ違う形）。"""
    recs = [{"description": _desc(f"結論から言うと{n}円です。\n計算します。")}
            for n in (12709, 77161, 3000)]
    f = D.frame(recs)
    assert f["opening"]["effective"] == 1.0
    assert f["opening"]["top_share"] == 1.0


def test_frame_drops_bodyless_videos_from_the_denominator():
    """本文の無い本は分母から落ちること（**空どうしが「同じ型」に化ける**ため）。"""
    recs = [{"description": _desc("あ")}, {"description": FOOTER}, {"description": ""}]
    f = D.frame(recs)
    assert f["n"] == 1
    assert f["empty"] == 2


# --------------------------------------------------------------------------
# 2) 本文と同じ物差しで当てる
# --------------------------------------------------------------------------

def test_persona_uses_the_same_function_as_new_scripts():
    """説明欄に名乗りがあれば当たること（解除条件1・2）。

    **当たるのは、いまのところ `channel.yaml` の旧 persona の原文だけです** ——
    言い換えの取りこぼしは下の xfail に置いてあります。
    """
    hit = {"title": "退職金の手取り", "description": _desc(
        "元・事業会社の経理／人事で、制度を実務で回してきた立場から解説します。")}
    ok = {"title": "退職金の手取り", "description": _desc(
        "前提を置いて計算します。条件が変わればこう変わります。")}
    assert len(D.persona_defects([hit])) == 1
    assert D.persona_defects([ok]) == []


@pytest.mark.xfail(reason="2026-08-30 に測って見つけた穴。"
                          "`verify._HUMAN_EXPERT_PATTERNS` が言い換えを取りこぼす —— "
                          "解除条件1・2 を閉じた『0/694本』は、"
                          "この検査の網の広さの上に乗っている", strict=True)
def test_persona_catches_the_obvious_rewordings():
    """**「元・事業会社の人事です」が素通りします。**

    実測（`python -m src.descriptions` を書いた回に、10通りを当てた）:
    当たったのは旧 persona の原文 1件だけで、**残り 9件 は素通り**でした。
    しかもその1件は `元[・]?<職業>` ではなく
    「制度を**実務で回してきた**」のほうで当たっています ——
    つまり **`元・<会社>の<職業>` の形は、1件も見ていません。**
    """
    misses = [
        "元・事業会社の人事です。",
        "元・事業会社の経理として、実務の感覚でお話しします。",
        "元大手企業の経理担当が解説します。",
        "私は経理として10年働いていました。",
        "経理の実務経験から言うと、ここは間違えやすいところです。",
        "人事部にいたころの話をします。",
    ]
    for text in misses:
        assert D.persona_defects([{"title": "x", "description": _desc(text)}]), text


def test_persona_does_not_fire_on_the_footer():
    """footer の「専門家にご確認ください」で誤爆しないこと（**分母から落ちている**）。"""
    assert D.persona_defects([{"title": "x", "description": _desc("計算します。")}]) == []


def test_advice_uses_the_shared_pattern_table():
    hit = {"title": "x", "description": _desc("おすすめです。")}
    assert len(D.advice_defects([hit])) == 1
    assert D.advice_defects([{"title": "x", "description": _desc("試算です。")}]) == []


# --------------------------------------------------------------------------
# 3) 台帳の読み
# --------------------------------------------------------------------------

def test_ledger_ids_are_unique_and_ordered(tmp_path):
    p = tmp_path / "uploaded.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in [
        {"video_id": "a"}, {"video_id": "b"}, {"video_id": "a"}, {"no_id": 1},
    ]) + "こわれた行\n", encoding="utf-8")
    assert D.ledger_ids(p) == ["a", "b"]


# --------------------------------------------------------------------------
# 4) 少ないほうで上書きしない
# --------------------------------------------------------------------------

def test_empty_result_does_not_clobber_a_bigger_cache():
    """日枠の 403 で **0本** を持ち帰った回が、測れていた分を消さないこと。"""
    prev = {"videos": [{"video_id": "a"}, {"video_id": "b"}]}
    assert D.should_write({"videos": []}, prev) is False


def test_first_run_writes_even_though_it_is_empty():
    """**1回目は書く** —— 手元に何も無ければ、空でも「撃った」と残るほうがよい。"""
    assert D.should_write({"videos": []}, {}) is True
    assert D.should_write({"videos": []}, {"videos": []}) is True


def test_same_or_more_writes():
    prev = {"videos": [{"video_id": "a"}]}
    assert D.should_write({"videos": [{"video_id": "a"}]}, prev) is True
    assert D.should_write({"videos": [{"video_id": "a"}, {"video_id": "b"}]}, prev) is True


def test_force_overrides():
    """本当に本が減った回のための口（減ったことを確かめてから使うこと）。"""
    prev = {"videos": [{"video_id": "a"}, {"video_id": "b"}]}
    assert D.should_write({"videos": []}, prev, force=True) is True


def test_report_says_it_has_never_been_taken(tmp_path):
    assert "まだ1度も取っていません" in D.report(cache=tmp_path / "none.json")
