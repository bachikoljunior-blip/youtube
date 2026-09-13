# -*- coding: utf-8 -*-
"""`scripts/method_growth.py` の **節ごと**（§0〜§6・§8）の物差し —— 2026-09-13 12:0x（optimizer・Opus）。

**なぜ足したか**: 合計の門（`verdict`）は引かれた回に

    **吸った節を名指しして、§5／§6 の形（決めは本文・derivation は外）を当てること**

と印字しますが、**その「名指し」をする口がありませんでした**（§3 の覆る条件 (2) が
2026-09-12 17:4x に「`--split` は §0〜§6・§8 を**まとめてしか見ていない**」と書いた当のもの）。
`views_streak`・`late_run`・`shape_run`・`turf_run` と同じ族の **11例目**。

**陽性対照は撃って落としてある**（§5 の教訓の形3つ目）:
`main_split_drawn` の行を報告から外すと、下の 2件 が落ちる。
"""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _mod():
    spec = importlib.util.spec_from_file_location("method_growth", ROOT / "scripts" / "method_growth.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


M = _mod()
TEXT = (ROOT / "docs" / "METHOD.md").read_text(encoding="utf-8")


def test_節ごとの合計は_measure_と_1字も違わないこと():
    """**割りは足し算を変えません** —— 違えば、名指しは別の物を測っています。"""
    split = M.measure_main_split(TEXT)
    whole = M.measure(TEXT)
    assert sum(c["body_chars"] for c in split.values()) == whole["body_chars"]
    assert sum(c["body_lines"] for c in split.values()) == whole["body_lines"]
    assert sum(c["quote_chars"] for c in split.values()) == whole["quote_chars"]


def test_節の名は_0_から_6_と_8():
    """§7 は「毎回 読む」側ではありません（`section7_spans` が別に数える側）。"""
    assert list(M.measure_main_split(TEXT)) == ["§0", "§1", "§2", "§3", "§4", "§5", "§6", "§8"]


def test_節の挟みは重ならず_隙間は_7_の_1か所だけ():
    lines = TEXT.split("\n")
    spans = M.main_spans(lines)
    for (_, _, b), (_, a2, _) in zip(spans, spans[1:]):
        assert b <= a2, "節が重なっています"
    gaps = [a2 - b for (_, _, b), (_, a2, _) in zip(spans, spans[1:]) if a2 != b]
    assert len(gaps) == 1, "空くのは §7 の1か所だけ"


def test_見出しが無ければ黙って_0_を返さないこと():
    """**止まるほうが、外れた数を配るより安い**（`main_spans` の覆る条件 (2)・冒頭の註）。"""
    with pytest.raises((KeyError, ValueError)):
        M.measure_main_split("## 0. なにか\n本文\n")   # `## 7.` が無い ＝ 挟みが外れる


def _p(vals):
    """`main_split` だけを持つ窓の並びを作る（門は 1周ぶんの字だけを見る）。"""
    return [{"main_split": v} for v in vals]


def test_節ごとの門は_2窓_続いたときだけ引く():
    assert M.main_split_drawn(_p([{"§5": 400.0}, {"§5": 400.0}])) == ["§5（+400 / +400）"]
    assert M.main_split_drawn(_p([{"§5": 400.0}, {"§5": 10.0}])) == []
    assert M.main_split_drawn(_p([{"§5": 10.0}, {"§5": 400.0}])) == []


def test_節ごとの門は窓が_1つ_しか無ければ引かないこと():
    assert M.main_split_drawn(_p([{"§5": 999.0}])) == []


def test_positive_control_合計が下を向いても節の門は鳴ること():
    """**合計は節どうしの打ち消しに対して盲**（`split_drawn` と同じ理由）。"""
    ps = _p([{"§4": -2000.0, "§5": 400.0}, {"§4": -2000.0, "§5": 400.0}])
    assert M.main_split_drawn(ps) == ["§5（+400 / +400）"]


def test_窓の頭に無い節は数えないこと():
    """節が増えた回に、書き下ろしを「1周ぶんの伸び」と読まないため（`points` 側で `None`）。"""
    assert M.main_split_drawn(_p([{"§5": None}, {"§5": 400.0}])) == []


def test_報告に節ごとの門の行が出ること():
    out = M.report(laps=6, n=3)
    assert "節ごとの門 1周 +300字:" in out


def test_positive_control_報告の行は_main_split_drawn_の答えを載せていること(monkeypatch):
    monkeypatch.setattr(M, "main_split_drawn", lambda ps: ["§9（+1 / +1）"])
    assert "§9（+1 / +1）" in M.report(laps=6, n=3)


def test_split_report_に節ごとの並びが出ること():
    out = M.split_report(laps=6, n=3)
    assert out.startswith("節ごとの伸び")
    assert "塊ごとの伸び" in out, "§7 の塊の側を落としていないこと"
    assert "§5" in out


def test_points_は節ごとの数も同じ窓で持つこと():
    ps = M.points(laps=6, n=2)
    assert ps and all(p.get("main_split") for p in ps)
    for p in ps:
        # 節ごとの 1周ぶんの和 ＝ 合計の 1周ぶん（同じ窓・同じ数え方）。
        assert abs(sum(p["main_split"].values()) - p["chars_per_lap"]) < 1e-6
