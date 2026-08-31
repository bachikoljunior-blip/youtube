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


def test_persona_catches_the_obvious_rewordings():
    """**言い換えでも当たること**（2026-08-30 夜に塞いだ穴）。

    塞ぐ前の実測（`python -m src.descriptions` を書いた回に、10通りを当てた）:
    当たったのは旧 persona の原文 1件だけで、**残り 9件 は素通り**でした。
    しかもその1件は `元[・]?<職業>` ではなく
    「制度を**実務で回してきた**」のほうで当たっており、
    **`元・<会社>の<職業>` の形は、閉じたときから1件も見ていません**でした。

    **この検査が守っているのは、解除条件1・2 の『0/694本』の意味です** ——
    網が狭ければ、0件 は「無い」ではなく「見えていない」になります。
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


def test_persona_still_lets_the_safe_forms_through():
    """**偽陽性が出ると投稿が止まります**（`CLAUDE.md`「途切れるのが最大の損失」）。

    網を広げた回に、実物で当て直した数:
    `python -m src.legacy_corpus` の控え694本で **0件**（広げる前と同じ）。
    """
    safe = [
        "税理士に確認してください。",
        "会社員として働く人は対象になります。",
        "専門家にご確認ください。",
        "元の経理処理に戻します。",
        "税務署に提出してください。",
        "年金事務所で確認できます。",
        "ハローワークに申請します。",
        "労基署に相談する道もあります。",
        "専門家に相談するのが確実です。",
    ]
    for text in safe:
        assert D.persona_defects([{"title": "x", "description": _desc(text)}]) == [], text


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


# --- 日枠で途中で止まった回を、「チャンネルに無い」と言わないこと ---
#
# **2026-08-30 22:31Z の実測。** `--refresh` が `quotaExceeded`（403）で
# 0/735 を持ち帰った回に、`report()` はこう印字していました:
#
#     台帳 735本 ／ 説明欄が返った 0本（差 735本 は**チャンネルに無い本**）
#     **735本 はチャンネルに返りませんでした** ——消したか、台帳にしか無い本です。
#     **1) 説明欄で人間の専門家を装っているか**  **0 / 0本**
#
# **3行とも嘘です。** 1本も問い合わせていません（`fetch()` は最初の束で break）。
# そして `0 / 0本` は、解除条件1・2 の根拠として読めてしまう形です。
# **測っていないことは「0件」ではありません。**

def _partial(asked: int = 735) -> dict:
    return {"at": "2026-08-30T22:31:54Z", "asked": asked, "got": 0,
            "partial": True, "videos": []}


def _write(tmp_path, payload: dict):
    p = tmp_path / "descriptions.json"
    p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return p


def test_partial_run_does_not_call_the_rest_missing(tmp_path):
    out = D.report(cache=_write(tmp_path, _partial()))
    assert "チャンネルに無い本" not in out
    assert "チャンネルに返りませんでした" not in out
    assert "まだ問い合わせていません" in out


def test_partial_run_names_the_day_quota_and_how_to_retry(tmp_path):
    out = D.report(cache=_write(tmp_path, _partial()))
    assert "quotaExceeded" in out
    assert "--refresh" in out


def test_empty_denominator_is_not_printed_as_zero_defects(tmp_path):
    """**`0 / 0本` を出さないこと。** 解除条件1・2 の根拠に読めてしまう。"""
    out = D.report(cache=_write(tmp_path, _partial()))
    assert "0 / 0本" not in out
    assert "測っていません" in out
    assert "「0件」ではありません" in out


def test_a_complete_run_still_says_which_books_are_gone(tmp_path):
    """**逆は残すこと。** 全部 問い合わせて返らなかった本は、本当に穴です。"""
    payload = {"at": "2026-08-30T00:00:00Z", "asked": 3, "got": 2,
               "partial": False,
               "videos": [{"video_id": "a", "title": "t", "description": "本文",
                           "privacy": "public"},
                          {"video_id": "b", "title": "t", "description": "本文",
                           "privacy": "public"}]}
    out = D.report(cache=_write(tmp_path, payload))
    assert "チャンネルに無い本" in out
    assert "1本 はチャンネルに返りませんでした" in out
