"""`calc:` の繋ぎ忘れを名指しする道具の検査（`src/topic_gaps.py`）。

**実物にも1件当てます**（`config/topics.yaml` と `src/calc/`）——
道具だけを模型で検査すると、**実物の形が変わったときに緑のまま外れます**
（`retro.noise_tokens` で1度踏んだ形）。
"""
from __future__ import annotations

from pathlib import Path

from src import config, topic_gaps

MODS = {"fukugyo", "ideco", "kokuho"}


def test_calc_ari_ha_dasanai():
    """`calc:` が入っているテーマは、そもそも出しません。"""
    rows = topic_gaps.calcless([{"id": "fukugyo-zeikin", "calc": "fukugyo"}], MODS)
    assert rows == []


def test_hyou_ga_aru_noni_tunagatte_inai():
    """表が在るのに繋がっていないものは、繋ぎ先の候補ごと出す。"""
    rows = topic_gaps.calcless([{"id": "fukugyo-zeikin", "title_seed": "副業"}], MODS)
    assert len(rows) == 1
    assert rows[0]["candidate"] == "fukugyo"


def test_hyou_ga_nai_mono_ha_kouho_nashi():
    """表が無いものは候補も無い ＝ (A) の題材のほう。"""
    rows = topic_gaps.calcless([{"id": "kojin-jigyo-keihi", "title_seed": "経費"}], MODS)
    assert rows[0]["candidate"] is None


def test_id_no_go_dake_wo_miru():
    """題や angle の全文では拾わない（言及しただけの表に当たるため）。"""
    rows = topic_gaps.calcless(
        [{"id": "nazo-no-tema", "title_seed": "国保と ideco はどちらが得か"}], MODS)
    assert rows[0]["candidate"] is None


def test_modules_ha_hyou_de_nai_mono_wo_otosu():
    """`_checks` / `_template` / `__init__` は表ではない。"""
    mods = topic_gaps.modules()
    assert "_checks" not in mods
    assert "_template" not in mods
    assert "__init__" not in mods
    assert "kokuho" in mods                      # 実物が読めていること


def test_toukou_zumi_ha_zaiko_ga_fuenai_to_iu():
    """投稿済みのテーマは、繋いでも在庫が増えないと言う。"""
    lines = topic_gaps.report_lines(
        [{"id": "fukugyo-zeikin", "title_seed": "副業"}],
        posted={"fukugyo-zeikin"}, mods=MODS)
    assert any("投稿済み" in ln for ln in lines)


def test_kara_nara_nani_mo_dasanai():
    """繋ぎ忘れが無ければ1行も出さない（一覧を空で育てないため）。"""
    assert topic_gaps.report_lines([{"id": "a", "calc": "kokuho"}], mods=MODS) == []


def test_jitsubutsu_no_topics_yaml_ni_atete_miru():
    """**実物**: `calc:` の無いテーマの候補は、実在する表しか指さない。"""
    topics = config.load_topics()["topics"]
    mods = topic_gaps.modules()
    calc_dir = Path(__file__).resolve().parent.parent / "src" / "calc"
    for row in topic_gaps.calcless(topics, mods):
        if row["candidate"]:
            assert (calc_dir / f"{row['candidate']}.py").exists(), row
