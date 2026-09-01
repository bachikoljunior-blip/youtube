"""読みの門が「語の一覧」ではなく「危ない形」で決まっていることの検査。

**戻すにはこの検査を消すしかありません**（diff に出ます）。

オーナー原文（`CLAUDE.md` 固定その3・**一字も変えないこと**）:
「ナレーションの漢字の読み方全部正しくして」

2026-09-02 まで `src/verify._check_yomi` が見ていた語は **1語**（裸の「額」）で、
この repo の読み上げ（694本・6,206行・漢字のかたまり 異なり 3,514語）の **0.03%**
だった。ここが見るのは「もう1語ずつではないこと」そのもの。
"""
from __future__ import annotations

import json

import pytest

from src import verify, yomi_gate
from src.yomi import to_speech


def test_門は語の一覧を持たない():
    """`inspect()` に語の表が直書きされていないこと。**足すのは形のほう。**"""
    src = (yomi_gate.ROOT / "src" / "yomi_gate.py").read_text(encoding="utf-8")
    body = src.split("def inspect(")[1].split("\ndef ")[0]
    # 註（`#` 行）は実測の記録なので除く。見るのは**動く行**だけ。
    code = "\n".join(ln for ln in body.splitlines()
                     if not ln.lstrip().startswith("#"))
    # 判定に使ってよいのは、実測から作った表（risk/ledger）だけ。
    assert "load_risk" in src and "load_ledger" in src
    for hardcoded in ("額", "控除", "年金", "日額"):
        assert hardcoded not in code, f"inspect() に語が直書きされている: {hardcoded}"


def test_危ない条件は4つとも生きている():
    src = (yomi_gate.ROOT / "src" / "yomi_gate.py").read_text(encoding="utf-8")
    for code in ("R0", "R1", "R2", "R3"):
        assert f'"code": "{code}"' in src, f"{code} が消えている"


@pytest.mark.skipif(not yomi_gate.available(), reason="open-jtalk が無い")
def test_音にならない漢字は無条件で落ちる():
    """R0。読めない字は open-jtalk が記号にして落とすので、音から消える。"""
    hits = yomi_gate.inspect("𠮟責について話します。", risk={}, ledger={})
    assert any(h["code"] == "R0" for h in hits), hits


@pytest.mark.skipif(not yomi_gate.available(), reason="open-jtalk が無い")
def test_割れる語は実測の表から名指しされる():
    """R1。表を差し替えれば名指しも変わる ＝ 一覧をコードに持っていない。"""
    hits = yomi_gate.inspect("長くもらえる人ほど得です。",
                             risk={"人": ["ニン", "ヒト"]}, ledger={})
    assert any(h["code"] == "R1" and h["surface"] == "人" for h in hits), hits
    # 耳が safe と言えば黙る
    quiet = yomi_gate.inspect("長くもらえる人ほど得です。",
                              risk={"人": ["ニン", "ヒト"]},
                              ledger={"人": {"verdict": "safe"}})
    assert not any(h["code"] == "R1" for h in quiet), quiet


@pytest.mark.skipif(not yomi_gate.available(), reason="open-jtalk が無い")
def test_数詞は割れても名指ししない():
    """1文字の数詞は、後ろの助数詞で読みが変わるのが**正しい**。

    実測（2026-09-02）: これを R1 に入れると1本ぶんの名指しが 168件 になり、
    その9割が数詞で埋まって、本当に危ない語が読めなくなった。
    **覆る条件**: 耳が数詞の誤読を実際に捕まえたら、この除外を外すこと。
    """
    hits = yomi_gate.inspect("十五キロと二十五キロ。",
                             risk={"十": ["ジュッ", "ジュー"]}, ledger={})
    assert not any(h["code"] == "R1" for h in hits), hits


@pytest.mark.skipif(not yomi_gate.available(), reason="open-jtalk が無い")
def test_R2は隣り合う並びだけを見る():
    """行の別の場所に在る1文字を、熟語の中に「見つけて」しまわないこと。

    2026-09-02 に実測で踏んだ形: 「賃金日額」が、同じ行の別の場所の
    1文字トークンで名指しされていた（文字列の当たりだけを見ていた）。
    """
    hits = yomi_gate.inspect("実際の額は賃金日額で決まります。", risk={}, ledger={})
    assert not any(h["code"] == "R2" for h in hits), hits


def test_台帳に正しい読みが無ければ自動置換しない():
    """向きが確かめられていない語を勝手に仮名にしないこと。

    2026-09-02 の実測: 「額」は open-jtalk が正しく Google が誤読、
    「年」は逆に open-jtalk が トシ と誤読していた。**距離では向きが決まらない。**
    """
    blob = {"words": {"甲": {"verdict": "misread", "dist": 9.9},
                      "乙": {"verdict": "misread", "dist": 9.9, "correct": "オツ"}}}
    yomi_gate.LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    keep = yomi_gate.LEDGER_PATH.read_text(encoding="utf-8") \
        if yomi_gate.LEDGER_PATH.exists() else None
    try:
        yomi_gate.LEDGER_PATH.write_text(json.dumps(blob, ensure_ascii=False),
                                         encoding="utf-8")
        assert yomi_gate.corrections() == {"乙": "オツ"}
        out = to_speech("甲と乙の話です。")
        assert "甲" in out, "向きが未確認の語を置換している"
        assert "オツ" in out and "乙" not in out, out
    finally:
        if keep is None:
            yomi_gate.LEDGER_PATH.unlink(missing_ok=True)
        else:
            yomi_gate.LEDGER_PATH.write_text(keep, encoding="utf-8")


def test_verify_が門を呼んでいる():
    """**撃たれない道具の効果はゼロ。** 呼び出しが消えたらここが落ちる。"""
    src = (yomi_gate.ROOT / "src" / "verify.py").read_text(encoding="utf-8")
    body = src.split("def _check_yomi(")[1].split("\ndef ")[0]
    assert "yomi_gate" in body and "yomi_gate.problems" in body
    assert "R0" in body and "R3" in body, "落とす条件が書かれていない"
    assert "_check_yomi(script)" in src, "script_only_problems から外れている"


def test_投稿を止めない側の設計が残っている():
    """R1/R2 は落とさず積む。**毎本に出る語で投稿を全部止めないため。**

    覆る条件: 耳が R1 をひととおり判定し終えたら、判定の無い R1 を落とす側へ寄せる。
    """
    src = (yomi_gate.ROOT / "src" / "verify.py").read_text(encoding="utf-8")
    body = src.split("def _check_yomi(")[1].split("\ndef ")[0]
    assert "queue" in body, "落とさない名指しを捨てている（積む先が無い）"
    assert hasattr(yomi_gate, "queue")


def test_耳が通した語は待ち行列から消える():
    """**減らない表は読まれなくなり、積んでいないのと同じになります。**"""
    keep_q = yomi_gate.QUEUE_PATH.read_text(encoding="utf-8") \
        if yomi_gate.QUEUE_PATH.exists() else None
    keep_l = yomi_gate.LEDGER_PATH.read_text(encoding="utf-8") \
        if yomi_gate.LEDGER_PATH.exists() else None
    try:
        yomi_gate.LEDGER_PATH.write_text(json.dumps({"words": {}}), encoding="utf-8")
        yomi_gate.queue([{"code": "R1", "surface": "丙", "why": "丙 が割れる", "seg": 1}])
        rows = yomi_gate._load(yomi_gate.QUEUE_PATH)["open"]
        assert any(v["surface"] == "丙" for v in rows.values()), rows
        # 耳が safe と言ったら、次に積んだときに消える
        yomi_gate.LEDGER_PATH.write_text(
            json.dumps({"words": {"丙": {"verdict": "safe"}}}, ensure_ascii=False),
            encoding="utf-8")
        yomi_gate.queue([])
        rows = yomi_gate._load(yomi_gate.QUEUE_PATH)["open"]
        assert not any(v["surface"] == "丙" for v in rows.values()), rows
    finally:
        for path, keep in ((yomi_gate.QUEUE_PATH, keep_q), (yomi_gate.LEDGER_PATH, keep_l)):
            if keep is None:
                path.unlink(missing_ok=True)
            else:
                path.write_text(keep, encoding="utf-8")
