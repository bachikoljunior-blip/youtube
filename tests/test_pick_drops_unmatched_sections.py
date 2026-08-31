"""**`calc_sections` が1つも当たらないテーマを、作る前に外すこと。**

## なぜ要るか（2026-08-30 に足した）

`src/script_writer.py` は、`calc_sections` に当たる節が
`src.calc.<calc>` の出力に1つも無いと `RuntimeError` を投げます ——
**台本を書く前に、確実に、毎回**落ちます。`dupes` の門と同じ
「**作る前に分かる死**」なのに、`pick()` はそれを見ていませんでした。

実測 2026-08-30: `tokurou-danjo-48kagetsu-4800000` は、同じ日の別の回が
`calc: saishushoku → tokurou` を直したときに **`calc_sections` を写し忘れ**、
再就職手当（雇用保険）の見出しを指したままでした。
`batch_build --count 11 --long` はそれを 11本目に選んでいます。
気づいたのは**全体スイートを別件で回したから**で、`pick()` からは見えません。
長尺は1本 13〜19分 なので、**そのまま撃てばその時間がまるごと捨て**でした。

**覆る条件**: `script_writer` が「当たらないときは全節を渡す」形に変わったら、
これは死ではなくなるので、この門ごと外すこと。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _batch_build():
    if "batch_build" in sys.modules:
        return sys.modules["batch_build"]
    spec = importlib.util.spec_from_file_location(
        "batch_build", ROOT / "scripts" / "batch_build.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["batch_build"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def bb(monkeypatch):
    mod = _batch_build()
    # 表は走らせない（この検査が見るのは**当たり判定**だけ）。
    monkeypatch.setattr(mod, "_calc_sections_cached", lambda calc: (
        ("=== 生まれた年で、65歳より前に受け取れる月数が階段状に消えていく ===", "…"),
        ("=== 同じ区分でも、女性は5年おくれの階段なのでここまで差が付く ===", "…"),
    ))
    return mod


def _topic(tid: str, sections: list[str] | None) -> dict:
    t = {"id": tid, "calc": "tokurou", "title_seed": ""}
    if sections is not None:
        t["calc_sections"] = sections
    return t


def test_a_topic_whose_sections_never_match_is_dropped(bb, capsys):
    doomed = _topic("tokurou-danjo", ["330日の区分で3分の1まで受給してから決めた人"])
    kept = bb._drop_doomed([doomed], [doomed])
    assert kept == []
    out = capsys.readouterr().out
    # **名前を出さずに落とさないこと**（`_drop_doomed` の docstring）。
    assert "tokurou-danjo" in out
    assert "calc_sections" in out


def test_a_topic_whose_sections_match_is_kept(bb):
    ok = _topic("tokurou-danjo", ["女性は5年おくれの階段"])
    assert bb._drop_doomed([ok], [ok]) == [ok]


def test_partial_match_is_enough(bb):
    """当たり判定は**部分一致**（`topic_forge.sections_for` が正本）。"""
    ok = _topic("tokurou-danjo", ["階段状に消えていく"])
    assert bb._drop_doomed([ok], [ok]) == [ok]


def test_a_topic_without_calc_sections_is_untouched(bb):
    """`calc_sections` の無いテーマは全節が渡るので、ここでは落ちない。"""
    ok = _topic("tokurou-nashi", None)
    assert bb._drop_doomed([ok], [ok]) == [ok]


def test_every_live_topic_with_sections_still_hits_its_calc():
    """**実物の台帳**（`config/topics.yaml`）で、当たらないテーマが無いこと。

    `tests/test_calc_sections_still_hit.py` と同じことを見ていますが、
    あちらは `calc` べつ、こちらは **`pick()` が実際に使う経路**で見ます。
    落ちたら直すのは `config/topics.yaml` の `calc_sections` です。
    """
    import yaml

    topics = yaml.safe_load(
        (ROOT / "config" / "topics.yaml").read_text(encoding="utf-8"))
    rows = topics["topics"] if isinstance(topics, dict) else topics
    bad = [t["id"] for t in rows
           if t.get("calc_sections") and not t.get("calc")]
    assert not bad, f"calc_sections はあるのに calc が無いテーマ: {bad}"
