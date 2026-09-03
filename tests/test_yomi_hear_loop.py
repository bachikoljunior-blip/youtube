"""**全文照合を輪にする**（2026-09-03）。

オーナー原文（`CLAUDE.md` 冒頭・**一字も変えないこと**）:
「全文照合はループにしてよ」
（＝ 聞き取り→照合→修正・再生成→再照合を、**誤読が 0 になるまで繰り返す輪**）

`src/yomi_hear.audit()` は 09/03 の朝まで**1周しか直しませんでした**。
ここが固定するのは、輪になっていることと、**回し続けないための出口**:

    誤読 0件              → 終わり（輪の目的）
    **同じ語が直らない**   → 止める（仮名置換では直らない形。もう1周 回しても
                            Google TTS を 64回 撃つ時間を払うだけ）
    上限                  → 止める（保険）

**音声認識も API キーも要りません** —— `hear()` を差し替えて、輪の側だけを見ます。
"""
from __future__ import annotations

import json

import pytest

from src import yomi_hear as H


def row(surface, pron, verdict="misread"):
    return {"surface": surface, "pron": pron, "heard": "ヒタイ", "verdict": verdict,
            "seg": 0, "sentence": "実際の額は", "spoken": "実際の額は", "char": 3,
            "k0": 0, "k1": 2, "pos": "名詞"}


def report_of(hits):
    return {"lines": 3, "words": 12, "split": len(hits), "hits": list(hits),
            "heard_text": ["あ", "い", "う"]}


@pytest.fixture
def stub(monkeypatch, tmp_path):
    """`hear()` の返りを周ごとに並べて渡す。`record()` は台帳を触らない。"""
    state = {"heard": 0, "resynth": 0, "recorded": []}

    def install(reports):
        def hear(lines, wavs, **kw):
            state["heard"] += 1
            return report_of(reports[min(state["heard"] - 1, len(reports) - 1)])

        def record(rep):
            fixed = {r["surface"]: r["pron"] for r in rep["hits"]
                     if r["verdict"] == "misread" and H.fixable(r["surface"])}
            state["recorded"].append(fixed)
            return fixed

        monkeypatch.setattr(H, "hear", hear)
        monkeypatch.setattr(H, "record", record)
        return state

    return install


def resynth_of(state):
    def resynth():
        state["resynth"] += 1
        return []
    return resynth


def test_誤読が消えるまで回る(stub, tmp_path):
    state = stub([[row("賃金日額", "チンギンニチガク")], []])
    rep = H.audit(["あ", "い", "う"], [], tmp_path,
                  resynth=resynth_of(state), log=lambda *a: None)
    assert rep["passes"] == 2, "1周で止まっている（輪になっていない）"
    assert rep["reason"] == "誤読 0件"
    assert state["resynth"] == 1
    assert rep["fixed"] == {"賃金日額": "チンギンニチガク"}


def test_3周でも回る(stub, tmp_path):
    """**「誤読が 0 になるまで」** —— 2周で切っていないこと。"""
    state = stub([[row("賃金日額", "チンギンニチガク")], [row("賞与", "ショーヨ")], []])
    rep = H.audit(["あ"], [], tmp_path, resynth=resynth_of(state), log=lambda *a: None)
    assert rep["passes"] == 3 and rep["reason"] == "誤読 0件"
    assert rep["fixed"] == {"賃金日額": "チンギンニチガク", "賞与": "ショーヨ"}


def test_同じ語が同じ読みで残ったら止める(stub, tmp_path):
    """焼き直したのにまた割れた ＝ 仮名置換では直らない形。**回し続けない。**"""
    state = stub([[row("賃金日額", "チンギンニチガク")]])       # ずっと同じ
    rep = H.audit(["あ"], [], tmp_path, resynth=resynth_of(state), log=lambda *a: None)
    assert rep["passes"] == 2, "同じ語で回り続けている"
    assert "同じ語が直らない" in rep["reason"] and "賃金日額" in rep["reason"]
    assert state["resynth"] == 1


def test_上限で止まる(stub, tmp_path, monkeypatch):
    """毎周 別の語が出続けても、上限で出ること（保険）。"""
    monkeypatch.setattr(H, "HEAR_MAX_PASSES", 3)
    state = stub([[row(f"語{i}", f"ゴ{i}")] for i in range(9)])
    rep = H.audit(["あ"], [], tmp_path, resynth=resynth_of(state), log=lambda *a: None)
    assert rep["passes"] == 3 and "上限" in rep["reason"]


def test_1文字の語では回らない(stub, tmp_path):
    """`fixable()` が弾く語で焼き直すと、**永久に回ります**（直せないので）。"""
    state = stub([[row("額", "ガク")]])
    rep = H.audit(["あ"], [], tmp_path, resynth=resynth_of(state), log=lambda *a: None)
    assert rep["passes"] == 1 and rep["reason"] == "誤読 0件"
    assert state["resynth"] == 0


def test_焼き直す口が無ければ1周で出る(stub, tmp_path):
    """`verify` の側の呼び（音はもう焼けている）。落とすのはあちら。"""
    stub([[row("賃金日額", "チンギンニチガク")]])
    rep = H.audit(["あ"], [], tmp_path, resynth=None, log=lambda *a: None)
    assert rep["passes"] == 1 and "焼き直す口が無い" in rep["reason"]
    assert rep["misread"] == 1


def test_控えに輪の記録が残る(stub, tmp_path):
    stub([[row("賃金日額", "チンギンニチガク")], []])
    H.audit(["あ"], [], tmp_path, resynth=resynth_of({"resynth": 0}),
            log=lambda *a: None)
    blob = json.loads((tmp_path / H.REPORT_NAME).read_text(encoding="utf-8"))
    assert blob["passes"] == 2 and blob["reason"] == "誤読 0件"
    assert blob["fingerprint"] == H.fingerprint(["あ"])


def test_輪の上限が定数で置いてある():
    """直値で書くと、次に触る回が理由を読まずに増やせます。"""
    src = (H.ROOT / "src" / "yomi_hear.py").read_text(encoding="utf-8")
    assert "HEAR_MAX_PASSES" in src
    assert "while True:" in src.split("def audit(")[1], "輪になっていない"
