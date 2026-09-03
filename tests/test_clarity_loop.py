"""**説明が分かりやすいかの修正ループ**の検査（2026-09-03）。

オーナー原文（`CLAUDE.md` 冒頭・**一字も変えないこと**）:
「説明が分かりやすいかの修正ループ回してから、その全文照合修正ループ回すようにして」
「説明が分かりやすいかの修正ループは評価する時に分かりにくい部分を批判的に全て上げ、
1番可能性が高いものがほとんど言いがかりになったらループおわり。」
「修正してからまた初めから評価する」

ここが固定するのは4つ:

    1. **順番** —— 分かりやすさの輪が、音を作るより前・全文照合より前に居ること
    2. **「ほとんど言いがかり」の物差し** —— 門A（根拠が本文に在るか）と
       門B（独立にもう1回で再現するか）。**先頭が再現しなければ輪は終わる**
    3. **白紙から評価し直す** —— 前の周の列挙を1件も引き継がないこと
    4. **止め方** —— 同じ指摘が2周 先頭／書き直しで検査が増える／上限

**模型は1度も叩きません**（`reader` / `rewriter` を差し替えて回します）。
"""
from __future__ import annotations

import json

import pytest

from src import clarity_loop as C


# ---------------------------------------------------------------- 形が生きているか

def test_pipeline_は分かりやすさの輪を音より前に回す():
    """**逆にすると、照合した音が全部 捨てになります**（読み上げが変わるので）。"""
    src = (C.config.ROOT / "src" / "pipeline.py").read_text(encoding="utf-8")
    assert "clarify_and_fix(script" in src, "pipeline から分かりやすさの輪が消えている"
    body = src.split("def main(")[1]
    at_clarity = body.index("clarify_and_fix(script")
    at_audio = body.index("# 2. 音声")
    at_hear = body.index("hear_and_fix(script")
    assert at_clarity < at_audio, "分かりやすさの輪が、音を作ったあとに落ちている"
    assert at_clarity < at_hear, (
        "オーナーの順（分かりやすさ → 全文照合）が逆になっている")


def test_verify_の門になっていて_全文照合より前に並ぶ():
    src = (C.config.ROOT / "src" / "verify.py").read_text(encoding="utf-8")
    assert "_check_clarity_loop(work, script)" in src
    body = src.split("def check(")[1]
    assert body.index("_check_clarity_loop(") < body.index("_check_yomi_heard("), (
        "門の並びが、オーナーの順（分かりやすさ → 全文照合）と逆")
    # 絵を描く前に撃たれる側（本文しか無い）へ入れていないこと ——
    # あちらは輪より前に走るので、控えがまだ在りません
    only = src.split("def script_only_problems(")[1].split("\ndef ")[0]
    assert "_check_clarity_loop" not in only


def test_書き直したら台本を置き直して機械の検査を当て直す():
    src = (C.config.ROOT / "src" / "pipeline.py").read_text(encoding="utf-8")
    body = src.split("if clarify_and_fix(script")[1][:900]
    assert 'work / "script.json"' in body, "書き換えた台本を置き直していない"
    assert "script_only_problems" in body, (
        "書き直しのあとに機械の検査を当て直していない"
        "（絵を全部 描いたあとで落ちます）")


# ---------------------------------------------------------------- 門A（根拠）

LINES = [
    "六十五歳から受け取ると、基準の額がそのまま受け取れます。",
    "七十歳まで待つと、この二つの差はひと月あたりで広がっていきます。",
    "先ほどの線は、そちらの帯の左端と同じ位置にあります。",
]


def f(seg, quote, why="耳で取れない", fix="言い換える"):
    return C.Finding(seg=seg, quote=quote, why=why, fix=fix)


def test_本文に無い引用は落とす():
    """**本文に無い所を指しているものは、本文の評価ではありません。**"""
    good = f(2, "この二つの差はひと月あたり")
    bad = f(2, "この三つの差は一年あたりで縮みます")
    assert C.grounded([bad, good], LINES) == [good]


def test_短すぎる引用は根拠にならない():
    assert C.grounded([f(1, "額")], LINES) == []
    assert C.grounded([f(1, "基準の額")], LINES) != []


def test_コマ番号が範囲の外なら落とす():
    assert C.grounded([f(9, "六十五歳から受け取ると")], LINES) == []
    assert C.grounded([f(0, "六十五歳から受け取ると")], LINES) == []


def test_空白のゆれは畳むが文字は落とさない():
    assert C.span(f(1, "基準の 額が　そのまま"), LINES) is not None
    assert C.span(f(1, "基準の値がそのまま"), LINES) is None


# ---------------------------------------------------------------- 門B（再現）

def test_同じコマの重なる範囲に出れば再現():
    a = f(3, "先ほどの線は、そちらの帯の左端")
    b = f(3, "そちらの帯の左端と同じ位置")
    assert C.reproduced(a, [b], LINES) is not None


def test_別のコマなら再現ではない():
    a = f(3, "先ほどの線は、そちらの帯の左端")
    b = f(2, "この二つの差はひと月あたり")
    assert C.reproduced(a, [b], LINES) is None


def test_同じコマでも重ならなければ再現ではない():
    a = f(2, "七十歳まで待つと")
    b = f(2, "ひと月あたりで広がって")
    assert C.reproduced(a, [b], LINES) is None


# ---------------------------------------------------------------- 輪

def script_of(lines):
    return {"segments": [{"narration": x, "visual": {}} for x in lines]}


@pytest.fixture(autouse=True)
def _no_ledger(tmp_path, monkeypatch):
    """**帳面を本物に書かないこと**（検査は data/ を汚さない）。"""
    monkeypatch.setattr(C, "LEDGER", tmp_path / "clarity_loop.jsonl")
    monkeypatch.setattr(C, "mech_problems", lambda script, topic, portrait: [])


def test_先頭が再現しなければ輪は終わる_これがオーナーの止め方():
    """**「1番可能性が高いものがほとんど言いがかりになったらループおわり。」**"""
    script = script_of(LINES)
    calls = {"read": 0, "fix": 0}

    def reader(ls):
        calls["read"] += 1
        # 1回目と2回目で、先頭が別のコマ ＝ 再現しない
        return ([f(1, "六十五歳から受け取ると")] if calls["read"] % 2
                else [f(3, "先ほどの線は、そちらの帯")])

    def rewriter(ls, hits):
        calls["fix"] += 1
        return {}

    rep = C.loop(script, "t", None, reader=reader, rewriter=rewriter, log=lambda *a: None)
    assert calls["fix"] == 0, "言いがかりで書き直しに行っている"
    assert len(rep["rounds"]) == 1
    assert rep["rounds"][0]["top_confirmed"] is False
    assert "言いがかり" in rep["reason"]
    assert rep["changed"] is False


def test_根拠のある指摘が0件でも終わる():
    script = script_of(LINES)
    rep = C.loop(script, "t", None,
                 reader=lambda ls: [f(1, "本文に無い言葉をここに書く")],
                 rewriter=lambda ls, h: {}, log=lambda *a: None)
    assert rep["rounds"][0]["grounded"] == [0, 0]
    assert "根拠" in rep["reason"]


def test_再現したら直して_白紙から評価し直す():
    """**「修正してからまた初めから評価する」** —— 前の列挙を引き継がないこと。"""
    script = script_of(LINES)
    seen: list[list[str]] = []

    def reader(ls):
        seen.append(list(ls))
        if "先ほどの線" in ls[2]:
            return [f(3, "先ほどの線は、そちらの帯の左端")]
        return []                       # 直ったら、もう挙がらない

    def rewriter(ls, hits):
        assert [h.seg for h in hits] == [3]
        return {2: "六十五歳の帯の左端と、七十歳の帯の左端は同じ位置にあります。"}

    rep = C.loop(script, "t", None, reader=reader, rewriter=rewriter, log=lambda *a: None)
    assert rep["fixed"] == 1
    assert rep["changed"] is True
    assert script["segments"][2]["narration"].startswith("六十五歳の帯")
    # 2周目の評価は、**書き換わった本文**を見ている（白紙から）
    assert "先ほどの線" in seen[0][2] and "先ほどの線" not in seen[-1][2]
    assert len(rep["rounds"]) == 2 and rep["rounds"][-1]["grounded"] == [0, 0]


def test_同じ指摘が2周_先頭に来たら止める():
    """書き直しがその文に触らなかった ＝ **この組では直らない**。"""
    script = script_of(LINES)
    rep = C.loop(script, "t", None,
                 reader=lambda ls: [f(3, "先ほどの線は、そちらの帯の左端")],
                 # 別のコマだけ書き換えて、指摘された文は触らない
                 rewriter=lambda ls, h: {0: "六十五歳から受け取ると、基準の額が出ます。"},
                 log=lambda *a: None)
    assert "直らない" in rep["reason"]
    assert len(rep["rounds"]) == 2


def test_書き直しで機械の検査が増えたらその周を捨てる(monkeypatch):
    """**分かりやすくして検査に落ちるのは、退化です。**"""
    script = script_of(LINES)
    before = list(LINES)
    monkeypatch.setattr(C, "mech_problems",
                        lambda s, t, p: ([] if s["segments"][2]["narration"] == LINES[2]
                                         else ["画面に無い数を言っている"]))
    rep = C.loop(script, "t", None,
                 reader=lambda ls: [f(3, "先ほどの線は、そちらの帯の左端")],
                 rewriter=lambda ls, h: {2: "新しい数 12万3000円 を足した文。"},
                 log=lambda *a: None)
    assert "増えた" in rep["reason"]
    assert [s["narration"] for s in script["segments"]] == before, (
        "捨てるはずの周が、台本に入っている")
    assert rep["changed"] is False


def test_上限で止まる():
    script = script_of(LINES)
    n = {"i": 0}

    def rewriter(ls, hits):
        n["i"] += 1
        return {2: f"言い換えた文 その{n['i']}。先ほどの線は、そちらの帯の左端です。"}

    rep = C.loop(script, "t", None, rounds=2,
                 reader=lambda ls: [f(3, "先ほどの線は、そちらの帯の左端")],
                 rewriter=rewriter, log=lambda *a: None)
    assert len(rep["rounds"]) == 2
    assert "上限" in rep["reason"] or "直らない" in rep["reason"]


def test_評価が落ちても輪は例外を投げない():
    """**模型が落ちたのは、本の欠陥ではない。**"""
    def boom(ls):
        raise RuntimeError("網が落ちた")

    rep = C.loop(script_of(LINES), "t", None, reader=boom,
                 rewriter=lambda ls, h: {}, log=lambda *a: None)
    assert "評価に失敗" in rep["reason"]


def test_控えを仕事場に置く(tmp_path):
    rep = C.loop(script_of(LINES), "t", tmp_path,
                 reader=lambda ls: [], rewriter=lambda ls, h: {}, log=lambda *a: None)
    blob = json.loads((tmp_path / C.REPORT_NAME).read_text(encoding="utf-8"))
    assert blob["end"] == C.fingerprint(LINES) == rep["end"]


# ---------------------------------------------------------------- 門（verify）

def test_控えが無ければ落とす(tmp_path):
    from src import verify
    if not __import__("shutil").which("claude"):
        pytest.skip("claude コマンドが無い環境では、この門は素通りする")
    out = verify._check_clarity_loop(tmp_path, script_of(LINES))
    assert out and "控え" in out[0]


def test_控えの指紋が違えば落とす(tmp_path):
    from src import verify
    if not __import__("shutil").which("claude"):
        pytest.skip("claude コマンドが無い環境では、この門は素通りする")
    (tmp_path / C.REPORT_NAME).write_text(
        json.dumps({"end": "0" * 16, "reason": "誤読 0件", "rounds": []}),
        encoding="utf-8")
    out = verify._check_clarity_loop(tmp_path, script_of(LINES))
    assert out and "この読み上げのもの" in out[0]


def test_指紋が合えば通す(tmp_path):
    from src import verify
    (tmp_path / C.REPORT_NAME).write_text(
        json.dumps({"end": C.fingerprint(LINES), "reason": "言いがかり", "rounds": [{}]}),
        encoding="utf-8")
    assert verify._check_clarity_loop(tmp_path, script_of(LINES)) == []


def test_模型が落ちた回は落とさない(tmp_path):
    """**誤報は不投稿。** 網が落ちたことは、本の欠陥ではありません。"""
    from src import verify
    (tmp_path / C.REPORT_NAME).write_text(
        json.dumps({"end": C.fingerprint(LINES),
                    "reason": "評価に失敗（RuntimeError: 網が落ちた）", "rounds": []}),
        encoding="utf-8")
    assert verify._check_clarity_loop(tmp_path, script_of(LINES)) == []
