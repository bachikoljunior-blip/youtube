"""読みの総当たり（`src/yomi_sweep.py`）の検査。**API キーも音声も要りません。**

ここが守っているのは、オーナーが固定した与件の1つ目です:

    「ナレーションの漢字の読み方全部正しくして」（2026-09-02・原文）

**「全部」を、語を1つずつ並べる形で満たさないこと。** だから検査も
「額が入っているか」ではなく、**候補が自分の台本から自動で出てくること**と、
**測れない語を『合っている』と数えないこと**を見ます。
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import yomi_sweep  # noqa: E402


def test_数詞は割れている語に数えない():
    """十 ジュッ/ジュー・百 ヒャク/ビャク/ピャク は連濁と促音便で、**正しい割れ方**。

    ここを候補に入れると、正しい音便が毎回「読みが割れている」として出て、
    本当の誤読がその中に埋もれます（2026-09-02 の実測で 30語 → 10語 に減る）。
    """
    occ = {
        "十": Counter({"ジュッ": 3, "ジュー": 5}),
        "百": Counter({"ヒャク": 4, "ビャク": 1}),
        "行": Counter({"クダリ": 13, "ギョー": 3}),
    }
    testable, _untestable = yomi_sweep.split_words(occ)
    assert set(testable) == {"行"}


def test_候補が1つの語は測れない側に入る():
    """**`額` がここに落ちます。**

    open-jtalk は全文脈で ガク と読み、Google だけが ひたい と読みました
    （2026-08-16・オーナーが耳で発見）。**自分の台本の中では割れないので、
    この道具では候補が作れません。** それを「合っている」に数えたら、
    直っていない語が直った顔をします。
    """
    occ = {"額": Counter({"ガク": 34}), "行": Counter({"クダリ": 13, "ギョー": 3})}
    testable, untestable = yomi_sweep.split_words(occ)
    assert "額" not in testable
    assert "額" in untestable


def test_片仮名の読みは平仮名の候補になる():
    """候補は文に差し込むので、既存の記録（がく／ひたい）と字を揃える。"""
    assert yomi_sweep._kata_to_hira("ギョー") == "ぎょー"
    assert yomi_sweep._kata_to_hira("ガク’") == "がく"


def test_公開済みの台本から地の文が取れる():
    """候補の出どころが空になっていないこと（`data/critique_queue` の形が変わったら赤）。"""
    lines = yomi_sweep.corpus_lines()
    assert len(lines) > 500, f"地の文が {len(lines)}行 しかありません"


def test_割れている語が自分の台本から出てくる():
    """**手で並べた一覧ではなく、実物から出ていること。**

    2026-09-02 の実測は 10語（年 日 人 分 行 上 方 下 高 後）。
    **この数そのものは動いてよい** —— 見ているのは
    「1語も出ない（＝ 候補の出どころが壊れた）」ことと
    「数詞まで出る（＝ 音便を誤読と呼んでいる）」ことだけです。
    """
    from scripts.check_yomi import available

    if not available():
        return  # open-jtalk が無い環境では飛ばす（`bash scripts/setup.sh` で入る）
    lines = yomi_sweep.corpus_lines()[:600]
    occ, _examples = yomi_sweep.readings_of(lines)
    testable, untestable = yomi_sweep.split_words(occ)
    assert occ, "漢字を含む語が1つも取れていません"
    assert len(untestable) > len(testable), "割れている語のほうが多いのは、数え方が壊れた合図"
    assert not any(yomi_sweep.NUMERAL.match(s) for s in testable)
