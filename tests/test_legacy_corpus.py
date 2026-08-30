"""`src/legacy_corpus.py` —— **すでに列に入っている本を、停止の理由で測り直す**道具。

**この検査が守っているのは「分母を黙って落とさないこと」です。**
控えの無い本を分母から外したまま「0件」と印字すると、
**見ていないものを『無かった』と読ませます**（解除条件5の判断が、そこで反転します）。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from src import legacy_corpus as lc


def _write(tmp_path, ledger_rows, stash):
    led = tmp_path / "uploaded.jsonl"
    led.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in ledger_rows),
                   encoding="utf-8")
    st = tmp_path / "critique_queue"
    st.mkdir(exist_ok=True)
    for vid, body in stash.items():
        (st / f"{vid}.json").write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    return led, st


NOW = datetime(2026, 8, 30, 3, 0, tzinfo=timezone.utc)


def test_ledger_is_folded_by_video_id_and_later_row_wins(tmp_path):
    """`retimed_at` で予定が動くので、**後の行が勝つ**こと。"""
    led, st = _write(
        tmp_path,
        [{"video_id": "a", "at": "2026-09-01T00:00:00Z", "title": "ふるい"},
         {"video_id": "a", "at": "2026-10-01T00:00:00Z", "title": "あたらしい"}],
        {"a": {"narration": ["x"]}},
    )
    recs = lc.corpus(ledger=led, stash=st, now=NOW)
    assert len(recs) == 1
    assert recs[0]["at"] == "2026-10-01T00:00:00Z"
    assert recs[0]["title"] == "あたらしい"


def test_videos_without_a_stashed_script_are_reported_not_silently_dropped(tmp_path):
    """**分母の話。** 控えの無い本は `corpus()` に入らないが、`coverage()` が数える。

    ここが黙ると、「0/694本」が「見た範囲では0」ではなく
    「1本も無い」と読まれます。**印字は必ず分母を並べること。**
    """
    led, st = _write(
        tmp_path,
        [{"video_id": "a", "at": "2026-09-01T00:00:00Z"},
         {"video_id": "b", "at": "2026-09-02T00:00:00Z"}],
        {"a": {"narration": ["x"]}},
    )
    assert len(lc.corpus(ledger=led, stash=st, now=NOW)) == 1
    cov = lc.coverage(ledger=led, stash=st)
    assert cov == {"ledger": 2, "with_script": 1, "without_script": 1}


def test_bucket_splits_published_from_scheduled(tmp_path):
    led, st = _write(
        tmp_path,
        [{"video_id": "a", "at": "2026-08-01T00:00:00Z"},
         {"video_id": "b", "at": "2026-09-30T00:00:00Z"},
         {"video_id": "c"}],
        {v: {"narration": ["x"]} for v in "abc"},
    )
    got = {r["video_id"]: r["bucket"] for r in lc.corpus(ledger=led, stash=st, now=NOW)}
    assert got == {"a": "public", "b": "scheduled", "c": "undated"}


def test_persona_check_is_borrowed_from_verify_not_reimplemented():
    """**新旧を同じ物差しで並べるため**、パターンをここに持たないこと。

    持つと `verify` 側にだけ語が足された日から、新旧の数が比べられなくなります。
    """
    src = (lc.ROOT / "src" / "legacy_corpus.py").read_text(encoding="utf-8")
    assert "_check_no_human_expert_claim" in src
    assert not hasattr(lc, "_HUMAN_EXPERT_PATTERNS"), (
        "人間の専門家のパターンを `legacy_corpus` に持たないこと（`verify` が正本）")


def test_persona_defect_is_found_when_it_is_really_there():
    """**0件 が「検査が動いていない」ことの結果ではない**と示す。"""
    bad = [{"video_id": "x", "bucket": "public", "title": "",
            "topic": "", "at": None, "narration": ["私は元・経理の担当でした。"],
            "change_ratios": [], "orientation": "縦"}]
    assert len(lc.persona_defects(bad)) == 1


@pytest.mark.parametrize("text", [
    "必ずご自身で確認してください。",   # 注意書き。**指図の逆**
    "税理士に確認してください。",
    "あなたの勤続は5年を越えていますか",  # 締めの問いかけ。助言ではない
    "対象は、使用者の責に帰すべき事由による休業だけです。",  # 法令用語
])
def test_advice_check_does_not_fire_on_disclaimers_or_closing_questions(text):
    """**実測で誤爆した4つ**（2026-08-30）。ここが緩むと「30%が助言」と出ます。"""
    rec = [{"video_id": "x", "bucket": "public", "title": "", "topic": "", "at": None,
            "narration": [text], "change_ratios": [], "orientation": "縦"}]
    assert lc.advice_defects(rec) == []


@pytest.mark.parametrize("text", [
    "この場合はやったほうがいいです。",
    "おすすめです。",
    "必ず得します。",
])
def test_advice_check_fires_on_real_directives(text):
    rec = [{"video_id": "x", "bucket": "public", "title": "", "topic": "", "at": None,
            "narration": [text], "change_ratios": [], "orientation": "縦"}]
    assert len(lc.advice_defects(rec)) == 1


def test_frame_measures_shape_not_content():
    """枠の同一性は**行数と締めの定型**で測る（中身のちがいと混ぜないこと）。"""
    recs = [{"video_id": str(i), "bucket": "public", "title": "", "topic": "", "at": None,
             "narration": ["a", "b", "c", "d", "e", "あなたの控除はいくらですか"],
             "change_ratios": [0.1], "orientation": "縦"} for i in range(10)]
    f = lc.frame(recs)
    assert f["modal_lines"] == 6
    assert f["modal_share"] == 1.0
    assert f["closing_anata"] == 10
    assert f["closing_anata_share"] == 1.0


def test_variety_collapses_digits_so_the_same_template_is_not_counted_as_different():
    """**数字だけがちがう本を「ちがう」と数えない。** そこが型の見分けの肝。"""
    recs = [{"video_id": str(i), "bucket": "public",
             "title": f"年金{i}歳繰下げ 分岐点は{i}か月",
             "topic": "s-nenkin-1", "at": None,
             "narration": [f"{i}万円が境目です。"],
             "change_ratios": [0.1], "orientation": "縦"} for i in range(10)]
    v = lc.variety(recs)
    assert v["opening_shapes"] == 1, "数字を潰したら1つの形になるはず"
    assert v["title_shapes"] == 1
    assert v["topic_families"] == 1


def test_report_names_what_it_did_not_look_at():
    """**見ていないものを言わない道具は、0件 を安全と読ませます。**"""
    out = lc.report()
    assert "見ていないもの" in out
    assert "説明欄" in out


def test_説明欄の行は写しではなく読んだ結果(monkeypatch):
    """**「見ていないもの: 説明欄」を、文字列で持たないこと。**

    あの1行は 2026-08-30 の夜まで固定文で入っており、
    **書いてあるのに誰も測らないまま**、解除条件1・2・5 が閉じました。
    いまは `data/descriptions.json` を読んで、測れていなければ
    **撃つ命令**を、測れていれば**本数と名乗りの件数**を出します。
    """
    from src import descriptions

    monkeypatch.setattr(descriptions, "load", lambda *a, **k: {})
    assert "まだ1本も測れていません" in lc.description_line()

    monkeypatch.setattr(descriptions, "load", lambda *a, **k: {
        "at": "2026-09-01T00:00:00+00:00",
        "videos": [{"title": "x", "description": "計算します。"}],
    })
    line = lc.description_line()
    assert "1本 測れています" in line
    assert "名乗り 0本" in line
