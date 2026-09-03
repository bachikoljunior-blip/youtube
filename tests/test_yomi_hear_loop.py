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


# ------------------------------------------- 実物の1本で踏んだ2つ（2026-09-03）

def test_コマの間の無音を足さないと長尺は1本も通らない():
    """`renderer.build_audio()` は間に 0.35秒 の無音を挟みます。

    足さずに「完成音声の秒数 ＝ コマの合計」で見ると、**コマ数 × 0.35秒** ぶん
    必ず食い違う —— 64コマの本で **22.4秒**。実測（09/04 `1huadpEk6HY` の焼き直し）:
    「完成音声 1332.0秒 とコマの合計 1309.6秒 が食い違う」で落ちました。
    **この門は、実物の長尺を1本残らず落とす形でした。**
    """
    src = (H.ROOT / "src" / "verify.py").read_text(encoding="utf-8")
    body = src.split("def _check_yomi_heard(")[1].split("\ndef ")[0]
    assert "SILENCE_SECONDS" in body, "無音ぶんを足していない（長尺が1本も通りません）"


def test_刻むときも無音を足す():
    """足さないと、ずれが1コマごとに積もって**別の所**を切り出します。"""
    src = (H.ROOT / "src" / "yomi_hear.py").read_text(encoding="utf-8")
    body = src.split("def slice_final(")[1]
    assert "start += dur + SILENCE_SECONDS" in body, (
        "刻む位置に無音を足していない（終わりのコマほどずれます）")


def test_活用形は台帳に入れない():
    """**実物の1本を、二度と通らない形にしました。**

    09/04 `1huadpEk6HY` の焼き直しが、認識器の書き違い（「留まって」「円割り」）から
    `止まっ → トマッ` / `変わり → カワリ` を台帳に入れ、`yomi_gate` の R3 が落とした。
    「全額止まっていました」の「止まっ」は**前が漢字**なので
    `apply_corrections()` が構造的に置換に行けず、**直す手が1つも無い。**
    そして活用形は台帳の単位として間違い（「止まっ」を直しても「止まり」は直らない）。
    """
    assert not H.fixable("止まっ", "動詞")
    assert not H.fixable("変わり", "動詞")
    assert not H.fixable("高く", "形容詞")
    assert H.fixable("控除額", "名詞")
    assert H.fixable("控除額")                       # 品詞を渡さない古い呼びは今までどおり


def test_R3_は置換が届かない出現では鳴らない():
    """届かない所で鳴らすと、**その本は二度と通りません。**"""
    from src import yomi_gate as G
    led = {"止まっ": {"verdict": "misread", "correct": "トマッ"}}
    # 前が漢字 ＝ `apply_corrections` が構造的に置換に行けない出現
    out = G.inspect("全額止まっていました", risk={}, ledger=led)
    assert not [x for x in out if x["code"] == "R3"], (
        "置換の届かない出現で R3 が鳴っている（直す手が無いのに落ちます）")
    # 前が漢字でない ＝ 置換に行けるはず。それでも残っていれば、それは本当の警報
    out = G.inspect("が止まっていました", risk={}, ledger=led)
    assert [x for x in out if x["code"] == "R3"], "本当の警報まで消している"
