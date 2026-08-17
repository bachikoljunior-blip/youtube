"""`src/section_depth.py` —— **在庫を増やす道を、2つとも出す**（2026-08-17）。

`status.py` は長らく「**増やす道は1つだけ ＝ 新しい表を書く**」と言っていました。
**その1つが、2つのうち高いほう**です（直近8回のうち7回で最大の時間食い・20〜25分）。

**故障注入つきで書くこと。** ここの検査は「一覧が当たりを含まないまま育つ」の
仲間になりやすい —— 出力が出ているだけで通ってしまうので、
**間違った並べ方をしたときに落ちるか**を必ず確かめます。
"""
from __future__ import annotations

import pytest

from src import section_depth


def _mods(counts: dict[str, int]) -> dict[str, dict[str, str]]:
    """モジュール名 → 節数 から、`topic_forge.survey()` の1つめの形を作る。"""
    return {m: {f"=== {m}{i} ===": "" for i in range(n)} for m, n in counts.items()}


def test_節の数を数える():
    got = section_depth.depths(_mods({"a": 3, "b": 7}))
    assert got == {"a": 3, "b": 7}


def test_目標は中央値ではなく上位四分位():
    """**中央値では低すぎます。** 実測 37本で、中央値5節・上位四分位7節。

    中央値に揃えると余地は +6節、上位四分位なら +53節。
    **「4分の1の表がもう届いている線」なので、届く証拠のある目標**です。
    """
    mods = _mods({f"m{i}": n for i, n in enumerate([3, 4, 5, 5, 6, 7, 8, 13])})
    assert section_depth.median_depth(mods) == 5.5
    assert section_depth.target_depth(mods) > section_depth.median_depth(mods)


def test_目標に届いている表は候補に出ない():
    mods = _mods({"deep": 13, "shallow": 3})
    got = [r[0] for r in section_depth.candidates(mods)]
    assert "deep" not in got
    assert "shallow" in got


def test_実績の高い族が先に来る():
    """**浅いだけで選ばない。** 門は登録者なので、族の順番の値を掛けます。"""
    mods = _mods({"yowai": 3, "tsuyoi": 4, "x": 7, "y": 7, "z": 7})
    scores = {"yowai": 0.1, "tsuyoi": 10.0}
    got = [r[0] for r in section_depth.candidates(mods, scores, base=1.0)]
    assert got[0] == "tsuyoi", "浅い順のままで、実績が並べ替えに効いていない"


def test_実績が無い族は全体平均で扱う():
    """`family_perf.scorer` と同じ扱い。**未知の族を0点にすると探索が死にます。**"""
    mods = _mods({"unknown": 3, "x": 7, "y": 7, "z": 7})
    got = section_depth.candidates(mods, scores={}, base=2.0)
    assert got and got[0][3] == pytest.approx(got[0][2] * 2.0)


def test_報告は道を2つとも名指しする():
    lines = "\n".join(section_depth.report_lines(_mods({"a": 3, "x": 7, "y": 7, "z": 7})))
    assert "(A)" in lines and "(B)" in lines
    assert "1つだけ" not in lines, "**直した文言が戻っています**"


def test_候補が無いときは新しい表を選べと言う():
    """**「候補なし」を黙って空行にしないこと。** 次の回が何を選ぶか分かりません。"""
    lines = "\n".join(section_depth.report_lines(_mods({"a": 7, "b": 7, "c": 7})))
    assert "(A) を選ぶこと" in lines


def test_表が1本も無くても落ちない():
    """`src/calc/` が読めない回でも `status.py` を止めないこと。"""
    assert section_depth.candidates({}) == []
    assert section_depth.target_depth({}) == 0
    assert section_depth.report_lines({})


def test_故障注入_目標を最大に置くと余地が水増しされる():
    """**楽観の側の壊れ方**を、検査が見分けられることを確かめる。

    最大（13節）を全部に課すと、3節の表の余地が 4 から 10 に膨らみます。
    **題材の深さを無視した数字**なので、上位四分位より必ず大きくなること。
    """
    mods = _mods({f"m{i}": n for i, n in enumerate([3, 4, 5, 5, 6, 7, 8, 13])})
    tgt = section_depth.target_depth(mods)
    biggest = max(section_depth.depths(mods).values())
    assert tgt < biggest, "目標が最大に張り付いている＝余地を水増ししている"
